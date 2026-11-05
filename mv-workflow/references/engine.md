# 合成引擎（src/mm）和镜头代码

参考实现：`F:\mv\manimani\src`。这里写的是用的时候最常查的东西；细节以源码为准。

## 目录
1. 文件结构
2. Shot 和 Timeline
3. 摄像机和坐标
4. 绘制调用
5. 后期调色（grade）
6. 文字
7. 镜头代码里常用的帮手
8. 坑

## 1. 文件结构

| 文件 | 内容 |
|---|---|
| `mm/engine.py` | `Engine`（moderngl 离屏渲染、着色器、后期）、`Cam`、`W, H = 1920, 1080`、`FOCAL = 1400` |
| `mm/timeline.py` | `Shot` 基类、`Timeline`（选当前镜头、转场、子帧运动模糊）、`Ctx`（共享的字形缓存和贴图集） |
| `mm/anim.py` | 缓动函数、`hexc`；节拍 `B(n)`、`bar(n)`、`beat_of(t)`；音频包络 `onset/rms/low`（导入时就读 `work/audio.json`） |
| `mm/text.py` | 字体表、`glyph_rgba`、`text_rgba`、`GlyphCache`、`lyric_lines()`（读 `work/lyrics_timed_v2.json`） |
| `mm/fx.py` | `make_paper()` 纸纹、`make_atlas()` 小精灵图集、`Field` 粒子场 |
| `mm/elements.py` | 程序画的元素：`chochin` 灯笼、`kiku_ring` 菊花瓣环、`disc` 圆盘等 |
| `mm/transfx.py`、`kit.py`、`lyrics.py`、`running.py` | 转场叠层、程序化构件、歌词排版、滚动歌词 |
| `render.py` | 多进程分块渲染加配音；`--stills` 出静帧 |
| `storyboard.py` | 各版本的 `build_*()`，每个返回一个 `Timeline` |
| `shots/*.py` | 所有镜头；`common.py`、`b2common.py`、`b3.py` 是通用帮手 |

## 2. Shot 和 Timeline

```python
from mm.timeline import Shot, Timeline

class MyShot(Shot):
    name = "my_shot"                       # 缓存键的前缀，要唯一
    grade = dict(G_WARM, bloom=0.45)       # 这个镜头的调色
    trans = ("strips", 0.4, (9.0, 0.0, 0.0, 0.0))   # 进入这个镜头的转场：(模式, 时长, 参数)

    def setup(self):                       # 第一次用到时调用：读贴图、生成素材
        self.bg = self.T(f"{ROOT}/assets/plates/x.png")
        self.lan = self.A("my_lantern", lambda: el.chochin("", 150, 210))   # 生成的 RGBA 数组，按键缓存

    def draw(self, t):                     # t 是歌曲时间（秒）；self.t0 / self.t1 是镜头起止
        u = self.u(t)                      # 0..1 的镜头进度；self.lt(t) = t - t0
        ...

    def grade_at(self, t):                 # 可选：随时间变的调色（推镜、闪光、模糊）
        return dict(self.grade)
```

- 转场模式：`cut fade wipe iris ink push shoji flash zoom strips`（见 `timeline.TRANS`）。push 和 wipe 要给方向。
- `Timeline(shots, lyrics=None).render(e, t)` 画一帧；`e.read()` 取回 RGB 的 `uint8 (1080, 1920, 3)` 数组。
- 子帧运动模糊：给镜头类设 `SHUTTER`（快门比例）和 `MB_N`（采样数）。
- 版本替换：`build_full_vNN()` 遍历上一版的镜头，按类名替换成新类，保留镜头自定义过的 `trans`。

## 3. 摄像机和坐标

- `Cam(x, y, z, roll=0, f=1400, shift=(sx, sy))`。世界坐标 y 朝下（和屏幕一样），z 朝里。
- 投影：屏幕 x = 960 + f·(X−cam.x)/(Z−cam.z) + sx，屏幕 y = 540 + f·(Y−cam.y)/(Z−cam.z) + sy。shift 是镜头平移，不会产生梯形变形；正的 y 让世界往下移，相当于抬头看。
- `cam.scale_at(z)` 返回深度 z 处每个世界单位等于多少像素。
- 要让某个东西出现在屏幕上某个位置，就从屏幕位置和深度反推世界坐标。参考片里的前景构件都是这样摆的（`pre1_2d.CaveFront`）。

## 4. 绘制调用

都是 `self.e`（Engine）上的方法，按调用顺序叠画（画家算法，没有深度测试）。

- `e.image(tex, x, y, z, w, h, rot=0, rx=0, ry=0, alpha=1, color=(1,1,1), add=(0,0,0), uv=(0,0,1,1), anchor=(0.5,0.5), screen=False, cam=None, blend="normal"|"add", mode=0, rim=None, rim_off=(du,dv), mask=0)`
  - `screen=True` 用像素坐标，否则用世界坐标经过 `cam`。只给 w 或 h 时，另一边按纹理比例算。
  - 旋转绕锚点进行；`rx/ry` 让卡片在 3D 里翻转（立体书的翻页、卡片立起来）。
  - `mode=1` 把图画成纯色剪影；`mode=2` 剪影加轮廓光：用 `color=(0,0,0)` 加 `blend="add"` 时，只叠一圈光边。`rim_off` 是 uv 偏移，轮廓光出现在朝偏移方向的边上，往太阳的方向偏就是逆光效果。
  - `mask=1` 只画在遮罩里面，`mask=2` 只画在遮罩外面。
