"""Per-shot motion: median optical-flow magnitude (px/frame at 320 wide) and zoom rate, sampled every 3rd frame.
Flags shots that barely move. The shot list comes from storyboard.py (MM_BUILD picks the build function, default
build); the video must start at song time 0. python work/motion_audit.py VIDEO

Flow is only measurable where there is texture at 320 x 180: big flat areas (an empty gradient sky, flat-colour
fills) read as still and pull the median down, so a moving shot can be flagged. Look at a flagged shot before
changing it; if it is mostly flat, layers that move with the camera (clouds, mist, props at several depths) help."""
import os
import sys

import cv2
import numpy as np

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
sys.path.insert(0, os.path.join(ROOT, "src"))
import storyboard  # noqa: E402

tl = getattr(storyboard, os.environ.get("MM_BUILD", "build"))()
cap = cv2.VideoCapture(sys.argv[1])
for s in tl.shots:
    mags, zooms = [], []
    f0, f1 = int(round((s.t0 + 0.3) * 30)), int(round((s.t1 - 0.3) * 30))
    for f in range(f0, f1, 3):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, a = cap.read()
        ok2, b = cap.read()
        if not (ok and ok2):
            break
        ga = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (320, 180))
        gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (320, 180))
        fl = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mags.append(float(np.median(np.linalg.norm(fl, axis=2))))
        yy, xx = np.mgrid[0:180, 0:320]
        rx, ry = xx - 160, yy - 90
        zooms.append(float(np.median((fl[..., 0] * rx + fl[..., 1] * ry) / (rx * rx + ry * ry + 1e-3))))
    if not mags:
        continue
    m, z = float(np.mean(mags)), float(np.mean(np.abs(zooms)))
    flag = "  <-- still" if m < 0.12 and z < 0.0006 else ""
    print(f"{s.t0:7.2f} {type(s).__name__:14s} flow {m:5.2f}  zoom {z * 1000:5.2f}{flag}")
