"""字幕：按剪辑表里写好的断句（cap，用 | 分屏，【】标强调词）对齐到她每个字的发音时间，换算成成片时间。
没写 cap 的条目按空格和 11 字上限自动断句。
用法：python scripts/captions.py <工程目录>
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edit import norm, char_range, char_times  # noqa: E402

MAXC = 11


def width(s):
    """按显示宽度计字数：汉字 1，英文字母/数字 0.55。"""
    s = s.replace("【", "").replace("】", "")
    return sum(1 if re.match(r"[一-鿿]", c) else (0.55 if c.strip() else 0.3) for c in s)


def auto_split(text):
    parts, cur = [], ""
    for w in re.split(r"(\s+)", text):
        if not w.strip():
            continue
        if cur and width(cur + w) > MAXC:
            parts.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        parts.append(cur)
    return parts


def build(proj):
    proj = Path(proj)
    tl = json.load(open(proj / "build/timeline.json"))
    from edit import project_paths
    phrases = {p["id"]: p for p in json.load(open(project_paths(proj)["phrases"]))}
    sp = tl["speed"]

    def to_out(ts, seg_list):
        for s in seg_list:
            if s["s_in"] - 0.03 <= ts <= s["s_out"] + 0.03:
                return (s["e_in"] + min(max(ts, s["s_in"]), s["s_out"]) - s["s_in"]) / sp
        # 落在被压缩掉的停顿里：取最近的段边界
        best = min(tl["segments"], key=lambda s: min(abs(ts - s["s_in"]), abs(ts - s["s_out"])))
        edge = best["s_in"] if abs(ts - best["s_in"]) < abs(ts - best["s_out"]) else best["s_out"]
        return (best["e_in"] + edge - best["s_in"]) / sp

    cues = []
    edl_items = json.load(open(proj / "edl.json"))["items"]

    def item_chars(it):
        key = (it["p"], it.get("keep", ""))
        segs_of_item = [g for g in tl["segments"] if any((i["p"], i.get("keep", "")) == key for i in g["items"])]
        p = phrases[it["p"]]
        c0, c1 = char_range(p, it.get("keep", ""))
        return [(to_out(a, segs_of_item), to_out(b, segs_of_item)) for _, a, b in char_times(p, c0, c1)]

    skip = 0
    for idx, it in enumerate(edl_items):
        if skip:
            skip -= 1; continue
        if it.get("nocap"):
            continue
        span = it.get("cap_span", 1)
        group = edl_items[idx:idx + span]
        skip = span - 1
        if True:
            p = phrases[it["p"]]
            chars = [c for g in group for c in item_chars(g)]
            spoken = " ".join(g.get("keep") or phrases[g["p"]]["text"] for g in group)
            cap = it.get("cap") or "|".join(auto_split(spoken))
            screens = [c for c in cap.split("|") if c.strip()]
            total = sum(len(norm(re.sub(r"[【】]", "", c))) for c in screens)
            k = 0
            for sc in screens:
                n = len(norm(re.sub(r"[【】]", "", sc)))
                i0 = round(k * len(chars) / max(total, 1)); i1 = round((k + n) * len(chars) / max(total, 1)) - 1
                i0 = min(i0, len(chars) - 1); i1 = max(min(i1, len(chars) - 1), i0)
                t0, t1 = chars[i0][0], chars[i1][1]
                if it.get("cap_src"):   # 手动指定每屏开口的原片时间（重复、口误多的句子 whisper 对不准）
                    segs_it = [g for g in tl["segments"] if any(i["p"] == it["p"] for i in g["items"])]
                    srcs = it["cap_src"]; si = len([c for c in cues if c["p"] == it["p"]])
                    t0 = to_out(srcs[si], segs_it)
                    t1 = to_out(srcs[si + 1], segs_it) - 0.05 if si + 1 < len(srcs) else t1
                html = re.sub(r"【(.+?)】", r"<b>\1</b>", sc.strip())
                cues.append({"t0": round(t0, 3), "t1": round(t1, 3), "text": html, "p": it["p"],
                             "style": "quote" if it.get("quote") else it.get("cap_style", "")})
                k += n
    cues.sort(key=lambda c: c["t0"])
    # 显示时长：提前 0.06s 出现；和下一条间隔 <0.45s 就一直留到下一条出现；最短 0.9s
    for i, c in enumerate(cues):
        c["t0"] = max(0.0, c["t0"] - 0.06)
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["t0"] if i + 1 < len(cues) else tl["out_dur"]
        end = c["t1"] + 0.22
        if nxt - end < 0.45:
            end = nxt - 0.02
        end = max(end, min(c["t0"] + 0.9, nxt - 0.02))
        c["t1"] = round(min(end, nxt - 0.02), 3)
    json.dump(cues, open(proj / "build/captions.json", "w"), ensure_ascii=False, indent=1)
    # 读速检查
    fast = [(c["text"], round(width(re.sub("<.*?>", "", c["text"])) / max(c["t1"] - c["t0"], 0.01), 1)) for c in cues]
    fast = [f for f in fast if f[1] > 7.0]
    print(f"{len(cues)} 条字幕；读速超过 7 字/秒的 {len(fast)} 条", fast[:8])
    return cues


if __name__ == "__main__":
    build(sys.argv[1])
