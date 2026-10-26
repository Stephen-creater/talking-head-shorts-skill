"""一键出片：剪辑表 → 时间线 → 机位 → 字幕 →（抠像）→ 底片 → 混音 → 图形 → 渲染合成 → 质检。
改了剪辑表（items、skip、frame）要从 edit 开始；只改了图形/字幕/配乐可以 --from captions / hf / mix 省掉重渲底片。
用法：python scripts/build.py <工程目录> [--name v1] [--from edit|captions|matte|base|mix|hf|render|qa]
产物：build/<name>.mp4（高码率草稿）和 build/qa_<name>/（质检报告、回听转写、联系表）
"""
import os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import hyperframes_cmd, chrome_shell, load_edl  # noqa: E402

HERE = Path(__file__).parent
STAGES = ["edit", "captions", "matte", "base", "mix", "hf", "render", "qa"]


def py(script, *args):
    subprocess.run([sys.executable, str(HERE / script), *map(str, args)], check=True)


def render(proj, name):
    env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1", HYPERFRAMES_NO_TELEMETRY="1")
    if chrome_shell():
        env["HYPERFRAMES_BROWSER_PATH"] = chrome_shell()
    silent = proj / f"build/{name}_silent.mp4"
    log = proj / f"build/render_{name}.log"
    with open(log, "w") as f:   # HyperFrames 日志很长，存文件；失败时打印最后几行
        r = subprocess.run([*hyperframes_cmd(), "render", ".", "-o", str(silent), "--fps", "30", "--quality", "high",
                            "--workers", os.environ.get("THS_WORKERS", "4"), "--quiet"], cwd=proj / "hf", env=env,
                           stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit("HyperFrames 渲染失败：\n" + "".join(open(log).readlines()[-30:]))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(proj / "build/mix.wav"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30",
                    "-g", "60", "-bf", "2", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest",
                    str(proj / f"build/{name}.mp4")], check=True)
    silent.unlink()


def main(argv):
    proj = Path(argv[0]).resolve()
    name = argv[argv.index("--name") + 1] if "--name" in argv else "draft"
    start = argv[argv.index("--from") + 1] if "--from" in argv else "edit"
    edl = load_edl(proj)
    todo = STAGES[STAGES.index(start):]
    for st in todo:
        t0 = time.time()
        print(f"\n== {st} ==", flush=True)
        if st == "edit":
            py("edit.py", proj); py("shots.py", proj)
        elif st == "captions":
            py("captions.py", proj)
        elif st == "matte":
            if edl.get("matte"):
                py("matte.py", proj)
            else:
                print("没开抠像，跳过")
        elif st == "base":
            py("render_base.py", proj)
        elif st == "mix":
            py("mix.py", proj)
        elif st == "hf":
            py("hf_build.py", proj)
        elif st == "render":
            render(proj, name)
        elif st == "qa":
            py("qa.py", proj, name)
        print(f"({time.time() - t0:.0f}s)")
    print(f"\n草稿：{proj / f'build/{name}.mp4'}\n质检：{proj / f'build/qa_{name}/report.txt'}")


if __name__ == "__main__":
    main(sys.argv[1:])
