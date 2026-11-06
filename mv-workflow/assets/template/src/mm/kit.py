"""Vector scene kit (flat paper-cut style, skia): boulder, rope, shide, cliff, steps, lanterns, cedars, houses, yagura.

Every builder returns an RGBA uint8 array. Colours are passed in so the same set can be relit per act.
"""
import math

import numpy as np
import skia

from .elements import C, _arr, _glyph_path, _grunge, _paint, _surface

NIGHT = dict(sky0="#0b0e20", sky1="#16203f", rock0="#0d1122", rock1="#18213d", rock2="#26345c", line="#c9a45a",
             paper="#efe4cc", rope="#b89a5a", rope_d="#6e5a30", lamp="#f2c66a", tree0="#0a0d1a", tree1="#121a30",
             step0="#1a2240", step1="#2a3866", wall="#1a1f36", roof="#0e1226", win="#2a3050", win_lit="#f6c766")
FEST = dict(NIGHT, sky0="#140c1c", sky1="#2a1530", rock0="#1a0f1a", rock1="#2c1a2a", rock2="#4a2a36", line="#e8b84c",
            step0="#2a1622", step1="#4a2830", tree0="#120a14", tree1="#22121e", wall="#2a1a26", roof="#140a12")
DAWN = dict(NIGHT, sky0="#f2b38a", sky1="#f6dca6", rock0="#4a2a3e", rock1="#7a4a5a", rock2="#b06a6a", line="#f6d68a",
            step0="#8a5a5a", step1="#c08a7a", tree0="#3a2032", tree1="#5a3a4a", wall="#c89a8a", roof="#5a3040")


def _blob(cx, cy, rx, ry, seed, n=22, jag=0.06):
    rng = np.random.default_rng(seed)
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi
        r = 1 + jag * (rng.random() - 0.5) * 2 + 0.04 * math.sin(a * 3 + seed)
        pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(1, n + 1):
        a = pts[i % n]
        b = pts[(i + 1) % n]
        p.quadTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    p.close()
    return p


def _dots_shader(cell=10, r=2.6, col="#000000", alpha=1.0, angle=30):
    tile = _surface(cell, cell)
    c = tile.getCanvas()
    c.drawCircle(cell / 2, cell / 2, r, _paint(col, alpha))
    img = tile.makeImageSnapshot()
    m = skia.Matrix()
    m.setRotate(angle)
    return img.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat, skia.SamplingOptions(), m)


def halftone_fill(c, path, col, alpha=0.8, cell=11, r=3.0, grad=None):
    """Fill path with a halftone dot pattern; grad=(x0,y0,x1,y1) fades dot alpha along a direction."""
    c.save()
    c.clipPath(path, doAntiAlias=True)
    p = skia.Paint(AntiAlias=True, Shader=_dots_shader(cell, r, col, alpha))
    if grad:
        x0, y0, x1, y1 = grad
        layer_bounds = path.getBounds()
        c.saveLayer(layer_bounds)
        c.drawPath(path, p)
        mask = skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)],
                                              [skia.Color4f(0, 0, 0, 1), skia.Color4f(0, 0, 0, 0)])
        c.drawPath(path, skia.Paint(Shader=mask, BlendMode=skia.BlendMode.kDstIn))
        c.restore()
    else:
        c.drawPath(path, p)
    c.restore()


