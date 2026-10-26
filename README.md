# talking-head-shorts · 口播短视频精剪 Skill

把手机自拍的口播素材，剪成可以直接发布的 1080×1920 竖屏短视频（视频号 / 抖音 / 小红书）。这是一个 [Claude Code](https://claude.com/claude-code) Skill：你把素材交给 Claude，说「剪这条口播」，它按这里的流程和标准从转写、挑句、写剪辑表一路做到成片、质检和封面。不用 Claude 也可以照 `SKILL.md` 手动跑命令。

它是在给一位 71 岁的口播创作者连续剪片的过程中做出来的：每一条成片都经过她本人看片提意见再修改，那些意见都沉淀进了 `docs/剪辑判断.md`。

## 成品是什么样的

- **只留最好的一遍**：口误、重说、前后矛盾的说法、镜头掉到天花板的几秒全部剪掉；切点贴在真实的有声 / 无声边界上，不切字。
- **节奏**：1.3 倍速（不变调）、句间停顿压到约 0.3 秒、伪双机位推镜（原画 / 推近 / 特写）+ 同机位 4 帧软切。
- **字幕**：逐字对齐发音、一屏 ≤ 11 字、关键词琥珀色，固定在不挡平台 UI 的高度。
- **图形**：纸面墨字 + 唯一强调色暖金——开场照片墙 / 题字、随口播逐格出现的目录卡、章节签、金句大字、人物出场、片尾相框签名 + 手写结束语 + 定格。
- **声音**：人声降噪均衡压缩、配乐说话时自动让开、片尾歌接着创作者的结束语唱出同一句、-15 LUFS。
- **可选抠像**：人像缩小、换纯色背景（手里举的东西也能保住）。
- **自动质检**：成片重新转写逐字比对、闪帧、爆音、响度；外加联系表供人看。
- **交付**：发布版压缩（SSIM ≥ 0.99）+ 3:4 封面（生图模型提示词模板 + 导出 + 换底色）。

一条 7 分钟的原片，剪成 2 分 30 秒的成片，在 M 系列 Mac 上全流程约 20 分钟（大部分是渲染）。

## 安装

需要 macOS（Apple Silicon 最佳）+ [Homebrew](https://brew.sh)、Python 3.10+。Linux 可用，把 `setup.sh` 里的 brew 换成对应包管理器。

```bash
git clone https://github.com/Stephen-creater/talking-head-shorts-skill.git ~/.claude/skills/talking-head-shorts
cd ~/.claude/skills/talking-head-shorts
./setup.sh          # 一次性：ffmpeg、whisper.cpp、Node + HyperFrames、Python 环境、模型、字体（约 1.7GB）
scripts/ths doctor  # 全部 ✓ 就可以用了
```

模型、字体、配乐都下载到 `~/.cache/talking-head-shorts/`（可用 `THS_HOME` 改），不放进仓库。

## 用法

在 Claude Code 里：

> 帮我剪这条口播：~/Movies/口播/0412.mp4，还有两张照片 ~/Movies/口播/a.jpg b.jpg，片尾用 ~/Music/片尾歌.m4a

手动跑（详见 `SKILL.md`）：

```bash
scripts/ths new_project ~/剪辑/0412 口播.mp4 --photos a.jpg b.jpg --end-song 片尾歌.m4a
scripts/ths prepare ~/剪辑/0412          # 转写、人脸、联系表
# 读 analysis/phrases.tsv 和联系表，写 edl.json（挑句、字幕、图形）——这一步是剪辑本身
scripts/ths build ~/剪辑/0412 --name v1  # 出片 + 质检
scripts/ths deliver ~/剪辑/0412 v1       # → out/成片.mp4
```

剪辑表的完整例子（一条真实的 2 分半成片）：`examples/edl.example.json`。

## 目录

```
SKILL.md              给 Claude 的流程说明（也是人读的操作手册）
setup.sh              一次性安装
scripts/ths           统一入口：scripts/ths <命令> …
scripts/              prepare / listen / frames / build / deliver / matte / cover_* …（每个文件开头写了用途）
docs/                 剪辑判断、剪辑表字段、设计规范、声音、质检与交付、封面、踩过的坑
examples/             剪辑表示例
```

## 技术路线

whisper.cpp large-v3-turbo 逐字转写 → 短语表 → 剪辑表（人 / AI 写）→ 帧精确时间线（切点贴有声边界、对齐帧格）→ 伪双机位规划 → Python 逐帧渲染底片（推镜 + 放大一次 Lanczos 仿射、可选 RobustVideoMatting 抠像）→ ffmpeg 调色 → [HyperFrames](https://www.npmjs.com/package/hyperframes)（HTML + GSAP）渲染字幕和图形 → numpy 混音 + 两遍 loudnorm → 质检 → 压缩。

## 许可

代码以 MIT 许可发布（见 `LICENSE`）。`setup.sh` 下载的第三方资源各有许可，不随仓库分发：

| 资源 | 许可 |
|---|---|
| 思源黑体 / 思源宋体（Noto Sans SC / Noto Serif SC）、Instrument Serif、Caveat、DM Mono | SIL Open Font License 1.1 |
| 霞鹜文楷 LXGW WenKai | SIL Open Font License 1.1 |
| GSAP | [GSAP Standard License](https://gsap.com/standard-license)（免费使用） |
| whisper.cpp 模型（OpenAI Whisper large-v3-turbo） | MIT |
| RobustVideoMatting 模型 | GPL-3.0（只在本机运行，不分发） |
| 《Wholesome》Kevin MacLeod | CC BY 4.0 —— **发布时须署名**：Wholesome – Kevin MacLeod (incompetech.com) |

片尾歌等流行音乐需要你自己提供，并自行确认发布平台的音乐版权规则。
