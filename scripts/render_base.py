"""按时间线渲染「底片」：人像画面（含推镜、软切）和变速后的人声。

画面：原片先轻降噪抽成帧缓存 → 每个成片帧按时间线找原片帧 → 一次 Lanczos 仿射（推镜+放大到 1080×1920 合成一步，只重采样一次）
      → ffmpeg 锐化、调色、编码成 build/base.mp4（无声）。
声音：按同一份时间线在采样级拼接降噪后的人声，切点做 12ms 等功率交叉淡化，再整体 atempo 变速 → build/voice.wav。
用法：python scripts/render_base.py <工程目录> [--frames-only|--audio-only] [--preview 秒数]
"""
import json, sys, subprocess, math
from pathlib import Path
import numpy as np
import cv2
import soundfile as sf

W, H = 1080, 1920
SW, SH = 544, 960          # 原片尺寸，运行时按 analysis/source.mkv 实测覆盖
SRC = CACHE = VOICE_CLEAN = NFR = None
MATTE, ALPHA, EDGE = None, None, None
# 调色：白墙校成暖白（约 RGB 239,237,230，和片中纸面设计同色），肤色保持自然，饱和度只加 5%
GRADE = ("cas=0.45,"
         "colorbalance=rm=0.016:gm=-0.008:bm=-0.014:rh=0.026:gh=-0.004:bh=-0.02,"
         "curves=master='0/0 0.25/0.25 0.5/0.53 0.75/0.805 0.92/0.968 1/1',"
         "eq=saturation=1.05:contrast=1.02")


def ensure_cache():
    if CACHE.exists() and len(list(CACHE.glob("*.jpg"))) > NFR - 30:
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-vf", "hqdn3d=1.2:1.0:2.5:2.0",
                    "-q:v", "1", "-qmin", "1", str(CACHE / "%05d.jpg")], check=True)


_frame_cache = {}


def src_frame(i):
    i = max(0, min(i, NFR - 1))
    if i not in _frame_cache:
        if len(_frame_cache) > 120:
            _frame_cache.pop(next(iter(_frame_cache)))
        p = CACHE / f"{i+1:05d}.jpg"
        im = cv2.imread(str(p))
        if im is None:
            return src_frame(i - 1)
        bgr = im
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32)
        if MATTE:  # 抠像：人留下，白墙换成纯色底；左右两边的衣服淡出，缩小后不会有生硬的竖直切边
            a = cv2.imread(str(ALPHA / f"{i+1:05d}.png"), cv2.IMREAD_GRAYSCALE)
            a = a if a is not None else np.full(im.shape[:2], 255, np.uint8)
            # 她举给镜头看的东西（橘子、口罩）抠像模型会当成背景：白墙是灰白的，颜色鲜艳或很深的地方一律算前景
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            obj = ((hsv[..., 1] > 70) | (hsv[..., 2] < 120)).astype(np.uint8) * 255
            obj = cv2.morphologyEx(obj, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            obj = cv2.morphologyEx(obj, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
            obj = cv2.GaussianBlur(obj, (5, 5), 0)
            a = np.maximum(a, obj).astype(np.float32) / 255
            a = a * EDGE
            im = im * a[..., None] + np.array(MATTE["bg"], np.float32) * (1 - a[..., None])
        _frame_cache[i] = im
    return _frame_cache[i]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def camera(shots, t_out):
    """成片时间 → (zoom, cx, cy)（原片像素坐标，cy 是眼睛线位置）。"""
    for s in shots:
        if s["o_in"] - 1e-6 <= t_out < s["o_out"] + 1e-6:
            u = (t_out - s["o_in"]) / max(s["o_out"] - s["o_in"], 1e-3)
            z = s["z0"] + (s["z1"] - s["z0"]) * (ease(u) if s.get("ease", True) else u)
            return z, s["cx"], s["cy"]
    s = shots[-1]
    return s["z1"], s["cx"], s["cy"]


def warp(img, z, cx, cy, eye=0.36):
    """把原片按 zoom 和人脸中心裁切并放大到 1080×1920（一次仿射）。
    抠像模式下 zoom 乘上 MATTE["scale"]（<1 即人像缩小）：人贴画面底边、左右居中，四周是纯色底。"""
    if MATTE:
        z = z * MATTE["scale"]
    cw, ch = SW / z, SH / z
    if MATTE and z < 1:
        x0, y0 = (SW - cw) / 2, SH - ch
    else:
        x0 = min(max(cx - cw / 2, 0), SW - cw)
        y0 = min(max(cy - eye * ch, 0), SH - ch)
    s = W / cw
    M = np.array([[s, 0, -x0 * s], [0, s, -y0 * s]], dtype=np.float32)
    if MATTE:
        return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=tuple(float(v) for v in MATTE["bg"]))
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)


