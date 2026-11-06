"""Glyph sprites (skia raster -> GPU textures) and animated vertical / horizontal text."""
import json
import math
import os
import sys

import numpy as np
import skia

from .anim import clamp01, ease_out, ease_out_back, hexc, remap, smooth
from .paths import ROOT

# in fonts/: all free Google Fonts (SIL OFL); python fonts/fetch_fonts.py downloads them
FONT_FILES = {
    "mincho": "ShipporiMinchoB1-ExtraBold.ttf",
    "mincho_b": "ShipporiMinchoB1-Bold.ttf",
    "old": "ZenOldMincho-Black.ttf",
    "brush": "YujiSyuku-Regular.ttf",
    "boku": "YujiBoku-Regular.ttf",
    "dela": "DelaGothicOne-Regular.ttf",
    "decol": "KaiseiDecol-Bold.ttf",
    "tokumin": "KaiseiTokumin-ExtraBold.ttf",
    "rampart": "RampartOne-Regular.ttf",
    "antique": "ZenAntique-Regular.ttf",
    "hina": "HinaMincho-Regular.ttf",
    "reggae": "ReggaeOne-Regular.ttf",
    "cinzel": "Cinzel[wght].ttf",
    "antique_b1": "ShipporiAntiqueB1-Regular.ttf",
}
_TF = {}


def typeface(name):
    if name not in _TF:
        path = f"{ROOT}/fonts/{FONT_FILES[name]}"
        tf = skia.Typeface.MakeFromFile(path)
        if tf is None:          # not downloaded yet: a system font that has Japanese, so drafts still render
            sys.stderr.write(f"[mm] {path} missing (python fonts/fetch_fonts.py): using a system font\n")
            mgr = skia.FontMgr()
            tf = (mgr.matchFamilyStyleCharacter("", skia.FontStyle(), ["ja"], ord("あ"))
                  or mgr.legacyMakeTypeface("", skia.FontStyle()))
        _TF[name] = tf
    return _TF[name]


SMALL_KANA = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")
ROTATE_V = set("ー～〜…‥—―-")
PUNCT_V = set("、。，．")
FULLWIDTH = {"!": "！", "?": "？", " ": " "}


def _color(c):
    if isinstance(c, str):
        c = hexc(c)
    r, g, b = c[:3]
    a = c[3] if len(c) > 3 else 1.0
    return skia.Color4f(r, g, b, a)


def glyph_rgba(ch, font="mincho", size=72, fill="#f3e9d2", stroke=None, stroke_w=0.0, shadow=None,
               vertical=True, pad=0.35, glow=None):
    """Rasterise one character centred in an em cell. Returns (rgba uint8, cell_px).

    stroke_w and shadow offsets are fractions of the em size. shadow = (dx, dy, blur, color)."""
    ch = FULLWIDTH.get(ch, ch)
    cell = int(math.ceil(size * (1 + 2 * pad)))
    info = skia.ImageInfo.Make(cell, cell, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    surf = skia.Surface.MakeRaster(info)
    c = surf.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    f = skia.Font(typeface(font), size)
    f.setSubpixel(True)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    glyphs = f.textToGlyphs(ch)
    adv = sum(f.getWidths(glyphs)) if len(glyphs) else size
    # em box centred in the cell; baseline at 0.88 em (CJK ideographic box)
    ox = (cell - adv) / 2.0
    by = (cell - size) / 2.0 + size * 0.88
    dx = dy = 0.0
    rot = 0.0
    if vertical:
        if ch in SMALL_KANA:
            dx, dy = size * 0.1, -size * 0.1
        elif ch in PUNCT_V:
            dx, dy = size * 0.58, -size * 0.58
        elif ch in ROTATE_V:
            rot = 90.0
    c.save()
    if rot:
        c.translate(cell / 2, cell / 2)
        c.rotate(rot)
        c.translate(-cell / 2, -cell / 2)
    c.translate(dx, dy)
    path = skia.Path()
    x = ox
    for g, wdt in zip(glyphs, f.getWidths(glyphs)):
        gp = f.getPath(g)
        if gp is not None:
            gp.offset(x, by)
            path.addPath(gp)
        x += wdt
    if glow is not None:
        gcol, gblur = glow
        p = skia.Paint(AntiAlias=True, Color4f=_color(gcol))
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, gblur * size))
        c.drawPath(path, p)
    if shadow is not None:
        sdx, sdy, sblur, scol = shadow
        p = skia.Paint(AntiAlias=True, Color4f=_color(scol))
        if sblur > 0:
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sblur * size))
        c.save()
        c.translate(sdx * size, sdy * size)
        c.drawPath(path, p)
        if stroke and stroke_w > 0:
            ps = skia.Paint(AntiAlias=True, Color4f=_color(scol), Style=skia.Paint.kStroke_Style,
                            StrokeWidth=stroke_w * size * 2, StrokeJoin=skia.Paint.kRound_Join)
            if sblur > 0:
                ps.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sblur * size))
            c.drawPath(path, ps)
        c.restore()
    if stroke and stroke_w > 0:
        ps = skia.Paint(AntiAlias=True, Color4f=_color(stroke), Style=skia.Paint.kStroke_Style,
                        StrokeWidth=stroke_w * size * 2, StrokeJoin=skia.Paint.kRound_Join)
        c.drawPath(path, ps)
    pf = skia.Paint(AntiAlias=True, Color4f=_color(fill))
    c.drawPath(path, pf)
    c.restore()
    arr = surf.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    return arr, cell


