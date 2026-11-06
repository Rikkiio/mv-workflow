"""Lyric carriers: lyrics drawn as part of the scene (in world space so they move with the parallax).

Each carrier takes one timed lyric line ({t, end, sung_end, text, chars:[{c,t}]}) and draws it at time t.
"""
import math

import numpy as np
import skia

from . import elements as el
from .anim import clamp01, ease_in, ease_io, ease_out, ease_out_back, ease_out_expo, hexc, lerp, remap, smooth
from .text import LYRIC_STYLE, glyph_rgba, lyric_lines, typeface

_LINES = None


def line(i):
    global _LINES
    if _LINES is None:
        _LINES = lyric_lines()
    return _LINES[i]


def find_line(prefix, after=0.0):
    global _LINES
    if _LINES is None:
        _LINES = lyric_lines()
    for L in _LINES:
        if L["text"].startswith(prefix) and L["t"] >= after - 0.01:
            return L
    raise KeyError(prefix)


def is_kana(c):
    o = ord(c[0])
    return 0x3040 <= o <= 0x30ff


def char_scale(c, big="", kana=0.8, big_scale=1.45):
    if c in big:
        return big_scale
    if is_kana(c):
        return kana
    return 1.0


def layout_columns(cols, x, y, size, col_gap, big, kana, big_scale, align="top"):
    """cols: list of [(c, t)]; returns [(c, t, cx, cy, scale)] with cumulative vertical spacing."""
    out = []
    for ci, col in enumerate(cols):
        cx = x - ci * size * col_gap
        scales = [char_scale(c, big, kana, big_scale) for c, _ in col]
        total = sum(scales) * size
        yy = y if align == "top" else (y - total / 2 if align == "center" else y - total)
        for (c, tc), sc in zip(col, scales):
            out.append((c, tc, cx, yy + sc * size / 2, sc))
            yy += sc * size
    return out


def phrases(L):
    """Split a line into phrases at spaces: list of lists of (char, time)."""
    out, cur = [], []
    for ch in L["chars"]:
        if ch["c"] in (" ", "　"):
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append((ch["c"], ch["t"]))
    if cur:
        out.append(cur)
    return out


def t_out_of(L, hold=0.5):
    return min(L["end"] - 0.05, max(L["sung_end"], L["chars"][0]["t"]) + hold)


class Carrier:
    def __init__(self, L, t_out=None, style=None, accent="", accent_style=None, cam=True):
        self.L = L
        self.t_in = L["chars"][0]["t"]
        self.t_out = t_out if t_out is not None else t_out_of(L)
        self.style = dict(LYRIC_STYLE)
        if style:
            self.style.update(style)
        self.accent = set(accent)
        self.accent_style = dict(self.style, fill="#e0452e")
        if accent_style:
            self.accent_style.update(accent_style)
        self.use_cam = cam

    def glyph(self, shot, c, vertical=True, style=None):
        st = style or (self.accent_style if c in self.accent else self.style)
        return shot.ctx.gc.get(c, vertical=vertical, **st)

    def active(self, t, pre=0.4, post=1.2):
        return self.t_in - pre <= t <= self.t_out + post


