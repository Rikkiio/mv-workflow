"""Vector design elements rasterised with skia: lanterns, paper slips, seals, banners, patterns, ornaments."""
import math

import numpy as np
import skia

from .text import typeface

C = lambda h, a=1.0: skia.Color4f(int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255, a)


def _surface(w, h):
    info = skia.ImageInfo.Make(int(w), int(h), skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    s = skia.Surface.MakeRaster(info)
    s.getCanvas().clear(skia.Color4f(0, 0, 0, 0))
    return s


def _arr(s):
    return s.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)


def _paint(col, a=1.0, stroke=0.0, cap=None):
    p = skia.Paint(AntiAlias=True, Color4f=C(col, a) if isinstance(col, str) else col)
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(cap or skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def _glyph_path(ch, font, size, cx, cy):
    f = skia.Font(typeface(font), size)
    g = f.textToGlyphs(ch)
    path = skia.Path()
    x = 0
    ws = f.getWidths(g)
    tot = sum(ws)
    for gi, w in zip(g, ws):
        gp = f.getPath(gi)
        if gp is not None:
            gp.offset(cx - tot / 2 + x, cy + size * 0.38)
            path.addPath(gp)
        x += w
    return path


def _grunge(s, w, h, seed, amount=0.25, col="#000000", n=900, rmax=3.0):
    """Speckle erosion for printed / stamped look (erases alpha)."""
    rng = np.random.default_rng(seed)
    c = s.getCanvas()
    p = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kDstOut, Color4f=skia.Color4f(0, 0, 0, amount))
    for _ in range(n):
        c.drawCircle(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.4, rmax), p)


def chochin(text="", w=180, h=260, body="#e8442e", text_col="#1a1010", rib="#7a1d14", cap="#141018",
            lit=True, font="boku", pattern=None, text_scale=1.0):
    """Japanese paper lantern (front view). Returns RGBA."""
    pad = 20
    s = _surface(w + 2 * pad, h + 2 * pad)
    c = s.getCanvas()
    cx, cy = (w + 2 * pad) / 2, (h + 2 * pad) / 2
    bw, bh = w * 0.5, h * 0.40
    capw, caph = w * 0.30, h * 0.07
    oval = skia.Rect(cx - bw, cy - bh, cx + bw, cy + bh)
    body_p = skia.Paint(AntiAlias=True)
    if lit:
        sh = skia.GradientShader.MakeRadial(skia.Point(cx, cy), bw * 1.15,
                                            [C("#fff2c8"), C(body), C(rib)], [0.0, 0.62, 1.0])
        body_p.setShader(sh)
    else:
        body_p.setColor4f(C(body))
    c.drawOval(oval, body_p)
    c.save()
    clip = skia.Path()
    clip.addOval(oval)
    c.clipPath(clip, doAntiAlias=True)
    # horizontal ribs (bamboo hoops)
    rp = _paint(rib, 0.55, 1.6)
    for k in range(1, 12):
        y = cy - bh + 2 * bh * k / 12
        half = bw * math.sqrt(max(0, 1 - ((y - cy) / bh) ** 2))
        c.drawLine(cx - half, y, cx + half, y, rp)
    if text:
        size = (h * 0.34 if len(text) == 1 else h * 0.22) * text_scale
        n = len(text)
        for i, ch in enumerate(text):
            yy = cy + (i - (n - 1) / 2) * size * 1.0
            c.drawPath(_glyph_path(ch, font, size, cx, yy), _paint(text_col))
    if pattern == "tomoe":
        c.drawCircle(cx, cy, bw * 0.45, _paint(text_col, 1.0, 5))
    c.restore()
    # caps
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(cx - capw, cy - bh - caph * 0.7, cx + capw, cy - bh + caph * 0.5), 4, 4), _paint(cap))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(cx - capw, cy + bh - caph * 0.5, cx + capw, cy + bh + caph * 0.7), 4, 4), _paint(cap))
    c.drawLine(cx, cy - bh - caph * 0.7, cx, cy - bh - caph * 1.6, _paint(cap, 1, 3))
    # tassel
    c.drawLine(cx, cy + bh + caph * 0.7, cx, cy + bh + caph * 1.6, _paint(cap, 1, 2))
    return _arr(s)


