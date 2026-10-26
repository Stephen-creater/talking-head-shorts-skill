"""剪辑时间线：把剪辑表（edl.json）变成精确到帧的时间线（timeline.json）。

三套时间：
  原片时间 src   —— analysis/source.mkv（统一后的原片）里的秒数
  剪辑时间 edit  —— 按剪辑表拼接后、变速前的秒数
  成片时间 out   —— 变速后的秒数 = edit / speed

切点规则：
  1. 每段的入点、出点先按逐字时间粗定，再贴到真实的「有声 / 无声」边界上（10ms 精度），保证不切字。
  2. 相邻两段在原片里连着、中间停顿又不长，就不切，原样保留（画面不跳）。
  3. 需要切的地方，只保留 gap 秒的停顿（前段留尾音、后段留起音），其余剪掉。
用法：python scripts/edit.py <工程目录>
"""
import json, sys, re
from pathlib import Path
import numpy as np
import soundfile as sf

HOP = 0.01


def speech_map(wav, thr_db=-41.0, min_gap=0.12, min_speech=0.06):
    """返回 [(起, 止)] 有声区间（秒）。阈值按降噪后的人声定。"""
    x, sr = sf.read(wav)
    if x.ndim > 1:
        x = x.mean(1)
    win = int(sr * 0.02); hop = int(sr * HOP)
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = 20 * np.log10(np.sqrt((x[idx] ** 2).mean(1)) + 1e-12)
    on = rms > thr_db
    regs = []; i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            regs.append([i * HOP, j * HOP + 0.02]); i = j
        else:
            i += 1
    merged = []
    for a, b in regs:  # 合并很短的缝
        if merged and a - merged[-1][1] < min_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged if b - a >= min_speech], rms


def norm(s):
    return re.sub(r"[\s，。、！？,.!?]", "", s).lower()


def char_range(phrase, keep):
    """在短语的逐字列表里找到 keep 对应的第一个和最后一个字（token）。"""
    toks = phrase["chars"]
    if not keep:
        return 0, len(toks) - 1
    flat = ""; owner = []
    for k, (t, _, _) in enumerate(toks):
        for ch in norm(t):
            flat += ch; owner.append(k)
    pos = flat.find(norm(keep))
    if pos < 0:
        raise ValueError(f"{phrase['id']} 里找不到「{keep}」：{phrase['text']}")
    return owner[pos], owner[pos + len(norm(keep)) - 1]


_REGS = {}
VOICE = {"path": None}   # 当前工程的降噪人声（由各脚本按 edl 设置）


def project_paths(proj):
    """工程里各素材的位置（默认是 prepare.py 生成的那一套；edl 里写同名字段可改，路径相对工程目录）。"""
    from common import resolve
    proj = Path(proj).resolve()
    e = json.load(open(proj / "edl.json"))
    pp = {"source": proj / "analysis/source.mkv", "phrases": proj / "analysis/phrases.json",
          "faces": proj / "analysis/faces.json", "voice": proj / "analysis/voice_clean.wav", "frames": proj / "build/src_frames"}
    for k in ("source", "phrases", "faces", "voice", "frames"):
        if e.get(k):
            pp[k] = resolve(proj, e[k])
    VOICE["path"] = str(pp["voice"])
    return pp


def char_times(phrase, c0, c1, wav=None):
    """短语第 c0～c1 个 token 展开成逐字的原片时间 [(字, 起, 止)]。
    whisper 的 token 时间有两个毛病：几个 token 挤在同一时刻、token 起点落在前面的停顿里。
    这里把挤在一起的字在前后可信时刻之间均分，并把落在停顿里的起点挪到下一段有声的开头。"""
    wav = wav or VOICE["path"]
    if wav not in _REGS:
        _REGS[wav] = speech_map(wav)[0]
    regs = _REGS[wav]
    chars = []
    for t, a, b in phrase["chars"][c0:c1 + 1]:
        s = norm(t) or t
        n = max(len(s), 1)
        for j in range(n):
            chars.append([s[j] if j < len(s) else "", a + (b - a) * j / n, a + (b - a) * (j + 1) / n])
    # 起点挪出停顿
    for c in chars:
        inside = [r for r in regs if r[0] - 0.02 <= c[1] <= r[1]]
        if not inside:
            nxt = [r[0] for r in regs if r[0] > c[1]]
            if nxt and nxt[0] < phrase["chars"][c1][2] + 0.3:
                c[1] = nxt[0]
    # 单调 + 挤在一起的均分
    k = 0
    while k < len(chars):
        j = k
        while j + 1 < len(chars) and chars[j + 1][1] - chars[k][1] < 0.06 * (j + 1 - k):
            j += 1
        if j > k:
            nxt = chars[j + 1][1] if j + 1 < len(chars) else max(chars[j][2], chars[k][1] + 0.18 * (j - k + 1))
            span = max(nxt - chars[k][1], 0.12 * (j - k + 1))
            for q in range(k, j + 1):
                chars[q][1] = chars[k][1] + span * (q - k) / (j - k + 1)
        k = j + 1
    for q in range(len(chars)):
        chars[q][1] = max(chars[q][1], chars[q - 1][1] + 0.04) if q else chars[q][1]
        chars[q][2] = chars[q + 1][1] if q + 1 < len(chars) else max(chars[q][2], chars[q][1] + 0.12)
    return [tuple(c) for c in chars]


