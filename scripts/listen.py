"""听一段原片：按真实的有声区间切开，每段单独再转写一遍，打印「起-止: 文字」。
whisper 的整片逐字时间常偏 0.3～1 秒，挑哪一遍、在哪下刀、skip 写多少，都以这里的结果为准。
用法：python scripts/listen.py <工程目录> <起秒> <止秒> [--prompt 提示词]
"""
import subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import WHISPER_MODEL, whisper_cli  # noqa: E402
from edit import speech_map, project_paths  # noqa: E402


def main(proj, a, b, prompt=None):
    proj = Path(proj).resolve()
    pp = project_paths(proj)
    regs, _ = speech_map(pp["voice"])
    with tempfile.TemporaryDirectory() as d:
        w = Path(d) / "r.wav"
        for x, y in [r for r in regs if r[1] > a and r[0] < b]:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0, x - 0.05)), "-to", str(y + 0.05),
                            "-i", str(pp["voice"]), "-ac", "1", "-ar", "16000", str(w)], check=True)
            cmd = [whisper_cli(), "-m", str(WHISPER_MODEL), "-l", "zh", "-t", "6", "-nt", str(w)]
            if prompt:
                cmd += ["--prompt", prompt]
            t = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().replace("\n", " ")
            print(f"{x:8.2f}-{y:8.2f}: {t}")


if __name__ == "__main__":
    args = sys.argv[1:]
    pr = args[args.index("--prompt") + 1] if "--prompt" in args else None
    main(args[0], float(args[1]), float(args[2]), pr)