def ofuda(text, w=110, h=360, paper="#efe4cc", ink="#1a1218", frame="#b8322a", font="mincho", seal=True, seed=0):
    """Vertical paper talisman with red frame and vertical text."""
    s = _surface(w, h)
    c = s.getCanvas()
    rng = np.random.default_rng(seed)
    c.drawRect(skia.Rect(2, 2, w - 2, h - 2), _paint(paper))
    c.drawRect(skia.Rect(8, 8, w - 8, h - 8), _paint(frame, 1, 3, skia.Paint.kSquare_Cap))
    c.drawRect(skia.Rect(13, 13, w - 13, h - 13), _paint(frame, 1, 1.2, skia.Paint.kSquare_Cap))
    n = max(len(text), 1)
    size = min(w * 0.62, (h - 70) / n * 0.95)
    for i, ch in enumerate(text):
        yy = 30 + size * 0.5 + i * (h - 60 - (size if seal else 0)) / n
        c.drawPath(_glyph_path(ch, font, size, w / 2, yy), _paint(ink))
    if seal:
        ss = w * 0.34
        y0 = h - 22 - ss
        c.drawRect(skia.Rect(w / 2 - ss / 2, y0, w / 2 + ss / 2, y0 + ss), _paint(frame))
        c.drawPath(_glyph_path("神", "old", ss * 0.72, w / 2, y0 + ss / 2), _paint(paper))
    _grunge(s, w, h, seed, 0.18, n=220, rmax=1.8)
    return _arr(s)


def hanko(text, size=300, col="#c8302a", font="old", shape="square", seed=1, inverse=True):
    """Red seal stamp. 1, 2 (vertical) or 4 (2x2, read right column first) characters."""
    s = _surface(size, size)
    c = s.getCanvas()
    m = size * 0.05
    rect = skia.Rect(m, m, size - m, size - m)
    if shape == "circle":
        path = skia.Path()
        path.addOval(rect)
    else:
        path = skia.Path()
        path.addRRect(skia.RRect.MakeRectXY(rect, size * 0.06, size * 0.06))
    n = len(text)
    if inverse:
        c.drawPath(path, _paint(col))
        tc = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kDstOut, Color4f=skia.Color4f(0, 0, 0, 1))
    else:
        c.drawPath(path, _paint(col, 1, size * 0.04))
        tc = _paint(col)
    inner = size - 2 * m
    if n == 1:
        c.drawPath(_glyph_path(text, font, inner * 0.78, size / 2, size / 2), tc)
    elif n == 2:
        for i, ch in enumerate(text):
            c.drawPath(_glyph_path(ch, font, inner * 0.44, size / 2, m + inner * (0.27 + 0.47 * i)), tc)
    elif n == 3:
        # big char right, two small left
        c.drawPath(_glyph_path(text[0], font, inner * 0.5, size / 2 + inner * 0.23, size / 2), tc)
        for i, ch in enumerate(text[1:]):
            c.drawPath(_glyph_path(ch, font, inner * 0.4, size / 2 - inner * 0.23, m + inner * (0.27 + 0.47 * i)), tc)
    else:
        order = [(1, 0), (1, 1), (0, 0), (0, 1)]  # right column top->bottom, then left column
        for (col_i, row), ch in zip(order, text[:4]):
            cx = m + inner * (0.27 + 0.46 * col_i)
            cy = m + inner * (0.27 + 0.46 * row)
            c.drawPath(_glyph_path(ch, font, inner * 0.42, cx, cy), tc)
    _grunge(s, size, size, seed, 0.85, n=int(size * 1.6), rmax=size * 0.012)
    return _arr(s)