def text_rgba(text, font="mincho", size=72, fill="#f3e9d2", stroke=None, stroke_w=0.0, shadow=None,
              glow=None, tracking=0.0, pad=0.3):
    """Horizontal string rasterised as one image."""
    f = skia.Font(typeface(font), size)
    f.setSubpixel(True)
    glyphs = f.textToGlyphs(text)
    widths = f.getWidths(glyphs)
    total = sum(widths) + tracking * size * max(len(glyphs) - 1, 0)
    w = int(math.ceil(total + 2 * pad * size))
    h = int(math.ceil(size * (1 + 2 * pad)))
    info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    surf = skia.Surface.MakeRaster(info)
    c = surf.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    path = skia.Path()
    x = pad * size
    by = (h - size) / 2 + size * 0.88
    for g, wd in zip(glyphs, widths):
        gp = f.getPath(g)
        if gp is not None:
            gp.offset(x, by)
            path.addPath(gp)
        x += wd + tracking * size
    if glow is not None:
        p = skia.Paint(AntiAlias=True, Color4f=_color(glow[0]))
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, glow[1] * size))
        c.drawPath(path, p)
    if shadow is not None:
        sdx, sdy, sblur, scol = shadow
        p = skia.Paint(AntiAlias=True, Color4f=_color(scol))
        if sblur > 0:
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sblur * size))
        c.save(); c.translate(sdx * size, sdy * size); c.drawPath(path, p); c.restore()
    if stroke and stroke_w > 0:
        c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=_color(stroke), Style=skia.Paint.kStroke_Style,
                                    StrokeWidth=stroke_w * size * 2, StrokeJoin=skia.Paint.kRound_Join))
    c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=_color(fill)))
    return surf.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)


class GlyphCache:
    def __init__(self, engine):
        self.e = engine

    def get(self, ch, **style):
        key = "g|" + ch + "|" + json.dumps(style, sort_keys=True, default=str)
        if key in self.e.cache:
            return self.e.cache[key]
        arr, cell = glyph_rgba(ch, **style)
        return self.e.texture_from_array(arr, key=key, mip=True)


LYRIC_STYLE = dict(font="mincho", size=66, fill="#f4ead3", stroke="#120d14", stroke_w=0.07,
                   shadow=(0.04, 0.06, 0.06, (0.03, 0.02, 0.05, 0.75)))


def lyric_lines():
    """The timed lyric lines (work/lyrics_timed_v2.json, from work/syll_mms.py); none until the lyrics are timed."""
    path = f"{ROOT}/work/lyrics_timed_v2.json"
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding="utf-8"))