def boulder(size=1000, pal=NIGHT, seed=3, cracks=0.0):
    """The sealing boulder: flat tones + gold carved contour lines + halftone shadow. cracks in [0,1] adds glowing cracks."""
    s = _surface(size, size)
    c = s.getCanvas()
    cx = cy = size / 2
    R = size * 0.46
    body = _blob(cx, cy, R, R * 0.92, seed, jag=0.05)
    c.drawPath(body, _paint(pal["rock1"]))
    # lit upper-left facet
    c.save()
    c.clipPath(body, doAntiAlias=True)
    hi = _blob(cx - R * 0.28, cy - R * 0.3, R * 0.62, R * 0.52, seed + 1, jag=0.12)
    c.drawPath(hi, _paint(pal["rock2"]))
    # shadow crescent lower-right
    sh = _blob(cx + R * 0.35, cy + R * 0.32, R * 0.85, R * 0.78, seed + 2, jag=0.1)
    c.drawPath(sh, _paint(pal["rock0"]))
    halftone_fill(c, sh, "#000000", 0.55, cell=12, r=3.4, grad=(cx + R, cy + R, cx - R * 0.2, cy - R * 0.2))
    halftone_fill(c, hi, pal["line"], 0.25, cell=12, r=2.2, grad=(cx - R, cy - R, cx, cy))
    # carved contour lines (woodblock gouges)
    rng = np.random.default_rng(seed)
    for k in range(9):
        a0 = rng.uniform(0, 2 * math.pi)
        rr = R * rng.uniform(0.35, 0.95)
        span = rng.uniform(0.4, 1.1)
        pth = skia.Path()
        pth.addArc(skia.Rect(cx - rr, cy - rr * 0.92, cx + rr, cy + rr * 0.92), math.degrees(a0), math.degrees(span))
        c.drawPath(pth, _paint(pal["line"], 0.55, rng.uniform(1.5, 3.5)))
    for k in range(6):
        x0, y0 = cx + rng.uniform(-R * 0.6, R * 0.6), cy + rng.uniform(-R * 0.6, R * 0.6)
        pth = skia.Path()
        pth.moveTo(x0, y0)
        for j in range(4):
            x0 += rng.uniform(-40, 40)
            y0 += rng.uniform(10, 50)
            pth.lineTo(x0, y0)
        c.drawPath(pth, _paint("#000000", 0.45, 2.0))
    c.restore()
    c.drawPath(body, _paint(pal["line"], 1, 5))
    c.drawPath(body, _paint("#05050a", 0.8, 2))
    _grunge(s, size, size, seed, 0.15, n=400, rmax=1.8)
    return _arr(s)


def crack_points(seed, x0, y0, x1, y1, n=18, jag=40):
    rng = np.random.default_rng(seed)
    pts = []
    for i in range(n + 1):
        k = i / n
        x = x0 + (x1 - x0) * k + (rng.uniform(-jag, jag) if 0 < i < n else 0)
        y = y0 + (y1 - y0) * k + (rng.uniform(-jag * 0.3, jag * 0.3) if 0 < i < n else 0)
        pts.append((x, y))
    return pts


def shimenawa(w=1400, h=260, pal=NIGHT, sag=70, n_tassel=5):
    """Twisted straw rope hanging in a shallow curve, with straw tassels."""
    s = _surface(w, h + 160)
    c = s.getCanvas()
    th = h * 0.42

    def ypos(x):
        k = x / w - 0.5
        return th * 0.6 + sag * (1 - 4 * k * k)
    top = skia.Path()
    bot = skia.Path()
    xs = np.linspace(0, w, 60)
    top.moveTo(0, ypos(0) - th / 2)
    for x in xs[1:]:
        top.lineTo(x, ypos(x) - th / 2 * (1.0 - 0.25 * abs(x / w - 0.5)))
    for x in xs[::-1]:
        top.lineTo(x, ypos(x) + th / 2 * (1.0 - 0.25 * abs(x / w - 0.5)))
    top.close()
    c.drawPath(top, _paint(pal["rope"]))
    c.save()
    c.clipPath(top, doAntiAlias=True)
    step = th * 0.55
    for x in np.arange(-th, w + th, step):
        pth = skia.Path()
        y = ypos(min(max(x, 0), w))
        pth.moveTo(x, y - th)
        pth.cubicTo(x + step * 0.5, y - th * 0.3, x + step * 0.2, y + th * 0.3, x + step * 0.8, y + th)
        c.drawPath(pth, _paint(pal["rope_d"], 1, step * 0.28))
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, h)], [C("#ffffff", 0.18), C("#000000", 0.35)])
    c.drawRect(skia.Rect(0, 0, w, h + 160), skia.Paint(Shader=sh))
    c.restore()
    c.drawPath(top, _paint("#1a1208", 0.8, 3))
    # tassels
    for i in range(n_tassel):
        x = w * (i + 1) / (n_tassel + 1)
        y = ypos(x) + th * 0.35
        tp = skia.Path()
        tp.moveTo(x - 16, y)
        tp.lineTo(x + 16, y)
        tp.lineTo(x + 26, y + 120)
        tp.lineTo(x - 26, y + 120)
        tp.close()
        c.drawPath(tp, _paint(pal["rope"]))
        for k in range(-3, 4):
            c.drawLine(x + k * 6, y + 10, x + k * 8.5, y + 118, _paint(pal["rope_d"], 0.8, 1.6))
        c.drawRect(skia.Rect(x - 18, y - 4, x + 18, y + 12), _paint(pal["rope_d"]))
    return _arr(s)