def nobori(text, w=150, h=620, cloth="#c8302a", ink="#f3ead6", pole="#2a1a14", font="boku"):
    s = _surface(w + 30, h + 40)
    c = s.getCanvas()
    c.drawRect(skia.Rect(6, 0, 12, h + 40), _paint(pole))
    c.drawRect(skia.Rect(12, 20, 12 + w, 20 + h), _paint(cloth))
    for k in range(5):
        c.drawCircle(12 + w, 30 + k * (h - 20) / 4, 4, _paint(pole))
    n = len(text)
    size = min(w * 0.7, (h - 40) / max(n, 1) * 0.92)
    for i, ch in enumerate(text):
        c.drawPath(_glyph_path(ch, font, size, 12 + w / 2, 20 + 20 + size / 2 + i * (h - 40) / max(n, 1)), _paint(ink))
    return _arr(s)


def torii(w=900, h=760, col="#cf3b2a", dark="#2a1416", gold=None):
    """Front-view torii gate (myojin style)."""
    s = _surface(w, h)
    c = s.getCanvas()
    p = _paint(col)
    d = _paint(dark)
    cx = w / 2
    # kasagi (curved top beam) + shimaki
    top = skia.Path()
    top.moveTo(0, h * 0.06)
    top.quadTo(cx, h * 0.12, w, h * 0.06)
    top.lineTo(w - w * 0.03, h * 0.12)
    top.quadTo(cx, h * 0.17, w * 0.03, h * 0.12)
    top.close()
    c.drawPath(top, d)
    c.drawRect(skia.Rect(w * 0.05, h * 0.12, w * 0.95, h * 0.17), p)
    # nuki (lower beam)
    c.drawRect(skia.Rect(w * 0.1, h * 0.3, w * 0.9, h * 0.355), p)
    # gakuzuka (centre strut)
    c.drawRect(skia.Rect(cx - w * 0.025, h * 0.17, cx + w * 0.025, h * 0.3), p)
    # pillars (slightly tapered)
    for sx in (-1, 1):
        x0 = cx + sx * w * 0.32
        pil = skia.Path()
        pil.moveTo(x0 - w * 0.03, h * 0.16)
        pil.lineTo(x0 + w * 0.03, h * 0.16)
        pil.lineTo(x0 + w * 0.036, h * 0.93)
        pil.lineTo(x0 - w * 0.036, h * 0.93)
        pil.close()
        c.drawPath(pil, p)
        c.drawRect(skia.Rect(x0 - w * 0.045, h * 0.9, x0 + w * 0.045, h), d)
    if gold:
        c.drawRect(skia.Rect(cx - w * 0.06, h * 0.19, cx + w * 0.06, h * 0.28), _paint(gold))
    return _arr(s)


def seigaiha(w, h, r=60, c0="#141a33", c1="#22305a", line="#c9a45a", lw=2.0, alpha=1.0):
    """Wave-scale pattern tile."""
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(0, 0, w, h), _paint(c0, alpha))
    rows = int(h / (r * 0.5)) + 3
    cols = int(w / (r * 2)) + 3
    for j in range(rows):
        y = j * r * 0.5
        off = r if j % 2 else 0
        for i in range(-1, cols):
            x = i * 2 * r + off
            for k in range(4, 0, -1):
                rr = r * k / 4
                c.drawCircle(x, y, rr, _paint(c0 if k % 2 == 0 else c1, alpha))
                c.drawCircle(x, y, rr, _paint(line, 0.55 * alpha, lw))
    return _arr(s)


def asanoha(w, h, r=70, bg="#151a30", line="#c9a45a", lw=1.6, alpha=0.6):
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(0, 0, w, h), _paint(bg))
    p = _paint(line, alpha, lw)
    dx = r * math.sqrt(3)
    for j in range(-1, int(h / (r * 1.5)) + 2):
        for i in range(-1, int(w / dx) + 2):
            x = i * dx + (dx / 2 if j % 2 else 0)
            y = j * r * 1.5
            pts = [(x + r * math.cos(a), y + r * math.sin(a)) for a in [math.pi / 6 + k * math.pi / 3 for k in range(6)]]
            for k in range(6):
                c.drawLine(x, y, *pts[k], p)
                c.drawLine(*pts[k], *pts[(k + 1) % 6], p)
                mx, my = (pts[k][0] + pts[(k + 1) % 6][0]) / 2, (pts[k][1] + pts[(k + 1) % 6][1]) / 2
                c.drawLine(x, y, mx, my, p)
    return _arr(s)


