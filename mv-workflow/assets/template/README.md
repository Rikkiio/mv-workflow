# MV 项目模板

mv-workflow skill 自带的项目骨架：2.5D 合成引擎（`src/mm`）、渲染器、音频分析、逐字歌词对齐、素材清理和自检工具，外加一个演示镜头。整个文件夹复制一份，就是一个新的 MV 项目。

## 开始

1. 把这个文件夹整个复制成新项目，比如 `F:\mv\新歌\`。
2. 建环境（Python 3.12 上测过）：

   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt
   ```

3. 下字体：`python fonts/fetch_fonts.py`（14 个 Google 免费字体，约 93 MB）。没下的字体会临时换成系统字体。
4. 渲演示镜头，确认环境通了：

   ```bash
   python src/render.py work/stills --stills 1,4,7
   python src/render.py out/demo.mp4 --end 8
   ```

5. 放歌：`audio/song.mp3`，有 LRC 歌词就放 `audio/song.lrc`，然后跑 `python src/analyze_audio.py`。跑之前引擎按 120 BPM 的占位节拍走。
6. 歌词卡点（可选）：先 `demucs -n htdemucs -o work/demucs audio/song.mp3` 分出人声，再跑 `python work/syll_mms.py`。
7. 在 `src/shots/` 写镜头（`demo.py` 可以当起点），在 `src/storyboard.py` 里排时间线。

## 目录

| 路径 | 内容 |
|---|---|
| `src/mm/` | 引擎：`engine.py`（离屏渲染、着色器、后期）、`timeline.py`（镜头、转场、运动模糊）、`anim.py`（缓动、节拍、音频包络）、`text.py`（字形、竖排横排歌词）、`fx.py`（纸纹、粒子）、`elements.py` 和 `kit.py`（程序画的灯笼、鸟居、山、纹样）、`transfx.py`（转场叠层）、`lyrics.py` 和 `running.py`（歌词排版、滚动歌词）、`paths.py`（项目根目录） |
| `src/render.py` | 多进程分块渲染，自动配上 `audio/song.mp3`；`--stills` 出静帧 |
| `src/analyze_audio.py` | 节拍网格、能量曲线、解析 LRC |
| `src/storyboard.py`、`src/shots/` | 时间线和镜头；`common.py`、`b2common.py` 是通用帮手 |
| `src/gpt_image.py`、`src/gpt_batch.py` | 经 Codex CLI 调用 gpt-image 出图 |
| `work/syll_mms.py` | 逐字歌词对齐 |
| `work/cut_magenta.py`、`defringe_cast.py`、`celify.py`、`deai.py` | 抠品红底、去白边、拍平成赛璐璐、温和去 AI 味 |
| `work/lyric_qa.py`、`cutsheet.py`、`motion_audit.py`、`jerk_scan.py`、`flicker_scan.py` | 自检：歌词截帧、切点前后帧、运动量、运动突变、局部闪烁 |
| `fonts/fetch_fonts.py` | 下载字体 |

## 注意

- 项目根目录由 `src/mm/paths.py` 按文件位置自动找到，复制到哪里都能用；也可以用环境变量 `MM_ROOT` 指定。
- 引擎用 moderngl 离屏渲染，需要支持 OpenGL 3.3 的显卡。
- 素材按目录放：角色图 `assets/cast/`，平面构件 `assets/kit/`，底图 `assets/plates/`，道具 `assets/props/`（`common.py` 里的 `cast_tex`、`kit_tex`、`plate_tex`、`prop_tex` 从这些目录读）。
- 转场 `goldcloud`、`rockpass`、`passer`、`firewall` 要用 `assets/kit/` 里的图（见 `transfx.py` 里 `KIT` 那行的注释），模板里没有，要用的话先自己准备。