class FloatV(Carrier):
    """Vertical columns (right-to-left) floating at a depth plane in the scene."""

    def __init__(self, L, x, y, z=0.0, size=None, col_gap=1.35, max_col=12, align="top", exit="rise", big="",
                 kana=0.8, big_scale=1.45, **kw):
        super().__init__(L, **kw)
        if size:
            self.style["size"] = size
        self.size = self.style["size"]
        self.z = z
        self.exit = exit
        cols = []
        for ph in phrases(L):
            for k in range(0, len(ph), max_col):
                cols.append(ph[k:k + max_col])
        self.items = layout_columns(cols, x, y, self.size, col_gap, big, kana, big_scale, align)

    def draw(self, shot, t, cam=None, alpha=1.0, screen=None):
        if not self.active(t):
            return
        e = shot.e
        scr = (cam is None) if screen is None else screen
        for i, (c, tc, x, y, cs) in enumerate(self.items):
            a = remap(t, tc - 0.05, tc + 0.12)
            if a <= 0:
                continue
            k = ease_out_back(remap(t, tc - 0.05, tc + 0.25), 2.0)
            sc = (1.0 + (1 - k) * 0.4) * cs
            dy = -(1 - ease_out(remap(t, tc - 0.05, tc + 0.22))) * self.size * 0.3
            o = remap(t, self.t_out + i * 0.03, self.t_out + 0.4 + i * 0.03)
            if self.exit == "rise":
                dy -= ease_in(o) * self.size * 0.8
            a *= (1 - o) * alpha
            if a <= 0.004:
                continue
            tex = self.glyph(shot, c)
            s = tex.w * sc
            if scr:
                e.image(tex, x, y + dy, 0, s, s, alpha=a, screen=True)
            else:
                e.image(tex, x, y + dy, self.z, s, s, alpha=a, cam=cam, screen=(cam is None))


class Tanzaku(Carrier):
    """Each phrase on a hanging paper strip that drops in and swings; characters ink in on time."""

    def __init__(self, L, x0, y_top, dx=-170, z=0.0, size=58, paper="#efe4cc", ink="#1c1418", band="#c8302a",
                 swing=0.12, exit="fly", **kw):
        st = dict(font="mincho", size=size, fill=ink, stroke=None, stroke_w=0.0, shadow=None)
        super().__init__(L, style=st, **kw)
        self.accent_style = dict(st, fill=band)
        self.size = size
        self.z = z
        self.swing = swing
        self.exit = exit
        self.strips = []
        for pi, ph in enumerate(phrases(L)):
            n = len(ph)
            w = size * 1.55
            h = n * size * 1.08 + size * 1.2
            key = f"tz|{w:.0f}|{h:.0f}|{paper}|{band}"
            self.strips.append(dict(ph=ph, x=x0 + pi * dx, w=w, h=h, key=key, t=ph[0][1], seed=pi))
        self.paper, self.band, self.ink = paper, band, ink
        self.y_top = y_top

    def _strip_tex(self, shot, s):
        def mk():
            surf = el._surface(s["w"], s["h"])
            c = surf.getCanvas()
            c.drawRect(skia.Rect(0, 0, s["w"], s["h"]), el._paint(self.paper))
            c.drawRect(skia.Rect(0, 0, s["w"], self.size * 0.35), el._paint(self.band))
            c.drawRect(skia.Rect(3, 3, s["w"] - 3, s["h"] - 3), el._paint("#8a6a4a", 0.6, 1.5))
            el._grunge(surf, s["w"], s["h"], s["seed"], 0.12, n=140, rmax=1.6)
            return el._arr(surf)
        return shot.A(s["key"], mk)

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t, 0.6, 1.5):
            return
        e = shot.e
        for si, s in enumerate(self.strips):
            t0 = s["t"] - 0.35
            if t < t0:
                continue
            k = ease_out_back(remap(t, t0, t0 + 0.45), 1.3)
            drop = (1 - k) * -(s["h"] + 200)
            ang = self.swing * math.sin((t - t0) * 5.0 + si) * math.exp(-(t - t0) * 1.6) + 0.015 * math.sin(t * 1.3 + si)
            o = remap(t, self.t_out + si * 0.08, self.t_out + 0.6 + si * 0.08)
            fly_y = -ease_in(o) * 900 if self.exit == "fly" else 0
            fly_r = ease_in(o) * (0.6 if si % 2 else -0.6)
            a = alpha * (1 - remap(o, 0.6, 1.0))
            px, py = s["x"], self.y_top + drop + fly_y
            ang += fly_r
            ca, sa = math.cos(ang), math.sin(ang)
            # string
            e.image(e.white, px, py - 400, self.z, 2.5, 800, color=(0.1, 0.08, 0.08), alpha=a, cam=cam, screen=(cam is None))
            tex = self._strip_tex(shot, s)
            cx, cy = px - sa * s["h"] / 2, py + ca * s["h"] / 2
            e.image(tex, cx, cy, self.z, s["w"], s["h"], rot=ang, alpha=a, cam=cam, screen=(cam is None))
            for k2, (c, tc) in enumerate(s["ph"]):
                ai = remap(t, tc - 0.04, tc + 0.1)
                if ai <= 0:
                    continue
                ly = self.size * 0.95 + k2 * self.size * 1.08
                gx, gy = px - sa * ly, py + ca * ly
                g = self.glyph(shot, c)
                sc = 1 + (1 - ease_out(remap(t, tc - 0.04, tc + 0.18))) * 0.35
                e.image(g, gx, gy, self.z, g.w * sc, g.w * sc, rot=ang, alpha=a * ai, cam=cam, screen=(cam is None))


