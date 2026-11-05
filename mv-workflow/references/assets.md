# 素材：角色立绘、平面构件、底图

## 目录
1. 生成工具
2. 提示词怎么写
3. 抠图
4. 清理和统一画风
5. 额度用完时的程序化改图
6. 一致性检查

## 1. 生成工具

| 工具 | 用法 | 适合 |
|---|---|---|
| gpt-image（经 Codex CLI） | `python src/gpt_image.py OUT.png "提示词" [参考图...]`；批量 `python src/gpt_batch.py jobs.json [并发数]` | 平面矢量、琳派金箔风构件（纯色底）、照参考图重画或外扩、照现有角色生成新姿势 |
| ComfyUI Illustrious-XL（本地，`F:\ComfyUI_windows_portable`） | `src/comfy.py`：txt2img、img2img，可接 ESRGAN 放大 | 早期的角色立绘；显卡只有 6 GB |
| Seedance 2.0 | 用户自己在外部平台生成 | 见 extras.md |

gpt-image 的要点：

- 没有 API key，走已登录的 Codex CLI：`codex exec --json --skip-git-repo-check -s read-only -C <dir> [-i ref.png] -`，提示词从 stdin 传进去。
- 出图存在 `~/.codex/generated_images/<thread-id>/`。从 `--json` 事件里读自己的 thread id；不要"拿最新的文件"，并行跑时会互相拿错。
- 每张 40–90 秒，4 个并行没问题。
- 额度有限，用完要等恢复，买不买额度由用户决定。

## 2. 提示词怎么写

完整手册在参考实现的 `work/prompt_guide.md`。要点：

1. **六块式，每块一行**：主体与用途 → 构图与布局 → 风格与材质 → 文字要求 → 画幅与格式 → 约束与反面清单。提示词正文用英文，模型对英文最稳。
2. **改图一定写"保留清单"**：构图、轮廓、脸、配色、物体位置哪些不许动，否则会漂。
3. **素材要单独、完整、纯色底**：`isolated, complete silhouette, nothing cropped, generous margin, flat #ff00ff background, no cast shadow on the background`，方便抠图分层。
4. **风格迁移附参考图和色卡**，写 `match the palette and line weight of the attached reference`。
5. **角色一致性**：附角色参考图，写服装和发型的不变项（例：Miku: teal twin-tails, white miko haori, red hakama）。
6. **不让模型画字**（`no text, no letters`），字全部由引擎排。
7. **反面清单写具体的 AI 味来源**：airbrush gradients, glossy plastic shading, painterly over-detailed texture, photorealism, 3D render, lens blur, extra fingers, watermark。

只学参考片的设计语言（纸剧场分层、限色、勾线剪影、画出来的光），题材、配色、造型换成自己的，保证原创。

## 3. 抠图

- `work/cut_magenta.py [--black] IN.png OUT.png ...`：按"品红程度"（min(R,B)−G）抠纯品红底，只去掉和边框相连的背景（形状内部的品红保留），把边缘溢色拉回中性，裁到内容加一点边。
- `src/prep_kit.py`：白底的平面矢量图转 RGBA，原色不变；可以拆成单独的物件；给成排的房子生成窗户遮罩（`k_houses1_win.png`，夜里叠加成暖光）。
- 渲染图和照片用 rembg 抠。rembg 会把奶油色的条纹当背景去掉，这种图改用从边框泛洪填充（`work/prep_street.py`）。

## 4. 清理和统一画风

角色图的标准流程，后一步在前一步的输出上做：

1. `work/defringe_cast.py [名字...]`：去掉抠图留下的浅色光边（暗场景里头发边上会发白）。原图先备份到 `assets/cast/_vec_orig/`。
2. `work/fix_holes.py`：去掉被包在图里的白底碎片（发丝之间、脸颊和头发之间的空隙）。备份在 `assets/cast/_preholes/`。
3. 按需要选一种：
   - `work/celify.py IN OUT [k]`：把涂得很满的图拍平成赛璐璐（新生成的脸显 AI 时用）。
   - `work/v30_deai.py`：温和地去 AI 味（头发的黄色轮廓光收回发色、高光和深渐变压平、皮肤压平、颜色稳一点、线条清楚、一点纸纹）。用户要的是这种程度，不要色块化。
   - `src/print_style.py 名字`：丝网印刷版，只当点缀用（印章、障子影子一类图形镜头）。
   - `work/woodblock2.py K OUTDIR IN...`：一组场景图共用一套墨色的木版画处理，降低 gpt 底图的 AI 味。
4. 同一个角色几张图之间颜色要一致：裙子在两个姿势之间变了颜色会被发现（`work/recolor_hakama.py` 把藏青裙子改回红色）。

平面构件（kit）的风格：深色平涂剪影，加细而均匀的奶油色或金色勾线，暖色小窗户，光是画出来的平面形状。参考实现 `assets/kit/` 里的成排房子、摊位、金云、五重塔、鸟居、红叶枝都是这一套。

## 5. 额度用完时的程序化改图

这一轮的大笑い（去掉重复的马尾）和 0:56 的回头笑（张嘴改成微笑）都是 gpt-image 没额度时用代码改的。做法：

- **按颜色分区**：在 HSV 里用阈值分出和服、皮肤、领子、头发（参考 `work/v32_tails.py` 的 `classes()`），只保留面积够大的连通块，挡掉头发里的暖色高光之类的误判。
- **去掉一块、补出下面的东西**：
  - 用多边形加分区掩码圈出要去掉的部分；
  - 从周围已知的像素做调和填充（拉普拉斯方程，`scipy.sparse` 求解；加一点正则，没有已知邻居的孔也能解）；
  - 再吸附到这张图自己的几种平涂色上（k-means 聚类，底色取附近最常见的那种）；
  - 被挡住的阴影形状按距离衰减着延伸进来；
  - 在保留部分和填充部分的交界处补一条原图颜色的描线，读起来像"落到了后面"。
- **改表情**：先用调和填充把原来的嘴抹成皮肤，再用 skia 按 8 倍尺寸画新的线，缩小后贴回去。线的颜色从原来的嘴线取。微笑要顺着两眼的连线，3/4 侧脸时近侧那一半更长（`work/turn_smile.py`）。
- 改完的图存进新的版本目录（`assets/vNN/cast/...`），原图不动。每次都输出"改前 | 改后"的对比图，先自己放大看一遍。

## 6. 一致性检查

- 同一个画面里的角色：画风、线条、角度、头身比、头的大小一致。可以量两眼间距（这次的封面：铃和 GUMI 约 56 px，往前一步的初音 63 px）。
- 生成图先查解剖：手指、重复的头发或肢体、扭得不自然的脖子。
- 一段里一个角色只用一张图；新姿势要照已有的图生成，不要拿风格不一样的旧图凑。