def snap_start(t, regs, look_back=0.35, look_fwd=0.65):
    """把粗入点贴到最近的有声区间起点（whisper 的字时间常偏 0.3～1 秒，取「起点离得最近」的那段）。"""
    cands = [r for r in regs if t - look_back - 0.6 <= r[0] <= t + look_fwd]
    inside = [r for r in regs if r[0] <= t <= r[1]]
    if inside and t - inside[0][0] < 0.25:
        return inside[0][0]
    if not cands:
        return inside[0][0] if inside else t
    return min(cands, key=lambda r: abs(r[0] - t))[0]


def snap_end(t, regs, look_back=0.30, look_fwd=0.35):
    cands = [r for r in regs if r[1] > t - look_back and r[0] < t + look_fwd]
    if not cands:
        return t
    return cands[-1][1]


def quiet_point(a, b, rms):
    """a~b 之间能量最低的时刻（用于在连读的两个字之间下刀）。"""
    i0, i1 = int(a / HOP), max(int(b / HOP), int(a / HOP) + 1)
    seg = rms[i0:i1]
    return (i0 + int(np.argmin(seg))) * HOP if len(seg) else a


def build(proj):
    proj = Path(proj)
    edl = json.load(open(proj / "edl.json"))
    root = proj.parent
    pp = project_paths(proj)
    phrases = {p["id"]: p for p in json.load(open(pp["phrases"]))}
    order = list(phrases)
    regs, rms = speech_map(pp["voice"])
    speed = edl["speed"]; gap_def = edl.get("gap", 0.32)

    # 1) 每条剪辑表条目 → 精确的有声起止
    items = []
    for it in edl["items"]:
        p = phrases[it["p"]]
        c0, c1 = char_range(p, it.get("keep", ""))
        toks = p["chars"]
        a, b = toks[c0][1], toks[c1][2]
        # 入点：前面还有同一句的字 → 在字缝里找最安静处；否则贴有声起点
        if c0 > 0:
            a = quiet_point(toks[c0 - 1][2] - 0.05, a + 0.05, rms)
        else:
            a = snap_start(a, regs)
        if c1 < len(toks) - 1:
            b = quiet_point(b - 0.05, toks[c1 + 1][1] + 0.05, rms)
        else:
            b = snap_end(b, regs)
        # whisper 常把句首/句尾的长停顿算进 token：按真实有声区间把两头的静音收掉
        inside = [r for r in regs if r[1] > a + 0.02 and r[0] < b - 0.02]
        if inside:
            if inside[0][0] > a:
                a = inside[0][0]
            if inside[-1][1] < b:
                b = inside[-1][1]
        items.append({**it, "s_in": round(a, 3), "s_out": round(b, 3), "text": it.get("keep") or p["text"],
                      "partial_in": c0 > 0, "partial_out": c1 < len(toks) - 1})

    # 2) 相邻条目之间：连着就并，不连就切，切的地方只留 gap 秒停顿
    def room_before(t):  # t 之前有多少安静
        prev = [r[1] for r in regs if r[1] < t - 0.02]
        return t - prev[-1] if prev else t

    def room_after(t):
        nxt = [r[0] for r in regs if r[0] > t + 0.02]
        return nxt[0] - t if nxt else 10.0

    def head(it):
        if it["partial_in"]:
            return 0.0
        return max(0.0, min(it.get("head", 0.09), room_before(it["s_in"]) - 0.02))

    segs, cur = [], None
    for k, it in enumerate(items):
        nxt = items[k + 1] if k + 1 < len(items) else None
        if cur is None:
            cur = {"s_in": round(it["s_in"] - head(it), 3), "items": []}
        cur["items"].append(it)
        gap = it.get("gap_after", gap_def)
        if nxt is not None and not it.get("cut_after") and not it["partial_out"] and not nxt["partial_in"] \
                and order.index(nxt["p"]) == order.index(it["p"]) + 1 \
                and nxt["s_in"] - it["s_out"] <= gap + 0.12:
            continue  # 原片里本来就连着，不切
        if it["partial_out"]:
            tail = 0.03
        elif nxt is None:
            tail = it.get("tail", 0.45)
        else:
            tail = max(0.10, gap - head(nxt))
        tail = max(0.0, min(tail, room_after(it["s_out"]) - 0.02)) if not it["partial_out"] else tail
        cur["s_out"] = round(it["s_out"] + tail, 3)
        segs.append(cur); cur = None

    # 2a) 剪辑表里标了 skip 的原片区间（口误、重复说了几遍）直接挖掉
    cut = []
    for s in segs:
        pieces = [[s["s_in"], s["s_out"]]]
        for it in s["items"]:
            for a, b in it.get("skip", []):
                nxt = []
                for x, y in pieces:
                    if b <= x or a >= y:
                        nxt.append([x, y])
                    else:
                        if a > x + 0.05:
                            nxt.append([x, a])
                        if b < y - 0.05:
                            nxt.append([b, y])
                pieces = nxt
        cut += [{"s_in": round(x, 3), "s_out": round(y, 3), "items": s["items"]} for x, y in pieces]
    segs = cut

    # 2b) 段内的长停顿（她说话常停 1～3 秒）也要压到 gap，段在这里一分为二
    max_pause = edl.get("max_pause", 0.55)
    split = []
    for s in segs:
        a = s["s_in"]
        inner = [(r1[1], r2[0]) for r1, r2 in zip(regs, regs[1:])
                 if r1[1] > s["s_in"] + 0.05 and r2[0] < s["s_out"] - 0.05 and r2[0] - r1[1] > max_pause]
        for (q0, q1) in inner:
            g = s["items"][0].get("gap_inner", gap_def)
            keep_tail = min(0.18, g * 0.55); keep_head = max(0.06, g - keep_tail)
            split.append({"s_in": a, "s_out": round(q0 + keep_tail, 3), "items": s["items"], "inner": True})
            a = round(q1 - keep_head, 3)
        split.append({"s_in": a, "s_out": s["s_out"], "items": s["items"]})
    segs = split

    # 2c) 切点对齐到原片帧格（1/fps 秒），画面和声音按同一组整数帧拼接，永不漂移
    fps = edl.get("fps", 30)
    for s in segs:
        s["s_in"] = round(round(s["s_in"] * fps) / fps, 6)
        s["s_out"] = round(round(s["s_out"] * fps) / fps, 6)
    segs = [s for s in segs if s["s_out"] - s["s_in"] >= 2 / fps]

    # 3) 剪辑时间、成片时间
    t = 0.0
    for i, s in enumerate(segs):
        s["id"] = f"G{i+1:03d}"
        s["e_in"] = round(t, 4); t += s["s_out"] - s["s_in"]; s["e_out"] = round(t, 4)
        s["o_in"] = round(s["e_in"] / speed, 4); s["o_out"] = round(s["e_out"] / speed, 4)
    tl = {"speed": speed, "fps": edl.get("fps", 30), "edit_dur": round(t, 4), "out_dur": round(t / speed, 4),
          "segments": segs}
    (proj / "build").mkdir(exist_ok=True)
    json.dump(tl, open(proj / "build/timeline.json", "w"), ensure_ascii=False, indent=1)
    return tl


def src_to_out(tl, ts):
    """原片时间 → 成片时间（不在保留段里返回 None）。"""
    for s in tl["segments"]:
        if s["s_in"] - 1e-6 <= ts <= s["s_out"] + 1e-6:
            return (s["e_in"] + ts - s["s_in"]) / tl["speed"]
    return None


if __name__ == "__main__":
    tl = build(sys.argv[1])
    segs = tl["segments"]
    print(f"{len(segs)} 段，剪辑后 {tl['edit_dur']:.1f}s，成片 {tl['out_dur']:.1f}s")
    for s in segs:
        print(f"{s['id']} 原片 {s['s_in']:7.2f}-{s['s_out']:7.2f}  成片 {s['o_in']:6.2f}-{s['o_out']:6.2f}  " +
              " / ".join(i["text"] for i in s["items"]))
