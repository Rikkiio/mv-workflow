"""Per-character sung times by forced alignment (torchaudio MMS_FA, CTC) of each lyric line's romaji against the
isolated vocal stem. Kanji readings come from pykakasi (word readings split across the word's kanji).

Inputs
  work/demucs/htdemucs/song/vocals.wav   the vocal stem: demucs -n htdemucs -o work/demucs audio/song.mp3
  work/lyrics_timed.json                 rough per-character timings, if you have them; otherwise
  work/lyrics_lines.json                 the LRC lines written by src/analyze_audio.py
  work/audio.json                        the beat grid (times close to a sixteenth snap to it)
Output: work/lyrics_timed_v2.json, read by mm/text.lyric_lines():
  [{"t", "end", "sung_end", "text", "chars": [{"c", "t", "m"}], "mora"}, ...]

--check measures the alignment against a stretch you timed by hand instead of writing anything:
  work/hand_timed.json = [{"t": line start (s), "text": "the line", "times": [time of each non-space character]}]

python work/syll_mms.py [--check]"""
import json
import os
import re
import sys

import librosa
import numpy as np
import pykakasi
import torch
import torchaudio
from torchaudio.pipelines import MMS_FA as bundle

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
_A = json.load(open(f"{ROOT}/work/audio.json"))
PERIOD, OFFSET = _A["beat_period"], _A["beat_offset"]
G = PERIOD / 4
kks = pykakasi.kakasi()
model = bundle.get_model(with_star=False)
model.eval()
DICT = bundle.get_dict(star=None)
SR = bundle.sample_rate
y, _ = librosa.load(f"{ROOT}/work/demucs/htdemucs/song/vocals.wav", sr=SR, mono=True)
SMALL = set("ゃゅょャュョぁぃぅぇぉァィゥェォ")


def from_lrc(rows):
    """Bare LRC lines in the timed format, the characters spread evenly over most of the line (a placeholder: the
    alignment replaces every time it can)."""
    out = []
    for r in rows:
        text, t0 = r["text"], r["t"]
        span = max(0.3, r["end"] - t0) * 0.8
        n = max(1, sum(1 for c in text if c.strip()))
        chars, k = [], 0
        for c in text:
            chars.append({"c": c, "t": round(t0 + span * k / n, 3), "m": 1 if c.strip() and c not in SMALL else 0})
            k += 1 if c.strip() else 0
        out.append({"t": t0, "end": r["end"], "sung_end": r["end"], "text": text, "chars": chars,
                    "mora": sum(ch["m"] for ch in chars)})
    return out


if os.path.exists(f"{ROOT}/work/lyrics_timed.json"):
    lines = json.load(open(f"{ROOT}/work/lyrics_timed.json", encoding="utf-8"))
else:
    lines = from_lrc(json.load(open(f"{ROOT}/work/lyrics_lines.json", encoding="utf-8")))


def is_kana(c):
    return 0x3040 <= ord(c) <= 0x30ff


def char_readings(text):
    """[(char, kana reading or '')] for every character of the line (spaces get '')."""
    out = []
    for w in kks.convert(text):
        orig, hira = w["orig"], w["hira"]
        if not orig.strip():
            out.extend((c, "") for c in orig)
            continue
        kana_chars = [c for c in orig if is_kana(c)]
        kanji = [c for c in orig if not is_kana(c)]
        if not kanji:
            out.extend((c, kks.convert(c)[0]["hira"] if c.strip() else "") for c in orig)
            continue
        n_k = max(1, len(hira) - len(kana_chars))
        per = [n_k // len(kanji) + (1 if i < n_k % len(kanji) else 0) for i in range(len(kanji))]
        pos, ki = 0, 0
        for c in orig:
            if is_kana(c):
                out.append((c, hira[pos:pos + 1]))
                pos += 1
            else:
                out.append((c, hira[pos:pos + per[ki]]))
                pos += per[ki]
                ki += 1
    return out


def romaji(kana):
    if not kana:
        return ""
    r = "".join(w["hepburn"] for w in kks.convert(kana))
    return re.sub(r"[^a-z]", "", r.lower())


def align_line(L, t_end, t_floor=0.0):
    rd = char_readings(L["text"])
    if len(rd) != len(L["chars"]):
        return None
    toks, owner = [], []
    for ci, (c, kana) in enumerate(rd):
        r = romaji(kana)
        if c in SMALL:            # small kana: romaji is merged into the previous character's syllable
            r = ""
        for ch in r:
            if ch in DICT:
                toks.append(DICT[ch])
                owner.append(ci)
    if not toks:
        return None
    t0 = max(0.0, L["t"] - 0.6, t_floor)        # never reach back into the previous line's held note
    t1 = min(len(y) / SR, t_end + 0.05)
    seg = torch.tensor(y[int(t0 * SR):int(t1 * SR)])[None]
    with torch.inference_mode():
        em, _ = model(seg)
    em = torch.log_softmax(em, dim=-1)
    if em.shape[1] < len(toks):
        return None
    ali, scores = torchaudio.functional.forced_align(em, torch.tensor([toks], dtype=torch.int32), blank=0)
    ali = ali[0].tolist()
    spans = torchaudio.functional.merge_tokens(torch.tensor(ali), scores[0].exp())
    ratio = (t1 - t0) / em.shape[1]
    starts = {}
    for k, sp in enumerate(spans):
        ci = owner[k]
        if ci not in starts:
            starts[ci] = t0 + sp.start * ratio
    out, last = [], L["t"]
    for ci, (c, kana) in enumerate(rd):
        if ci in starts:
            last = starts[ci]
        out.append(last)
    return out


def snap(t):
    g = OFFSET + round((t - OFFSET) / G) * G
    return g if abs(g - t) < 0.07 else t


new = []
prev_last = 0.0
for i, L in enumerate(lines):
    t_end = lines[i + 1]["t"] if i + 1 < len(lines) else L["end"]
    L2 = json.loads(json.dumps(L))
    if not L["text"].startswith("la"):           # (scat lines like "la la la" are left as they are)
        ts = align_line(L, t_end, prev_last + 0.22)
        if ts is not None:
            for ch, tt in zip(L2["chars"], ts):
                ch["t"] = round(snap(tt), 3)
            sung = [c["t"] for c in L2["chars"] if c["c"].strip()]
            L2["sung_end"] = round(max(sung) + 0.25, 3)
            prev_last = max(sung)
    new.append(L2)

if "--check" in sys.argv:
    manual = json.load(open(f"{ROOT}/work/hand_timed.json", encoding="utf-8"))
    allerr = []
    for L, L2 in zip(lines, new):
        for m in manual:
            if m["text"].strip() != L["text"].strip() or abs(m["t"] - L["t"]) > 1.5:
                continue
            nw = [c["t"] for c in L2["chars"] if c["c"].strip()]
            k = min(len(nw), len(m["times"]))
            e = np.abs(np.array(nw[:k]) - np.array(m["times"][:k]))
            allerr += list(e)
            print(f"{L['t']:6.2f} err mean {e.mean():.3f} max {e.max():.3f}  new {nw[:k]}")
    if allerr:
        print("overall mean", np.mean(allerr), "median", np.median(allerr), "max", np.max(allerr))
    else:
        print("no line of work/hand_timed.json matched a lyric line")
else:
    json.dump(new, open(f"{ROOT}/work/lyrics_timed_v2.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("lines", len(new))