def shide(h=200, pal=NIGHT):
    """Zigzag paper streamer (4 folds)."""
    w = int(h * 0.42)
    s = _surface(w + 10, h + 10)
    c = s.getCanvas()
    seg = h / 4
    pth = skia.Path()
    xs = [0.35, 0.65, 0.35, 0.65]
    for i in range(4):
        x0 = (xs[i] - 0.3) * w + 5
        y0 = 5 + i * seg
        sub = skia.Path()
        sub.moveTo(x0, y0)
        sub.lineTo(x0 + w * 0.6, y0)
        sub.lineTo(x0 + w * 0.6 + (w * 0.3 if i % 2 == 0 else -w * 0.3), y0 + seg)
        sub.lineTo(x0 + (w * 0.3 if i % 2 == 0 else -w * 0.3), y0 + seg)
        sub.close()
        c.drawPath(sub, _paint(pal["paper"]))
        c.drawPath(sub, _paint("#8a7a60", 0.8, 1.2))
    return _arr(s)


def cliff(w=2600, h=1500, pal=NIGHT, seed=5, mouth=(0.5, 0.62, 0.21, 0.27)):
    """Rock cliff face with a dark cave mouth (cx, cy, rx, ry as fractions)."""
    rng = np.random.default_rng(seed)
    s = _surface(w, h)
    c = s.getCanvas()
    outline = skia.Path()
    outline.moveTo(0, h)
    pts = [(0, h * 0.35)]
    for i in range(1, 12):
        x = w * i / 11
        y = h * (0.12 + 0.18 * abs(math.sin(i * 0.7 + seed)) + 0.06 * rng.random())
        if 0.3 < i / 11 < 0.7:
            y *= 0.6
        pts.append((x, y))
    for x, y in pts:
        outline.lineTo(x, y)
    outline.lineTo(w, h)
    outline.close()
    c.drawPath(outline, _paint(pal["rock1"]))
    c.save()
    c.clipPath(outline, doAntiAlias=True)
    # rock facets
    for k in range(26):
        x = rng.uniform(0, w)
        y = rng.uniform(h * 0.1, h)
        fp = _blob(x, y, rng.uniform(80, 260), rng.uniform(60, 200), seed * 10 + k, n=9, jag=0.25)
        tone = pal["rock2"] if rng.random() < 0.4 else pal["rock0"]
        c.drawPath(fp, _paint(tone, 0.85))
        c.drawPath(fp, _paint(pal["line"], 0.35, 2))
    halftone_fill(c, outline, "#000000", 0.35, cell=13, r=3.2, grad=(0, h, w * 0.3, h * 0.3))
    # cave mouth
    mx, my, mrx, mry = mouth
    arch = skia.Path()
    arch.addOval(skia.Rect(w * (mx - mrx), h * (my - mry), w * (mx + mrx), h * (my + mry) + h * 0.3))
    c.drawPath(arch, _paint("#030308"))
    c.drawPath(arch, _paint(pal["line"], 0.9, 4))
    c.restore()
    c.drawPath(outline, _paint(pal["line"], 0.9, 4))
    _grunge(s, w, h, seed, 0.12, n=900, rmax=2.0)
    return _arr(s)


