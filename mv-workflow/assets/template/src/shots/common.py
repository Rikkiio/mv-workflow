"""Shared helpers for shot definitions."""
import math
import os

import numpy as np

from mm import elements as el
from mm.anim import (B, bar, beat_of, clamp01, ease_in, ease_io, ease_out, ease_out_back, ease_out_expo, hexc,
                     kick, lerp, remap, shake, smooth, wobble)
from mm.engine import FOCAL, Cam
from mm.fx import Field
from mm.text import text_rgba
from mm.paths import ROOT
from mm.timeline import Shot, mix_grades

W, H = 1920, 1080

# ---------------------------------------------------------------- palette
INK = hexc("#0e0b14")
INDIGO = hexc("#151a32")
NAVY = hexc("#22305a")
GOLD = hexc("#d6ae5c")
CREAM = hexc("#f2e7cf")
VERM = hexc("#d8452e")
CRIMSON = hexc("#9c2330")
ORANGE = hexc("#ef8f3b")
TEAL = hexc("#3cc4b8")
TEAL_D = hexc("#1f8f8a")
BLONDE = hexc("#f6d860")
GREEN = hexc("#76c454")
ROSE = hexc("#e0796a")
PEACH = hexc("#f6b46a")
PLUM = hexc("#33213f")
SKY = hexc("#8fb5cf")
WHITE = (1, 1, 1, 1)

# ---------------------------------------------------------------- grades
G_NIGHT = dict(bloom=0.30, thr=0.70, gain=(0.95, 0.97, 1.05), sat=0.95, grain=0.04, vig=0.45, paper=0.55)
G_CAVE = dict(bloom=0.45, thr=0.55, gain=(0.9, 0.95, 1.05), lift=(0.01, 0.012, 0.02), sat=0.9, grain=0.045, vig=0.6, paper=0.5)
G_WARM = dict(bloom=0.40, thr=0.65, gain=(1.05, 0.98, 0.92), sat=1.0, grain=0.04, vig=0.4, paper=0.55)
G_FEST = dict(bloom=0.55, thr=0.62, gain=(1.05, 1.0, 0.95), sat=1.08, grain=0.035, vig=0.3, paper=0.5)
G_GLOOM = dict(bloom=0.35, thr=0.6, gain=(0.97, 0.9, 1.05), lift=(0.012, 0.0, 0.02), sat=0.85, grain=0.05, vig=0.6, paper=0.55)
G_DAWN = dict(bloom=0.32, thr=0.78, gain=(1.0, 0.96, 0.92), sat=1.05, grain=0.03, vig=0.3, paper=0.5)
G_DAY = dict(bloom=0.35, thr=0.75, gain=(1.02, 1.0, 0.98), sat=1.05, grain=0.03, vig=0.2, paper=0.5)
G_PAPER = dict(bloom=0.15, thr=0.9, grain=0.03, vig=0.25, paper=0.85)

LEAF_COLS = [VERM, ORANGE, hexc("#e9b94c"), CRIMSON, hexc("#c84a2a")]
GOLD_COLS = [hexc("#e9b94c"), hexc("#f2cf6a"), hexc("#d89a3a")]


def leaves_field(seed=1, n=140, vel=(-50, 95), size=(30, 64), box=(-1700, 1700, -1100, 1100, -500, 900), cols=None,
                 kinds=("momiji1", "momiji2", "momiji3", "ginkgo"), alpha=(0.85, 1.0)):
    return Field(n, seed, list(kinds), cols or LEAF_COLS, box=box, vel=vel, size=size, alpha=alpha)


def dust_field(seed=2, n=120, col=None, vel=(6, -10), size=(3, 9), box=(-1300, 1300, -800, 800, -300, 600)):
    return Field(n, seed, ["dot"], [col or (1, 0.95, 0.85, 0.6)], box=box, vel=vel, size=size, spin=(0, 0),
                 sway=(20, 0.15), flutter=0.0, alpha=(0.2, 0.8), twinkle=0.6)


