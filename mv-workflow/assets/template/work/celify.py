"""Flatten a painted-looking cast picture toward the flat cel look of the vector cast (the user: the new faces read as
AI): edge-preserving smoothing, colours quantised to a small palette (k-means in Lab), soft tone steps kept as two
cel levels, dark line art put back from the original's edges. python celify.py IN.png OUT.png [k]"""
import sys

import cv2
import numpy as np


def celify(src, dst, k=26):
    im = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    bgr, a = im[..., :3], im[..., 3]
    sm = bgr.copy()
    for _ in range(3):
        sm = cv2.bilateralFilter(sm, 9, 30, 6)
    lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] = 255.0 * (lab[..., 0] / 255.0) ** 0.86          # a little lighter, like the vector cast
    lab[..., 1:] = 128.0 + (lab[..., 1:] - 128.0) * 1.08
    flat = lab.reshape(-1, 3)
    m = a.reshape(-1) > 20
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lab_k, cent = cv2.kmeans(flat[m], k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    q = flat.copy()
    q[m] = cent[lab_k.ravel()]
    qb = cv2.cvtColor(np.clip(q, 0, 255).reshape(bgr.shape).astype(np.uint8), cv2.COLOR_LAB2BGR)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ed = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.4), 60, 150) > 0
    dark = ed & (g < 110)
    out = qb.copy()
    out[dark] = (qb[dark] * 0.45).astype(np.uint8)
    hi = (g > 235) & (a > 200)                                        # keep the highlights in the eyes and tears
    out[hi] = bgr[hi]
    cv2.imwrite(dst, np.dstack([out, a]))


if __name__ == "__main__":
    celify(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 26)