def ichimatsu(w, h, cell=48, c0="#3a1c2c", c1="#2a1422"):
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(0, 0, w, h), _paint(c0))
    for j in range(int(h / cell) + 1):
        for i in range(int(w / cell) + 1):
            if (i + j) % 2:
                c.drawRect(skia.Rect(i * cell, j * cell, (i + 1) * cell, (j + 1) * cell), _paint(c1))
    return _arr(s)


def corner_ornament(size=260, col="#c9a45a", lw=3.0):
    """Art-deco / Japanese corner bracket (top-left orientation)."""
    s = _surface(size, size)
    c = s.getCanvas()
    p = _paint(col, 1, lw)
    m = 10
    c.drawLine(m, m, size - m, m, p)
    c.drawLine(m, m, m, size - m, p)
    c.drawLine(m + 16, m + 16, size * 0.7, m + 16, _paint(col, 1, lw * 0.6))
    c.drawLine(m + 16, m + 16, m + 16, size * 0.7, _paint(col, 1, lw * 0.6))
    # spiral cloud curl
    path = skia.Path()
    path.moveTo(m + 16, size * 0.45)
    path.cubicTo(m + 60, size * 0.45, m + 70, size * 0.25, m + 45, m + 45)
    path.cubicTo(m + 30, m + 30, m + 70, m + 20, size * 0.45, m + 16)
    c.drawPath(path, _paint(col, 1, lw * 0.8))
    c.drawCircle(m + 45, m + 45, 9, _paint(col, 1, lw * 0.7))
    c.drawCircle(m + 45, m + 45, 3, _paint(col))
    for k in range(3):
        c.drawCircle(size * 0.78 + k * 14, m + 16, 2.5, _paint(col))
        c.drawCircle(m + 16, size * 0.78 + k * 14, 2.5, _paint(col))
    c.drawRect(skia.Rect(m - 4, m - 4, m + 4, m + 4), _paint(col))
    return _arr(s)


def frame_border(w=1920, h=1080, col="#c9a45a", inset=36, lw=2.0):
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(inset, inset, w - inset, h - inset), _paint(col, 0.9, lw))
    c.drawRect(skia.Rect(inset + 8, inset + 8, w - inset - 8, h - inset - 8), _paint(col, 0.6, lw * 0.6))
    return _arr(s)


def compass_rose(size=900, col="#d8b25e", dark="#1a1a30", red="#c8302a"):
    s = _surface(size, size)
    c = s.getCanvas()
    cx = cy = size / 2
    R = size * 0.46
    c.drawCircle(cx, cy, R, _paint(col, 1, 3))
    c.drawCircle(cx, cy, R * 0.93, _paint(col, 1, 1.2))
    c.drawCircle(cx, cy, R * 0.55, _paint(col, 0.8, 1.2))
    for k in range(64):
        a = k / 64 * 2 * math.pi
        l = R * (0.07 if k % 8 == 0 else 0.035 if k % 2 == 0 else 0.02)
        c.drawLine(cx + math.cos(a) * (R * 0.93), cy + math.sin(a) * (R * 0.93),
                   cx + math.cos(a) * (R * 0.93 - l), cy + math.sin(a) * (R * 0.93 - l), _paint(col, 1, 1.5))
    for k in range(16):
        a = k / 16 * 2 * math.pi - math.pi / 2
        L = R * (0.88 if k % 4 == 0 else 0.6 if k % 2 == 0 else 0.4)
        wdt = R * (0.09 if k % 4 == 0 else 0.06 if k % 2 == 0 else 0.04)
        for side, colr in ((1, col), (-1, dark if k % 4 else red)):
            pth = skia.Path()
            pth.moveTo(cx, cy)
            pth.lineTo(cx + math.cos(a + side * math.pi / 2) * wdt, cy + math.sin(a + side * math.pi / 2) * wdt)
            pth.lineTo(cx + math.cos(a) * L, cy + math.sin(a) * L)
            pth.close()
            c.drawPath(pth, _paint(colr))
            c.drawPath(pth, _paint(col, 1, 1.0))
    c.drawCircle(cx, cy, R * 0.05, _paint(col))
    return _arr(s)


