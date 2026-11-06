"""Run many gpt-image generations through Codex in parallel. usage: gpt_batch.py jobs.json [workers]"""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from gpt_image import generate

# STYLE and PAL are the house style and palettes of the 神のまにまに MV: appended to every prompt unless a job sets
# "pal": "raw". Replace them with your own project's look.
STYLE = ("Flat Japanese screen-print poster illustration: clean bold flat shapes, minimal texture, crisp thin "
         "outlines, large areas of solid color, subtle halftone dot shading only in shadows, Taisho-era graphic "
         "design meets ukiyo-e woodblock print. No text, no letters, no writing, no signature, no watermark.")
PAL = {
    "night": "Strictly limited palette: deep indigo, navy, sumi black, antique gold, washi cream.",
    "fest": "Strictly limited palette: indigo night, vermilion red, crimson, warm gold, lantern orange, washi cream.",
    "gloom": "Strictly limited palette: near-black violet, dark plum, dusty mauve, tarnished gold, pale cream.",
    "dawn": "Strictly limited palette: rose pink, peach, warm gold, cream, soft sky blue, plum shadows.",
    "day": "Strictly limited palette: sky blue, cream, vermilion, gold, autumn red, fresh green, navy outlines.",
    "none": "",
}
lock = threading.Lock()


def run(job):
    out = job["out"]
    if os.path.exists(out):
        return out, 0
    prompt = job["prompt"]
    if job.get("pal", "none") != "raw":
        prompt = f'{prompt} {PAL.get(job.get("pal", "none"), "")} {STYLE}'
    try:
        p, dt = generate(out, prompt, job.get("images", []))
        with lock:
            print(f"ok {out} {dt:.0f}s", flush=True)
        return p, dt
    except Exception as ex:
        with lock:
            print(f"FAIL {out} {ex}", flush=True)
        return None, 0


if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1], encoding="utf-8"))
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    os.makedirs(os.path.dirname(jobs[0]["out"]), exist_ok=True)
    with ThreadPoolExecutor(n) as ex:
        list(ex.map(run, jobs))
    print("ALL DONE", flush=True)
