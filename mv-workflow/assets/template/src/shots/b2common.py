"""More shared helpers: beat grid, lyric syllables, popping glyphs in rows / columns / on arcs, whole-frame camera
pushes (post-shader keys xs / xo / xr / zb / mb), and texture lookups for props in assets/props (p_masks_<i>,
p_yokai_sheet_<i>, p_items_<i>)."""
import math

import numpy as np

from mm import elements as el
from mm import lyrics as ly
from mm.anim import OFFSET, PERIOD
from shots.common import *

BEAT = PERIOD
SMALL = "っゃゅょぁぃぅぇぉッャュョァィゥェォ"


def beat_t(n):
    return OFFSET + n * BEAT


def bar_t(n):
    return OFFSET + n * 4 * BEAT


def syl(i):
    """(char, time) of lyric line i, spaces dropped."""
    return [(c["c"], c["t"]) for c in ly.line(i)["chars"] if c["c"].strip()]


def phr(i):
    return ly.phrases(ly.line(i))


def lerp_c(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def impact(t, hits, tau=0.12):
    return sum(math.exp(-(t - h) / tau) for h in hits if t >= h)


def push(g, zoom, cx=960.0, cy=540.0, roll=0.0):
    """Zoom the whole frame toward the screen point (cx, cy) in post."""
    S = (cx / 1920.0, 1.0 - cy / 1080.0)
    g["xs"] = zoom
    g["xo"] = ((S[0] - 0.5) * (1 - 1 / zoom), (S[1] - 0.5) * (1 - 1 / zoom))
    if roll:
        g["xr"] = roll
    return g


def center(g, zoom, cx=960.0, cy=540.0, roll=0.0):
    """Zoom the whole frame by `zoom` with the screen point (cx, cy) brought to the centre (clamped so the frame never
    runs off the picture). For tracking moves."""
    m = 0.5 - 0.5 / zoom
    g["xs"] = zoom
    g["xo"] = (min(max(cx / 1920.0 - 0.5, -m), m), min(max((1.0 - cy / 1080.0) - 0.5, -m), m))
    if roll:
        g["xr"] = roll
    return g


def pop_k(t, tc, dur=0.22, back=1.8):
    return ease_out_back(remap(t, tc - 0.03, tc + dur), back), remap(t, tc - 0.03, tc + 0.05)


def glyph(shot, c, x, y, size, t, tc, vertical=True, font="old", fill="#f2e7cf", stroke="#0e0b14", stroke_w=0.05,
          shadow=None, glow=None, s0=1.65, rot=0.0, alpha=1.0, t_out=None, dur_out=0.25, out="fade", color=None):
    """One character popping in on its syllable (scale overshoot), optionally leaving at t_out."""
    if t < tc - 0.03:
        return
    k, a = pop_k(t, tc)
    sc = lerp(s0, 1.0, k)
    dy = 0.0
    if t_out is not None and t > t_out:
        o = remap(t, t_out, t_out + dur_out)
        a *= 1 - o
        if out == "rise":
            dy = -60 * ease_in(o, 2)
        elif out == "drop":
            dy = 80 * ease_in(o, 2)
    if a <= 0.004:
        return
    g = shot.ctx.gc.get(c, vertical=vertical, font=font, size=int(size), fill=fill, stroke=stroke, stroke_w=stroke_w,
                        shadow=shadow, glow=glow)
    shot.e.image(g, x, y + dy, 0, g.w * sc, g.w * sc, alpha=a * alpha, screen=True, rot=rot + (1 - k) * 0.12,
                 color=color or (1, 1, 1))


def column(shot, chars, x, y_top, size, t, step=1.02, **kw):
    """A vertical column read top to bottom, small kana set up and to the right; returns the bottom y."""
    y = y_top
    for c, tc in chars:
        small = c in SMALL
        adv = size * step * (0.62 if small else 1.0)
        cx = x + (size * 0.2 if small else 0.0)
        cy = y + adv / 2 - (size * 0.08 if small else 0.0)
        glyph(shot, c, cx, cy, size * (0.7 if small else 1.0), t, tc, **kw)
        y += adv
    return y


def row(shot, chars, x_mid, y, size, t, step=1.02, sizes=None, **kw):
    """A horizontal row centred on x_mid."""
    widths = [size * step * (0.7 if c in SMALL else 1.0) for c, _ in chars]
    x = x_mid - sum(widths) / 2
    for (c, tc), w in zip(chars, widths):
        s = (sizes or {}).get(c, size) * (0.75 if c in SMALL else 1.0)
        glyph(shot, c, x + w / 2, y + (size * 0.12 if c in SMALL else 0.0), s, t, tc, vertical=False, **kw)
        x += w


def arc_chars(shot, chars, cx, cy, rx, ry, a0, a1, size, t, upright=False, **kw):
    """Characters spread along an elliptical arc from angle a0 to a1 (degrees, 0 = right, 90 = down)."""
    n = len(chars)
    for i, (c, tc) in enumerate(chars):
        a = math.radians(a0 + (a1 - a0) * (i + 0.5) / n)
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        rot = 0.0 if upright else math.atan2(ry * math.cos(a), -rx * math.sin(a)) + math.pi
        glyph(shot, c, x, y, size, t, tc, vertical=False, rot=rot, **kw)


def mask_tex(shot, i):
    return prop_tex(shot, f"p_masks_{i}")


def yokai_tex(shot, i):
    return prop_tex(shot, f"p_yokai_sheet_{i}")


def item_tex(shot, i):
    return prop_tex(shot, f"p_items_{i}")


def shadow_under(shot, x, y, w, alpha=0.5):
    shot.e.image(shot.ctx.atlas, x, y, 0, w, w * 0.16, uv=shot.ctx.uv["glow"], color=(0.0, 0.0, 0.0), alpha=alpha,
                 screen=True)


def glow(shot, x, y, size, col, alpha):
    shot.e.image(shot.ctx.atlas, x, y, 0, size, size, uv=shot.ctx.uv["glow"], color=col, alpha=alpha, screen=True,
                 blend="add")


def hand_drawn_x(shot, key, size=200, col="#c8302a", seed=0):
    """A brushed batsu (×) mark."""
    import skia
    from mm.elements import _arr, _surface

    def make():
        s = _surface(size, size)
        c = s.getCanvas()
        rng = np.random.default_rng(seed)
        p = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*[int(col[i:i + 2], 16) / 255 for i in (1, 3, 5)], 1.0))
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        m = size * 0.18
        for (x0, y0, x1, y1) in ((m, m, size - m, size - m), (size - m, m, m, size - m)):
            for k in range(3):
                p.setStrokeWidth(size * (0.13 - 0.03 * k))
                j = rng.uniform(-size * 0.02, size * 0.02, 4)
                c.drawLine(x0 + j[0], y0 + j[1], x1 + j[2], y1 + j[3], p)
        return _arr(s)
    return shot.A(key, make)


def hand_drawn_o(shot, key, size=200, col="#d4a640", seed=0, lw=0.12):
    """A brushed maru (○) mark; lw = stroke width as a fraction of size."""
    import skia
    from mm.elements import _arr, _surface

    def make():
        s = _surface(size, size)
        c = s.getCanvas()
        p = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*[int(col[i:i + 2], 16) / 255 for i in (1, 3, 5)], 1.0))
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        r = size * 0.33
        r = size * 0.5 - size * lw
        for k in range(3):
            p.setStrokeWidth(size * lw * (1.0 - 0.25 * k))
            c.drawArc(skia.Rect(size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r), -80 + k * 6, 340 - k * 10, False, p)
        return _arr(s)
    return shot.A(key, make)