class VLine:
    """A lyric line laid out vertically (columns right-to-left), revealed char by char on its timing."""

    def __init__(self, line, x=1760, y=110, size=66, max_col=11, col_gap=1.3, style=None, accent=None,
                 accent_style=None, t_out=None, hold=0.35, split_spaces=True, align="top", out_mode="rise"):
        self.line = line
        self.size = size
        self.style = dict(LYRIC_STYLE, size=size)
        if style:
            self.style.update(style)
        self.accent = set(accent or "")
        self.accent_style = dict(self.style, fill="#e0452e")
        if accent_style:
            self.accent_style.update(accent_style)
        self.t_in = line["chars"][0]["t"] if line["chars"] else line["t"]
        self.t_out = t_out if t_out is not None else min(line["end"], max(line["sung_end"], self.t_in) + hold + 0.6)
        self.out_mode = out_mode
        # layout
        cols, cur = [], []
        for ch in line["chars"]:
            c = ch["c"]
            if c in (" ", "　"):
                if split_spaces and cur:
                    cols.append(cur); cur = []
                continue
            cur.append(ch)
            if len(cur) >= max_col:
                cols.append(cur); cur = []
        if cur:
            cols.append(cur)
        self.items = []
        for ci, col in enumerate(cols):
            cx = x - ci * size * col_gap
            n = len(col)
            y0 = y if align == "top" else y - n * size / 2 if align == "center" else y - n * size
            for k, ch in enumerate(col):
                self.items.append((ch["c"], ch["t"], cx, y0 + k * size + size / 2))

    def draw(self, e, gc, t, alpha=1.0):
        if t < self.t_in - 0.3 or t > self.t_out + 0.8:
            return
        insts = {}
        n = len(self.items)
        for i, (c, tc, cx, cy) in enumerate(self.items):
            a_in = remap(t, tc - 0.06, tc + 0.16)
            if a_in <= 0:
                continue
            k = ease_out_back(remap(t, tc - 0.06, tc + 0.22), 2.2)
            sc = 1.0 + (1 - k) * 0.35
            dy = (1 - ease_out(remap(t, tc - 0.06, tc + 0.2))) * -self.size * 0.35
            # exit: staggered rise + fade
            o = remap(t, self.t_out + i * 0.025, self.t_out + 0.35 + i * 0.025)
            if self.out_mode == "rise":
                dy -= ease_out(o) * self.size * 0.5
            a = a_in * (1 - o) * alpha
            if a <= 0.003:
                continue
            st = self.accent_style if c in self.accent else self.style
            tex = gc.get(c, vertical=True, **st)
            s = tex.w * sc
            key = id(tex)
            insts.setdefault(key, (tex, []))[1].append(e.inst(cx, cy + dy, 0, s, s, 0, 0, 0, (0, 0, 1, 1), (1, 1, 1, a)))
        for tex, lst in insts.values():
            e.sprites(tex, np.stack(lst), screen=True)


class HLine:
    """Horizontal lyric (centred at x,y)."""

    def __init__(self, line, x=960, y=960, size=58, style=None, t_out=None, hold=0.35, tracking=0.08,
                 accent=None, accent_style=None):
        self.line = line
        self.size = size
        self.style = dict(LYRIC_STYLE, size=size)
        if style:
            self.style.update(style)
        self.accent = set(accent or "")
        self.accent_style = dict(self.style, fill="#e0452e")
        if accent_style:
            self.accent_style.update(accent_style)
        chars = [c for c in line["chars"]]
        self.t_in = chars[0]["t"] if chars else line["t"]
        self.t_out = t_out if t_out is not None else min(line["end"], max(line["sung_end"], self.t_in) + hold + 0.6)
        adv = []
        for ch in chars:
            c = ch["c"]
            if c in (" ", "　"):
                adv.append(size * 0.5)
            elif len(c) > 1:
                adv.append(size * 1.1 * len(c) * 0.6)
            else:
                adv.append(size * (1 + tracking))
        total = sum(adv)
        xx = x - total / 2
        self.items = []
        for ch, a in zip(chars, adv):
            if ch["c"].strip():
                self.items.append((ch["c"], ch["t"], xx + a / 2, y))
            xx += a

    def draw(self, e, gc, t, alpha=1.0):
        if t < self.t_in - 0.3 or t > self.t_out + 0.8:
            return
        for i, (c, tc, cx, cy) in enumerate(self.items):
            a_in = remap(t, tc - 0.05, tc + 0.15)
            if a_in <= 0:
                continue
            k = ease_out_back(remap(t, tc - 0.05, tc + 0.22), 2.0)
            sc = 1.0 + (1 - k) * 0.4
            dy = (1 - ease_out(remap(t, tc - 0.05, tc + 0.2))) * self.size * 0.3
            o = remap(t, self.t_out + i * 0.02, self.t_out + 0.3 + i * 0.02)
            a = a_in * (1 - o) * alpha
            if a <= 0.003:
                continue
            st = self.accent_style if c in self.accent else self.style
            if len(c) > 1:
                key = "h|" + c + json.dumps(st, sort_keys=True, default=str)
                if key not in e.cache:
                    arr = text_rgba(c, **{k: v for k, v in st.items()})
                    e.texture_from_array(arr, key=key)
                tex = e.cache[key]
            else:
                tex = gc.get(c, vertical=False, **st)
            e.image(tex, cx, cy - dy - ease_out(o) * self.size * 0.3, 0, scale=sc, alpha=a, screen=True)