def calendar_page(day_text, w=360, h=480, seed=0, red=False):
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(0, 0, w, h), _paint("#f1e7d2"))
    c.drawRect(skia.Rect(0, 0, w, 46), _paint("#c8302a" if red else "#2a2a3a"))
    for k in range(6):
        c.drawCircle(w * (0.18 + k * 0.13), 23, 6, _paint("#f1e7d2"))
    n = len(day_text)
    size = min(w * 0.7, (h - 140) / max(n, 1) * 0.9)
    for i, ch in enumerate(day_text):
        c.drawPath(_glyph_path(ch, "old", size, w / 2, 90 + size / 2 + i * size), _paint("#c8302a" if red else "#1a1620"))
    _grunge(s, w, h, seed, 0.1, n=150, rmax=1.5)
    return _arr(s)


def kiku_ring(size, n, petal_len, petal_w, r0, col, edge="#3a1a10", lw=1.5, seed=0):
    """One ring of chrysanthemum petals around the centre."""
    s = _surface(size, size)
    c = s.getCanvas()
    cx = cy = size / 2
    rng = np.random.default_rng(seed)
    for k in range(n):
        a = k / n * 2 * math.pi + rng.uniform(-0.03, 0.03)
        L = petal_len * rng.uniform(0.92, 1.06)
        c.save()
        c.translate(cx, cy)
        c.rotate(math.degrees(a))
        pth = skia.Path()
        pth.moveTo(r0, 0)
        pth.cubicTo(r0 + L * 0.3, -petal_w, r0 + L * 0.85, -petal_w * 0.8, r0 + L, 0)
        pth.cubicTo(r0 + L * 0.85, petal_w * 0.8, r0 + L * 0.3, petal_w, r0, 0)
        c.drawPath(pth, _paint(col))
        c.drawPath(pth, _paint(edge, 0.7, lw))
        c.restore()
    return _arr(s)


def disc(size, col, ring=None, ring_w=0.0, tex_seed=None, soft=0.0):
    s = _surface(size, size)
    c = s.getCanvas()
    r = size / 2 - 4 - ring_w
    p = _paint(col)
    if soft:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, soft))
    c.drawCircle(size / 2, size / 2, r, p)
    if ring:
        c.drawCircle(size / 2, size / 2, r + ring_w / 2, _paint(ring, 1, ring_w))
    if tex_seed is not None:
        rng = np.random.default_rng(tex_seed)
        for _ in range(40):
            a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.8)
            c.drawCircle(size / 2 + math.cos(a) * d, size / 2 + math.sin(a) * d, rng.uniform(r * 0.03, r * 0.14),
                         _paint("#000000", 0.08))
    return _arr(s)


def mountains(w, h, layers, seed=3):
    """Layered ridge silhouettes. layers: list of (base_y_frac, amp_frac, color, edge_color). Returns list of RGBA."""
    rng = np.random.default_rng(seed)
    out = []
    for li, (by, amp, col, edge) in enumerate(layers):
        s = _surface(w, h)
        c = s.getCanvas()
        n = 9 + li * 3
        xs = np.linspace(-0.05, 1.05, n) * w
        ys = by * h - amp * h * (0.3 + 0.7 * rng.random(n)) * (0.6 + 0.4 * np.sin(np.linspace(0, 3, n) + li))
        pth = skia.Path()
        pth.moveTo(xs[0], h)
        pth.lineTo(xs[0], ys[0])
        for i in range(1, n):
            mx = (xs[i - 1] + xs[i]) / 2
            pth.quadTo(xs[i - 1] + (xs[i] - xs[i - 1]) * 0.25, ys[i - 1] - amp * h * 0.08, mx, (ys[i - 1] + ys[i]) / 2)
            pth.quadTo(xs[i] - (xs[i] - xs[i - 1]) * 0.25, ys[i] - amp * h * 0.05, xs[i], ys[i])
        pth.lineTo(xs[-1], h)
        pth.close()
        c.drawPath(pth, _paint(col))
        if edge:
            c.save()
            c.clipPath(pth, doAntiAlias=True)
            edgep = skia.Path(pth)
            c.drawPath(edgep, _paint(edge, 0.9, 3.0))
            c.restore()
        out.append(_arr(s))
    return out