def steps(w=1200, h=520, n=9, pal=NIGHT):
    s = _surface(w, h)
    c = s.getCanvas()
    for i in range(n):
        k0, k1 = i / n, (i + 1) / n
        top_w = w * (0.35 + 0.65 * k0)
        bot_w = w * (0.35 + 0.65 * k1)
        y0, y1 = h * k0, h * k1
        p = skia.Path()
        p.moveTo((w - top_w) / 2, y0)
        p.lineTo((w + top_w) / 2, y0)
        p.lineTo((w + bot_w) / 2, y1)
        p.lineTo((w - bot_w) / 2, y1)
        p.close()
        c.drawPath(p, _paint(pal["step1"] if i % 2 == 0 else pal["step0"]))
        c.drawLine((w - top_w) / 2, y0, (w + top_w) / 2, y0, _paint(pal["line"], 0.7, 2.5))
    return _arr(s)


def stone_lantern(w=220, h=520, pal=NIGHT, lit=True):
    s = _surface(w, h)
    c = s.getCanvas()
    col = _paint(pal["rock0"])
    edge = _paint(pal["line"], 0.8, 2.5)
    cx = w / 2
    parts = [
        ("rect", (cx - w * 0.38, h * 0.9, cx + w * 0.38, h)),
        ("rect", (cx - w * 0.12, h * 0.56, cx + w * 0.12, h * 0.9)),
        ("rect", (cx - w * 0.3, h * 0.5, cx + w * 0.3, h * 0.56)),
        ("rect", (cx - w * 0.24, h * 0.3, cx + w * 0.24, h * 0.5)),
    ]
    for _, (x0, y0, x1, y1) in parts:
        c.drawRect(skia.Rect(x0, y0, x1, y1), col)
        c.drawRect(skia.Rect(x0, y0, x1, y1), edge)
    roof = skia.Path()
    roof.moveTo(cx - w * 0.48, h * 0.3)
    roof.quadTo(cx, h * 0.12, cx + w * 0.48, h * 0.3)
    roof.lineTo(cx + w * 0.3, h * 0.2)
    roof.lineTo(cx, h * 0.08)
    roof.lineTo(cx - w * 0.3, h * 0.2)
    roof.close()
    c.drawPath(roof, col)
    c.drawPath(roof, edge)
    c.drawCircle(cx, h * 0.06, w * 0.06, col)
    win = skia.Rect(cx - w * 0.13, h * 0.34, cx + w * 0.13, h * 0.46)
    c.drawRect(win, _paint(pal["lamp"] if lit else "#05050a"))
    return _arr(s)


def cedar(w=420, h=1300, pal=NIGHT, seed=0, tiers=7):
    rng = np.random.default_rng(seed)
    s = _surface(w, h)
    c = s.getCanvas()
    cx = w / 2
    c.drawRect(skia.Rect(cx - w * 0.04, h * 0.2, cx + w * 0.04, h), _paint(pal["tree0"]))
    for i in range(tiers):
        k = i / (tiers - 1)
        y = h * (0.04 + 0.78 * k)
        tw = w * (0.18 + 0.82 * k) * rng.uniform(0.85, 1.0)
        th = h * 0.16
        p = skia.Path()
        p.moveTo(cx, y - th * 0.4)
        for j in range(7):
            jj = j / 6
            p.lineTo(cx + tw / 2 * jj, y + th * (0.2 + 0.5 * jj) + (8 if j % 2 else -8))
        p.lineTo(cx - tw / 2, y + th * 0.7)
        p.close()
        c.drawPath(p, _paint(pal["tree1"] if i % 2 else pal["tree0"]))
        c.drawPath(p, _paint(pal["line"], 0.35, 1.8))
    return _arr(s)


