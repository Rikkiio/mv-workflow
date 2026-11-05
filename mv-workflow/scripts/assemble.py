"""Splice re-rendered pieces over a base cut, frame-exact, put the song under it, and encode the deliverables.

Only the shots that changed get rendered again (as pieces covering exact song-frame ranges); everything else comes
from earlier renders. The config is JSON:

    {
      "fps": 30,
      "dir": "F:/mv/manimani/out",                 # where the video files are
      "audio": "F:/mv/manimani/audio/song.mp3",
      "out": "F:/mv/manimani/out/manimani_v32",     # -> _v32.mp4, _v32_720p.mp4, _v32_phone.mp4
      "base": [[0, 315, "v19_a.mp4", 0], [315, 570, "v22_a0.mp4", 315], ...],
      "over": [[5529, 5688, "v32_p_dance.mp4", 5529], ...]
    }

Each entry is [first song frame, end song frame (exclusive), file, the song frame of the file's first frame]. Base
entries must cover the whole length; an over entry wins inside its range (missing files are skipped, so the list can
name pieces that are still rendering). The master is libx264 crf 16 + AAC 192k; 720p is lanczos crf 20 with
faststart; phone is 960x540, light hqdn3d, two-pass 820k (about 28 MB for 4:16, under the 30 MB phone limit).

usage: python assemble.py CONFIG.json [--plan] [--only master|720p|phone ...]
"""
import argparse
import json
import os
import subprocess


def plan(cfg):
    """The cut as (start, end, file, file offset) segments: over pieces where they exist, the base elsewhere."""
    over = [o for o in cfg.get("over", []) if os.path.exists(os.path.join(cfg["dir"], o[2]))]
    base = cfg["base"]
    cuts = sorted({b for seg in base + over for b in seg[:2]})
    segs = []
    for a, b in zip(cuts, cuts[1:]):
        src = next(((f, off) for s, e, f, off in over if s <= a and b <= e), None) or \
            next(((f, off) for s, e, f, off in base if s <= a and b <= e), None)
        if src is None:
            raise SystemExit(f"no base covers song frames {a}-{b}")
        if segs and segs[-1][2] == src[0] and segs[-1][3] == src[1] and segs[-1][1] == a:
            segs[-1] = (segs[-1][0], b, src[0], src[1])
        else:
            segs.append((a, b, src[0], src[1]))
    return segs


def master(cfg, segs, path):
    files = []
    for _, _, f, _ in segs:
        if f not in files:
            files.append(f)
    uses = {f: sum(1 for s in segs if s[2] == f) for f in files}
    graph, labels, used = [], [], {f: 0 for f in files}
    for i, f in enumerate(files):
        if uses[f] > 1:
            graph.append(f"[{i}:v]split={uses[f]}" + "".join(f"[{i}s{k}]" for k in range(uses[f])))
    for j, (a, b, f, off) in enumerate(segs):
        i = files.index(f)
        src = f"[{i}s{used[f]}]" if uses[f] > 1 else f"[{i}:v]"
        used[f] += 1
        graph.append(f"{src}trim=start_frame={a - off}:end_frame={b - off},setpts=PTS-STARTPTS[p{j}]")
        labels.append(f"[p{j}]")
    graph.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files:
        cmd += ["-i", os.path.join(cfg["dir"], f)]
    cmd += ["-i", cfg["audio"], "-filter_complex", ";".join(graph), "-map", "[v]", "-map", f"{len(files)}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(cfg.get("fps", 30)),
            "-c:a", "aac", "-b:a", "192k", "-shortest", path]
    subprocess.run(cmd, check=True)


def encode_720p(src, path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", "scale=1280:720:flags=lanczos",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", path], check=True)


def encode_phone(src, path):
    vf = "hqdn3d=0.7:0.7:3:3,scale=960:540:flags=lanczos"
    log = os.path.splitext(path)[0] + "_pass"
    null = "NUL" if os.name == "nt" else "/dev/null"
    for k in (1, 2):
        tail = ["-an", "-f", "null", null] if k == 1 else ["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
                                                          path]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", vf, "-c:v", "libx264",
                        "-preset", "veryslow", "-tune", "animation", "-b:v", "820k", "-pass", str(k),
                        "-passlogfile", log] + tail, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--plan", action="store_true", help="only print the segments")
    ap.add_argument("--only", nargs="+", choices=["master", "720p", "phone"], default=["master", "720p", "phone"])
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    fps = cfg.get("fps", 30)
    segs = plan(cfg)
    for s, e, f, off in segs:
        print(f"{s / fps:8.2f} - {e / fps:8.2f}  {f}")
    if a.plan:
        return
    out = cfg["out"]
    if "master" in a.only:
        master(cfg, segs, f"{out}.mp4")
    if "720p" in a.only:
        encode_720p(f"{out}.mp4", f"{out}_720p.mp4")
    if "phone" in a.only:
        encode_phone(f"{out}.mp4", f"{out}_phone.mp4")
    print("done")


if __name__ == "__main__":
    main()