def cloud_band(w=900, h=220, col="#d9b45e", line="#8a6a2a", seed=0):
    """Ukiyo-e style rounded cloud band (suyari-gasumi)."""
    rng = np.random.default_rng(seed)
    s = _surface(w, h)
    c = s.getCanvas()
    path = skia.Path()
    base = h * 0.75
    path.moveTo(w * 0.04, base)
    x = w * 0.04
    while x < w * 0.92:
        r = rng.uniform(h * 0.18, h * 0.32)
        path.arcTo(skia.Rect(x, base - 2 * r, x + 2 * r, base), 180, 180, False)
        x += 2 * r * rng.uniform(0.75, 0.9)
    path.lineTo(w * 0.96, base)
    path.arcTo(skia.Rect(w * 0.9, base - h * 0.06, w * 0.98, base + h * 0.06), 270, 180, False)
    path.lineTo(w * 0.06, base + h * 0.06)
    path.close()
    c.drawPath(path, _paint(col))
    c.drawPath(path, _paint(line, 1, 2.5))
    return _arr(s)


def shoji(w=1920, h=1080, paper="#f0dfb0", frame="#2b1a12", cols=8, rows=5, glow=True):
    s = _surface(w, h)
    c = s.getCanvas()
    if glow:
        sh = skia.GradientShader.MakeRadial(skia.Point(w / 2, h / 2), w * 0.7, [C("#fff4d0"), C(paper), C("#c9a060")], [0, 0.6, 1])
        c.drawRect(skia.Rect(0, 0, w, h), skia.Paint(AntiAlias=True, Shader=sh))
    else:
        c.drawRect(skia.Rect(0, 0, w, h), _paint(paper))
    p = _paint(frame, 1, 7)
    for i in range(cols + 1):
        x = i * w / cols
        c.drawLine(x, 0, x, h, p)
    for j in range(rows + 1):
        y = j * h / rows
        c.drawLine(0, y, w, y, _paint(frame, 1, 5))
    c.drawRect(skia.Rect(0, 0, w, h), _paint(frame, 1, 30))
    return _arr(s)


def ring_text(text, radius, size, font="mincho", col="#d9b45e", start=-90.0, spread=None):
    """Characters laid on a circle (top start), as one RGBA."""
    S = int(2 * (radius + size * 1.5))
    s = _surface(S, S)
    c = s.getCanvas()
    n = len(text)
    spread = spread or 360.0 * n / max(n, 1)
    f = skia.Font(typeface(font), size)
    for i, ch in enumerate(text):
        a = math.radians(start + (i + 0.5) / n * spread)
        c.save()
        c.translate(S / 2 + math.cos(a) * radius, S / 2 + math.sin(a) * radius)
        c.rotate(math.degrees(a) + 90)
        c.drawPath(_glyph_path(ch, font, size, 0, 0), _paint(col))
        c.restore()
    return _arr(s)


def rock_layer(w, h, side, seed=0, col="#10131f", edge="#c9a45a", gap=0.12, jag=0.18, lw=2.5, light=None):
    """Kirie-style rock silhouette filling one side of the frame (side=-1 left, 1 right)."""
    rng = np.random.default_rng(seed)
    s = _surface(w, h)
    c = s.getCanvas()
    path = skia.Path()
    edge_x = w * (0.5 + side * gap)
    pts = []
    n = 14
    for i in range(n + 1):
        y = h * i / n
        x = edge_x + side * w * jag * (0.55 * math.sin(i * 0.9 + seed * 2.1) + 0.45 * (rng.random() - 0.5))
        pts.append((x, y))
    if side < 0:
        path.moveTo(0, 0)
        for x, y in pts:
            path.lineTo(x, y)
        path.lineTo(0, h)
    else:
        path.moveTo(w, 0)
        for x, y in pts:
            path.lineTo(x, y)
        path.lineTo(w, h)
    path.close()
    c.drawPath(path, _paint(col))
    if light:
        c.save(); c.clipPath(path, doAntiAlias=True)
        sh = skia.GradientShader.MakeLinear([skia.Point(edge_x, 0), skia.Point(edge_x + side * w * 0.25, 0)],
                                            [C(light, 0.35), C(light, 0.0)])
        c.drawRect(skia.Rect(0, 0, w, h), skia.Paint(AntiAlias=True, Shader=sh))
        # crack lines inside the rock
        for _ in range(6):
            x0 = edge_x - side * rng.uniform(0.05, 0.3) * w
            y0 = rng.uniform(0, h)
            pp = skia.Path(); pp.moveTo(x0, y0)
            for k in range(4):
                x0 -= side * rng.uniform(10, 60); y0 += rng.uniform(-40, 80); pp.lineTo(x0, y0)
            c.drawPath(pp, _paint(edge, 0.35, 1.2))
        c.restore()
    if edge:
        ep = skia.Path()
        ep.moveTo(*pts[0])
        for x, y in pts[1:]:
            ep.lineTo(x, y)
        c.drawPath(ep, _paint(edge, 1, lw))
    return _arr(s)


