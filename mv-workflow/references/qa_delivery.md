# 自检、拼接、交付

## 1. 自动扫描

| 工具 | 查什么 | 命令 |
|---|---|---|
| `scripts/qa_scan.py`（本 skill） | 接近全黑的帧、单帧跳变、≥1 秒的冻结 | `python qa_scan.py VIDEO` |
| `scripts/contact_sheet.py`（本 skill） | 每隔 N 秒抽一帧拼成接触表，看全片节奏和构图 | `python contact_sheet.py VIDEO OUT 0 256 2` |
| `work/lyric_qa.py` | 每行最后一个音节刚唱完时的帧，整行要完整清楚 | `python work/lyric_qa.py VIDEO OUTPREFIX` |
| `work/cutsheet.py` | 每个切点前后 13 帧，查转场有没有跳和闪 | `python work/cutsheet.py VIDEO OUT OFFSET CUT1,CUT2` |
| `work/motion_audit.py` | 每个镜头的光流中位数和推拉速度，标出几乎不动的镜头 | `python work/motion_audit.py VIDEO` |
| `work/jerk_scan.py` | 镜头内部的运动突变（不在切点上的） | `python work/jerk_scan.py VIDEO OFFSET CUTS` |
| `work/flicker_scan.py` | 局部的单帧闪烁（某块画面只出现一帧又消失） | `python work/flicker_scan.py VIDEO [t0 t1]` |

扫描结果要对照设计来看。设计好的淡入、墨水淹没、片尾黑场都会被报成黑帧；设计好的闪光转场会被报成跳变。每一项都要能说出来"这是设计的"，说不出来的就是问题。

## 2. 交付前用眼睛看一遍

扫描查不出审美问题。交付前按用户的眼光过一遍（对照 style_rules.md）：

- 每个有角色的镜头出一张静帧：脚着地没有？大小、角度和同框的人一致吗？有没有解剖错误、切边、白边？
- 每行歌词：完整在画面里吗？底干净吗？字号和前后镜头差不多吗？
- 每个转场：有理由吗？有没有一帧闪过、黑帧、跳帧？
- 每个运镜：有没有停在半路？太快导致糊成一片吗？
- 和上一版比：用户没点名的地方有没有被误改（拿对比图看）。

## 3. 拼接

只重渲改过的片段，拼进上一版的底片里，不用整片重渲：

- 片段按帧精确渲染：`--start f0/30 --end (f1-0.5)/30`，文件名 `out/vNN_p_<名>.mp4`。
- `scripts/assemble.py CONFIG.json` 按配置拼：`base` 是底片段（歌曲帧区间 → 文件，以及文件第一帧对应的歌曲帧），`over` 是覆盖上去的新片段（文件不存在的会跳过）。配置的例子写在脚本的文档字符串里。
- 拼接点放在没改动的地方，离转场至少半秒；会淡出到下一个镜头的镜头，要画过它的 t1。

## 4. 压制

| 版本 | 参数 | 用途 |
|---|---|---|
| 1080p 母版 | libx264 `-preset medium -crf 16 -pix_fmt yuv420p`，AAC 192k | 在电脑上看，作为母版 |
| 720p | lanczos 缩放，`-preset slow -crf 20`，`+faststart` | 分享 |
| 手机版 | `hqdn3d=0.7:0.7:3:3`、960×540，两遍编码 `-b:v 820k -preset veryslow -tune animation`，AAC 96k | 4 分多钟控制在 30 MB 以内，发到手机 |

`assemble.py` 会一次压出这三个版本。整个过程要十几分钟，放后台跑，等进程结束（PowerShell 里 `Wait-Process`），不要反复去读输出文件。

## 5. 交付

1. **对比图**：`scripts/compare_sheet.py OLD.mp4 NEW.mp4 OUT.jpg --rows "187.2|说明" ...`，旧版在左、新版在右，每行上面一条中文说明，三行一张。
2. **发给用户**：用 SendUserFile 发对比图（或者静帧、封面）；在资源管理器里选中 1080p 成片。
3. **中文小结**，按这个顺序写：
   - 按用户的每条意见，说改了什么、怎么改的；
   - 有什么要注意的地方，比如某个转场里两张图会重叠零点几秒，以及可以怎么改；
   - 自检结果（和上一版相比有没有新问题）；
   - 文件在哪；
   - 这一轮可以删的中间文件和大小（不要自己删）。
4. **更新项目 memory**：这一版的片段布局、新文件、用户这轮的意见里有哪些是以后也要遵守的。

## 6. 版本命名

- 成片：`out/<名>_vNN.mp4`、`_720p.mp4`、`_phone.mp4`。旧版都留着。
- 镜头：`src/shots/back_vNN.py`（新类继承旧类，`VNN_SWAP`），`storyboard.build_full_vNN()`。
- 素材：改过的图放进 `assets/vNN/...`，原图不动。
- 工具：`work/vNN_<做什么>.py`，文档字符串第一段写清这一版是为了用户的哪条意见（引用原话）、做了什么、输出到哪。
