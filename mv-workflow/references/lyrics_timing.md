# 节拍和逐字歌词时间轴

用户对字幕卡点要求很严："轴没卡上"说的是真实存在的 0.3–0.9 秒偏差。时间必须从人声里测出来，不能只信 LRC。

## 1. 节拍和能量：`src/analyze_audio.py`

读 `audio/song.mp3` 和 `audio/song.lrc`，写出两个文件：

- `work/audio.json`：`duration`、`fps`(30)、`tempo`、`beat_period`、`beat_offset`、`beats_tracked`，以及每帧一个值的 `onset`、`rms`、`low`、`high` 包络。
- `work/lyrics_lines.json`：解析好的 LRC 行。

`mm/anim.py` 导入时就读 `audio.json`，镜头代码通过它取节拍：`B(n)` 是第 n 拍的时间，`bar(n)` 是第 n 小节，`beat_of(t)` 把时间换成拍数，`kick(t)` 在拍点上给一个衰减脉冲，`onset/rms/low` 取音频包络。片头一类的图形快切，用 `intro_2d.beat_t(n)` 和 `step_ease` 让东西在拍点上一步一步走。

## 2. 分离人声

用 demucs（htdemucs）把歌拆开（`demucs -n htdemucs -o work/demucs audio/song.mp3`），得到 `work/demucs/htdemucs/song/vocals.wav` 和 `no_vocals.wav`。之后所有的对齐都在 vocals.wav 上做，伴奏会干扰对齐。

## 3. 逐字对齐：`work/syll_mms.py`

- 用 torchaudio 的 MMS_FA 做 CTC 强制对齐，对象是每行歌词的罗马音。
- 汉字读音来自 pykakasi，一个词的读音按词里的汉字拆开分配。
- 每行有自己的时间窗，窗口不会伸回上一行里去。挤在一起的行，退回用 Whisper 的时间。
- 输入：有 `work/lyrics_timed.json`（粗的逐字时间）就用它；没有就用 `analyze_audio.py` 写出的 `work/lyrics_lines.json`（LRC 行）。
- `--check` 不写文件，而是和手工卡好的一段比对：`work/hand_timed.json`，格式写在脚本的文档字符串里（这次用的是副歌一）。这个项目的平均误差是 0.05 秒。

输出 `work/lyrics_timed_v2.json`：一个行的列表，每行长这样：

```json
{"t": 37.29, "end": 40.75, "sung_end": 40.974, "text": "…",
 "chars": [{"c": "思", "t": 37.168, "m": 1}, {"c": "い", "t": 37.279, "m": 1}], "mora": 16}
```

其中 `c` 是显示的字，`t` 是这个字开始唱的时间，`m` 是它占几个音拍（空格是 0）。`mm/text.lyric_lines()` 读的就是这个文件。

另一条思路是参考实现里的 `src/lyrics_timing.py`：在人声里检测起音点，用单调 DP 把音拍放到吸附在十六分音符网格上的起音候选上。精度不如 MMS_FA，只作备用。

## 4. 用的时候

- 每个字在它自己的时间上出现（弹出、盖章、点亮）。镜头代码按 `chars[i]["t"]` 驱动，不要自己估计。
- 一行的最后一个字唱完以后，整行至少要在画面里停一会儿再走；镜头结尾的推镜不能把它推出去。
- 渲染后用 `work/lyric_qa.py VIDEO OUTPREFIX` 检查：它在每行最后一个音节刚唱完时各截一帧，标上歌词，12 张一页。这一帧里整行都应该完整、看得清。
