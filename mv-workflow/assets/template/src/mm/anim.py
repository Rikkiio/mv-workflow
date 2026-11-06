"""Easing, beat grid and audio-reactive helpers. Everything is a pure function of time.

The beat grid and the energy curves come from work/audio.json (src/analyze_audio.py writes it from audio/song.mp3).
Until the song has been analysed, a 120 BPM placeholder grid is used so shots can already be drafted."""
import json
import math
import os
import sys

import numpy as np

from .paths import ROOT

FPS = 30
_AUDIO = f"{ROOT}/work/audio.json"
if os.path.exists(_AUDIO):
    _A = json.load(open(_AUDIO))
else:
    sys.stderr.write(f"[mm] {_AUDIO} not found (run src/analyze_audio.py): using a 120 BPM placeholder\n")
    _A = {"beat_period": 0.5, "beat_offset": 0.0, "duration": 60.0,
          "low": [0.0] * (60 * FPS), "onset": [0.0] * (60 * FPS), "rms": [0.0] * (60 * FPS)}
PERIOD = _A["beat_period"]
OFFSET = _A["beat_offset"]
DURATION = _A["duration"]
_LOW = np.array(_A["low"], np.float32)
_ONSET = np.array(_A["onset"], np.float32)
_RMS = np.array(_A["rms"], np.float32)


def B(beat):
    """Time (s) of a beat index on the fitted grid."""
    return OFFSET + beat * PERIOD


def bar(n):
    """Time of bar n (4 beats per bar)."""
    return B(4 * n)


def beat_of(t):
    return (t - OFFSET) / PERIOD


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def lerp(a, b, t):
    return a + (b - a) * t


def remap(x, a, b):
    return clamp01((x - a) / (b - a)) if b != a else float(x >= a)


def smooth(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def ease_out(t, p=3):
    t = clamp01(t)
    return 1 - (1 - t) ** p


def ease_in(t, p=3):
    t = clamp01(t)
    return t ** p


def ease_io(t, p=3):
    t = clamp01(t)
    return (2 ** (p - 1)) * t ** p if t < 0.5 else 1 - (-2 * t + 2) ** p / 2


def ease_out_back(t, s=1.70158):
    t = clamp01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_expo(t):
    t = clamp01(t)
    return 1 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_out_elastic(t):
    t = clamp01(t)
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1


def lerp_c(c0, c1, t):
    return tuple(a + (b - a) * t for a, b in zip(c0, c1))


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def kick(t, decay=0.12, every=1, phase=0, t_start=-1e9, t_end=1e9):
    """Exponential pulse on the beat grid (every Nth beat), deterministic."""
    if t < t_start or t > t_end:
        return 0.0
    b = beat_of(t) - phase
    k = math.floor(b / every) * every
    dt = (b - k) * PERIOD
    return math.exp(-dt / decay)


def low(t):
    i = int(t * FPS)
    return float(_LOW[min(max(i, 0), len(_LOW) - 1)])


def onset(t):
    i = int(t * FPS)
    return float(_ONSET[min(max(i, 0), len(_ONSET) - 1)])


def rms(t):
    i = int(t * FPS)
    return float(_RMS[min(max(i, 0), len(_RMS) - 1)])


def env_smooth(arr_fn, t, win=0.1):
    n = 5
    return sum(arr_fn(t - win * (k / (n - 1) - 0.5)) for k in range(n)) / n


def wobble(t, seed=0.0, freq=0.3, amp=1.0):
    """Smooth 1D noise built from incommensurate sines (handheld drift)."""
    return amp * (0.5 * math.sin(t * freq * 6.283 + seed * 1.7)
                  + 0.3 * math.sin(t * freq * 2.31 * 6.283 + seed * 3.1)
                  + 0.2 * math.sin(t * freq * 4.77 * 6.283 + seed * 5.3))


def shake(t, t0, dur=0.35, amp=12.0, seed=0.0):
    """Decaying impact shake (x, y) starting at t0."""
    if t < t0 or t > t0 + dur:
        return 0.0, 0.0
    k = 1 - (t - t0) / dur
    k = k * k
    return (amp * k * math.sin((t - t0) * 61.0 + seed), amp * k * math.sin((t - t0) * 47.0 + seed * 2.1))
