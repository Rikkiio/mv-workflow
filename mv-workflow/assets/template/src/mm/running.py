"""Running lyric line in the reference style: a quiet vertical column at a fixed home, revealed character by
character on the vocal and carried across cuts. When the next line starts the previous one steps left and dims;
the one before that fades. Long lines break at a phrase boundary into two columns. No backing band."""
import numpy as np

from .anim import clamp01, ease_out, ease_out_back, lerp, remap, smooth
from .text import LYRIC_STYLE, lyric_lines

KANA_SCALE = 0.86
SPACE = 0.38


def _is_kana(c):
    return 0x3040 <= ord(c[0]) <= 0x30ff


class RunningLines:
    def __init__(self, t0, t1, x=1808, y=86, size=60, col_gap=1.5, max_chars=10, accent=(), style=None,
                 accent_style=None, dim=0.3, hold=1.4):
        self.size = size
        self.x, self.y = x, y
        self.colw = size * col_gap
        self.style = dict(LYRIC_STYLE, size=size, stroke_w=0.06)
        if style:
            self.style.update(style)
        self.accent_style = dict(self.style, fill="#f07a4f")
        if accent_style:
            self.accent_style.update(accent_style)
        self.dim = dim
        self.hold = hold
        self.lines = []
        for L in lyric_lines():
            chars = L["chars"]
            if not chars or L["text"].lower().startswith("la"):
                continue
            t_in = chars[0]["t"]
            if t_in > t1 or L["end"] < t0:
                continue
            cols = self._layout(chars, max_chars, accent)
            self.lines.append(dict(t_in=t_in, end=L["end"], sung_end=L.get("sung_end", L["end"]), cols=cols))
        for i, ln in enumerate(self.lines):
            ln["t_next"] = self.lines[i + 1]["t_in"] if i + 1 < len(self.lines) else 1e9

    def _layout(self, chars, max_chars, accent):
        seq = [(ch["c"], ch["t"]) for ch in chars]
        text = "".join(c for c, _ in seq)
        hot = set()
        for w in accent:
            k = text.find(w)
            while k >= 0:
                hot.update(range(k, k + len(w)))
                k = text.find(w, k + 1)
        phrases, cur = [], []
        for i, (c, tc) in enumerate(seq):
            if c in (" ", "　"):
                if cur:
                    phrases.append(cur)
                    cur = []
            else:
                cur.append((c, tc, i in hot))
        if cur:
            phrases.append(cur)
        n = sum(len(p) for p in phrases)
        if n <= max_chars or len(phrases) == 1:
            groups = [phrases]
        else:
            best = None
            for k in range(1, len(phrases)):
                d = abs(sum(len(p) for p in phrases[:k]) - n / 2)
                if best is None or d < best[0]:
                    best = (d, k)
            groups = [phrases[:best[1]], phrases[best[1]:]]
        cols = []
        for g in groups:
            items, yy = [], 0.0
            for pi, ph in enumerate(g):
                if pi:
                    yy += SPACE * self.size
                for c, tc, h in ph:
                    sc = KANA_SCALE if _is_kana(c) else 1.0
                    items.append((c, tc, yy + sc * self.size / 2, sc, h))
                    yy += sc * self.size
            cols.append(items)
        return cols

    def draw(self, e, gc, t, alpha=1.0):
        insts = {}
        for i, ln in enumerate(self.lines):
            if t < ln["t_in"] - 0.2:
                continue
            shift = rank = 0.0
            for j in range(i + 1, min(i + 3, len(self.lines))):
                k = smooth(remap(t, self.lines[j]["t_in"] - 0.08, self.lines[j]["t_in"] + 0.3))
                shift += k * (len(self.lines[j]["cols"]) * self.colw + self.colw * 0.2)
                rank += k
            if rank >= 2.0:
                continue
            a_line = lerp(1.0, self.dim, min(rank, 1.0)) * (1 - clamp01((rank - 1.0) / 0.5))
            if ln["t_next"] - ln["sung_end"] > self.hold + 0.6:
                tf = ln["sung_end"] + self.hold
                a_line *= 1 - smooth(remap(t, tf, tf + 0.5))
            a_line *= alpha
            if a_line <= 0.003:
                continue
            x0 = self.x - shift
            for ci, col in enumerate(ln["cols"]):
                cx = x0 - ci * self.colw
                for c, tc, cy, sc, hot in col:
                    a_in = remap(t, tc - 0.05, tc + 0.12)
                    if a_in <= 0:
                        continue
                    pop = ease_out_back(remap(t, tc - 0.05, tc + 0.2), 2.0)
                    s = sc * (1.0 + (1 - pop) * 0.3)
                    dy = (1 - ease_out(remap(t, tc - 0.05, tc + 0.18))) * -self.size * 0.3
                    tex = gc.get(c, vertical=True, **(self.accent_style if hot else self.style))
                    w = tex.w * s
                    insts.setdefault(id(tex), (tex, []))[1].append(
                        e.inst(cx, self.y + cy + dy, 0, w, w, 0, 0, 0, (0, 0, 1, 1), (1, 1, 1, a_in * a_line)))
        for tex, lst in insts.values():
            e.sprites(tex, np.stack(lst), screen=True)
