"""Whole-video QA scan: near-black stretches, one-frame pops and frozen stretches.

A pop is a frame that differs from both of its neighbours while they agree with each other (something appears or
vanishes for a single frame); designed flashes show up here too, so read the list against the edit. Near-black runs
include designed fades and ink floods. Times are in seconds of the video.

usage: python qa_scan.py VIDEO [--dark 6] [--freeze 1.0] [--top 8]
"""
import argparse

import cv2
import numpy as np


def runs(mask):
    """(first, last) index pairs of the True runs in a boolean array."""
    idx = np.nonzero(mask)[0]
    if not len(idx):
        return []
    out, start = [], idx[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if b != a + 1:
            out.append((start, a))
            start = b
    out.append((start, idx[-1]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--dark", type=float, default=6.0, help="mean grey level below which a frame counts as near-black")
    ap.add_argument("--freeze", type=float, default=1.0, help="report still stretches at least this long (s)")
    ap.add_argument("--top", type=int, default=8, help="how many of the strongest pops to list")
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (160, 90)).astype(np.float32))
    F = np.array(frames)
    print(f"frames {len(F)}  fps {fps:g}  duration {len(F) / fps:.2f} s")
    if len(F) < 3:
        return
    m = F.mean(axis=(1, 2))
    print("near-black runs:", [(round(float(s) / fps, 2), round(float(e) / fps, 2)) for s, e in runs(m < a.dark)])
    d1 = np.abs(F[1:] - F[:-1]).mean(axis=(1, 2))
    d2 = np.abs(F[2:] - F[:-2]).mean(axis=(1, 2))
    pop = np.minimum(d1[:-1], d1[1:]) - d2
    top = np.argsort(-pop)[:a.top]
    print("top pops (t, strength):", [(round(float(k + 1) / fps, 2), round(float(pop[k]), 1)) for k in top])
    still = [(s, e) for s, e in runs(d1 < 0.25) if e - s + 1 >= a.freeze * fps]
    print(f"frozen >= {a.freeze:g} s:", [(round(float(s) / fps, 2), round(float(e + 1) / fps, 2)) for s, e in still])


if __name__ == "__main__":
    main()
