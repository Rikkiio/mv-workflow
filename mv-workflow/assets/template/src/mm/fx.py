"""Procedural textures (washi paper, sprite atlas) and deterministic particle fields."""
import math

import cv2
import numpy as np
import skia


def _fbm(h, w, seed, octaves=5, base=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.random((n + 1, int(n * w / h) + 2)).astype(np.float32)
        out += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-6)


def make_paper(w=1920, h=1080, seed=7):
    """RGB = multiply map (warm washi with fibres & blotches), A = ink-void speckle for dark areas."""
    rng = np.random.default_rng(seed)
    base = 1.0 - 0.07 * _fbm(h, w, seed, 5, 3) - 0.03 * _fbm(h, w, seed + 1, 3, 24)
    fib = np.zeros((h, w), np.float32)
    for _ in range(2600):
        x, y = rng.random() * w, rng.random() * h
        ang = rng.random() * math.pi
        L = rng.uniform(8, 60)
        pts = []
        for k in range(6):
            ang += rng.normal(0, 0.25)
            x2, y2 = x + math.cos(ang) * L / 5, y + math.sin(ang) * L / 5
            pts.append(((x, y), (x2, y2)))
            x, y = x2, y2
        v = rng.uniform(0.25, 1.0) * (1 if rng.random() < 0.7 else -0.6)
        for (a, b) in pts:
            cv2.line(fib, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), float(v), 1, cv2.LINE_AA)
    fib = cv2.GaussianBlur(fib, (0, 0), 0.6)
    grain = rng.normal(0, 1, (h, w)).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (0, 0), 0.7)
    m = base - 0.035 * np.clip(fib, 0, None) + 0.02 * np.clip(-fib, 0, None) - 0.012 * grain
    m = np.clip(m, 0.78, 1.02)
    rgb = np.stack([m * 1.0, m * 0.985, m * 0.95], -1)
    speck = np.clip(0.6 * np.clip(fib, 0, None) + 0.5 * (_fbm(h, w, seed + 5, 4, 40) > 0.78), 0, 1)
    out = np.dstack([np.clip(rgb, 0, 1), speck[..., None]])
    return (out * 255).astype(np.uint8)


# ----------------------------------------------------------------------------------- sprite atlas
CELL = 128
ATLAS_KINDS = ["momiji1", "momiji2", "momiji3", "ginkgo", "petal", "kiku", "confetti", "confetti2",
               "glow", "spark", "dot", "streak", "star4", "ring", "ember", "leaf"]


def _maple_path(cx, cy, r, lobes=7, sharp=0.42, seed=0):
    rng = np.random.default_rng(seed)
    p = skia.Path()
    n = lobes
    pts = []
    for i in range(n):
        a0 = -math.pi / 2 + (i - (n - 1) / 2) * (math.pi * 1.55 / (n - 1))
        lr = r * (1.0 - 0.32 * abs(i - (n - 1) / 2) / ((n - 1) / 2)) * rng.uniform(0.92, 1.05)
        tip = (cx + math.cos(a0) * lr, cy + math.sin(a0) * lr)
        al = a0 - math.pi / n * 0.95
        ar = a0 + math.pi / n * 0.95
        notch = r * sharp * (0.85 if i else 1.0)
        pts.append(("n", (cx + math.cos(al) * notch, cy + math.sin(al) * notch)))
        # serrated lobe edges
        for s in (0.55, 0.8):
            aa = a0 - (math.pi / n) * 0.55 * (1 - s)
            pts.append(("p", (cx + math.cos(aa - 0.12) * lr * s, cy + math.sin(aa - 0.12) * lr * s)))
        pts.append(("t", tip))
        for s in (0.8, 0.55):
            aa = a0 + (math.pi / n) * 0.55 * (1 - s)
            pts.append(("p", (cx + math.cos(aa + 0.12) * lr * s, cy + math.sin(aa + 0.12) * lr * s)))
    pts.append(("n", (cx + math.cos(ar) * notch, cy + math.sin(ar) * notch)))
    p.moveTo(cx, cy + r * 0.12)
    for _, (x, y) in pts:
        p.lineTo(x, y)
    p.close()
    return p


