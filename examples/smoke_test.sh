#!/bin/bash
# 冒烟测试：不需要任何素材。用 macOS 的中文语音合成一段 20 秒「口播」，配一个彩色测试画面，
# 从建工程一路跑到交付，确认整条工具链在这台机器上能用。约 3～5 分钟。
# 用法：examples/smoke_test.sh [工作目录，默认 /tmp/ths-smoke]
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W="${1:-/tmp/ths-smoke}"
rm -rf "${W:?}"; mkdir -p "$W"
say -v Tingting -o "$W/voice.aiff" "大家好，今天跟你们讲讲我坐飞机的三个习惯。第一个是戴口罩。第二个是带一瓶自己的水。第三个是上飞机先用酒精把座位擦干净。希望大家都有一个快乐的旅程。" \
  || { echo "需要 macOS 自带的中文语音 Tingting（系统设置 → 辅助功能 → 朗读内容 → 系统声音里添加）"; exit 1; }
ffmpeg -v error -y -f lavfi -i "testsrc2=s=544x960:r=30" -i "$W/voice.aiff" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "$W/口播.mp4"
"$HERE/scripts/ths" new_project "$W/proj" "$W/口播.mp4"
"$HERE/scripts/ths" prepare "$W/proj"
"$HERE/scripts/ths" draft_edl "$W/proj"
"$HERE/scripts/ths" build "$W/proj" --name smoke
"$HERE/scripts/ths" deliver "$W/proj" smoke
echo; cat "$W/proj/build/qa_smoke/report.txt"
