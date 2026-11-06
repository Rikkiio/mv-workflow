"""Local one-frame blips: on a 32x18 grid of cells, a cell that differs from both neighbours in time while those
neighbours agree (something appears or vanishes for a single frame). python work/flicker_scan.py VIDEO [t0 t1]"""
import sys

import cv2
import numpy as np

cap = cv2.VideoCapture(sys.argv[1])
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
cap.set(cv2.CAP_PROP_POS_FRAMES, int(t0 * 30))
frames = []
f = int(t0 * 30)
while f < t1 * 30:
    ok, fr = cap.read()
    if not ok:
        break
    g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (32, 18), interpolation=cv2.INTER_AREA).astype(np.float32)
    frames.append(g)
    f += 1
F = np.array(frames)
blip = np.minimum(np.abs(F[1:-1] - F[:-2]), np.abs(F[1:-1] - F[2:])) - np.abs(F[2:] - F[:-2])
score = blip.reshape(len(blip), -1).max(axis=1)
order = np.argsort(-score)
seen = []
print("frames", len(F))
for k in order:
    t = t0 + (k + 1) / 30
    if any(abs(t - s) < 0.2 for s in seen):
        continue
    seen.append(t)
    cell = int(np.argmax(blip[k]))
    print(f"  {t:7.2f}  blip {score[k]:6.1f}  cell x{cell % 32} y{cell // 32}")
    if len(seen) >= 14:
        break
