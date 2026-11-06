"""Element-driven transitions: an object sweeps across the frame and hides the cut."""
import math

import numpy as np
import skia

from . import elements as el
from .anim import ease_io, lerp, remap, smooth
from .paths import ROOT


def cloud_wall_rgba(w=2600, h=1400, col="#d6ae5c", line="#9a7430", seed=1):
    rng = np.random.default_rng(seed)
    s = el._surface(w, h)
    c = s.getCanvas()
    path = skia.Path()
    # scalloped left and right edges made of big arcs
    path.moveTo(w * 0.12, 0)
    y = 0.0
    while y < h:
        r = rng.uniform(90, 170)
        path.arcTo(skia.Rect(w * 0.12 - r * 1.2, y, w * 0.12 + r * 0.8, y + 2 * r), 270, -180, False)
        y += 2 * r
    path.lineTo(w * 0.88, h)
    y = h
    while y > 0:
        r = rng.uniform(90, 170)
        path.arcTo(skia.Rect(w * 0.88 - r * 0.8, y - 2 * r, w * 0.88 + r * 1.2, y), 90, -180, False)
        y -= 2 * r
    path.close()
    c.drawPath(path, el._paint(col))
    c.save()
    c.clipPath(path, doAntiAlias=True)
    for k in range(0, h, 46):
        p2 = skia.Path()
        p2.moveTo(0, k)
        for x in range(0, w + 200, 200):
            p2.quadTo(x + 100, k + 18 * math.sin(x * 0.01 + k), x + 200, k)
        c.drawPath(p2, el._paint(line, 0.55, 2.5))
    c.restore()
    c.drawPath(path, el._paint(line, 1, 5))
    return el._arr(s)


def draw_cloud_wall(e, ctx, p, direction=-1):
    """Two layered cloud walls slide across; full coverage around p=0.5."""
    key = "__cloudwall"
    if key not in e.cache:
        e.texture_from_array(cloud_wall_rgba(), key=key)
        e.texture_from_array(cloud_wall_rgba(col="#c99a48", line="#7a5622", seed=4), key=key + "2")
    t1, t2 = e.cache[key], e.cache[key + "2"]
    k = ease_io(p)
    for tex, lag, yoff in ((t2, 0.06, 40), (t1, 0.0, 0)):
        kk = min(1.0, max(0.0, (k - lag) / (1 - lag))) if lag else k
        x = 960 - direction * lerp(-2700, 2700, kk)
        e.image(tex, x, 540 + yoff, 0, 2600, 1400, screen=True)


def draw_slip_flurry(e, ctx, p, seed=3):
    key = "__slips"
    if key not in e.cache:
        texs = [el.ofuda(c, 110, 330, seed=i) for i, c in enumerate("神祭福寿吉縁")]
        for i, a in enumerate(texs):
            e.texture_from_array(a, key=f"{key}{i}")
        e.cache[key] = e.cache[f"{key}0"]
    rng = np.random.default_rng(seed)
    n = 140
    for i in range(n):
        tex = e.cache[f"{key}{i % 6}"]
        y0 = rng.uniform(-200, 1280)
        sp = rng.uniform(0.8, 1.3)
        ph = rng.uniform(-0.25, 0.25)
        k = (p - 0.5 + ph) * sp + 0.5
        if k < 0 or k > 1:
            continue
        x = lerp(2300, -400, k)
        y = y0 + 120 * math.sin(k * 6 + i)
        s = rng.uniform(0.9, 1.8)
        e.image(tex, x, y, 0, 110 * s, 330 * s, rot=k * rng.uniform(-6, 6), ry=math.sin(k * 8 + i) * 0.8, screen=True)