def glyph_points(text, font, size, spacing=14.0):
    """Points sampled along the outline of the text (for constellation / dotted drawings). Returns (N,2) and contour ids."""
    f = skia.Font(typeface(font), size)
    g = f.textToGlyphs(text)
    ws = f.getWidths(g)
    tot = sum(ws)
    pts, ids = [], []
    x = -tot / 2
    cid = 0
    for gi, wd in zip(g, ws):
        gp = f.getPath(gi)
        if gp is not None:
            gp.offset(x, size * 0.38)
            pm = skia.PathMeasure(gp, False)
            while True:
                L = pm.getLength()
                if L > 0:
                    n = max(3, int(L / spacing))
                    for k in range(n):
                        p, _ = pm.getPosTan(L * k / n)
                        pts.append((p.x(), p.y())); ids.append(cid)
                    cid += 1
                if not pm.nextContour():
                    break
        x += wd
    return np.array(pts, np.float32), np.array(ids)


def torii_glow_floor(w=1024, h=1024, col="#1a1426", path_col="#3a1c24"):
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(0, 0, w, h), _paint(col))
    c.drawRect(skia.Rect(w * 0.3, 0, w * 0.7, h), _paint(path_col))
    for k in range(0, h, 64):
        c.drawLine(w * 0.3, k, w * 0.7, k, _paint("#000000", 0.25, 2))
    return _arr(s)


def post_lantern(w=120, h=520, body="#f0dfb0", lit=False):
    """Stone/wood post with a small square lantern box on top (toro-like)."""
    s = _surface(w, h)
    c = s.getCanvas()
    c.drawRect(skia.Rect(w * 0.42, h * 0.28, w * 0.58, h), _paint("#1b1418"))
    c.drawRect(skia.Rect(w * 0.12, h * 0.02, w * 0.88, h * 0.06), _paint("#1b1418"))
    box = skia.Rect(w * 0.2, h * 0.06, w * 0.8, h * 0.26)
    if lit:
        sh = skia.GradientShader.MakeRadial(skia.Point(w / 2, h * 0.16), w * 0.5, [C("#fff4cc"), C(body), C("#d08a3a")], [0, 0.6, 1])
        c.drawRect(box, skia.Paint(AntiAlias=True, Shader=sh))
    else:
        c.drawRect(box, _paint("#3a3040"))
    c.drawRect(box, _paint("#1b1418", 1, 4))
    c.drawLine(w / 2, h * 0.06, w / 2, h * 0.26, _paint("#1b1418", 1, 3))
    c.drawRect(skia.Rect(w * 0.1, h * 0.26, w * 0.9, h * 0.29), _paint("#1b1418"))
    return _arr(s)


