"""Parallel renderer: GPU workers -> ffmpeg chunks -> concat + audio.

usage: python src/render.py OUT.mp4 [--start S] [--end E] [--workers N] [--crf C] [--preset P] [--half]
       python src/render.py OUTDIR --stills t1,t2,...        (jpg stills: the quickest way to check a composition)
MM_BUILD picks the build function in storyboard.py (default: build). audio/song.mp3 is muxed in when it exists.
"""
import argparse, math, os, subprocess, sys, time
import multiprocessing as mp

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
sys.path.insert(0, os.path.join(ROOT, "src"))
FPS = 30


def worker(args):
    f0, f1, path, crf, half, preset = args
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from mm.engine import Engine
    from mm.fx import make_paper
    import storyboard
    e = Engine(paper=make_paper())
    tl = getattr(storyboard, os.environ.get("MM_BUILD", "build"))()
    vf = ["-vf", "scale=960:540:flags=area"] if half else []
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
           "-r", str(FPS), "-i", "-", *vf, "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-tune", "film", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(f0, f1):
        tl.render(e, f / FPS)
        img = e.read()
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    return path, f1 - f0, time.time() - t0


def stills(times, outdir):
    import cv2
    from mm.engine import Engine
    from mm.fx import make_paper
    import storyboard
    e = Engine(paper=make_paper())
    tl = getattr(storyboard, os.environ.get("MM_BUILD", "build"))()
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for t in times:
        tl.render(e, t)
        img = e.read()
        pth = os.path.join(outdir, f"still_{t:07.2f}.jpg")
        cv2.imwrite(pth, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
        paths.append(pth)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--stills", default=None, help="comma separated times -> jpg stills")
    a = ap.parse_args()
    if a.stills:
        ts = [float(x) for x in a.stills.split(",")]
        for p in stills(ts, a.out):
            print(p)
        return
    from mm.anim import DURATION
    end = a.end if a.end is not None else DURATION
    f0, f1 = int(round(a.start * FPS)), int(math.ceil(end * FPS))
    n = max(1, min(a.workers, (f1 - f0) // 15))
    step = math.ceil((f1 - f0) / n)
    cdir = os.path.join(ROOT, "work", "chunks")
    os.makedirs(cdir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.out))[0]
    jobs = [(s, min(s + step, f1), os.path.join(cdir, f"{tag}_{k:03d}.mp4"), a.crf, a.half, a.preset)
            for k, s in enumerate(range(f0, f1, step))]
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(len(jobs)) as pool:
        for path, nf, dt in pool.imap_unordered(worker, jobs):
            print(f"chunk {os.path.basename(path)}: {nf} frames in {dt:.0f}s", flush=True)
    lst = os.path.join(cdir, f"{tag}_list.txt")
    with open(lst, "w") as f:
        for j in jobs:
            f.write(f"file '{j[2]}'\n")
    song = os.path.join(ROOT, "audio", "song.mp3")
    if os.path.exists(song):
        # the audio is seeked as an input option (-ss before its -i), so a piece starts on the right sample
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
               "-ss", f"{f0 / FPS:.3f}", "-i", song,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
               "-t", f"{(f1 - f0) / FPS:.3f}", a.out]
    else:
        print("no audio/song.mp3: writing the video without sound", flush=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy", a.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {a.out} ({f1 - f0} frames) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
