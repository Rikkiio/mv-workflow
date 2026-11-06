"""Gentle de-AI pass for a character picture: the drawing is kept as it is, only the cues that read as AI are toned
down - the warm rim glow round the hair folded back into the hair colour, the glossy strand highlights and the deep
hair gradients compressed, the airbrushed skin flattened, the colours a little calmer, the line art crisper, a light
paper grain over it. (Posterising into big flat colour blocks went too far: it read as crude.)

Tuned on a teal-haired character: --hue is the hair's hue range (OpenCV hue, 0-180), --fy the face centre as a
fraction of the picture height (the face is kept out of the hair mask).

python work/deai.py NAME [NAME ...] [--hue 70 110] [--fy 0.42]
reads assets/cast/NAME.png (RGBA) -> assets/deai/deai_NAME.png, plus work/deai_check.jpg (before | after)"""
import argparse
import os

import cv2
import numpy as np

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
CAST = f"{ROOT}/assets/cast"
OUT = f"{ROOT}/assets/deai"


def deai(name, fy=0.42, hue=(70, 110)):
    im = cv2.imread(f"{CAST}/{name}.png", cv2.IMREAD_UNCHANGED)
    bgr, alpha = im[..., :3].copy(), im[..., 3]
    solid = alpha > 128
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    Hh, Ss, Vv = (hsv[..., i].astype(np.float32) for i in range(3))
    h_, w_ = solid.shape
    yy, xx = np.mgrid[0:h_, 0:w_].astype(np.float32)
    face = ((xx - w_ * 0.5) / (h_ * 0.2)) ** 2 + ((yy - h_ * fy) / (h_ * 0.17)) ** 2 < 1.0
    teal = (Hh >= hue[0]) & (Hh <= hue[1]) & (Ss > 55) & solid
    if teal.sum() < 500:
        raise SystemExit(f"{name}: almost no pixels in hue {hue[0]:g}-{hue[1]:g}; set --hue to the hair colour")
    teal_c = cv2.morphologyEx(teal.astype(np.uint8), cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
    near = cv2.dilate(teal_c.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))) > 0
    # the warm rim light and the pale crown light on the hair: yellowish (not the skin's orange), near the hair, never
    # in the face, never the gold ornaments (saturated)
    warm_px = (Hh >= 21) & (Hh <= 46) & (Ss < 125) & (Vv > 120) & near & ~face & solid
    hair = teal_c | warm_px
    a0, b0 = np.median(A[teal]), np.median(B[teal])
    Lm = np.median(L[teal])
    # the hair: its warm rim light and pale crown light turned back to the hair colour; its gloss and depth compressed
    warm = hair & ~teal
    w = cv2.GaussianBlur(warm.astype(np.float32), (0, 0), 1.5)
    A = A * (1 - w) + a0 * w
    B = B * (1 - w) + b0 * w
    wm = warm.astype(np.float32)                             # (smooth inside: the crown light read mottled)
    Lw = cv2.GaussianBlur(L * wm, (0, 0), 4.0) / (cv2.GaussianBlur(wm, (0, 0), 4.0) + 1e-4)
    Lt = np.minimum(Lm + 0.3 * (Lw - Lm), Lm + 10)
    L = L * (1 - w) + Lt * w
    hi = np.quantile(L[hair], 0.9)
    L = np.where(hair & (L > hi), hi + (L - hi) * 0.5, L)     # (the glossy strand highlights tamed)
    L = np.where(hair, Lm + (L - Lm) * 0.88, L)               # (and the deep gradients)
    lab2 = np.dstack([L, A, B])
    out = cv2.cvtColor(np.clip(lab2, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    # the skin: the airbrush flattened (an edge-preserving smoothing on the skin only)
    skin = (hsv[..., 0] < 26) & (hsv[..., 1] > 25) & (hsv[..., 1] < 160) & (hsv[..., 2] > 120) & solid & ~hair
    sk = out.copy()
    for _ in range(3):
        sk = cv2.bilateralFilter(sk, 9, 22, 5)
    ws = cv2.GaussianBlur(skin.astype(np.float32), (0, 0), 1.2)[..., None]
    out = (out * (1 - ws) + sk * ws).astype(np.float32)
    # calmer colours: a little less saturation and contrast overall
    hsv2 = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv2[..., 1] *= 0.9
    out = cv2.cvtColor(np.clip(hsv2, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    out = 128 + (out - 128) * 0.95
    # crisper line art: the drawing's dark strokes a shade darker
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    local = cv2.GaussianBlur(g, (0, 0), 3.0)
    ln = np.clip((local - g - 14) / 20.0, 0, 1) * (g < 130) * solid
    out = out * (1 - 0.35 * ln[..., None])
    # a light paper grain (the digital smoothness is part of the look)
    rng = np.random.default_rng(sum(map(ord, name)))
    grain = cv2.GaussianBlur(rng.normal(0, 1, out.shape[:2]).astype(np.float32), (0, 0), 0.6)
    out = out + grain[..., None] * 3.2
    res = np.dstack([np.clip(out, 0, 255), alpha]).astype(np.uint8)
    cv2.imwrite(f"{OUT}/deai_{name}.png", res)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+")
    ap.add_argument("--hue", type=float, nargs=2, default=(70, 110))
    ap.add_argument("--fy", type=float, default=0.42)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(f"{ROOT}/work", exist_ok=True)
    rows = []
    for n in a.names:
        res = deai(n, a.fy, a.hue)
        org = cv2.imread(f"{CAST}/{n}.png", cv2.IMREAD_UNCHANGED)
        tiles = []
        for x in (org, res):
            al = x[..., 3:4].astype(np.float32) / 255
            tiles.append((x[..., :3] * al + 40 * (1 - al)).astype(np.uint8))
        rows.append(cv2.resize(np.concatenate(tiles, 1), (1000, int(1000 * res.shape[0] / (2 * res.shape[1])))))
        print("ok", n, "->", f"{OUT}/deai_{n}.png")
    cv2.imwrite(f"{ROOT}/work/deai_check.jpg", np.concatenate(rows, 0), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"{ROOT}/work/deai_check.jpg")


if __name__ == "__main__":
    main()