class BrushV(Carrier):
    """Big calligraphy columns painted top-to-bottom per character."""

    def __init__(self, L, x, y, z=0.0, size=120, col_gap=1.2, font="brush", fill="#f2e7cf", glow=None,
                 blend="normal", splatter=True, max_col=8, big="", kana=0.8, big_scale=1.45, align="top", **kw):
        st = dict(font=font, size=size, fill=fill, stroke=None, stroke_w=0.0, shadow=None, glow=glow)
        super().__init__(L, style=st, **kw)
        self.size, self.z, self.blend, self.splatter = size, z, blend, splatter
        cols = []
        for ph in phrases(L):
            for k in range(0, len(ph), max_col):
                cols.append(ph[k:k + max_col])
        self.items = layout_columns(cols, x, y, size * 0.98, col_gap, big, kana, big_scale, align)

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t):
            return
        e = shot.e
        for i, (c, tc, x, y, cs) in enumerate(self.items):
            p = remap(t, tc - 0.03, tc + 0.22)
            if p <= 0:
                continue
            o = remap(t, self.t_out + i * 0.04, self.t_out + 0.45 + i * 0.04)
            a = alpha * (1 - o)
            if a <= 0.004:
                continue
            g = self.glyph(shot, c)
            cut = (0.0, 1.0, lerp(0.0, 1.15, ease_out(p)), 0.15) if p < 1 else None
            e.sprites(g, e.inst(x, y, self.z, g.w * cs, g.w * cs, 0, 0, 0, (0, 0, 1, 1), (1, 1, 1, a))[None], cam=cam,
                      screen=(cam is None), blend=self.blend, cut=cut)