def ember_field(seed=3, n=90, col=None, vel=(10, -70), size=(8, 22), box=(-1300, 1300, -800, 800, -300, 600)):
    return Field(n, seed, ["ember"], [col or (1.0, 0.7, 0.35, 1.0)], box=box, vel=vel, size=size, spin=(0, 0),
                 sway=(40, 0.3), flutter=0.0, alpha=(0.4, 1.0), twinkle=0.5)


def confetti_field(seed=4, n=160, vel=(-30, 160), size=(14, 30), box=(-1500, 1500, -1000, 1000, -400, 800), cols=None):
    return Field(n, seed, ["confetti", "confetti2"], cols or [VERM, GOLD, CREAM, TEAL, ORANGE, CRIMSON], box=box,
                 vel=vel, size=size, spin=(-6, 6), sway=(40, 0.6), flutter=2.0)


def firefly_field(seed=5, n=60, col=None, box=(-1300, 1300, -800, 800, -300, 600)):
    return Field(n, seed, ["glow"], [col or (0.6, 1.0, 0.9, 1.0)], box=box, vel=(4, -6), size=(14, 36), spin=(0, 0),
                 sway=(60, 0.12), flutter=0.0, alpha=(0.3, 0.9), twinkle=0.8)


# ---------------------------------------------------------------- camera helpers
def cam_dolly(z_plane, zoom, x=0.0, y=0.0, roll=0.0):
    """Camera that shows the plane at z_plane at `zoom` times the default (z=0 at 1:1) scale."""
    base = z_plane + FOCAL  # distance at default camera
    return Cam(x=x, y=y, z=z_plane - base / zoom, roll=roll)


