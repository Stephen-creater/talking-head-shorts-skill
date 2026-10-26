"""公共设置：工程目录结构、外部工具和素材的位置。

工程目录（任意位置，一条视频一个）：
  edl.json        剪辑表（唯一需要手写的文件，字段见 docs/剪辑表字段.md）
  sources/        原始素材：口播视频、要插进片子的照片
  stills/         图形里用到的图片（照片墙、人物出场），渲染时自动拷进 hf/assets
  analysis/       prepare.py 生成：统一后的原片、降噪人声、逐字转写、短语表、人脸位置、联系表
  build/          中间产物：时间线、底片、人声、混音、草稿成片、质检报告
  hf/             HyperFrames 图形工程（自动生成）
  out/            交付：成片.mp4、封面.jpg

外部资源默认放在 ~/.cache/talking-head-shorts（setup.sh 负责下载），可用环境变量 THS_HOME 改位置。
"""
import json, os, glob, shutil, subprocess
from pathlib import Path

W, H = 1080, 1920
SKILL = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("THS_HOME", Path.home() / ".cache/talking-head-shorts"))
FONTS_DIR = Path(os.environ.get("THS_FONTS", HOME / "fonts"))
WHISPER_MODEL = Path(os.environ.get("THS_WHISPER_MODEL", HOME / "models/ggml-large-v3-turbo.bin"))
RVM_MODEL = HOME / "models/rvm_mobilenetv3_fp32.onnx"
GSAP = HOME / "js/gsap.min.js"
HYPERFRAMES_VERSION = "0.8.188"


def load_edl(proj):
    return json.load(open(Path(proj) / "edl.json"))


def resolve(proj, p):
    """剪辑表里的路径：绝对路径原样；$HOME/ 开头指外部资源目录；其余相对工程目录。"""
    p = str(p)
    if p.startswith("$HOME/"):
        return HOME / p[6:]
    q = Path(p).expanduser()
    return q if q.is_absolute() else Path(proj).resolve() / q


def whisper_cli():
    return shutil.which("whisper-cli") or "whisper-cli"


def hyperframes_cmd():
    """优先用全局装好的 hyperframes（不联网），否则用 npx 固定版本。"""
    exe = shutil.which("hyperframes")
    if exe:
        return [exe]
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    js = Path(root) / "hyperframes/bin/hyperframes.mjs"
    if js.exists():
        return ["node", str(js)]
    return ["npx", "-y", f"hyperframes@{HYPERFRAMES_VERSION}"]


def chrome_shell():
    """HyperFrames 自带下载的 chrome-headless-shell；找不到就交给 HyperFrames 自己处理。"""
    if os.environ.get("HYPERFRAMES_BROWSER_PATH"):
        return os.environ["HYPERFRAMES_BROWSER_PATH"]
    hits = sorted(glob.glob(str(Path.home() / ".cache/hyperframes/chrome/chrome-headless-shell/*/*/chrome-headless-shell")))
    return hits[-1] if hits else None


def probe_size(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
    w, h = r.split(",")[:2]
    return int(w), int(h)


def probe_duration(video):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                capture_output=True, text=True).stdout)