class Particles(Carrier):
    """Text formed by glowing motes that converge onto the glyph outline at each character's time."""

    def __init__(self, L, x, y, z=0.0, size=110, col_gap=1.3, color=(0.7, 1.0, 0.95), spacing=7.0, src=None,
                 font="mincho", max_col=9, fill_alpha=0.85, big="", kana=1.0, big_scale=1.45, **kw):
        super().__init__(L, **kw)
        self.size, self.z, self.color, self.src = size, z, color, src
        self.font = font
        self.fill_alpha = fill_alpha
        self.items = []
        rng = np.random.default_rng(len(L["text"]))
        cols = []
        for ph in phrases(L):
            for k in range(0, len(ph), max_col):
                cols.append(ph[k:k + max_col])
        for c, tc, cx, cy, cs in layout_columns(cols, x, y, size * 1.02, col_gap, big, kana, big_scale):
            sz = int(size * cs)
            pts, _ = el.glyph_points(c, font, sz, spacing)
            start = rng.normal(0, 1, (len(pts), 2)) * sz * 2.5
            delay = rng.uniform(0, 0.25, len(pts))
            self.items.append((c, tc, cx, cy, pts, start, delay, sz))

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t, 0.8, 1.5):
            return
        e = shot.e
        uv = shot.ctx.uv["glow"]
        for i, (c, tc, cx, cy, pts, start, delay, gsz) in enumerate(self.items):
            t0 = tc - 0.55
            if t < t0:
                continue
            k = np.clip((t - t0 - delay) / 0.55, 0, 1)
            k = 1 - (1 - k) ** 3
            o = remap(t, self.t_out + i * 0.03, self.t_out + 0.7 + i * 0.03)
            sx = cx + start[:, 0] if self.src is None else self.src[0] + start[:, 0] * 0.2
            sy = cy + start[:, 1] if self.src is None else self.src[1] + start[:, 1] * 0.2
            px = sx + (cx + pts[:, 0] - sx) * k + o * start[:, 0] * 0.8
            py = sy + (cy + pts[:, 1] - sy) * k - o * 120 + o * start[:, 1] * 0.5
            a = (0.35 + 0.65 * k) * (1 - o) * alpha
            n = len(pts)
            inst = np.zeros((n, 19), np.float32)
            inst[:, 0], inst[:, 1], inst[:, 2] = px, py, self.z
            sz = gsz * 0.11 * (1.6 - 0.6 * k)
            inst[:, 3] = sz
            inst[:, 4] = sz
            inst[:, 8:12] = uv
            inst[:, 12:15] = self.color
            inst[:, 15] = a * (0.6 + 0.4 * np.sin(t * 9 + np.arange(n)))
            e.sprites(shot.ctx.atlas, inst, cam=cam, screen=cam is None, blend="add")
            # solid glyph fades in once the motes have gathered
            fa = remap(t, tc + 0.05, tc + 0.35) * (1 - o) * self.fill_alpha * alpha
            if fa > 0:
                g = shot.ctx.gc.get(c, vertical=True, font=self.font, size=gsz, fill="#e8fff8", stroke=None,
                                    stroke_w=0.0, shadow=None, glow=("#3cc4b8", 0.12))
                if cam is None:
                    e.image(g, cx, cy, 0, g.w, g.w, alpha=fa, screen=True, blend="add")
                else:
                    e.image(g, cx, cy, self.z, g.w, g.w, alpha=fa, cam=cam, screen=(cam is None), blend="add")


class Carved(Carrier):
    """Gold-inlaid characters carved into a surface, revealed by a chisel wipe per character."""

    def __init__(self, L, x, y, z=0.0, size=96, col_gap=1.3, gold="#d9b45e", shade="#06060c", max_col=10, big="",
                 kana=0.8, big_scale=1.45, **kw):
        st = dict(font="old", size=size, fill=gold, stroke=None, stroke_w=0.0, shadow=None)
        super().__init__(L, style=st, **kw)
        self.shade_style = dict(st, fill=shade)
        self.size, self.z = size, z
        cols = []
        for ph in phrases(L):
            for k in range(0, len(ph), max_col):
                cols.append(ph[k:k + max_col])
        self.items = layout_columns(cols, x, y, size, col_gap, big, kana, big_scale)

    def draw(self, shot, t, cam=None, alpha=1.0, xoff=0.0):
        if not self.active(t):
            return
        e = shot.e
        for i, (c, tc, x, y, cs) in enumerate(self.items):
            p = remap(t, tc - 0.03, tc + 0.2)
            if p <= 0:
                continue
            o = remap(t, self.t_out + i * 0.03, self.t_out + 0.35 + i * 0.03)
            a = alpha * (1 - o)
            sh = shot.ctx.gc.get(c, vertical=True, **self.shade_style)
            g = self.glyph(shot, c)
            cut = (0.0, 1.0, lerp(0, 1.15, ease_out(p)), 0.1) if p < 1 else None
            d = self.size * 0.035 * cs
            e.sprites(sh, e.inst(x + xoff - d, y - d, self.z, sh.w * cs, sh.w * cs, 0, 0, 0, (0, 0, 1, 1), (1, 1, 1, a * 0.9))[None],
                      cam=cam, screen=(cam is None), cut=cut)
            e.sprites(g, e.inst(x + xoff, y, self.z, g.w * cs, g.w * cs, 0, 0, 0, (0, 0, 1, 1), (1, 1, 1, a))[None], cam=cam, screen=(cam is None), cut=cut)
            if p < 1 and p > 0:
                # chisel sparks
                sy = y - self.size / 2 + p * self.size
                e.image(shot.ctx.atlas, x + xoff, sy, self.z - 5, 40, 40, uv=shot.ctx.uv["spark"], color=(1, 0.85, 0.5),
                        alpha=a * (1 - p), cam=cam, screen=(cam is None), blend="add")