def make_atlas():
    n = len(ATLAS_KINDS)
    cols = 8
    rows = math.ceil(n / cols)
    info = skia.ImageInfo.Make(cols * CELL, rows * CELL, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    s = skia.Surface.MakeRaster(info)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    uv = {}
    W_, H_ = cols * CELL, rows * CELL
    white = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 1))
    vein = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.72, 0.72, 0.72, 1), Style=skia.Paint.kStroke_Style,
                      StrokeWidth=2.2, StrokeCap=skia.Paint.kRound_Cap)
    shade = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.84, 0.84, 0.84, 1))
    for i, k in enumerate(ATLAS_KINDS):
        x0, y0 = (i % cols) * CELL, (i // cols) * CELL
        cx, cy = x0 + CELL / 2, y0 + CELL / 2
        uv[k] = ((x0 + 1) / W_, (y0 + 1) / H_, (x0 + CELL - 1) / W_, (y0 + CELL - 1) / H_)
        c.save()
        c.clipRect(skia.Rect(x0, y0, x0 + CELL, y0 + CELL))
        if k.startswith("momiji"):
            seed = int(k[-1])
            path = _maple_path(cx, cy + 6, 50, lobes=7 if seed != 2 else 5, sharp=0.38 + 0.05 * seed, seed=seed)
            c.drawPath(path, white)
            # half-leaf shading for a printed look
            c.save(); c.clipRect(skia.Rect(cx, y0, x0 + CELL, y0 + CELL)); c.drawPath(path, shade); c.restore()
            for j in range(5):
                a = -math.pi / 2 + (j - 2) * 0.62
                c.drawLine(cx, cy + 12, cx + math.cos(a) * 38, cy + 6 + math.sin(a) * 38, vein)
            c.drawLine(cx, cy + 12, cx, cy + 52, vein)
        elif k == "ginkgo":
            p = skia.Path()
            p.moveTo(cx, cy + 18)
            p.cubicTo(cx - 20, cy + 6, cx - 52, cy - 18, cx - 46, cy - 40)
            p.cubicTo(cx - 24, cy - 50, cx - 6, cy - 44, cx - 2, cy - 30)
            p.lineTo(cx + 2, cy - 30)
            p.cubicTo(cx + 6, cy - 44, cx + 24, cy - 50, cx + 46, cy - 40)
            p.cubicTo(cx + 52, cy - 18, cx + 20, cy + 6, cx, cy + 18)
            p.close()
            c.drawPath(p, white)
            for j in range(-3, 4):
                c.drawLine(cx, cy + 16, cx + j * 11, cy - 36, vein)
            c.drawLine(cx, cy + 16, cx + 2, cy + 54, vein)
        elif k == "petal":
            p = skia.Path()
            p.moveTo(cx, cy + 44)
            p.cubicTo(cx - 40, cy + 10, cx - 30, cy - 36, cx - 6, cy - 44)
            p.lineTo(cx, cy - 34)
            p.lineTo(cx + 6, cy - 44)
            p.cubicTo(cx + 30, cy - 36, cx + 40, cy + 10, cx, cy + 44)
            c.drawPath(p, white)
        elif k == "kiku":
            p = skia.Path()
            p.addRRect(skia.RRect.MakeRectXY(skia.Rect(cx - 9, cy - 50, cx + 9, cy + 50), 9, 9))
            c.drawPath(p, white)
            c.drawLine(cx, cy - 40, cx, cy + 40, vein)
        elif k == "confetti":
            c.drawRect(skia.Rect(cx - 30, cy - 18, cx + 30, cy + 18), white)
        elif k == "confetti2":
            c.drawRect(skia.Rect(cx - 40, cy - 10, cx + 40, cy + 10), white)
        elif k in ("glow", "dot", "ember"):
            rad = {"glow": 62, "dot": 30, "ember": 40}[k]
            stops = {"glow": ([1, 0.55, 0.18, 0], [0, 0.25, 0.55, 1]),
                     "dot": ([1, 1, 0], [0, 0.6, 1]),
                     "ember": ([1, 0.8, 0.2, 0], [0, 0.2, 0.5, 1])}[k]
            cols_ = [skia.Color4f(1, 1, 1, a) for a in stops[0]]
            sh = skia.GradientShader.MakeRadial(skia.Point(cx, cy), rad, cols_, stops[1])
            c.drawCircle(cx, cy, rad, skia.Paint(AntiAlias=True, Shader=sh))
        elif k == "spark":
            sh = skia.GradientShader.MakeRadial(skia.Point(cx, cy), 60, [skia.Color4f(1, 1, 1, 1), skia.Color4f(1, 1, 1, 0)], [0, 1])
            p = skia.Paint(AntiAlias=True, Shader=sh)
            path = skia.Path()
            for j in range(4):
                a = j * math.pi / 2
                path.moveTo(cx, cy)
                path.lineTo(cx + math.cos(a - 0.12) * 14, cy + math.sin(a - 0.12) * 14)
                path.lineTo(cx + math.cos(a) * 60, cy + math.sin(a) * 60)
                path.lineTo(cx + math.cos(a + 0.12) * 14, cy + math.sin(a + 0.12) * 14)
                path.close()
            c.drawPath(path, p)
            c.drawCircle(cx, cy, 10, white)
        elif k == "streak":
            sh = skia.GradientShader.MakeLinear([skia.Point(x0, cy), skia.Point(x0 + CELL, cy)],
                                                [skia.Color4f(1, 1, 1, 0), skia.Color4f(1, 1, 1, 1), skia.Color4f(1, 1, 1, 0)], [0, 0.7, 1])
            c.drawRect(skia.Rect(x0, cy - 3, x0 + CELL, cy + 3), skia.Paint(AntiAlias=True, Shader=sh))
        elif k == "star4":
            path = skia.Path()
            for j in range(8):
                a = j * math.pi / 4 - math.pi / 2
                r = 58 if j % 2 == 0 else 14
                (path.moveTo if j == 0 else path.lineTo)(cx + math.cos(a) * r, cy + math.sin(a) * r)
            path.close()
            c.drawPath(path, white)
        elif k == "ring":
            c.drawCircle(cx, cy, 44, skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 1),
                                                Style=skia.Paint.kStroke_Style, StrokeWidth=8))
        elif k == "leaf":
            p = skia.Path()
            p.moveTo(cx, cy - 52)
            p.cubicTo(cx + 34, cy - 20, cx + 30, cy + 30, cx, cy + 52)
            p.cubicTo(cx - 30, cy + 30, cx - 34, cy - 20, cx, cy - 52)
            c.drawPath(p, white)
            c.drawLine(cx, cy - 44, cx, cy + 50, vein)
        c.restore()
    arr = s.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    return arr, uv


