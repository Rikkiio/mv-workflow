"""Cut gpt layer pieces drawn on flat magenta (#ff00ff) into RGBA kit textures: chroma key on 'magenta-ness'
(min(R, B) - G), only the background region connected to the border is removed (magenta inside a shape stays), edge
spill pulled back toward neutral, cropped to the content with a small margin.

python cut_magenta.py [--black] IN.png OUT.png [IN.png OUT.png ...]"""
import sys

import cv2
import numpy as np


def cut(src, dst, margin=12, black=False):
    im = cv2.imread(src, cv2.IMREAD_COLOR).astype(np.float32)
    b, g, r = im[..., 0], im[..., 1], im[..., 2]
    if black:       # the model sometimes paints the ground pure black instead of magenta
        mag = np.zeros_like(g)
        key = np.clip((26.0 - np.max(im, axis=2)) / 14.0, 0.0, 1.0)
    else:
        mag = np.minimum(r, b) - g                     # ~255 on the key colour, <= 0 on neutral or green-ish art
        key = np.clip((mag - 70.0) / 90.0, 0.0, 1.0)
    # background = key regions touching the border, or big enclosed ones (a frame's opening)
    seed = (key > 0.5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(seed, connectivity=8)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    big = {i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 0.02 * seed.size}
    # magenta never occurs in the art, so every keyed pocket goes (gaps between leaves); black can, so only big ones
    bg = np.isin(lab, list(border | big)) if black else seed.astype(bool)
    bg = cv2.dilate(bg.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    alpha = np.where(bg, 1.0 - key, 1.0)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.7)
    # despill: pull the magenta cast out of soft edge pixels
    spill = np.clip(mag, 0, None) * (1.0 - alpha) * 1.2
    r2, b2 = np.clip(r - spill, 0, 255), np.clip(b - spill, 0, 255)
    out = np.dstack([b2, g, r2, alpha * 255.0]).astype(np.uint8)
    ys, xs = np.where(alpha > 0.05)
    y0, y1 = max(ys.min() - margin, 0), min(ys.max() + margin + 1, out.shape[0])
    x0, x1 = max(xs.min() - margin, 0), min(xs.max() + margin + 1, out.shape[1])
    cv2.imwrite(dst, out[y0:y1, x0:x1])
    print("cut", src, "->", dst, out[y0:y1, x0:x1].shape)


if __name__ == "__main__":
    a = sys.argv[1:]
    black = "--black" in a
    a = [x for x in a if x != "--black"]
    for i in range(0, len(a), 2):
        cut(a[i], a[i + 1], black=black)