- `e.mask_begin()` … `e.mask_end()`：中间画的东西写进遮罩，用的是 alpha。用一个径向光晕当遮罩，就能让效果只在光源附近出现。
- `e.sprites(self.ctx.atlas, field.instances(t, self.ctx.uv), screen=True, blend="add")`：大量粒子。
  图集里的精灵：`momiji1-3 ginkgo petal kiku confetti confetti2 glow spark dot streak star4 ring ember leaf`。
- `e.shape("disc"|"ring"|"rect"|"seg", center, params, color_rgba, soft=0, ...)`：屏幕空间的距离场形状。
- `e.rays(center, n, color_rgba, rot, width, rad=(r0, r1), soft, blend="add")`：放射光芒。
- `e.gradient(a, b, c0, c1, c2=None, pos=(0, .5, 1), radial=False)`：**会填满整个屏幕**，端点以外延续端点颜色。只适合做整屏底色；地面、水面这种带子要用有边界的贴片。
- `e.fill(rgba)`：整屏铺色（闪白、压暗）。
- `e.layer(tex, z, cover)`：按参考摄像机铺满屏幕的一层。`e.globe(...)` 是会转的纸灯笼地球，`e.sky(...)` 是等距柱状天空。
- 纹理：`self.T(path)` 读文件（有缓存）；`self.A(key, fn)` 缓存生成的数组。纹理有 `.w .h .aspect`。**纹理不平铺**，uv 不要超过 1，要铺满就多画几份。

## 5. 后期调色（grade）

`grade` 字典的键（默认值见 `Engine.post`）：

| 键 | 作用 |
|---|---|
| `bloom`、`thr` | 光晕强度、阈值 |
| `lift`、`gamma`、`gain`、`exposure`、`sat` | 调色 |
| `grain`、`paper`、`vig` | 颗粒、纸纹、暗角 |
| `flash=(r,g,b,a)` | 整屏闪色 |
| `ca` | 色差 |
| `fade` | 整体亮度 |
| `xs`、`xr`、`xo` | 整帧缩放、旋转、平移，用来做后期推镜 |
| `zb`、`zbc` | 径向推镜模糊，强度和中心 |
| `mb=(dx,dy)` | 方向运动模糊（甩镜） |
| `rb=(角度,cx,cy)` | 旋转模糊 |

- 预设在 `shots/common.py`：`G_WARM`、`G_FEST`、`G_MORN` 等。
- `b2common.push(g, zoom, cx, cy)` 绕某点做后期推镜，偏移会自动算好。

## 6. 文字

- 字体键：`mincho`、`mincho_b`、`old`（ZenOldMincho-Black，标题常用）、`brush`、`boku`、`dela`、`decol`、`tokumin`、`rampart`、`antique`、`hina`、`reggae`、`cinzel`、`antique_b1`。
- `self.ctx.gc.get(ch, vertical, font, size, fill, stroke, stroke_w, shadow=(dx,dy,blur,rgba), glow=(rgba, blur))` 返回单字贴图。描边宽度和阴影偏移都是字号的倍数。
- `common.big_text(shot, text, x, y, size, t, t_in, ...)`：一整行横排字，带 pop/slide/zoom/drop 入场。
- `b2common.glyph(...)` 让单字在它的音节上弹出；`column(...)` 竖排一列，小假名自动缩小偏移；`row(...)` 横排一行。
- 对比图上的中文说明用 `C:/Windows/Fonts/msyhbd.ttc`，ZenOldMincho 没有简体字。
- 毛笔字：`gen/fude/u<码位>.png` 是逐字生成的扫描字（`b3.fude_stages`、`back_v30.fude_stages_filled` 把墨洇开的过程画出来）。没有扫描的字会退回字体，字号只有扫描字的一半，要先裁到墨迹再缩放。

## 7. 镜头代码里常用的帮手

- `common.py`：
  - `kit_tex(shot, name)` 读 `assets/kit/name.png`；
  - `cast_tex(shot, name)` 读角色图，`resolve()` 优先用 `_vec`、其次 `_full`、再其次原图，名字加 `@pr` 表示丝网印刷版；
  - `prop_tex`；`character(shot, name, x, y, z, h, ...)`；
  - `vignette_dark(e, a)`、`ember_field(...)`、`silhouette(...)`、`stamp(...)`、`with_flash(...)`。
- `b3.py`：`figure(shot, name, x, y, h, mode="color"|"mono"|"pen"|"ghost"|"sil")` 一张角色图的几种处理，还有 `tatami`、`plate_pen` 等。
- `act1.py`：`mist(e, y, h, col, a)`、`stars_field(seed, n)`、`MTN_UV`。
- `back_v22.py`：`GrottoCam`（看向目标的摄像机，用来在合成器里做程序化 3D）、`ground_quad`、`PlateSeq`（Blender 底片序列）。
- `intro_2d.py`：`gold_sun`、`beat_t(n)`、`step_ease`（按拍点一步一步走的缓动）。

## 8. 坑

- `e.gradient` 填满整个屏幕（见上）。
- 屏幕坐标的绘制要写 `screen=True`。漏写过一次，の! 的花瓣爆开整个偏到了右下角。
- 纹理不平铺。
- 会淡出到下一个镜头的镜头，要画过它的 `t1`。BWild 的最后一格在 184.5 秒跳了一下，就是因为没画过去。
- 分段渲染的接缝放在没有改动的地方；一个镜头拆到两个片段里时，两边的状态要一致。
- 生成素材的缓存键（`self.A` 的 key）要唯一，换了生成参数就换键，否则读到旧缓存。
- 音节密集时，快速盖在移动路径上的字会堆在一起：后来的字要把前面的推开。
- 字沿着圆环往上爬会读反：要从顶上绕过去往下走。
- 子类覆盖了父类的 `draw` 但想复用父类的一部分时，把那部分拆成方法（比如 `draw_doors`、`row_part`），不要复制一大段代码。
