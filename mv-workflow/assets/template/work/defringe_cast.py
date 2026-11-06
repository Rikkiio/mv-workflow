"""Remove the light halo left round the cast cut-outs (white matte fringe that shows against dark scenes, e.g. on
Miku's hair): edge pixels lighter than the colour just inside the figure take that inside colour (inpainted from the
interior), and the outermost 1 px of alpha is trimmed. Originals are copied to assets/cast/_vec_orig/ first.

python defringe_cast.py [NAME ...]     (default: every *_vec.png in assets/cast)"""
import glob
import os
import shutil
import sys

import cv2
import numpy as np

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
CAST = f"{ROOT}/assets/cast"
BACK = f"{CAST}/_vec_orig"


def defringe(bgra, band=5):
    a = bgra[..., 3]
    k = np.ones((3, 3), np.uint8)
    solid = (a > 250).astype(np.uint8)
    interior = cv2.erode(solid, k, iterations=band)
    edge = (a > 0) & (interior == 0)
    rgb = np.ascontiguousarray(bgra[..., :3])
    # colours of the edge zone continued from the interior (small inpaint radius, interior pixels unchanged)
    filled = cv2.inpaint(rgb, (edge * 255).astype(np.uint8), 4, cv2.INPAINT_TELEA)
    lum_e = rgb.astype(np.int32).sum(-1)
    lum_f = filled.astype(np.int32).sum(-1)
    halo = edge & (lum_e > lum_f + 60)          # only where the edge is clearly lighter than the figure inside
    out = bgra.copy()
    out[..., :3][halo] = filled[halo]
    out[..., 3] = cv2.erode(a, k, iterations=1)
    return out, int(halo.sum())


def run(name):
    src = f"{CAST}/{name}.png"
    os.makedirs(BACK, exist_ok=True)
    keep = f"{BACK}/{name}.png"
    if not os.path.exists(keep):
        shutil.copy2(src, keep)
    im = cv2.imread(keep, cv2.IMREAD_UNCHANGED)
    if im is None or im.ndim != 3 or im.shape[2] != 4:
        print("skip", name)
        return
    out, n = defringe(im)
    cv2.imwrite(src, out)
    print(f"defringe {name}: {n} halo px")


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(f"{CAST}/*_vec.png"))
    for n in names:
        run(n)