def draw_leaf_gust(e, ctx, p, seed=5, cols=None):
    rng = np.random.default_rng(seed)
    n = 520
    uv = ctx.uv
    kinds = ["momiji1", "momiji2", "momiji3", "ginkgo"]
    cols = cols or [(0.85, 0.27, 0.18), (0.94, 0.56, 0.23), (0.91, 0.72, 0.3), (0.61, 0.14, 0.19)]
    inst = np.zeros((n, 19), np.float32)
    m = 0
    for i in range(n):
        ph = rng.uniform(-0.3, 0.3)
        sp = rng.uniform(0.8, 1.4)
        k = (p - 0.5 + ph) * sp + 0.5
        if k < 0 or k > 1:
            continue
        x = lerp(-300, 2250, k) + rng.uniform(-300, 300)
        y = rng.uniform(-100, 1180) + 200 * math.sin(k * 5 + i) - 300 * (k - 0.5)
        s = rng.uniform(50, 130)
        c = cols[i % len(cols)]
        inst[m] = [x, y, 0, s, s, math.sin(k * 9 + i) * 1.2, math.cos(k * 7 + i), k * 8 + i, *uv[kinds[i % 4]], *c, 1.0, 0, 0, 0]
        m += 1
    e.sprites(ctx.atlas, inst[:m], screen=True)


OVERLAYS = {"cloud": draw_cloud_wall, "slips": draw_slip_flurry, "leaves": draw_leaf_gust}


# the goldcloud / rockpass / passer / firewall transitions below draw kit images that are not part of the template:
# k_clouds1_0-2, k_clouds2_0-3, k_rocks_0-1, sil_procession_2/5/7 and fire.png in assets/kit
KIT = f"{ROOT}/assets/kit"


def draw_gold_clouds(e, ctx, p, seed=2):
    """Rimpa folding-screen transition: stacked gold-leaf cloud bands slide across in alternating directions over an
    indigo ground; fully covered around p=0.5."""
    bands = [e.tex(f"{KIT}/k_clouds1_{i}.png") for i in range(3)]
    curls = [e.tex(f"{KIT}/k_clouds2_{i}.png") for i in range(4)]
    k = ease_io(p)
    cover = 1 - abs(2 * p - 1)            # 0 -> 1 -> 0
    a = min(1.0, max(0.0, (cover - 0.25) / 0.35))
    e.gradient((960, 0), (960, 1080), (0.07, 0.07, 0.16, a), (0.12, 0.1, 0.2, a), (0.07, 0.07, 0.16, a), pos=(0, 0.5, 1))
    rng = np.random.default_rng(seed)
    rows = 9
    for r in range(rows):
        tex = bands[r % 3]
        d = -1 if r % 2 == 0 else 1
        lag = rng.uniform(0.0, 0.12)
        kk = min(1.0, max(0.0, (k - lag) / (1 - 0.12)))
        w = 2600 + 300 * (r % 3)
        h = w / tex.aspect
        x = 960 + d * lerp(2600, -2600, kk)
        y = -40 + r * 140
        e.image(tex, x, y, 0, w, h * 1.5, screen=True)
    for i in range(4):
        tex = curls[i]
        d = 1 if i % 2 == 0 else -1
        kk = min(1.0, max(0.0, (k - 0.05 * i) / 0.8))
        x = 960 + d * lerp(2200, -2200, kk)
        y = 150 + i * 260
        w = 1100
        e.image(tex, x, y, 0, w, w / tex.aspect, screen=True)


OVERLAYS["goldcloud"] = draw_gold_clouds


def draw_rock_pass(e, ctx, p, seed=4):
    """The camera passes through a rock wall: a dark rock band with gold fissures sweeps right-to-left, rock pillars
    at its leading and trailing edges; fully covered around p=0.5."""
    rocks = [e.tex(f"{KIT}/k_rocks_0.png"), e.tex(f"{KIT}/k_rocks_1.png")]
    k = ease_io(p)
    xc = lerp(960 + 2800, 960 - 2800, k)
    hw = 1350
    e.image(e.white, xc, 540, 0, 2 * hw, 1200, color=(0.05, 0.05, 0.09), screen=True)
    rng = np.random.default_rng(seed)
    for i in range(14):
        x0 = xc + rng.uniform(-hw * 0.9, hw * 0.9)
        y0 = rng.uniform(-50, 1130)
        for j in range(5):
            dx, dy = rng.uniform(-90, 90), rng.uniform(40, 140)
            e.shape("seg", (x0, y0), (dx, dy, 2.5), (0.85, 0.66, 0.35, 0.55))
            x0, y0 = x0 + dx, y0 + dy
    for sd, tex in ((-1, rocks[0]), (1, rocks[1])):
        h = 2600
        w = h * tex.aspect
        e.image(tex, xc + sd * hw, 1300, 0, w * 1.4, h, anchor=(0.5, 1.0), color=(0.75, 0.78, 0.95), screen=True,
                uv=(1, 0, 0, 1) if sd > 0 else (0, 0, 1, 1))


