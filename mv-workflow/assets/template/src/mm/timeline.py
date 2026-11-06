"""Shot base class, transitions, the global lyric track and frame rendering."""
import math

import numpy as np

from .anim import clamp01, lerp, remap
from .engine import FOCAL, Cam
from .fx import Field, make_atlas
from .text import GlyphCache, HLine, VLine, lyric_lines
from .transfx import OVERLAYS

TRANS = {"cut": -1, "fade": 0, "wipe": 1, "iris": 2, "ink": 3, "push": 4, "shoji": 5, "flash": 6, "zoom": 7, "strips": 8,
         "cloud": 0, "slips": 0, "leaves": 0, "goldcloud": 0, "rockpass": 0, "passer": 0, "firewall": 0}
OVERLAY_MODES = ("cloud", "slips", "leaves", "goldcloud", "rockpass", "passer", "firewall")


class Ctx:
    """Per-process shared resources."""

    def __init__(self, e):
        self.e = e
        self.gc = GlyphCache(e)
        arr, self.uv = make_atlas()
        self.atlas = e.texture_from_array(arr, key="__atlas")


class Shot:
    name = "shot"
    grade = None          # dict for Engine.post
    trans = ("cut", 0.0)  # transition INTO this shot: (mode, duration, q, col)
    clear = (0, 0, 0, 1)

    def __init__(self, t0, t1, **kw):
        self.t0, self.t1 = t0, t1
        self.kw = kw
        self.ready = False
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def dur(self):
        return self.t1 - self.t0

    def u(self, t):
        return clamp01((t - self.t0) / self.dur)

    def lt(self, t):
        return t - self.t0

    def ensure(self, ctx):
        if not self.ready:
            self.ctx = ctx
            self.e = ctx.e
            self.setup()
            self.ready = True

    def T(self, path):
        return self.e.tex(path)

    def A(self, key, fn):
        if key not in self.e.cache:
            self.e.texture_from_array(fn(), key=key)
        return self.e.cache[key]

    def setup(self):
        pass

    def draw(self, t):
        pass

    def grade_at(self, t):
        return self.grade or {}

    # convenience
    def leaves(self, field, t, cam=None, alpha=1.0, blend="normal", screen=False):
        self.e.sprites(self.ctx.atlas, field.instances(t, self.ctx.uv, alpha=alpha), cam=cam, blend=blend, screen=screen)


def mix_grades(a, b, k):
    out = dict(a)
    for key, vb in b.items():
        va = a.get(key, vb)
        if isinstance(vb, (tuple, list)):
            out[key] = tuple(lerp(x, y, k) for x, y in zip(va, vb))
        else:
            out[key] = lerp(va, vb, k)
    for key, va in a.items():
        if key not in b:
            out[key] = va
    return out


class LyricTrack:
    """Global lyric layer drawn above the shot composite. styles: {line_index: dict(mode, ...)}"""

    def __init__(self, styles, default=None):
        self.lines = lyric_lines()
        self.default = default or dict(mode="v")
        self.styles = styles
        self.items = []
        for i, L in enumerate(self.lines):
            st = dict(self.default)
            st.update(styles.get(i, {}))
            mode = st.pop("mode", "v")
            if mode == "none":
                continue
            if mode == "v":
                self.items.append(VLine(L, **st))
            else:
                self.items.append(HLine(L, **st))

    def draw(self, ctx, t):
        for it in self.items:
            it.draw(ctx.e, ctx.gc, t)


class Timeline:
    def __init__(self, shots, lyrics=None, overlay=None):
        self.shots = sorted(shots, key=lambda s: s.t0)
        for a, b in zip(self.shots, self.shots[1:]):
            if abs(a.t1 - b.t0) > 1e-6:
                raise ValueError(f"gap/overlap between {a.name} ({a.t1}) and {b.name} ({b.t0})")
        self.lyrics = lyrics
        self.overlay = overlay
        self.ctx = None

    def index_at(self, t):
        for i, s in enumerate(self.shots):
            if s.t0 <= t < s.t1:
                return i
        return len(self.shots) - 1

    def render(self, e, t):
        if self.ctx is None:
            self.ctx = Ctx(e)
        ctx = self.ctx
        e.time = t
        i = self.index_at(t)
        cur = self.shots[i]
        pair = None
        # transition into current shot (centred on the cut)
        mode, d = cur.trans[0], cur.trans[1]
        if mode != "cut" and d > 0 and i > 0 and t < cur.t0 + d / 2:
            pair = (self.shots[i - 1], cur, (t - (cur.t0 - d / 2)) / d, cur.trans)
        elif i + 1 < len(self.shots):
            nxt = self.shots[i + 1]
            m2, d2 = nxt.trans[0], nxt.trans[1]
            if m2 != "cut" and d2 > 0 and t >= nxt.t0 - d2 / 2:
                pair = (cur, nxt, (t - (nxt.t0 - d2 / 2)) / d2, nxt.trans)
        if pair is None:
            cur.ensure(ctx)
            shutter, n = getattr(cur, "SHUTTER", 0.0), getattr(cur, "MB_N", 1)
            if shutter > 0 and n > 1:                    # (v28: motion blur - the shot drawn at sub-frame times
                for k in range(n):                       #  across the shutter and averaged; its plates come
                    e.cam = Cam()                        #  blurred already, the same frame for every sub-frame)
                    e.begin(e.fbo_shot[0], clear=cur.clear)
                    cur.draw(t + (k / (n - 1) - 0.5) * shutter / 30.0)
                    e.accumulate(e.fbo_shot[0], e.fbo_acc, 1.0 / n, clear=k == 0)
                e.accumulate(e.fbo_acc, e.fbo_shot[0], 1.0, blend=False)
            else:
                e.cam = Cam()
                e.begin(e.fbo_shot[0], clear=cur.clear)
                cur.draw(t)
            src = e.fbo_shot[0]
            grade = cur.grade_at(t)
        else:
            a, b, p, tr = pair
            p = clamp01(p)
            for k, sh in enumerate((a, b)):
                sh.ensure(ctx)
                e.cam = Cam()
                e.begin(e.fbo_shot[k], clear=sh.clear)
                sh.draw(t)
            q = tr[2] if len(tr) > 2 else (0, 0, 0, 0)
            if tr[0] in ("push", "wipe") and abs(q[0]) + abs(q[1]) < 1e-6:
                q = (-1.0, 0.0, q[2], q[3])          # a push/wipe given no direction: normalize(0,0) drew black frames
            if tr[0] == "wipe" and q[2] <= 0:
                q = (q[0], q[1], 40.0, q[3])         # and a wipe needs a soft edge (smoothstep(0, 0, x) is undefined)
            col = tr[3] if len(tr) > 3 else (1, 1, 1, 1)
            if tr[0] in OVERLAY_MODES:
                pc = min(1.0, max(0.0, (p - 0.44) / 0.12))
                src = e.transition(0, pc, q, col)
                e.begin(src, clear=None)
                e.cam = Cam()
                OVERLAYS[tr[0]](e, ctx, p)
                grade = mix_grades(a.grade_at(t), b.grade_at(t), pc)
            else:
                src = e.transition(TRANS[tr[0]], p, q, col)
                grade = mix_grades(a.grade_at(t), b.grade_at(t), p)
        # global layers on top of the composite
        e.begin(src, clear=None)
        e.cam = Cam()
        if self.lyrics:
            self.lyrics.draw(ctx, t)
        if self.overlay:
            self.overlay(ctx, t)
        return e.post(src, grade, t)
