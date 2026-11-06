"""Find jerky camera motion inside shots: Farneback flow between consecutive frames at low resolution, the median
flow vector and the median divergence (zoom) per frame, then spikes in their frame-to-frame change away from cuts.
python work/jerk_scan.py VIDEO OFFSET CUT1,CUT2,..."""
import sys

import cv2
import numpy as np

video, off = sys.argv[1], float(sys.argv[2])
cuts = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
cap = cv2.VideoCapture(video)
prev = None
vel, zoom = [], []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (320, 180))
    if prev is not None:
        fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        vel.append(np.median(fl.reshape(-1, 2), axis=0))
        h, w = g.shape
        yy, xx = np.mgrid[0:h, 0:w]
        rx, ry = xx - w / 2, yy - h / 2
        r2 = rx * rx + ry * ry + 1e-3
        zoom.append(float(np.median((fl[..., 0] * rx + fl[..., 1] * ry) / r2)))
    prev = g
vel, zoom = np.array(vel), np.array(zoom)
acc = np.linalg.norm(vel[1:] - vel[:-1], axis=1)
zacc = np.abs(zoom[1:] - zoom[:-1])
ts = off + (np.arange(len(acc)) + 1.5) / 30
near = lambda t: min([abs(t - c) for c in cuts] + [9])
cand = [(acc[i], zacc[i], ts[i]) for i in range(len(acc)) if near(ts[i]) > 0.25]
print("pan-acceleration spikes (px/frame^2 at 320 wide):")
for a, z, t in sorted(cand, reverse=True)[:14]:
    print(f"  {t:7.2f}  acc {a:5.2f}  zoom-acc {z:.4f}")
print("zoom-acceleration spikes:")
for a, z, t in sorted(cand, key=lambda c: -c[1])[:10]:
    print(f"  {t:7.2f}  zoom-acc {z:.4f}  acc {a:5.2f}")
