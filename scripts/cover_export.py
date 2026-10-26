"""封面导出：把生图模型给的原图（通常 1792×2400 或 768×1024，3:4）缩放到视频号竖版封面 1242×1656，轻锐化，存 JPEG。
用法：python scripts/cover_export.py <原图> <输出.jpg>
"""
import subprocess, sys, tempfile
from pathlib import Path


def main(src, out):
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "c.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                        "scale=1242:1656:force_original_aspect_ratio=increase:flags=lanczos,crop=1242:1656,unsharp=5:5:0.5",
                        str(png)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-q:v", "2", out], check=True)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
