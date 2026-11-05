"""Before | after sheet for a delivery: the same moments from the old and the new cut side by side, a caption bar over
each row (Chinese is fine: the default font is Microsoft YaHei Bold), a few rows per sheet.

usage: python compare_sheet.py OLD.mp4 NEW.mp4 OUT.jpg --rows "187.2|3:07 caption" "187.9|another caption"
           [--labels "v31 | v32"] [--per 3] [--font C:/Windows/Fonts/msyhbd.ttc]
more than PER rows -> OUT_1.jpg, OUT_2.jpg, ...
"""
import argparse
import os
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def grab(video, t, w=960, h=540):
    """One frame at t seconds, decoded exactly (ffmpeg seeks to the keyframe and decodes up to t)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-f",
                          "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-"], capture_output=True).stdout
    if len(raw) < w * h * 3:
        return np.zeros((h, w, 3), np.uint8)
    return np.frombuffer(raw, np.uint8)[:w * h * 3].reshape(h, w, 3).copy()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("out")
    ap.add_argument("--rows", nargs="+", required=True, help='"seconds|caption" per row')
    ap.add_argument("--labels", default="旧 | 新")
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--font", default="C:/Windows/Fonts/msyhbd.ttc")
    a = ap.parse_args()

    font = ImageFont.truetype(a.font, 30)
    rows = []
    for spec in a.rows:
        t, _, cap = spec.partition("|")
        old, new = grab(a.old, float(t)), grab(a.new, float(t))
        row = np.concatenate([old, np.full((old.shape[0], 8, 3), 20, np.uint8), new], 1)
        bar = Image.new("RGB", (row.shape[1], 48), (24, 18, 28))
        d = ImageDraw.Draw(bar)
        d.text((14, 6), cap.strip(), font=font, fill=(255, 240, 214))
        lw = d.textlength(a.labels, font=font)
        d.text((row.shape[1] - lw - 14, 6), a.labels, font=font, fill=(200, 180, 150))
        rows.append(np.concatenate([cv2.cvtColor(np.array(bar), cv2.COLOR_RGB2BGR), row], 0))
    stem, ext = os.path.splitext(a.out)
    for k, s in enumerate(range(0, len(rows), a.per)):
        path = a.out if len(rows) <= a.per else f"{stem}_{k + 1}{ext}"
        cv2.imwrite(path, np.concatenate(rows[s:s + a.per], 0), [cv2.IMWRITE_JPEG_QUALITY, 86])
        print(path)


if __name__ == "__main__":
    main()