def keyed(t, keys, ease=ease_io):
    """keys: list of (time, value or tuple). Piecewise eased interpolation."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            k = ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, k) for a, b in zip(v0, v1))
            return lerp(v0, v1, k)
    return keys[-1][1]


# ---------------------------------------------------------------- drawing helpers
def plate_tex(shot, name):
    return shot.T(f"{ROOT}/assets/plates/{name}.png")


def resolve(name):
    """Prefer the vector art, then the completed (un-cropped) redraw, then the original. "name@pr" asks for the
    screen-print treatment (src/print_style.py) instead: an accent for graphic shots, not the default look."""
    if name.endswith("@pr"):
        pr = f"{name[:-3]}_vec_pr"
        if os.path.exists(f"{ROOT}/assets/cast/{pr}.png") and os.path.exists(f"{ROOT}/assets/cast/{pr}_hair.png"):
            return pr
        name = name[:-3]
    vec = f"{name}_vec"
    if os.path.exists(f"{ROOT}/assets/cast/{vec}.png") and os.path.exists(f"{ROOT}/assets/cast/{vec}_hair.png"):
        return vec
    full = f"{name}_full"
    if os.path.exists(f"{ROOT}/assets/cast/{full}.png") and os.path.exists(f"{ROOT}/assets/cast/{full}_hair.png"):
        return full
    return name


def cast_tex(shot, name):
    return shot.T(f"{ROOT}/assets/cast/{resolve(name)}.png")


def hair_tex(shot, name):
    return shot.T(f"{ROOT}/assets/cast/{resolve(name)}_hair.png")


def prop_tex(shot, name):
    return shot.T(f"{ROOT}/assets/props/{name}.png")


def exists_cast(name):
    return os.path.exists(f"{ROOT}/assets/cast/{name}.png")


def silhouette(shot, name, x, y, z, h, col=INK, hair_col=None, rim=None, alpha=1.0, cam=None, screen=False,
               flip=False, rot=0.0, warp=None, warp2=None, anchor=(0.5, 1.0)):
    """Solid silhouette with optional hair colour accent and rim light. Anchored at feet by default."""
    e = shot.e
    tex = cast_tex(shot, name)
    w = h * tex.aspect
    uv = (1, 0, 0, 1) if flip else (0, 0, 1, 1)
    mode = 2 if rim else 1
    kw = dict(cam=cam, screen=screen, warp=warp, warp2=warp2)
    e.image(tex, x, y, z, w, h, rot=rot, uv=uv, color=col[:3], alpha=alpha * col[3], anchor=anchor, mode=mode,
            rim=rim, rim_off=(0.003 * (-1 if flip else 1), 0.003), **kw)
    if hair_col is not None:
        ht = hair_tex(shot, name)
        e.image(ht, x, y, z, w, h, rot=rot, uv=uv, color=hair_col[:3], alpha=alpha * hair_col[3], anchor=anchor,
                mode=3, **kw)


def character(shot, name, x, y, z, h, alpha=1.0, color=(1, 1, 1), add=(0, 0, 0), cam=None, screen=False, flip=False,
              rot=0.0, warp=None, warp2=None, anchor=(0.5, 0.5), blend="normal", mask=0, feather=0):
    e = shot.e
    tex = feathered(shot, name, feather) if feather else cast_tex(shot, name)
    w = h * tex.aspect
    uv = (1, 0, 0, 1) if flip else (0, 0, 1, 1)
    e.image(tex, x, y, z, w, h, rot=rot, uv=uv, color=color, add=add, alpha=alpha, anchor=anchor, cam=cam,
            screen=screen, warp=warp, warp2=warp2, blend=blend, mask=mask)


def stamp(shot, key, fn, x, y, size, t, t_hit, rot=-0.08, alpha=1.0, dur_out=None, t_out=None):
    """Seal stamp slam: scale 1.8 -> 1 with overshoot, slight rotation; returns impact amount for shake."""
    if t < t_hit - 0.05:
        return 0.0
    tex = shot.A(key, fn)
    k = remap(t, t_hit - 0.05, t_hit + 0.12)
    s = lerp(1.9, 1.0, ease_out_expo(k))
    a = alpha * remap(t, t_hit - 0.05, t_hit + 0.02)
    if t_out is not None:
        a *= 1 - remap(t, t_out, t_out + (dur_out or 0.3))
    shot.e.image(tex, x, y, 0, size * s, size * s, rot=rot * (1 - 0.3 * k), alpha=a, screen=True)
    return math.exp(-max(0.0, t - t_hit) / 0.12) if t >= t_hit else 0.0


def big_text(shot, text, x, y, size, t, t_in, t_out=None, font="boku", fill="#f2e7cf", stroke="#0e0b14", stroke_w=0.05,
             mode="pop", rot=0.0, alpha=1.0, shadow=(0.03, 0.04, 0.03, (0, 0, 0, 0.6)), tracking=0.0, glow=None,
             dur_in=0.25, dur_out=0.3, blend="normal"):
    """Horizontal display text with pop/slide/zoom entrance."""
    if t < t_in - 0.02 or (t_out is not None and t > t_out + dur_out):
        return
    key = f"bt|{text}|{font}|{size}|{fill}|{stroke}|{stroke_w}|{shadow}|{tracking}|{glow}"
    tex = shot.A(key, lambda: text_rgba(text, font=font, size=size, fill=fill, stroke=stroke, stroke_w=stroke_w,
                                        shadow=shadow, tracking=tracking, glow=glow))
    k = remap(t, t_in, t_in + dur_in)
    a = alpha * remap(t, t_in - 0.02, t_in + dur_in * 0.5)
    if t_out is not None:
        a *= 1 - remap(t, t_out, t_out + dur_out)
    sc, dx, dy = 1.0, 0.0, 0.0
    if mode == "pop":
        sc = lerp(1.6, 1.0, ease_out_back(k, 2.0))
    elif mode == "zoom":
        sc = lerp(0.6, 1.0, ease_out_expo(k))
    elif mode == "slide":
        dx = (1 - ease_out_expo(k)) * 160
    elif mode == "drop":
        dy = -(1 - ease_out_back(k, 1.6)) * 120
    shot.e.image(tex, x + dx, y + dy, 0, scale=sc, rot=rot, alpha=a, screen=True, blend=blend)


def vchars(shot, text, x, y, size, t, times, font="mincho", fill="#f2e7cf", stroke="#0e0b14", stroke_w=0.06,
           shadow=(0.04, 0.05, 0.05, (0, 0, 0, 0.7)), t_out=None, gap=1.0, alpha=1.0, mode="drop", glow=None):
    """Vertical characters revealed at given times (list or single time + stagger)."""
    if isinstance(times, (int, float)):
        times = [times + i * 0.08 for i in range(len(text))]
    for i, (ch, tc) in enumerate(zip(text, times)):
        if t < tc - 0.05:
            continue
        tex = shot.ctx.gc.get(ch, font=font, size=size, fill=fill, stroke=stroke, stroke_w=stroke_w, shadow=shadow,
                              vertical=True, glow=glow)
        k = remap(t, tc - 0.05, tc + 0.2)
        a = alpha * remap(t, tc - 0.05, tc + 0.08)
        if t_out is not None:
            a *= 1 - remap(t, t_out + i * 0.03, t_out + 0.3 + i * 0.03)
        sc = lerp(1.5, 1.0, ease_out_back(k, 2.2)) if mode == "pop" else 1.0
        dy = -(1 - ease_out(k)) * size * 0.4 if mode == "drop" else 0
        shot.e.image(tex, x, y + i * size * gap + dy, 0, scale=sc, alpha=a, screen=True)


def flash_amt(t, t_hit, dur=0.35, peak=1.0):
    if t < t_hit:
        return 0.0
    return peak * math.exp(-(t - t_hit) / (dur / 3))


def with_flash(grade, t, hits, col=(1, 1, 1), dur=0.35, peak=0.9):
    a = max([flash_amt(t, h, dur, peak) for h in hits] + [0.0])
    g = dict(grade)
    g["flash"] = (*col, min(1.0, a))
    return g


def vignette_dark(e, alpha=0.6):
    e.gradient((W / 2, H / 2), (W / 2 + 1100, H / 2), (0, 0, 0, 0), (0, 0, 0, 0), (0.02, 0.01, 0.04, alpha),
               pos=(0.0, 0.55, 1.0), radial=True)


def beam(e, x0, y0, x1, y1, w0, w1, col, alpha):
    """Soft light beam as a quad strip (screen space) using a radial glow sprite stretched."""
    pass


def feathered(shot, name, px=60):
    """Cast texture with alpha feathered to zero at the image borders (hides hard crop edges of close-ups)."""
    name = resolve(name)
    key = f"{ROOT}/assets/cast/{name}.png|f{px}"
    if key in shot.e.cache:
        return shot.e.cache[key]
    from mm.engine import load_rgba
    im = load_rgba(f"{ROOT}/assets/cast/{name}.png").copy()
    h, w = im.shape[:2]
    yy = np.minimum(np.arange(h), np.arange(h)[::-1]) / px
    xx = np.minimum(np.arange(w), np.arange(w)[::-1]) / px
    m = np.clip(np.minimum(yy[:, None], xx[None, :]), 0, 1)
    m = m * m * (3 - 2 * m)
    im[..., 3] = (im[..., 3] * m).astype(np.uint8)
    return shot.e.texture_from_array(im, key=key)


def round_window(shot, cx, cy, r, draw_inside, ring=GOLD, wall=None, t=0.0):
    """Marumado: draw_inside() is clipped to a circle; gold double ring frame."""
    e = shot.e
    e.mask_begin()
    e.shape("disc", (cx, cy), (r,), (1, 1, 1, 1))
    e.mask_end()
    draw_inside()
    e.shape("ring", (cx, cy), (r + 6, 8, 0), ring)
    e.shape("ring", (cx, cy), (r + 22, 2.5, 0), (*ring[:3], 0.8))


def firework(shot, cx, cy, t, t0, col=(1.0, 0.8, 0.4), n=90, R=320, dur=1.6, seed=0, kind="spark", trail=3,
             screen=True, cam=None, z=0.0, size=26):
    """Chrysanthemum-style burst (deterministic). Returns nothing; draws additive sparks with short trails."""
    if t < t0 or t > t0 + dur:
        return
    e = shot.e
    rng = np.random.default_rng(seed)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + rng.uniform(0, 0.2, n)
    sp = rng.uniform(0.75, 1.0, n)
    k = (t - t0) / dur
    inst = []
    for j in range(trail):
        kk = max(0.0, k - j * 0.035)
        r = R * sp * (1 - (1 - kk) ** 3)
        gx = cx + np.cos(ang) * r
        gy = cy + np.sin(ang) * r + 160 * kk * kk
        a = (1 - k) ** 1.4 * (1 - j / trail)
        for x, y in zip(gx, gy):
            inst.append(shot.e.inst(x, y, z, size * (1 - j * 0.25), size * (1 - j * 0.25), 0, 0, 0, shot.ctx.uv[kind],
                                    (*col, a)))
    if k < 0.15:
        inst.append(shot.e.inst(cx, cy, z, R * 1.2, R * 1.2, 0, 0, 0, shot.ctx.uv["glow"], (*col, (1 - k / 0.15) * 0.8)))
    e.sprites(shot.ctx.atlas, np.stack(inst), screen=screen, cam=cam, blend="add")


def ground_text(shot, chars, x0, z0, dz, y, t, size=150, cam=None, font="boku", fill="#f2e7cf", t_out=None,
                tilt=1.25, dx=0.0, alpha=1.0):
    """Characters lying on the ground plane receding in depth (like stepping stones)."""
    e = shot.e
    for i, (c, tc) in enumerate(chars):
        a = remap(t, tc - 0.05, tc + 0.12) * alpha
        if t_out is not None:
            a *= 1 - remap(t, t_out + i * 0.04, t_out + 0.4 + i * 0.04)
        if a <= 0:
            continue
        g = shot.ctx.gc.get(c, vertical=False, font=font, size=size, fill=fill, stroke="#120c10", stroke_w=0.05,
                            shadow=None)
        k = ease_out_back(remap(t, tc - 0.05, tc + 0.25), 2.0)
        s = g.w * lerp(1.5, 1.0, k)
        e.image(g, x0 + dx * i, y, z0 + dz * i, s, s, rx=-tilt, alpha=a, cam=cam)


def scroll_unroll(shot, text_chars, x, y_top, t, t0, t1, width=170, size=78, cam=None, z=0.0, t_out=None):
    """Hanging scroll (kakejiku) that unrolls downward revealing vertical text."""
    e = shot.e
    n = len(text_chars)
    full_h = n * size * 1.05 + size * 1.6
    k = ease_io(remap(t, t0, t1))
    if k <= 0:
        return
    a = 1.0 if t_out is None else 1 - remap(t, t_out, t_out + 0.4)
    h = full_h * k
    e.image(e.white, x, y_top + h / 2, z, width, h, color=(0.94, 0.9, 0.8), alpha=a, cam=cam, screen=cam is None)
    e.image(e.white, x, y_top + h / 2, z - 0.5, width - 18, max(h - 18, 0), color=(0.97, 0.94, 0.86), alpha=a, cam=cam,
            screen=cam is None)
    for yy in (y_top, y_top + h):
        e.image(e.white, x, yy, z - 1, width + 40, 16, color=(0.15, 0.08, 0.06), alpha=a, cam=cam, screen=cam is None)
    for i, (c, tc) in enumerate(text_chars):
        cy = y_top + size * 0.9 + i * size * 1.05
        if cy > y_top + h - size * 0.4:
            break
        ai = remap(t, tc - 0.05, tc + 0.15) * a
        if ai <= 0:
            continue
        g = shot.ctx.gc.get(c, vertical=True, font="mincho", size=size, fill="#1c1418", stroke=None, stroke_w=0,
                            shadow=None)
        e.image(g, x, cy, z - 2, g.w, g.w, alpha=ai, cam=cam, screen=cam is None)


def sub_line(L, idx=None, chars=None):
    """Make a lyric-line dict containing only some phrases (idx list) or explicit chars."""
    from mm import lyrics as ly
    ph = ly.phrases(L)
    if chars is None:
        chars = [c for i in idx for c in ph[i]]
    return {**L, "chars": [{"c": c, "t": tt} for c, tt in chars]}


def kit_tex(shot, name):
    return shot.T(f"{ROOT}/assets/kit/{name}.png")


# ---------------------------------------------------------------- composite devices (错位 / 镂空)
def slices(shot, name, x, y, h, t, n=5, axis=0, t_in=None, dur=0.5, spread=260.0, gap=6.0, t_out=None, out_dir=1,
           color=(1, 1, 1), screen=True, cam=None, z=0.0, stagger=0.07, drift=0.0):
    """Character image cut into n strips (axis 0 = vertical strips) that slide in from alternating sides and lock
    into place, with thin gaps (offset 'misaligned' print look). drift adds a slow residual offset per strip."""
    e = shot.e
    tex = feathered(shot, name, 30)
    w = h * tex.aspect
    for k in range(n):
        u0, u1 = k / n, (k + 1) / n
        side = -1 if k % 2 == 0 else 1
        kin = 1.0 if t_in is None else ease_out_expo(remap(t, t_in + k * stagger, t_in + k * stagger + dur))
        kout = 0.0 if t_out is None else ease_in(remap(t, t_out + k * stagger, t_out + k * stagger + dur * 0.8), 2)
        off = side * spread * (1 - kin) + out_dir * side * spread * 2.2 * kout + side * drift * (k - n / 2) / n
        a = min(1.0, kin * 1.5) * (1 - kout)
        if a <= 0:
            continue
        if axis == 0:
            sw = w / n
            cx = x - w / 2 + (k + 0.5) * sw
            e.image(tex, cx, y + off, z, sw - gap, h, uv=(u0, 0, u1, 1), color=color, alpha=a, screen=screen, cam=cam)
        else:
            sh = h / n
            cy = y - h / 2 + (k + 0.5) * sh
            e.image(tex, x + off, cy, z, w, sh - gap, uv=(0, u0, 1, u1), color=color, alpha=a, screen=screen, cam=cam)


def figure_window(shot, name, x, y, h, draw_inside, rim=(1.0, 0.85, 0.5, 1.0), rim_w=4.0, anchor=(0.5, 0.5),
                  flip=False, alpha=1.0, outline=True):
    """镂空: the character's silhouette becomes a window onto another scene (draw_inside draws with mask=1)."""
    e = shot.e
    tex = cast_tex(shot, name)
    w = h * tex.aspect
    uv = (1, 0, 0, 1) if flip else (0, 0, 1, 1)
    if outline:
        for k in range(8):
            ang = k / 8 * 6.2832
            e.image(tex, x + math.cos(ang) * rim_w, y + math.sin(ang) * rim_w, 0, w, h, uv=uv, mode=1, color=rim[:3],
                    alpha=alpha * rim[3], anchor=anchor, screen=True)
    e.mask_begin()
    e.image(tex, x, y, 0, w, h, uv=uv, mode=1, color=(1, 1, 1), anchor=anchor, screen=True)
    e.mask_end()
    draw_inside()


