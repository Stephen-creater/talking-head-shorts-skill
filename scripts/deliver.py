"""交付：把高码率草稿压成发布版（1080×1920，libx264 veryslow CRF 21，AAC 160k，faststart），并报告和草稿的 SSIM。
两分半的片子一般 50～100MB，SSIM ≥ 0.99（肉眼看不出区别）。
用法：python scripts/deliver.py <工程目录> <草稿名，如 v3> [输出文件，默认 out/成片.mp4]
"""
import re, subprocess, sys
from pathlib import Path


def main(proj, name, out=None):
    proj = Path(proj).resolve()
    src = proj / f"build/{name}.mp4"
    out = Path(out) if out else proj / "out/成片.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "veryslow", "-crf", "21",
                    "-tune", "film", "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(out)], check=True)
    r = subprocess.run(["ffmpeg", "-i", str(src), "-i", str(out), "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    ssim = re.findall(r"All:([\d.]+)", r)
    print(f"{out}  {out.stat().st_size / 1e6:.0f}MB  SSIM {ssim[-1] if ssim else '?'}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
