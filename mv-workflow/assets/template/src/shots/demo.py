"""Demo shot: a dusk sky painted on washi, a sun with rays, paper-cut ridges at three depths, paper lanterns swaying,
drifting embers, a camera that keeps pushing in for the whole shot, a title that zooms in and then a vertical line
that drops in.

Copy it as the starting point for a new shot. `python src/render.py work/stills --stills 1,4,7` shows three frames.
Once the song is analysed, time things on the beat grid with B(n) / bar(n) instead of seconds after t0."""
import math

import cv2
import numpy as np

from mm.fx import make_paper
from shots.common import *


def papered(rgba, paper, k=2.5):
    """A layer cut from washi: the paper's fibres and blotches pressed into its colour (k = how strongly)."""
    h, w = rgba.shape[:2]
    p = cv2.resize(paper, (w, h))[..., :3].astype(np.float32) / 255.0
    out = rgba.copy()
    out[..., :3] = np.clip(rgba[..., :3] * (1.0 - k * (1.0 - p)), 0, 255).astype(np.uint8)
    return out


def washi_veil(paper, col=(40, 24, 46)):
    """The paper's fibres as a dark veil (alpha from how dark the paper is there), to lay over a flat sky."""
    a = np.clip((1.0 - paper[..., :3].mean(-1) / 255.0) * 3.0, 0, 1)
    out = np.zeros(paper.shape, np.uint8)
    out[..., :3] = col
    out[..., 3] = (a * 255).astype(np.uint8)
    return out


class Demo(Shot):
    name = "demo"
    grade = dict(G_WARM, bloom=0.5)
    SUN = (1240, 500)

    def setup(self):
        paper = make_paper(1600, 900, seed=11)
        ridges = el.mountains(2400, 900, [(0.50, 0.22, "#3b2546", "#c9a45a"),
                                          (0.62, 0.16, "#271a33", "#a8844a"),
                                          (0.76, 0.10, "#120d1a", "#6e5232")], seed=5)
        self.ridges = [self.A(f"demo_ridge{i}", lambda r=r: papered(r, paper)) for i, r in enumerate(ridges)]
        self.veil = self.A("demo_veil", lambda: washi_veil(paper))
        self.lantern = self.A("demo_lantern", lambda: el.chochin("", 150, 210))
        self.px = self.A("demo_px", lambda: np.full((4, 4, 4), 255, np.uint8))     # a white pixel, tinted when drawn
        self.embers = ember_field(seed=7, n=110)
        rng = np.random.default_rng(3)       # thin dusk clouds: (x, y, z, w, h, alpha)
        self.clouds = [(rng.uniform(-2600, 2600), rng.uniform(-950, -200), rng.uniform(1300, 2800),
                        rng.uniform(900, 1900), rng.uniform(45, 110), rng.uniform(0.25, 0.5)) for _ in range(16)]

    def cam(self, t):
        u = self.u(t)       # never stops: a steady push in, with a slow drift to the right
        return Cam(x=lerp(-90, 130, smooth(u)), y=-20, z=lerp(-1700, -650, u))

    def draw(self, t):
        e, cam, t0 = self.e, self.cam(t), self.t0
        # the sky gradient and the sun are screen space (the sun is at infinity); the washi veil over the sky is in the
        # world, so the sky moves with the camera too
        e.gradient((960, 0), (960, 1080), hexc("#1d1638"), hexc("#7b3c52"), hexc("#f2a75c"), pos=(0.0, 0.55, 0.92))
        e.layer(self.veil, z=2600, cover=1.5, alpha=0.6, cam=cam)
        sx, sy = self.SUN
        e.image(self.ctx.atlas, sx, sy, 0, 1100, 1100, uv=self.ctx.uv["glow"], color=(1.0, 0.72, 0.4), alpha=0.55,
                screen=True, blend="add")
        e.rays(self.SUN, 16, (1.0, 0.78, 0.45, 0.16), rot=0.04 * t, width=0.22, rad=(150, 1500))
        e.shape("disc", self.SUN, (115,), hexc("#ffe3ad"), soft=3.0)
        for x, y, z, w, h, a in self.clouds:     # (in front of the sun, sliding against the ridges as the camera moves)
            col = (1.0, 0.66, 0.5) if y > -520 else (0.62, 0.38, 0.52)
            e.image(self.ctx.atlas, x, y, z, w, h, uv=self.ctx.uv["glow"], color=col, alpha=a, cam=cam)
        # far to near (painter's order): two ridges, the lanterns, the near ridge, the embers
        for tex, z, y in zip(self.ridges[:2], (3200, 1900), (820, 590)):     # (y pushes each ridge down the frame)
            e.layer(tex, z=z, cover=1.35, y=y, cam=cam)
        for i, x in enumerate((-1100, -550, 550, 1100)):
            sway = 0.05 * math.sin(1.6 * t + 1.3 * i)
            e.image(self.ctx.atlas, x, -270, 420, 520, 520, uv=self.ctx.uv["glow"], color=(1.0, 0.55, 0.3),
                    alpha=0.35, cam=cam, blend="add")
            e.image(self.px, x, -400, 400, w=4, h=900, color=(0.13, 0.08, 0.1), anchor=(0.5, 1.0), cam=cam)  # cord
            e.image(self.lantern, x, -400, 400, h=260, rot=sway, anchor=(0.5, 0.0), cam=cam)
        e.layer(self.ridges[2], z=250, cover=1.35, y=120, cam=cam)
        self.leaves(self.embers, t, cam=cam, blend="add")
        # one line of text at a time, on the clean sky
        big_text(self, "MV WORKFLOW", 960, 150, 96, t, t0 + 0.8, t_out=t0 + 3.8, font="cinzel", mode="zoom",
                 stroke="#2a1420")
        vchars(self, "はじまり", 960, 150, 88, t, t0 + 4.3, font="old", mode="drop")