def misreg(shot, name, x, y, h, amt, anchor=(0.5, 0.5), screen=True, flip=False, feather=0):
    """Risograph misregistration copies (red / teal plates) for impact frames; amt in [0,1]."""
    if amt <= 0.01:
        return
    e = shot.e
    tex = feathered(shot, name, feather) if feather else cast_tex(shot, name)
    w = h * tex.aspect
    uv = (1, 0, 0, 1) if flip else (0, 0, 1, 1)
    d = 18 * amt
    e.image(tex, x - d, y + d * 0.4, 0, w, h, uv=uv, mode=1, color=(0.95, 0.2, 0.25), alpha=0.55 * amt, anchor=anchor,
            screen=screen, blend="screen")
    e.image(tex, x + d, y - d * 0.4, 0, w, h, uv=uv, mode=1, color=(0.15, 0.8, 0.85), alpha=0.55 * amt, anchor=anchor,
            screen=screen, blend="screen")


def anim_frame(t, frames, hits, pre=0.12, post=0.30):
    """Pick a sprite-sheet frame for a hit cycle: frames = [raise, swing, impact, recoil]; hits = impact times."""
    best = frames[0]
    for th in hits:
        if th - pre - 0.25 <= t < th - pre:
            best = frames[0]
        elif th - pre <= t < th:
            best = frames[1]
        elif th <= t < th + post * 0.45:
            best = frames[2]
        elif th + post * 0.45 <= t < th + post:
            best = frames[3]
    return best
