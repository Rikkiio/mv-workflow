"""Audio analysis: tempo, beat grid, per-frame energy curves, parsed LRC lines.

Reads audio/song.mp3 (and audio/song.lrc when there is one). Writes work/audio.json, which mm/anim.py reads for the
beat grid B(n) / bar(n) and the onset / rms / low envelopes, and work/lyrics_lines.json, the LRC lines that
work/syll_mms.py times per character. python src/analyze_audio.py"""
import json, os, re, sys
import numpy as np
import librosa

ROOT = (os.environ.get("MM_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
FPS = 30

y, sr = librosa.load(f"{ROOT}/audio/song.mp3", sr=22050, mono=True)
dur = len(y) / sr
hop = 512

onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop, tightness=400)
beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=hop)
tempo = float(np.atleast_1d(tempo)[0])

# Regularise beat grid: fit a straight line through tracked beats (assumes a constant tempo)
idx = np.arange(len(beat_t))
A = np.vstack([idx, np.ones_like(idx)]).T
period, offset = np.linalg.lstsq(A, beat_t, rcond=None)[0]
resid = beat_t - (idx * period + offset)
print(f"tempo(librosa)={tempo:.2f}  fitted period={period:.5f}s -> {60/period:.3f} BPM  offset={offset:.3f}  resid std={resid.std()*1000:.1f}ms")

# Per-video-frame curves
n_frames = int(np.ceil(dur * FPS))
t_frames = np.arange(n_frames) / FPS
env_t = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=hop)
onset_f = np.interp(t_frames, env_t, onset_env / (onset_env.max() + 1e-9))

rms = librosa.feature.rms(y=y, hop_length=hop)[0]
rms_f = np.interp(t_frames, env_t[:len(rms)], rms / rms.max())

# Low band energy (kick) and high band (hats) from STFT
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
low = S[(freqs > 30) & (freqs < 150)].sum(0)
high = S[(freqs > 5000)].sum(0)
low_f = np.interp(t_frames, env_t[:len(low)], low / low.max())
high_f = np.interp(t_frames, env_t[:len(high)], high / high.max())

# Parse LRC (optional)
lines = []
lrc = f"{ROOT}/audio/song.lrc"
if os.path.exists(lrc):
    pat = re.compile(r"^\[(\d+):(\d+\.\d+)\](.*)$")
    for raw in open(lrc, encoding="utf-8"):
        m = pat.match(raw.strip())
        if m:
            t = int(m.group(1)) * 60 + float(m.group(2))
            lines.append({"t": round(t, 3), "text": m.group(3).strip()})
else:
    print("no audio/song.lrc: beat grid and envelopes only")
for i, l in enumerate(lines):
    l["end"] = lines[i + 1]["t"] if i + 1 < len(lines) else dur
lyr = [l for l in lines if l["text"] and not (l["t"] < 1.0 and " - " in l["text"])]   # (not an opening "title - artist")

os.makedirs(f"{ROOT}/work", exist_ok=True)
json.dump({
    "duration": dur, "fps": FPS, "tempo": 60 / period, "beat_period": period, "beat_offset": offset,
    "beats_tracked": beat_t.round(4).tolist(),
    "onset": onset_f.round(4).tolist(), "rms": rms_f.round(4).tolist(),
    "low": low_f.round(4).tolist(), "high": high_f.round(4).tolist(),
}, open(f"{ROOT}/work/audio.json", "w"))
json.dump(lyr, open(f"{ROOT}/work/lyrics_lines.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("duration", dur, "beats", len(beat_t), "lyric lines", len(lyr))
# Print the beat index nearest each lyric line start (for section planning)
for l in lyr:
    b = (l["t"] - offset) / period
    print(f'{l["t"]:7.2f}  beat {b:7.2f}  {l["text"]}')
