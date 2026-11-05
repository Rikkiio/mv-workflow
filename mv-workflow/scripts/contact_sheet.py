"""Contact sheets from a video: one frame every DT seconds from T0 to T1, each labelled with its time (m:ss and
seconds), COLS per row, PER frames per sheet. Frames are taken by frame number, so the labels are exact (ffmpeg's fps
filter rounds and its labels run early).

With --offset, labels are song time = video time + offset (for a piece that starts mid-song).

usage: python contact_sheet.py VIDEO OUTPREFIX T0 T1 DT [--offset 0] [--cols 5] [--per 40] [--width 480]
writes OUTPREFIX_0.jpg, OUTPREFIX_1.jpg, ...
"""
import argparse

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("dt", type=float)
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--per", type=int, default=40)
    ap.add_argument("--width", type=int, default=480)
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    vw, vh = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    w, h = a.width, int(round(a.width * vh / vw))
    tiles = []
    for t in np.arange(a.t0, a.t1 + 1e-6, a.dt):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round((t - a.offset) * fps)))
        ok, fr = cap.read()
        th = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA) if ok else np.zeros((h, w, 3), np.uint8)
        label = f"{int(t // 60)}:{t % 60:05.2f} ({t:.2f})"
        cv2.putText(th, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4)
        cv2.putText(th, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        tiles.append(th)
    for s in range(0, len(tiles), a.per):
        chunk = tiles[s:s + a.per]
        while len(chunk) % a.cols:
            chunk.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(chunk[i:i + a.cols]) for i in range(0, len(chunk), a.cols)]
        path = f"{a.out}_{s // a.per}.jpg"
        cv2.imwrite(path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(path)


if __name__ == "__main__":
    main()
