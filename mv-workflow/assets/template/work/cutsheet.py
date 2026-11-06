"""Every frame from -0.2 s to +0.23 s around each cut of the section, one row per cut (13 frames), in sheets.
python work/cutsheet.py VIDEO OUTPREFIX OFFSET CUT1,CUT2,..."""
import sys

import cv2
import numpy as np

video, out, off = sys.argv[1], sys.argv[2], float(sys.argv[3])
cuts = [float(x) for x in sys.argv[4].split(",")]
cap = cv2.VideoCapture(video)
rows = []
for c in cuts:
    f0 = int(round((c - off) * 30)) - 6
    tiles = []
    for f in range(f0, f0 + 13):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        th = cv2.resize(fr, (240, 135)) if ok else np.zeros((135, 240, 3), np.uint8)
        cv2.putText(th, f"{off + f / 30:.3f}", (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        tiles.append(th)
    rows.append(np.hstack(tiles))
for k in range(0, len(rows), 6):
    cv2.imwrite(f"{out}_{k // 6}.jpg", np.vstack(rows[k:k + 6]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{out}_{k // 6}.jpg")