class Lanterns(Carrier):
    """Each character on its own chochin; lanterns hang on a rope and light up as the character is sung."""

    def __init__(self, L, x0, y, dx=230, z=0.0, size=None, body="#d8452e", lit_body="#f2a03a", sag=40, **kw):
        super().__init__(L, **kw)
        self.z, self.dx, self.y, self.sag = z, dx, y, sag
        chars = [(c["c"], c["t"]) for c in L["chars"] if c["c"].strip()]
        self.items = [(c, tc, x0 + i * dx) for i, (c, tc) in enumerate(chars)]
        self.body, self.lit_body = body, lit_body

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t, 0.8, 1.2):
            return
        e = shot.e
        n = len(self.items)
        for i, (c, tc, x) in enumerate(self.items):
            off = shot.A(f"lanoff|{c}", lambda c=c: el.chochin(c, 170, 240, body="#5a2228", rib="#2a0e12", lit=False,
                                                                text_col="#1a0c0e"))
            on = shot.A(f"lanon|{c}", lambda c=c: el.chochin(c, 170, 240, body=self.body, rib="#7a1d14", lit=True))
            k = (i / max(n - 1, 1)) - 0.5
            yy = self.y + self.sag * (1 - 4 * k * k)
            ent = ease_out_back(remap(t, self.t_in - 0.6 + i * 0.03, self.t_in - 0.2 + i * 0.03), 1.2)
            yy -= (1 - ent) * 500
            rot = 0.07 * math.sin(t * 2.0 + i * 0.8) + (0.15 * math.exp(-(t - tc) * 3) * math.sin((t - tc) * 14) if t > tc else 0)
            o = remap(t, self.t_out, self.t_out + 0.5)
            a = alpha * (1 - o)
            lit = remap(t, tc - 0.03, tc + 0.12)
            e.image(off, x, yy, self.z, 170, 240, rot=rot, anchor=(0.5, 0.08), alpha=a, cam=cam, screen=(cam is None))
            if lit > 0:
                e.image(on, x, yy, self.z, 170, 240, rot=rot, anchor=(0.5, 0.08), alpha=a * lit, cam=cam, screen=(cam is None))
                e.image(shot.ctx.atlas, x, yy + 100, self.z + 1, 420, 420, uv=shot.ctx.uv["glow"],
                        color=(1.0, 0.65, 0.3), alpha=0.35 * lit * a, cam=cam, screen=(cam is None), blend="add")


    def draw_rope(self, shot, cam=None, alpha=1.0, col=(0.05, 0.03, 0.04), width=3.0, extend=0.7, segs=24):
        """The rope the lanterns hang from: the same sag curve as their hang points, rising past the end lanterns."""
        if alpha <= 0:
            return
        n = len(self.items)
        x0, span = self.items[0][2], max((n - 1) * self.dx, 1.0)
        xs = np.linspace(x0 - extend * self.dx, x0 + span + extend * self.dx, segs + 1)
        k = (xs - x0) / span - 0.5
        ys = self.y + self.sag * (1 - 4 * k * k)
        for i in range(segs):
            dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
            shot.e.image(shot.e.white, (xs[i] + xs[i + 1]) / 2, (ys[i] + ys[i + 1]) / 2, self.z + 1,
                         math.hypot(dx, dy) + 1.5, width, rot=math.atan2(dy, dx), color=col, alpha=alpha, cam=cam,
                         screen=(cam is None))