OVERLAYS["rockpass"] = draw_rock_pass


def draw_passer(e, ctx, p, seed=6):
    """Festival-goers walking past right in front of the lens (v21): a dark crowd band, people's silhouettes at its
    leading and trailing edges, lantern light on their rims; fully covered around p=0.5."""
    sils = [e.tex(f"{KIT}/sil_procession_{k}.png") for k in (2, 5, 7)]
    k = ease_io(p)
    hw = 1150
    xc = lerp(-1900, 1920 + 1900, k)
    e.image(e.white, xc, 540, 0, 2 * hw, 1300, color=(0.02, 0.015, 0.025), screen=True)
    for j, (sd, tex) in enumerate(((-1, sils[0]), (1, sils[1]), (0.35, sils[2]))):
        h = 2500 if j < 2 else 2200
        w = h * tex.aspect
        e.image(tex, xc + sd * hw, 1350 if j < 2 else 1280, 0, w, h, anchor=(0.5, 1.0), mode=2,
                color=(0.02, 0.015, 0.025), rim=(1.0, 0.66, 0.38, 1.0), rim_off=(0.003 * (1 if sd < 0 else -1), 0.0),
                screen=True)


OVERLAYS["passer"] = draw_passer


def draw_fire_wall(e, ctx, p, seed=8):
    """A wall of fire rises through the frame (v21): a row of flames on its leading edge, a red-hot body, smoke and
    embers trailing below it; fully covered around p=0.5, then it rises out of the top."""
    fire = e.tex(f"{KIT}/fire.png")
    k = ease_io(p)
    hh = 720.0                                               # (a thin sweep: a short flat hold, both shots seen longer)
    yc = lerp(1080 + hh + 420, -hh - 420, k)                 # band centre, rising
    top, bot = yc - hh, yc + hh
    body = (0.62, 0.16, 0.05)
    if "fade_v" not in e.cache:                              # opaque at the top, gone at the bottom
        a = (1.0 - np.linspace(0.0, 1.0, 128)) ** 1.6
        rgba = np.dstack([np.full((128, 4), 255.0)] * 3 + [np.repeat(a[:, None], 4, 1) * 255]).astype(np.uint8)
        e.texture_from_array(rgba, key="fade_v")
    e.image(e.white, 960, (top + bot - 400) / 2, 0, 2400, 2 * hh - 400, color=body, screen=True)
    e.image(e.cache["fade_v"], 960, bot - 400 + 240, 0, 2400, 480, color=body, screen=True)   # a soft trailing edge
    e.image(ctx.atlas, 960, yc, 0, 3000, 2 * hh * 0.9, uv=ctx.uv["glow"], color=(1.0, 0.55, 0.18), alpha=0.85,
            screen=True, blend="add")
    rng = np.random.default_rng(seed)
    for i in range(16):                                      # the flames along the leading edge
        x = -120 + i * 145 + rng.uniform(-40, 40)
        h = rng.uniform(520, 820) * (1 + 0.08 * math.sin(p * 40 + i))
        e.image(fire, x, top + 140, 0, h * fire.aspect, h, anchor=(0.5, 1.0), screen=True, blend="add",
                alpha=0.95)
    e.image(ctx.atlas, 960, top, 0, 3000, 500, uv=ctx.uv["glow"], color=(1.0, 0.8, 0.45), alpha=0.6, screen=True,
            blend="add")
    for j in range(5):                                       # smoke trailing below, uncovering what lies behind
        e.image(ctx.atlas, 960, bot - j * 70, 0, 3400, 420, uv=ctx.uv["glow"], color=(0.08, 0.03, 0.02),
                alpha=0.35, screen=True)
    for i in range(70):                                      # embers thrown up off it
        x = rng.uniform(-50, 1970)
        y = top - rng.uniform(0, 600) - 900 * (k % 0.5)
        s = rng.uniform(4, 10)
        e.image(ctx.atlas, x + 30 * math.sin(p * 9 + i), y, 0, s, s, uv=ctx.uv["glow"], color=(1.0, 0.75, 0.4),
                alpha=0.9, screen=True, blend="add")


OVERLAYS["firewall"] = draw_fire_wall
