"""Generate / edit an image with gpt-image through the Codex CLI.

usage: python gpt_image.py OUT.png "prompt" [input images...]
Codex saves generated images under ~/.codex/generated_images/<thread id>/. We read our own thread id
from the --json event stream (fallback: a unique tag searched in the session logs), so parallel
runs never pick up each other's images.
"""
import glob, os, re, shutil, subprocess, sys, time, uuid

HOME = os.path.expanduser("~/.codex")
GEN_DIR = os.path.join(HOME, "generated_images")
UUID_RE = re.compile(r'"(?:thread_id|session_id|conversation_id|id)"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"')


def _find_by_tag(tag, t0):
    for f in glob.glob(os.path.join(HOME, "sessions", "*", "*", "*", "rollout-*.jsonl")):
        if os.path.getmtime(f) < t0 - 5:
            continue
        try:
            txt = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if tag in txt:
            m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$", f)
            if m:
                return m.group(1)
    return None


def generate(out, prompt, images=(), timeout=900, retries=2):
    for attempt in range(retries + 1):
        t0 = time.time()
        tag = "mmjob-" + uuid.uuid4().hex[:12]
        instr = ("Use your image generation tool to create exactly one image. Do not write code, do not run "
                 "shell commands, do not create files yourself; just generate the image and then reply 'done'. "
                 f"(job id {tag}, ignore it)\n\n"
                 + ("Edit / redraw the attached image(s) as instructed.\n\n" if images else "")
                 + "IMAGE PROMPT:\n" + prompt)
        cmd = ["codex", "exec", "--json", "--skip-git-repo-check", "-s", "read-only",
               "-C", os.path.dirname(os.path.abspath(out))]
        for im in images:
            cmd += ["-i", im]
        cmd += ["-"]
        log = ""
        try:
            p = subprocess.run(cmd, input=instr, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout)
            log = (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired as ex:
            log = str(ex.stdout or "")
        tid = None
        m = UUID_RE.search(log)
        if m:
            tid = m.group(1)
        cands = glob.glob(os.path.join(GEN_DIR, tid, "*.png")) if tid else []
        if not cands:
            tid2 = _find_by_tag(tag, t0)
            if tid2:
                cands = glob.glob(os.path.join(GEN_DIR, tid2, "*.png"))
        if cands:
            cands.sort(key=os.path.getmtime)
            shutil.copy(cands[-1], out)
            return out, time.time() - t0
        sys.stderr.write(f"[gpt_image] attempt {attempt} produced no image ({tid}); log tail:\n{log[-1200:]}\n")
    raise RuntimeError("no image generated")


if __name__ == "__main__":
    out, prompt = sys.argv[1], sys.argv[2]
    ims = sys.argv[3:]
    path, dt = generate(out, prompt, ims)
    print(f"saved {path} in {dt:.0f}s")
