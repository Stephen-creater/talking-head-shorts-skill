#!/bin/bash
# 一次性安装（可重复运行，已有的会跳过）。macOS + Homebrew；Linux 把 brew 换成对应包管理器即可。
# 装什么：ffmpeg、whisper.cpp、Node + HyperFrames（图形渲染）、Python 环境，
#        以及模型/字体/脚本库/配乐，统一放在 ~/.cache/talking-head-shorts（可用 THS_HOME 改）。
# 需要下载约 1.7GB（大头是 1.6GB 的转写模型）。
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
THS_HOME="${THS_HOME:-$HOME/.cache/talking-head-shorts}"
mkdir -p "$THS_HOME"/{models,fonts,js,music}
say() { printf "\n\033[1m%s\033[0m\n" "$*"; }
fetch() {  # fetch <url> <目标文件>：已存在就跳过；先下到临时文件，成功再改名
  [ -s "$2" ] && { echo "已有 $(basename "$2")"; return; }
  echo "下载 $(basename "$2")"; curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

say "1/5 命令行工具"
if command -v brew >/dev/null; then
  for p in ffmpeg whisper-cpp node; do
    bin=$p; [ $p = whisper-cpp ] && bin=whisper-cli
    command -v $bin >/dev/null && echo "已有 $bin" || brew install $p
  done
else
  echo "没有 Homebrew：请自行安装 ffmpeg、whisper.cpp（提供 whisper-cli）、Node.js 18+ 后重跑"
fi

say "2/5 Python 环境（$THS_HOME/venv）"
[ -x "$THS_HOME/venv/bin/python" ] || python3 -m venv "$THS_HOME/venv"
"$THS_HOME/venv/bin/python" -m pip install -q --upgrade pip
"$THS_HOME/venv/bin/python" -m pip install -q -r "$HERE/requirements.txt"

say "3/5 HyperFrames（HTML 图形渲染成视频）"
if [ -f "$(npm root -g)/hyperframes/bin/hyperframes.mjs" ] || command -v hyperframes >/dev/null; then
  echo "已有 hyperframes"
else
  npm install -g hyperframes@0.8.188
fi

say "4/5 模型"
fetch "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin" "$THS_HOME/models/ggml-large-v3-turbo.bin"
fetch "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx" "$THS_HOME/models/rvm_mobilenetv3_fp32.onnx"

say "5/5 字体、GSAP、默认配乐"
G=https://raw.githubusercontent.com/google/fonts/main/ofl
fetch "$G/notosanssc/NotoSansSC%5Bwght%5D.ttf" "$THS_HOME/fonts/NotoSansSC[wght].ttf"
fetch "$G/notoserifsc/NotoSerifSC%5Bwght%5D.ttf" "$THS_HOME/fonts/NotoSerifSC[wght].ttf"
fetch "$G/instrumentserif/InstrumentSerif-Italic.ttf" "$THS_HOME/fonts/InstrumentSerif-Italic.ttf"
fetch "$G/caveat/Caveat%5Bwght%5D.ttf" "$THS_HOME/fonts/Caveat[wght].ttf"
fetch "$G/dmmono/DMMono-Medium.ttf" "$THS_HOME/fonts/DMMono-Medium.ttf"
fetch "https://github.com/lxgw/LxgwWenKai/releases/download/v1.530/LXGWWenKai-Medium.ttf" "$THS_HOME/fonts/LXGWWenKai-Medium.ttf"
fetch "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js" "$THS_HOME/js/gsap.min.js"
fetch "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wholesome.mp3" "$THS_HOME/music/Wholesome.mp3"

say "检查"
"$HERE/scripts/ths" doctor
