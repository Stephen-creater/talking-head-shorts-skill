"""素材准备：把 sources/ 里的口播视频统一成一条原片，并做完剪辑前需要的全部分析。

  1. 拼接、统一成 9:16 / 30fps / 单声道 48kHz → analysis/source.mkv（不放大，原分辨率保留到渲染时一次放大）
  2. 人声降噪、均衡、压缩 → analysis/voice_clean.wav（剪辑和成片都用这条人声）
  3. whisper large-v3-turbo 逐字转写 → analysis/asr.json → 短语表 analysis/phrases.tsv
  4. 每 0.5 秒检测一次人脸 → analysis/faces.json（推镜头时对准脸）
  5. 每 2 秒一帧的联系表（带时间码）→ analysis/sheets/，用来看哪里镜头歪了、举了东西、人离开画面
用法：python scripts/prepare.py <工程目录> [视频1 视频2 …]   （不写视频就用 edl.json 的 "sources"）
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent))
from common import WHISPER_MODEL, whisper_cli, probe_size, probe_duration  # noqa: E402

# 人声处理链：去低频轰鸣 → 轻降噪 → 去闷、提清晰度和空气感 → 去齿音 → 轻压缩
VOICE_CHAIN = ("highpass=f=85:poles=2,highpass=f=85:poles=2,afftdn=nr=10:nf=-50:tn=1,"
               "equalizer=f=220:t=q:w=1.0:g=-1.5,equalizer=f=3200:t=q:w=1.1:g=2.5,equalizer=f=9000:t=h:w=0.7:g=1.5,"
               "deesser=i=0.35:m=0.5:f=0.5,acompressor=threshold=-24dB:ratio=2.5:attack=6:release=90:makeup=3dB:knee=4")


def run(cmd):
    subprocess.run(cmd, check=True)


def target_size(w, h):
    """9:16 竖屏：宽高取偶数；横屏或非 9:16 的素材按高度居中裁成 9:16；宽超过 1080 的缩到 1080。"""
    if abs(w / h - 9 / 16) > 0.01:
        w = int(h * 9 / 16)
    if w > 1080:
        w, h = 1080, 1920
    else:
        h = int(round(w * 16 / 9))
    return w // 2 * 2, h // 2 * 2


def normalize(proj, videos):
    out = proj / "analysis/source.mkv"
    tw, th = target_size(*probe_size(videos[0]))
    args, fv = [], []
    for i, v in enumerate(videos):
        args += ["-i", str(v)]
        fv.append(f"[{i}:v]scale={tw}:{th}:force_original_aspect_ratio=increase:flags=lanczos,crop={tw}:{th},fps=30,setsar=1[v{i}];"
                  f"[{i}:a]aresample=48000,aformat=channel_layouts=mono[a{i}]")
    cat = "".join(f"[v{i}][a{i}]" for i in range(len(videos))) + f"concat=n={len(videos)}:v=1:a=1[v][a]"
    run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fv) + ";" + cat, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-c:a", "pcm_s16le", str(out)])
    print(f"原片：{len(videos)} 段拼成 {tw}×{th}，{probe_duration(out):.1f} 秒")
    return out


def faces(src, out):
    cap = cv2.VideoCapture(str(src))
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    res, i = [], 0
    while True:
        if not cap.grab():
            break
        if i % 15 == 0:
            _, fr = cap.retrieve()
            f = cc.detectMultiScale(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(int(w * 0.22),) * 2)
            if len(f):
                x, y, fw, fh = max(f, key=lambda r: r[2] * r[3]); res.append([round(i / 30, 2), int(x), int(y), int(fw), int(fh)])
            else:
                res.append([round(i / 30, 2), None, None, None, None])
        i += 1
    json.dump(res, open(out, "w"))
    hit = [r for r in res if r[1] is not None]
    print(f"人脸：{len(hit)}/{len(res)} 个采样点检测到")


def sheets(src, outdir, step=2.0, cols=10, rows=3, cell_w=162):
    """联系表：每 step 秒一帧，左上角印时间码（本机 ffmpeg 常没有 drawtext，用 OpenCV 画）。"""
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.jpg"):
        f.unlink()
    cap = cv2.VideoCapture(str(src))
    dur = probe_duration(src)
    ts = np.arange(0, dur, step)
    per = cols * rows
    for k in range(0, len(ts), per):
        tiles = []
        for t in ts[k:k + per]:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            if not ok:
                break
            im = cv2.resize(fr, (cell_w, int(cell_w * fr.shape[0] / fr.shape[1])))
            cv2.rectangle(im, (0, 0), (70, 22), (0, 0, 0), -1)
            cv2.putText(im, f"{int(t // 60)}:{t % 60:04.1f}", (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            tiles.append(im)
        while len(tiles) % cols:
            tiles.append(np.full_like(tiles[0], 255))
        grid = np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(len(tiles) // cols)])
        cv2.imwrite(str(outdir / f"sheet_{k // per + 1:02d}.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"联系表：{(len(ts) + per - 1) // per} 张（每 {step:g} 秒一帧）→ {outdir}")


def main(proj, videos):
    proj = Path(proj).resolve()
    edl = json.load(open(proj / "edl.json"))
    videos = [Path(v).resolve() for v in videos] or [proj / v for v in edl.get("sources", [])]
    if not videos:
        sys.exit("没有素材：在 edl.json 的 sources 里列出口播视频，或在命令行给出")
    a = proj / "analysis"
    a.mkdir(exist_ok=True)
    src = normalize(proj, videos)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(a / "src16k.wav")])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-af", VOICE_CHAIN, "-ar", "48000", "-ac", "1",
         "-c:a", "pcm_s24le", str(a / "voice_clean.wav")])
    print("转写中（large-v3-turbo，约为片长的 1/10）…", flush=True)
    subprocess.run([whisper_cli(), "-m", str(WHISPER_MODEL), "-l", edl.get("language", "zh"), "-mc", "0", "-t", "6", "-ojf",
                    "-of", str(a / "asr"), str(a / "src16k.wav")], check=True, capture_output=True)
    import phrases
    phrases.main(proj)
    faces(src, a / "faces.json")
    sheets(src, a / "sheets")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