def taiko_side(w=900, h=760, body="#a8241c", band="#1a0f0c", stud="#e8c46a", head="#efe2c4"):
    """Big taiko drum seen from the side (barrel), drum head on the LEFT, on a wooden stand."""
    s = _surface(w, h)
    c = s.getCanvas()
    bw, bh = w * 0.72, h * 0.62
    cx, cy = w * 0.52, h * 0.40
    # stand
    for x0 in (cx - bw * 0.36, cx + bw * 0.36):
        c.drawRect(skia.Rect(x0 - 14, cy + bh * 0.3, x0 + 14, h - 10), _paint("#3a1c10"))
    c.drawRect(skia.Rect(cx - bw * 0.48, h - 40, cx + bw * 0.48, h - 14), _paint("#2a140c"))
    c.drawRect(skia.Rect(cx - bw * 0.44, cy + bh * 0.42, cx + bw * 0.44, cy + bh * 0.42 + 18), _paint("#3a1c10"))
    # barrel body (bulging)
    p = skia.Path()
    x0, x1 = cx - bw / 2, cx + bw / 2
    p.moveTo(x0, cy - bh * 0.42)
    p.cubicTo(cx - bw * 0.2, cy - bh * 0.56, cx + bw * 0.2, cy - bh * 0.56, x1, cy - bh * 0.42)
    p.lineTo(x1, cy + bh * 0.42)
    p.cubicTo(cx + bw * 0.2, cy + bh * 0.56, cx - bw * 0.2, cy + bh * 0.56, x0, cy + bh * 0.42)
    p.close()
    c.drawPath(p, _paint(body))
    c.save()
    c.clipPath(p, doAntiAlias=True)
    sh = skia.GradientShader.MakeLinear([skia.Point(0, cy - bh / 2), skia.Point(0, cy + bh / 2)],
                                        [C("#ffffff", 0.18), C("#000000", 0.0), C("#000000", 0.45)], [0, 0.4, 1])
    c.drawRect(skia.Rect(0, 0, w, h), skia.Paint(Shader=sh))
    # mitsudomoe crest on the body
    r = bh * 0.2
    c.drawCircle(cx, cy, r * 1.25, _paint(stud, 1, 5))
    for k in range(3):
        a = k * 2 * math.pi / 3
        c.drawCircle(cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45, r * 0.42, _paint(stud))
    c.restore()
    # rims and studs at both ends
    for xe in (x0, x1):
        c.drawRect(skia.Rect(xe - 16, cy - bh * 0.44, xe + 16, cy + bh * 0.44), _paint(band))
        for k in range(9):
            y = cy - bh * 0.4 + k * bh * 0.8 / 8
            c.drawCircle(xe + (22 if xe == x0 else -22), y, 7, _paint(stud))
    # drum head (edge-on ellipse) on the left
    c.drawOval(skia.Rect(x0 - 34, cy - bh * 0.43, x0 + 20, cy + bh * 0.43), _paint(head))
    c.drawOval(skia.Rect(x0 - 34, cy - bh * 0.43, x0 + 20, cy + bh * 0.43), _paint(band, 1, 6))
    c.drawPath(p, _paint(band, 0.8, 3))
    return _arr(s)


def kite(ch, w=240, h=300, paper="#f3e8cc", border="#c8302a", ink="#14100e", font="boku"):
    """Rectangular kaku-dako kite with a big painted kanji (bridle point at the top centre)."""
    s = _surface(w, h)
    c = s.getCanvas()
    m = 6
    c.drawRect(skia.Rect(m, m, w - m, h - m), _paint(paper))
    c.drawRect(skia.Rect(m + 6, m + 6, w - m - 6, h - m - 6), _paint(border, 1, 10))
    c.drawLine(m, m, w - m, h - m, _paint("#6a4a2a", 0.5, 3))
    c.drawLine(w - m, m, m, h - m, _paint("#6a4a2a", 0.5, 3))
    c.drawPath(_glyph_path(ch, font, h * 0.62, w / 2, h / 2), _paint(ink))
    _grunge(s, w, h, ord(ch[0]) % 97, 0.12, n=200, rmax=1.6)
    return _arr(s)


def signboard_text(text, w, h, font="boku", ink="#1c120c"):
    """Transparent layer with vertical text sized to a board (for painting lyrics onto kit signposts)."""
    s = _surface(w, h)
    c = s.getCanvas()
    n = len(text)
    size = min(w * 0.8, h / max(n, 1) * 0.92)
    for i, ch in enumerate(text):
        c.drawPath(_glyph_path(ch, font, size, w / 2, h / 2 + (i - (n - 1) / 2) * size), _paint(ink))
    return _arr(s)