def house(w=520, h=420, pal=NIGHT, seed=0, lit=False):
    """Japanese house elevation: curved tiled roof, plaster wall, lattice windows. lit=True draws only lit windows."""
    rng = np.random.default_rng(seed)
    s = _surface(w, h)
    c = s.getCanvas()
    wall_top = h * 0.42
    nwin = int(rng.integers(2, 4))
    wins = []
    for i in range(nwin):
        ww = w * 0.16
        x0 = w * 0.12 + i * (w * 0.76 - ww) / max(nwin - 1, 1)
        wins.append(skia.Rect(x0, h * 0.55, x0 + ww, h * 0.78))
    if lit:
        for r in wins:
            c.drawRect(r, _paint(pal["win_lit"]))
            for k in range(1, 3):
                c.drawLine(r.left(), r.top() + r.height() * k / 3, r.right(), r.top() + r.height() * k / 3, _paint("#5a3a1a", 0.8, 2))
            c.drawLine((r.left() + r.right()) / 2, r.top(), (r.left() + r.right()) / 2, r.bottom(), _paint("#5a3a1a", 0.8, 2))
        return _arr(s)
    c.drawRect(skia.Rect(w * 0.06, wall_top, w * 0.94, h), _paint(pal["wall"]))
    for r in wins:
        c.drawRect(r, _paint(pal["win"]))
        c.drawRect(r, _paint(pal["line"], 0.5, 2))
    roof = skia.Path()
    roof.moveTo(0, wall_top + 10)
    roof.quadTo(w * 0.5, wall_top - h * 0.06, w, wall_top + 10)
    roof.lineTo(w * 0.86, h * 0.12)
    roof.quadTo(w * 0.5, h * 0.06, w * 0.14, h * 0.12)
    roof.close()
    c.drawPath(roof, _paint(pal["roof"]))
    for k in range(1, 9):
        x = w * k / 9
        c.drawLine(x, h * 0.13, x + (x - w / 2) * 0.12, wall_top + 4, _paint(pal["line"], 0.25, 2))
    c.drawPath(roof, _paint(pal["line"], 0.7, 2.5))
    c.drawRect(skia.Rect(w * 0.06, wall_top, w * 0.94, h), _paint(pal["line"], 0.5, 2))
    c.drawRect(skia.Rect(w * 0.4, h * 0.6, w * 0.58, h), _paint("#05050a"))
    return _arr(s)


def yagura(w=700, h=1000, pal=FEST):
    s = _surface(w, h)
    c = s.getCanvas()
    wood = _paint("#3a1c14")
    for x in (w * 0.15, w * 0.85):
        c.drawRect(skia.Rect(x - 10, h * 0.25, x + 10, h), wood)
    c.drawRect(skia.Rect(w * 0.05, h * 0.25, w * 0.95, h * 0.3), wood)
    # kohaku (red/white striped) curtain around the platform
    stripes = 10
    for i in range(stripes):
        x0 = w * 0.1 + i * w * 0.8 / stripes
        c.drawRect(skia.Rect(x0, h * 0.3, x0 + w * 0.8 / stripes, h * 0.48), _paint("#d8452e" if i % 2 else "#f2e7cf"))
    c.drawRect(skia.Rect(w * 0.1, h * 0.3, w * 0.9, h * 0.48), _paint(pal["line"], 0.9, 3))
    roof = skia.Path()
    roof.moveTo(0, h * 0.26)
    roof.quadTo(w * 0.5, h * 0.18, w, h * 0.26)
    roof.lineTo(w * 0.5, h * 0.08)
    roof.close()
    c.drawPath(roof, _paint("#2a1410"))
    c.drawPath(roof, _paint(pal["line"], 0.8, 3))
    for i in range(6):
        x = w * (0.12 + i * 0.152)
        c.drawOval(skia.Rect(x - 22, h * 0.5, x + 22, h * 0.56), _paint("#f2a03a"))
    return _arr(s)
