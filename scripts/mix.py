"""混音：人声 + 配乐片段（可按人声自动闪避、可写电平包络）+ 少量音效 → 两遍响度标准化。
配置写在剪辑表 edl.json 的 "music" 里（时间都是成片时间，电平单位 dB；文件路径相对工程目录，$HOME/ 开头指 ~/.cache/talking-head-shorts）：
  clips: [{file, offset, start, end, level, duck?, lift?, fade_in, fade_out, auto:[{from,to,db,ramp}]}]
  sfx:   [{file, t, db}]
用法：python scripts/mix.py <工程目录>
"""
import json, sys, subprocess, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SR = 48000
sys.path.insert(0, str(Path(__file__).parent))
from common import resolve  # noqa: E402


def load(path, offset=0.0, dur=None):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{offset}"]
        if dur:
            cmd += ["-t", f"{dur}"]
        cmd += ["-i", str(path), "-ac", "2", "-ar", str(SR), "-c:a", "pcm_f32le", f.name]
        subprocess.run(cmd, check=True)
        x, _ = sf.read(f.name, dtype="float32")
    return x if x.ndim == 2 else np.stack([x, x], 1)


def db(v):
    return 10 ** (np.asarray(v, dtype=np.float64) / 20)


def smooth(g, attack, release):
    """一阶包络：往下用 attack、往上用 release（单位：样本数，在 1kHz 控制率上算）。"""
    out = np.empty_like(g); y = g[0]
    aa = np.exp(-1 / max(attack, 1)); ar = np.exp(-1 / max(release, 1))
    for i, v in enumerate(g):
        c = aa if v < y else ar
        y = c * y + (1 - c) * v; out[i] = y
    return out


def voice_activity(v, hop=0.001, hold=0.45):
    """1kHz 控制率的「正在说话」标记（短停顿算在说话里，避免音乐在句间忽高忽低）。"""
    n = int(len(v) / (SR * hop))
    blk = v[:n * int(SR * hop)].reshape(n, -1)
    e = 20 * np.log10(np.sqrt((blk ** 2).mean(1)) + 1e-12)
    act = e > -44
    k = int(hold / hop)
    return np.convolve(act.astype(float), np.ones(2 * k + 1), "same") > 0


def last_speech(v):
    act = voice_activity(v, hold=0.0)
    idx = np.nonzero(act)[0]
    return idx[-1] / 1000.0 if len(idx) else len(v) / SR


def fade(x, fi, fo):
    n = len(x)
    if fi > 0:
        k = min(int(fi * SR), n); x[:k] *= (np.sin(np.linspace(0, np.pi / 2, k)) ** 2)[:, None]
    if fo > 0:
        k = min(int(fo * SR), n); x[n - k:] *= (np.cos(np.linspace(0, np.pi / 2, k)) ** 2)[:, None]
    return x


def mix(proj):
    proj = Path(proj)
    edl = json.load(open(proj / "edl.json"))
    m = edl["music"]
    v, _ = sf.read(proj / "build/voice.wav", dtype="float32")
    v = v if v.ndim == 1 else v.mean(1)
    tl = json.load(open(proj / "build/timeline.json"))
    total = tl["out_dur"] + edl.get("end_extra", 7.0)
    N = int(total * SR)
    t_end = last_speech(v)
    print(f"人声最后一个字结束于 {t_end:.3f}s")
    ctx = {"END_SPEECH": t_end, "TOTAL": total}

    def T(x):
        if isinstance(x, str):
            return float(eval(x, {}, ctx))
        return float(x)

    out = np.zeros((N, 2), np.float32)
    out[:min(len(v), N)] += np.stack([v, v], 1)[:N] * float(db(m.get("voice_db", 0)))
    act = voice_activity(v)
    act = np.pad(act, (0, max(0, int(total * 1000) + 10 - len(act))))

    for c in m["clips"]:
        if not resolve(proj, c["file"]).exists():
            print(f"跳过配乐（文件不存在）：{c['file']}")
            continue
        st, en = T(c["start"]), T(c["end"])
        off = T(c.get("offset", 0))
        dur = en - st
        x = load(resolve(proj, c["file"]), off, dur + 0.05)[:int(dur * SR)].copy()
        x = fade(x, c.get("fade_in", 0.03), c.get("fade_out", 0.03))
        n_ms = int(dur * 1000) + 1
        t_ms = st + np.arange(n_ms) / 1000.0
        g = np.full(n_ms, float(c["level"]))
        if c.get("duck"):
            a = act[int(st * 1000):int(st * 1000) + n_ms]
            a = np.pad(a, (0, n_ms - len(a)))
            g = np.where(a, g, g + c.get("lift", 5.0))
            g = smooth(g, 60, 450)
        for p in c.get("auto", []):
            f0, f1, r = T(p["from"]), T(p["to"]), p.get("ramp", 0.15)
            w = np.clip(np.minimum((t_ms - f0) / r + 1, (f1 - t_ms) / r + 1), 0, 1)  # 两头各 r 秒线性过渡
            g = g + w * p["db"]
        gl = db(g).astype(np.float32)
        gl = np.interp(np.arange(len(x)) / SR, np.arange(n_ms) / 1000.0, gl).astype(np.float32)
        i0 = int(round(st * SR)); n = min(len(x), N - i0)
        out[i0:i0 + n] += x[:n] * gl[:n, None]

    for s in m.get("sfx", []):
        x = load(resolve(proj, s["file"]))
        i0 = int(round(T(s["t"]) * SR)); n = min(len(x), N - i0)
        out[i0:i0 + n] += x[:n] * float(db(s.get("db", -20)))

    tmp = proj / "build/mix_raw.wav"
    sf.write(tmp, out, SR, subtype="FLOAT")
    I, TP = m.get("lufs", -15.0), m.get("tp", -1.5)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(tmp), "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    js = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", af + ",aresample=48000", "-c:a", "pcm_s24le",
                    str(proj / "build/mix.wav")], check=True)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(proj / "build/mix.wav"), "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    js2 = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
    print(f"混音完成：{js2['input_i']} LUFS，真峰值 {js2['input_tp']} dBTP，时长 {N / SR:.2f}s")
    json.dump({"end_speech": t_end}, open(proj / "build/mix_info.json", "w"))


if __name__ == "__main__":
    mix(sys.argv[1])
