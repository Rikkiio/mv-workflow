"""One frame per lyric line, just after its last syllable (all of the line should be on screen), labelled with the
line number and time, in sheets of 12. The video must start at song time 0. python work/lyric_qa.py VIDEO OUTPREFIX"""
import os
import sys

import cv2
import numpy as np

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
sys.path.insert(0, os.path.join(ROOT, "src"))
from mm.text import lyric_lines  # noqa: E402
from shots.b2common import syl  # noqa: E402

video, out = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(video)
tiles = []
for i in range(len(lyric_lines())):
    ch = syl(i)
    if not ch:
        continue
    t = ch[-1][1] + 0.18
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * 30)))
    ok, fr = cap.read()
    if not ok:
        continue
    th = cv2.resize(fr, (640, 360))
    cv2.rectangle(th, (0, 0), (150, 24), (0, 0, 0), -1)
    cv2.putText(th, f"L{i} {t:.2f}", (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    tiles.append(th)
if not tiles:
    sys.exit("no frames: are the lyrics timed (work/lyrics_timed_v2.json) and does the video reach them?")
for k in range(0, len(tiles), 12):
    chunk = tiles[k:k + 12]
    while len(chunk) % 3:
        chunk.append(np.zeros_like(tiles[0]))
    cv2.imwrite(f"{out}_{k // 12}.jpg", np.vstack([np.hstack(chunk[j:j + 3]) for j in range(0, len(chunk), 3)]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{out}_{k // 12}.jpg")