class Banner(Carrier):
    """Fluttering vertical nobori banner carrying a phrase; rises into frame."""

    def __init__(self, L, x, y, z=0.0, w=150, h=640, cloth="#c8302a", ink="#f3ead6", font="boku", text=None, **kw):
        super().__init__(L, **kw)
        self.x, self.y, self.z, self.w, self.h = x, y, z, w, h
        self.text = text or "".join(c["c"] for c in L["chars"] if c["c"].strip())
        self.cloth, self.ink, self.font = cloth, ink, font

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t):
            return
        e = shot.e
        tex = shot.A(f"nobori|{self.text}|{self.cloth}", lambda: el.nobori(self.text, self.w, self.h, self.cloth, self.ink,
                                                                           font=self.font))
        k = ease_out_back(remap(t, self.t_in - 0.3, self.t_in + 0.2), 1.2)
        o = remap(t, self.t_out, self.t_out + 0.4)
        y = self.y + (1 - k) * (self.h + 300) + ease_in(o) * (self.h + 300)
        e.image(tex, self.x, y, self.z, tex.w, tex.h, alpha=alpha, cam=cam, screen=(cam is None), warp=(10, 1.4, 6.0, 0.05))


class Plaque(Carrier):
    """Black-lacquer shrine plaque (gaku) with gold frame; flips in, characters glint in."""

    def __init__(self, L, x, y, z=0.0, size=70, **kw):
        st = dict(font="old", size=size, fill="#e8c46a", stroke=None, stroke_w=0.0, shadow=None)
        super().__init__(L, style=st, **kw)
        self.x, self.y, self.z, self.size = x, y, z, size
        self.chars = [(c["c"], c["t"]) for c in L["chars"] if c["c"].strip()]
        self.h = len(self.chars) * size * 1.02 + size * 1.0
        self.w = size * 1.7

    def draw(self, shot, t, cam=None, alpha=1.0):
        if not self.active(t):
            return
        e = shot.e
        key = f"plaque|{self.w:.0f}|{self.h:.0f}"

        def mk():
            s = el._surface(self.w, self.h)
            c = s.getCanvas()
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(0, 0, self.w, self.h), 8, 8), el._paint("#120c10"))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(6, 6, self.w - 6, self.h - 6), 6, 6), el._paint("#d9b45e", 1, 4))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(14, 14, self.w - 14, self.h - 14), 4, 4), el._paint("#d9b45e", 1, 1.4))
            return el._arr(s)
        tex = shot.A(key, mk)
        k = ease_out_back(remap(t, self.t_in - 0.35, self.t_in + 0.1), 1.4)
        o = remap(t, self.t_out, self.t_out + 0.35)
        ry = (1 - k) * 1.4 + ease_in(o) * -1.4
        a = alpha * remap(t, self.t_in - 0.35, self.t_in - 0.2) * (1 - remap(o, 0.7, 1))
        e.image(tex, self.x, self.y, self.z, self.w, self.h, ry=ry, alpha=a, cam=cam, screen=(cam is None), anchor=(0.5, 0.0))
        for i, (c, tc) in enumerate(self.chars):
            ai = remap(t, tc - 0.04, tc + 0.1) * a * (1 - abs(ry) / 1.4)
            if ai <= 0:
                continue
            g = self.glyph(shot, c)
            gy = self.y + self.size * 0.5 + self.size * 0.5 + i * self.size * 1.02
            e.image(g, self.x, gy, self.z - 1, g.w, g.w, alpha=ai, cam=cam, screen=(cam is None))


