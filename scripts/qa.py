"""成片质检（能用代码判的都在这里判，不靠看图）：
  1. 规格：分辨率、帧率、时长、码率、响度、真峰值
  2. 回听：把成片重新转写，和剪辑表里应该说的话逐字对比，找漏字、切掉半个字的地方
  3. 跳切：成片上实测画面切换点，找 1 秒内连切两次的闪帧
  4. 爆音：人声拼接点附近有没有采样突变
  5. 出联系表：每 2 秒一帧，13 帧一张，供人工/评审看
用法：python scripts/qa.py <工程目录> <成片名，如 draft1>
"""
import json, re, subprocess, sys, difflib
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from edit import norm  # noqa: E402
from common import WHISPER_MODEL, whisper_cli  # noqa: E402


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main(proj, name):
    proj = Path(proj).resolve()
    mp4 = proj / f"build/{name}.mp4"
    qa = proj / f"build/qa_{name}"
    qa.mkdir(exist_ok=True)
    rep = []
    # 1 规格
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=codec_name,width,height,r_frame_rate,sample_rate",
            "-of", "json", str(mp4)])
    info = json.loads(r.stdout)
    v = [s for s in info["streams"] if s["codec_name"] == "h264"][0]
    dur = float(info["format"]["duration"])
    r = sh(["ffmpeg", "-v", "info", "-i", str(mp4), "-af", "loudnorm=print_format=json", "-f", "null", "-"]).stderr
    ln = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
    rep.append(f"规格：{v['width']}×{v['height']} {v['r_frame_rate']}fps，{dur:.2f}s，{int(info['format']['bit_rate']) / 1e6:.1f} Mbps，"
               f"{ln['input_i']} LUFS，真峰值 {ln['input_tp']} dBTP")

    # 2 回听
    wav = qa / "audio16k.wav"
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-ac", "1", "-ar", "16000", str(wav)])
    sh([whisper_cli(), "-m", str(WHISPER_MODEL), "-l", "zh", "-mc", "0", "-t", "6",
        "-oj", "-of", str(qa / "asr"), str(wav)])
    asr = json.load(open(qa / "asr.json"))["transcription"]
    heard = "".join(s["text"] for s in asr)
    (qa / "asr.txt").write_text("\n".join(f"[{s['offsets']['from'] / 1000:6.1f}] {s['text'].strip()}" for s in asr))
    edl = json.load(open(proj / "edl.json"))
    from edit import project_paths
    ph = {p["id"]: p for p in json.load(open(project_paths(proj)["phrases"]))}
    want = "".join(it.get("keep") or ph[it["p"]]["text"] for it in edl["items"])
    a, b = norm(want), norm(heard)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    miss = [(a[i1:i2], b[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op in ("delete", "replace") and i2 - i1 >= 2]
    rep.append(f"回听：应说 {len(a)} 字，听到 {len(b)} 字，一致率 {sm.ratio():.3f}；疑似漏/变（≥2 字）{len(miss)} 处：" +
               "；".join(f"「{x}」→「{y}」" for x, y in miss[:20]))

    # 3 跳切 / 闪帧
    r = sh(["ffmpeg", "-v", "info", "-i", str(mp4), "-vf", "select='gt(scene,0.18)',showinfo", "-an", "-f", "null", "-"]).stderr
    cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]
    flash = [(round(c1, 2), round(c2, 2)) for c1, c2 in zip(cuts, cuts[1:]) if c2 - c1 < 1.0]
    rep.append(f"画面切换 {len(cuts)} 次（平均每 {dur / max(len(cuts), 1):.1f}s 一次）；1 秒内连切 {len(flash)} 处：{flash[:12]}")

    # 4 爆音：人声轨在每个拼接点 ±15ms 内的最大跳变
    tl = json.load(open(proj / "build/timeline.json"))
    x, sr = sf.read(proj / "build/voice.wav")
    x = x if x.ndim == 1 else x.mean(1)
    d = np.abs(np.diff(x))
    base = np.percentile(d, 99.9)
    bad = []
    for s in tl["segments"][1:]:
        i = int(s["o_in"] * sr)
        w = d[max(0, i - 720):i + 720]
        if len(w) and w.max() > 3 * base:
            bad.append(round(s["o_in"], 2))
    rep.append(f"人声拼接点 {len(tl['segments']) - 1} 个，疑似爆音 {len(bad)} 个：{bad[:12]}")

    # 5 联系表
    for k in range(int(np.ceil(dur / 26))):
        sh(["ffmpeg", "-v", "error", "-y", "-ss", str(k * 26), "-t", "26", "-i", str(mp4), "-vf",
            "fps=1/2,scale=270:-2,tile=13x1:padding=4:color=white", "-frames:v", "1", str(qa / f"sheet_{k + 1}.jpg")])
    (qa / "report.txt").write_text("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