def frame_at(tl, segs, t_out, soft):
    """成片时间 → 原片帧（软切处两边交叉混合）。"""
    sp, fps = tl["speed"], tl["fps"]
    te = t_out * sp
    for k, s in enumerate(segs):
        if s["e_in"] - 1e-6 <= te < s["e_out"] + 1e-6:
            ts = s["s_in"] + te - s["e_in"]
            img = src_frame(int(round(ts * fps)))
            # 软切：在切点前后 half 秒（剪辑时间）内与另一侧混合
            half = soft.get(k, 0) / 2
            if half and te > s["e_out"] - half and k + 1 < len(segs):
                nb = segs[k + 1]
                w = 0.5 * (te - (s["e_out"] - half)) / half
                other = src_frame(int(round((nb["s_in"] - (s["e_out"] - te)) * fps)))
                return img * (1 - w) + other * w
            halfp = soft.get(k - 1, 0) / 2
            if halfp and te < s["e_in"] + halfp and k > 0:
                pa = segs[k - 1]
                w = 0.5 + 0.5 * (te - s["e_in"]) / halfp
                other = src_frame(int(round((pa["s_out"] + (te - s["e_in"])) * fps)))
                return img * w + other * (1 - w)
            return img
    return src_frame(int(round(segs[-1]["s_out"] * fps)))


def render_video(proj, preview=None):
    ensure_cache()
    tl = json.load(open(proj / "build/timeline.json"))
    shots = json.load(open(proj / "build/shots.json"))
    segs = tl["segments"]
    soft = {k: s.get("soft_after", 0) for k, s in enumerate(segs) if s.get("soft_after")}
    dur = tl["out_dur"] if not preview else min(preview, tl["out_dur"])
    n = int(math.floor(dur * tl["fps"] + 1e-6))
    out = proj / ("build/base_preview.mp4" if preview else "build/base.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(tl["fps"]), "-i", "-", "-vf", GRADE + ",format=yuv420p",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-tune", "film",
                           "-g", "30", "-keyint_min", "30",   # 每秒一个关键帧：HyperFrames 逐帧跳转取画面，关键帧稀会卡帧
                           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                           str(out)], stdin=subprocess.PIPE)
    for k in range(n):
        t = k / tl["fps"]
        img = frame_at(tl, segs, t, soft)
        z, cx, cy = camera(shots, t)
        o = warp(img, z, cx, cy)
        ff.stdin.write(np.clip(o, 0, 255).astype(np.uint8).tobytes())
        if k % 300 == 0:
            print(f"  画面 {k}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("写出", out)


def render_audio(proj):
    tl = json.load(open(proj / "build/timeline.json"))
    x, sr = sf.read(VOICE_CLEAN)
    segs = tl["segments"]
    xf = int(sr * 0.012)
    parts = []
    for k, s in enumerate(segs):
        a, b = int(round(s["s_in"] * sr)), int(round(s["s_out"] * sr))
        parts.append(x[a:b].copy())
    # 等长拼接（保证和画面帧数一致），切点两侧各 12ms 等功率淡入淡出
    out = []
    for k, p in enumerate(parts):
        if len(p) > 2 * xf:
            ramp = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
            if k > 0:
                p[:xf] *= ramp
            if k < len(parts) - 1:
                p[-xf:] *= ramp[::-1]
        out.append(p)
    y = np.concatenate(out)
    tmp = proj / "build/voice_edit.wav"
    sf.write(tmp, y, sr, subtype="PCM_24")
    sp = tl["speed"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", f"atempo={sp}", "-ar", "48000",
                    "-c:a", "pcm_s24le", str(proj / "build/voice.wav")], check=True)
    d = sf.info(proj / "build/voice.wav").duration
    print(f"人声 {d:.3f}s（时间线 {tl['out_dur']:.3f}s）")


if __name__ == "__main__":
    if sys.argv[1] == "--print-grade":   # 给试算抠像底色用
        print(GRADE); sys.exit()
    proj = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(Path(__file__).parent))
    from edit import project_paths
    _pp = project_paths(proj)
    SRC, CACHE, VOICE_CLEAN = _pp["source"], _pp["frames"], _pp["voice"]
    from common import probe_size
    SW, SH = probe_size(SRC)
    MATTE = json.load(open(proj / "edl.json")).get("matte")
    ALPHA = proj / "build/alpha"
    if MATTE:
        MATTE["bg"] = [int(MATTE["bg_pre"][k:k + 2], 16) for k in (1, 3, 5)]
        if not (ALPHA.exists() and any(ALPHA.iterdir())):
            sys.exit("开了抠像（edl 里有 matte）但还没有 build/alpha：先运行 python scripts/matte.py <工程目录>")
        EDGE = np.ones((SH, SW), np.float32)
        k = max(8, int(SW * 0.13))   # 两侧各约 13% 宽度淡出
        ramp = np.sin(np.linspace(0, np.pi / 2, k, dtype=np.float32)) ** 2
        EDGE[:, :k] *= ramp; EDGE[:, -k:] *= ramp[::-1]
    NFR = int(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(SRC)],
                                   capture_output=True, text=True).stdout) * 30)
    args = sys.argv[2:]
    prev = float(args[args.index("--preview") + 1]) if "--preview" in args else None
    if "--frames-only" not in args:
        render_audio(proj)
    if "--audio-only" not in args:
        render_video(proj, prev)