class Column(Carrier):
    """Prominent vertical lyric (reference style): bold mincho, cream on a dark translucent band with gold rules;
    chars in `red` sit on vermilion squares; kana smaller, `big` kanji larger. Columns run right-to-left."""

    def __init__(self, L, x, y, size=86, col_gap=1.42, max_col=9, font="mincho", fill="#f7eedb", band=0.62,
                 big="", kana=0.8, big_scale=1.3, red="", band_col=(0.04, 0.03, 0.06), gold=(0.84, 0.68, 0.36),
                 align="top", **kw):
        st = dict(font=font, size=size, fill=fill, stroke="#0b0910", stroke_w=0.06,
                  shadow=(0.03, 0.05, 0.05, (0.0, 0.0, 0.0, 0.7)))
        super().__init__(L, style=st, **kw)
        self.red_style = dict(st, fill="#fff6e8", stroke=None, stroke_w=0.0, shadow=None)
        self.size, self.band, self.band_col, self.gold = size, band, band_col, gold
        self.red = set(red)
        cols = []
        for ph in phrases(L):
            for k in range(0, len(ph), max_col):
                cols.append(ph[k:k + max_col])
        self.items = layout_columns(cols, x, y, size, col_gap, big, kana, big_scale, align)
        self.cols = {}
        for c, tc, cx, cy, cs in self.items:
            self.cols.setdefault(round(cx), []).append((tc, cy, cs))

    def draw(self, shot, t, cam=None, alpha=1.0, dx=0.0, dy=0.0):
        if not self.active(t, 0.4, 1.0):
            return
        e = shot.e
        o_all = remap(t, self.t_out, self.t_out + 0.45)
        # bands
        if self.band > 0:
            for ci, (cx, lst) in enumerate(sorted(self.cols.items(), reverse=True)):
                t0 = lst[0][0]
                vis = [(tc, cy, cs) for tc, cy, cs in lst if t >= tc - 0.06]
                if not vis:
                    continue
                top = lst[0][1] - lst[0][2] * self.size * 0.62
                k = ease_out(remap(t, t0 - 0.12, t0 + 0.1))
                bot = vis[-1][1] + vis[-1][2] * self.size * 0.62
                bot = top + (bot - top) * k
                h = max(bot - top, 1)
                w = self.size * 1.22
                a = self.band * alpha * (1 - o_all) * k
                yc = (top + bot) / 2 + dy - ease_in(o_all) * 40
                e.image(e.white, cx + dx, yc, 0, w, h, color=self.band_col, alpha=a, screen=True)
                for sx in (-1, 1):
                    e.image(e.white, cx + dx + sx * w / 2, yc, 0, 2.0, h, color=self.gold, alpha=a * 1.3, screen=True)
        for i, (c, tc, x, y, cs) in enumerate(self.items):
            a = remap(t, tc - 0.05, tc + 0.1)
            if a <= 0:
                continue
            k = ease_out_back(remap(t, tc - 0.05, tc + 0.22), 2.2)
            sc = (1.0 + (1 - k) * 0.35) * cs
            yy = y + dy - (1 - ease_out(remap(t, tc - 0.05, tc + 0.18))) * self.size * 0.35 - ease_in(o_all) * 40
            a *= alpha * (1 - remap(t, self.t_out + i * 0.02, self.t_out + 0.35 + i * 0.02))
            if a <= 0.004:
                continue
            if c in self.red:
                s = self.size * cs * 1.02
                e.image(e.white, x + dx, yy, 0, s, s, color=(0.78, 0.16, 0.14), alpha=a, screen=True)
                g = shot.ctx.gc.get(c, vertical=True, **self.red_style)
            else:
                g = self.glyph(shot, c)
            e.image(g, x + dx, yy, 0, g.w * sc, g.w * sc, alpha=a, screen=True)
