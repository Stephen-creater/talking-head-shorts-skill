"""机位规划：在时间线的切点上决定「换机位（原画↔推近）」还是「软切（同机位 4 帧交叉）」。

规则（伪双机位）：
  - 一个机位至少停 min_shot 秒（成片时间）才允许换；没到时间的切点用软切。
  - 机位在 wide（1.00）和 tight（1.14）之间交替；剪辑表里标 emph 的句子用 1.24 的特写。
  - 长于 5 秒的机位做很慢的推近（+2.5%），画面不死。
  - 全屏图形盖住的时间段里，切点一律硬切、不换机位（反正看不见）。
用法：python scripts/shots.py <工程目录>
"""
import json, sys
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))

ZOOM = {"wide": 1.0, "tight": 1.14, "emph": 1.24}


def face_center(faces, ranges, size=(544, 960)):
    pts = [(x + w / 2, y + h / 2) for t, x, y, w, h in faces if x is not None and any(a <= t <= b for a, b in ranges)]
    if not pts:
        return size[0] / 2, size[1] * 0.36
    a = np.array(pts)
    return float(np.median(a[:, 0])), float(np.median(a[:, 1]))


def plan(proj):
    proj = Path(proj)
    tl = json.load(open(proj / "build/timeline.json"))
    edl = json.load(open(proj / "edl.json"))
    from edit import project_paths
    pp = project_paths(proj)
    faces = json.load(open(pp["faces"]))
    from common import probe_size
    size = probe_size(pp["source"])
    segs = tl["segments"]
    min_shot = edl.get("min_shot", 2.6)
    soft_dur = edl.get("soft_frames", 4) / tl["fps"] * tl["speed"]   # 剪辑时间里的软切长度
    covered = [(g["o_in"], g["o_out"]) for g in edl.get("full_cover", [])]

    def is_covered(t):
        return any(a - 0.05 <= t <= b + 0.05 for a, b in covered)

    # 版式页（人像缩成小窗）期间一律用原画、不换机位
    idx = {it["p"]: n for n, it in enumerate(edl["items"])}
    page_rng = [(idx[pg["from_p"]], idx[pg["to_p"]]) for pg in edl.get("pages", [])]

    def in_page(s):
        return any(a <= idx.get(i["p"], -1) <= b for i in s["items"] for a, b in page_rng)

    shots, cur = [], None
    order = ["wide", "tight"]
    for k, s in enumerate(segs):
        forced = next((i.get("frame") for i in s["items"] if i.get("frame")), None)
        if in_page(s):
            forced = "wide"
            if cur is not None and cur["frame"] == "wide" and in_page(segs[k - 1]):
                segs[k - 1]["soft_after"] = round(soft_dur, 4)
                cur["segs"].append(k); continue
        if cur is None:
            cur = {"segs": [k], "o_in": s["o_in"], "frame": forced or "wide"}
            continue
        cut_t = s["o_in"]
        dur = cut_t - cur["o_in"]
        if is_covered(cut_t):
            cur["segs"].append(k); continue
        want_new = forced is not None and forced != cur["frame"]
        same = forced is not None and forced == cur["frame"]   # 指定了和当前一样的机位：不换，只软切
        if not same and (dur >= min_shot or (want_new and dur >= 1.2)):
            cur["o_out"] = cut_t; shots.append(cur)
            nxt = forced or order[(order.index(cur["frame"]) + 1) % 2 if cur["frame"] in order else 0]
            cur = {"segs": [k], "o_in": cut_t, "frame": nxt}
        else:
            segs[k - 1]["soft_after"] = round(soft_dur, 4)
            cur["segs"].append(k)
    cur["o_out"] = tl["out_dur"]; shots.append(cur)

    out = []
    for sh in shots:
        ranges = [(segs[k]["s_in"], segs[k]["s_out"]) for k in sh["segs"]]
        cx, cy = face_center(faces, ranges, size)
        z = ZOOM[sh["frame"]]
        d = sh["o_out"] - sh["o_in"]
        push = 0.025 if d > 5 else 0.0
        out.append({"o_in": round(sh["o_in"], 4), "o_out": round(sh["o_out"], 4), "frame": sh["frame"],
                    "z0": z, "z1": round(z + push, 4), "cx": round(cx, 1), "cy": round(cy, 1)})
    json.dump(out, open(proj / "build/shots.json", "w"), ensure_ascii=False, indent=1)
    json.dump(tl, open(proj / "build/timeline.json", "w"), ensure_ascii=False, indent=1)
    soft = sum(1 for s in segs if s.get("soft_after"))
    lens = [s["o_out"] - s["o_in"] for s in out]
    print(f"{len(out)} 个机位（换机位 {len(out)-1} 次，软切 {soft} 次），机位时长 中位 {np.median(lens):.1f}s 最短 {min(lens):.1f}s")
    return out


if __name__ == "__main__":
    plan(sys.argv[1])