class Field:
    """Deterministic drifting particles wrapped inside a world-space box.

    kinds: list of atlas keys (chosen per particle); colors: list of rgba tuples.
    vel: (vx, vy) mean velocity in world units/s; spread: velocity jitter fraction.
    """

    def __init__(self, n, seed, kinds, colors, box=(-1400, 1400, -900, 900, -200, 1200), vel=(40, 90),
                 spread=0.4, size=(18, 42), spin=(-2.0, 2.0), sway=(30, 0.4), flutter=1.0, alpha=(0.7, 1.0),
                 twinkle=0.0, add=(0, 0, 0), size_depth=True):
        rng = np.random.default_rng(seed)
        self.n = n
        x0, x1, y0, y1, z0, z1 = box
        self.box = box
        self.p0 = np.stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n), rng.uniform(z0, z1, n)], 1)
        self.v = np.stack([vel[0] * (1 + spread * rng.normal(0, 1, n)), vel[1] * (1 + spread * rng.normal(0, 1, n))], 1)
        self.size = rng.uniform(size[0], size[1], n)
        self.spin = rng.uniform(spin[0], spin[1], n)
        self.rot0 = rng.uniform(0, 2 * math.pi, n)
        self.sw_amp = sway[0] * rng.uniform(0.5, 1.5, n)
        self.sw_f = sway[1] * rng.uniform(0.6, 1.6, n)
        self.ph = rng.uniform(0, 2 * math.pi, (n, 3))
        self.fl = flutter * rng.uniform(0.6, 1.4, n)
        self.alpha = rng.uniform(alpha[0], alpha[1], n)
        self.kind = rng.integers(0, len(kinds), n)
        self.kinds = kinds
        self.col = np.array([colors[i] for i in rng.integers(0, len(colors), n)], np.float32)
        self.twinkle = twinkle
        self.add = add

    def instances(self, t, uvmap, alpha=1.0, t0=0.0):
        x0, x1, y0, y1, z0, z1 = self.box
        tt = t - t0
        x = self.p0[:, 0] + self.v[:, 0] * tt + self.sw_amp * np.sin(self.sw_f * tt * 6.283 + self.ph[:, 0])
        y = self.p0[:, 1] + self.v[:, 1] * tt
        x = x0 + np.mod(x - x0, x1 - x0)
        y = y0 + np.mod(y - y0, y1 - y0)
        z = self.p0[:, 2]
        rz = self.rot0 + self.spin * tt
        rx = self.fl * 1.2 * np.sin(tt * 2.1 * self.fl + self.ph[:, 1])
        ry = self.fl * 1.0 * np.sin(tt * 1.7 * self.fl + self.ph[:, 2])
        a = self.alpha * alpha
        if self.twinkle:
            a = a * (1 - self.twinkle + self.twinkle * (0.5 + 0.5 * np.sin(tt * 5.0 + self.ph[:, 0] * 3)))
        out = np.zeros((self.n, 19), np.float32)
        out[:, 0], out[:, 1], out[:, 2] = x, y, z
        out[:, 3] = self.size
        out[:, 4] = self.size
        out[:, 5], out[:, 6], out[:, 7] = rx, ry, rz
        uvs = np.array([uvmap[self.kinds[k]] for k in self.kind], np.float32)
        out[:, 8:12] = uvs
        out[:, 12:15] = self.col[:, :3]
        out[:, 15] = a * self.col[:, 3]
        out[:, 16:19] = self.add
        return out
