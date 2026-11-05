---
name: mv-workflow
description: >-
  用代码做音乐视频（MV / PV / 二创 MV）的整套工作流，来自《神のまにまに》MV 三十多版的实战：节拍分析和逐字歌词时间轴 →
  故事与分镜 → 角色立绘和平面素材（生成、抠图、去 AI 味）→ moderngl 2.5D 合成引擎里搭镜头（配 Blender 三维底片）→
  分段渲染 → 自动自检 → 只重渲改动片段再拼接、压手机版 → 对比图交付 → 按意见迭代；以及封面、无字插图、投稿简介。
  只要用户想给一首歌做 MV/PV、接着改一支做到一半的 MV（"这个镜头…""字幕看不清""改回原版""出 v33"）、从 MV 出封面、缩略图或插图，
  或者写 MV 的简介、标题和标签，都要用这个 skill，哪怕用户没提"工作流"。Use it for making or revising a music video from a song
  with this code pipeline, and for its covers, stills and upload text.
---

# MV 工作流

一首歌做成一支几分钟、有纵深和运镜、歌词长在画面里的 MV。画面全部由代码合成：

- **2.5D 合成引擎**（moderngl）：镜头、歌词、特效、调色都在这里做。
- **Blender**：渲大场景的三维底片。
- **生成式图像**：只用来出素材（角色立绘、平面构件、底图），每张都要清理，统一成一套画风。

参考实现是 `F:\mv\manimani`（《神のまにまに》，成片是 v32），新 MV 直接复用它的引擎和工具。本地没有这个目录时，从用户 GitHub 仓库 `manimani-mv` 的 `project/` 文件夹取。所有 Python 都用 `F:\mv\manimani\.venv\Scripts\python.exe`，里面装好了 moderngl、skia-python、opencv、scipy、torchaudio 等，任何项目目录都能用。

## 和用户怎么配合

这几条比任何技术细节都重要，几十轮修改的经验都在这里。

- **看意见**：用户用中文提意见，常配截图和红框，也说过"我表述的不一定是我脑子里的真正的想法，你尝试意会一下"。所以要读出意图再改，不必逐字照做。用户点名的地方改到位，没点名的保持原样（"原样的好"就别动）。
- **准备好换回来**：新做法可能不如原版，用户说"不如原版的"就马上换回去。所以替换镜头时，旧的类、素材和渲染片段都留着。
- **不删文件**：任何文件都不删，包括中间文件。每轮交付时列出可以删的东西和大小，让用户自己删。
- **有截止时间就做满**：用户说"优化到 X 点"，就一轮一轮改到那个时间，中途给阶段版，不要做完一版就停下。
- **交付内容**：文件、对比图（旧 | 新，配中文说明）、中文小结，再在资源管理器里选中成片。用户在电脑上看 1080p；手机版要 ≤ 30 MB。
- **额度会用完**：gpt-image 通过 Codex CLI 调用，有额度；Seedance 只能由用户自己在外部平台生成；本机 ComfyUI 只有 6 GB 显存。额度没了就改用程序化手段（代码重画、图像处理）继续做，不要停下等。

## 流程

| 步骤 | 做什么 | 产出 | 细节 |
|---|---|---|---|
| 1. 开工 | 要到歌曲 mp3、LRC 歌词、用户的想法和参考片，问清截止时间 | `audio/song.mp3`、`audio/song.lrc` | |
| 2. 时间轴 | 节拍网格；分离人声；按字对齐时间 | `work/audio.json`、`work/lyrics_timed_v2.json` | references/lyrics_timing.md |
| 3. 方案 | 一个能把歌词串起来的故事（神话、季节、旅程）、色彩弧线、母题、约 10 个相连的地点；按段落写分镜 | `work/mv_plan.md` | references/style_rules.md |
| 4. 素材 | 角色立绘（一套画风）、平面构件、底图、Blender 场景 | `assets/cast`、`assets/kit`、`assets/plates`、`work/blender/*` | references/assets.md、references/blender.md |
| 5. 搭镜头 | 在 `src/shots/*.py` 写 `Shot` 子类，在 `storyboard.py` 排时间线 | 一个可以渲染的 build 函数 | references/engine.md |
| 6. 渲染 | 先出静帧和半分辨率小样，再分段渲成片 | `out/*.mp4` | 见下文"常用命令" |
| 7. 自检 | 自动扫描，再看接触表、歌词表、转场帧 | 问题清单 | references/qa_delivery.md |
| 8. 交付 | 拼接、压 720p 和手机版、做对比图、写小结 | `out/<名>_vNN*.mp4`、对比图 | references/qa_delivery.md |
| 9. 迭代 | 按意见出下一版 vNN，只重渲改动的片段 | 下一版 | 见下文"版本管理" |
| 10. 周边 | 封面、无字插图、投稿简介 | `out/cover*.jpg`、简介文字 | references/extras.md |

不要第一版就把整支片子做满。先做一段代表性的样片（比如副歌一的 15–20 秒），让用户确认方向再铺开，否则方向错了全部返工。

## 分镜怎么写

每个镜头写清四件事：时间段（按节拍）、地点、画面里发生的一件事、这句歌词以什么物体出现。好镜头是画面、运动和歌词的意思融成一件事。用户夸过的例子：

