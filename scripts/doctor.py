"""环境检查：逐项确认工具、模型、字体都在，并且 ffmpeg 有需要的滤镜。
用法：scripts/ths doctor
"""
import shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import HOME, FONTS_DIR, WHISPER_MODEL, RVM_MODEL, GSAP, hyperframes_cmd, whisper_cli  # noqa: E402
from fonts import FONTS  # noqa: E402


def main():
    bad = []

    def check(ok, label, fix=""):
        print(("  ✓ " if ok else "  ✗ ") + label + ("" if ok else f"  → {fix}"))
        if not ok:
            bad.append(label)

    check(shutil.which("ffmpeg") is not None, "ffmpeg", "brew install ffmpeg")
    if shutil.which("ffmpeg"):
        f = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for flt in ("afftdn", "deesser", "loudnorm", "ssim", "hqdn3d", "cas"):
            check(f" {flt} " in f, f"ffmpeg 滤镜 {flt}", "换用 Homebrew 的完整版 ffmpeg")
        e = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        check("libx264" in e, "ffmpeg 编码器 libx264", "换用带 libx264 的 ffmpeg")
    check(shutil.which(whisper_cli()) is not None, "whisper-cli", "brew install whisper-cpp")
    check(WHISPER_MODEL.exists(), f"转写模型 {WHISPER_MODEL.name}", "运行 setup.sh")
    check(RVM_MODEL.exists(), "抠像模型（只有换背景时用）", "运行 setup.sh")
    check(GSAP.exists(), "GSAP", "运行 setup.sh")
    check(shutil.which("node") is not None, "Node.js", "brew install node")
    check(hyperframes_cmd()[0] != "npx", "HyperFrames", "npm install -g hyperframes@0.8.188")
    for name, (cands, _, _) in FONTS.items():
        hit = next((c for c in cands if (FONTS_DIR / c).exists()), None)
        check(hit is not None, f"字体 {name}（{hit or cands[-1]}）", "运行 setup.sh")
    check((HOME / "music/Wholesome.mp3").exists(), "默认配乐 Wholesome", "运行 setup.sh")
    try:
        import numpy, cv2, soundfile, fontTools, onnxruntime  # noqa: F401
        check(int(cv2.__version__.split(".")[0]) < 5, f"OpenCV {cv2.__version__}（需要 4.x，5.x 没有人脸检测器）", "pip install 'opencv-python<5'")
    except ImportError as ex:
        check(False, f"Python 依赖 {ex.name}", "运行 setup.sh")
    print("\n全部就绪" if not bad else f"\n还缺 {len(bad)} 项")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