- 八百万的面具拼成马赛克，镜头一拉远拼出这句歌词；
- 巨石滚过来封住洞口，和开场的日食呼应；
- 黑暗在插画地图上蔓延开；
- 歌词变成障子上的人影。

相邻段落不要重复同一个点子。镜头之间要有过渡的理由：身体擦过镜头、匹配剪辑、摇上烟花再摇下河面、钻进桥下的暗处、飞进雾里。具体规则见 references/style_rules.md，动手前至少读一遍。

## 开新项目

1. 建目录 `F:\mv\<名字>\`，下面建 `audio`、`assets\{cast,kit,plates,props}`、`gen`、`fonts`、`src\shots`、`src\blender`、`work`、`out`。
2. 从参考实现复制：
   - `src/mm/`（引擎）、`src/render.py`、`src/analyze_audio.py`；
   - `work/syll_mms.py`（逐字对齐）；
   - `src/shots/common.py` 和 `src/shots/b2common.py`（通用绘制帮手）；
   - `fonts/` 整个目录；
   - 工具脚本：`src/gpt_image.py`、`src/gpt_batch.py`、`work/cut_magenta.py`、`work/defringe_cast.py`、`work/celify.py`、`work/v30_deai.py`。
3. 把复制过来的文件里写死的 `F:/mv/manimani` 换成新目录（`src/mm/anim.py`、`fx.py`、`text.py`、`transfx.py`，`src/render.py`，`src/shots/common.py` 里都有）。
4. 把歌放进 `audio/song.mp3`，先跑 `analyze_audio.py`，因为 `mm/anim.py` 一导入就要读 `work/audio.json`。
5. 写一个最小的 `storyboard.py`，里面一个 `build()` 返回 `Timeline([某个 Shot(0, 5)])`，渲一张静帧确认环境通了再往下做。

## 常用命令

都在项目根目录下运行。`PY` 指上面那个 venv 的 python。

```bash
# 渲染一段（多进程分块，自动配上音频）；MM_BUILD 选 storyboard.py 里的 build 函数
MM_BUILD=build_full_v32 $PY src/render.py out/v32_p_dance.mp4 --start 184.3 --end 189.583
# 精确到帧的片段：--start f0/30 --end (f1-0.5)/30
# 静帧（看构图最快）
MM_BUILD=build_full_v32 $PY src/render.py work/stills --stills 187.2,187.9
# Blender 无界面渲染（Steam 版 Blender 5.2）：路径一律写绝对路径，相对路径会落到 C:\
"/e/steam/steamapps/common/Blender/blender.exe" -b --factory-startup --python-exit-code 1 \
  -P F:/mv/x/src/blender/town.py -- --anim F:/mv/x/work/blender/town --range 1:300
```

本 skill 的 `scripts/` 里有通用工具，先用 `--help` 看参数：

- `qa_scan.py`：全片扫描接近全黑的帧、单帧跳变和冻结。
- `contact_sheet.py`：按时间间隔抽帧拼成接触表。
- `compare_sheet.py`：旧版和新版同一时刻并排，配中文说明。
- `assemble.py`：按配置把片段拼进底片，压 1080p、720p 和手机版。

## 版本管理

一次只改用户点名的地方，其余的直接沿用上一版的渲染：

- **新镜头类**：写在 `src/shots/back_vNN.py`，继承上一版的类，再写一个 `VNN_SWAP = {"旧类名": "新类名"}`。
- **时间线**：`storyboard.build_full_vNN()` 遍历上一版的镜头，按类名替换；镜头自定义过的 `trans` 要保留。
- **只重渲改动的片段**：按帧精确渲成 `out/vNN_p_<名>.mp4`，在拼接配置里覆盖到底片上。
- **分段点**：放在没改动的地方，离转场至少半秒。会淡出到下一个镜头的镜头，要画过它的 `t1`，否则接缝处会跳。
- **记录**：每版的片段布局（哪段来自哪个文件）记进项目 memory，下一轮才知道该重渲哪里。

## 最常踩的坑

- `e.gradient` 会填满整个屏幕（端点以外的部分延续端点颜色），做一条带子要用有边界的贴片。
- 纹理采样不平铺：uv 滚动不要超过 1，要铺满就多画几份。
- 屏幕坐标的绘制都要写 `screen=True`，漏写的会被当成世界坐标，画到奇怪的位置。
- 镜头结尾的推镜会把最后一个字推出画面：最后一个字完全写出后，至少还要在画面里停 0.15 秒。
- 生成的角色图要先检查解剖错误（这次每根马尾都画了两遍）。
- 这个 shell 里 heredoc 夹中文会出错，含中文的脚本先写成文件再跑。
- Blender 渲染要检查摄像机的 clip 范围、远景雾、共面闪烁（共面的层至少错开 10 cm）。
- Seedance 片段是 24 fps，转 30 fps 用 `minterpolate=mi_mode=mci`，不要用 `fps=30`（每 5 帧重复一帧，推拉镜头会抖）。
- 接触表的标签时间要用 `contact_sheet.py` 按帧号取；ffmpeg 的 fps 滤镜会四舍五入，标签会偏早约一个间隔。

更多坑写在各个 reference 文件里。
