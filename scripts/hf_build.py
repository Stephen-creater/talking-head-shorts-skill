"""生成 HyperFrames 工程（index.html）：底片视频层 + 版式页/揭底/片尾 + 题字金句纸条 + 字幕。
所有图形的出现时间都用「锚点」写在剪辑表里（如 "P41@综合+0.2" = P41 里「综」字发音时刻再晚 0.2 秒），
改剪辑后重跑就自动对齐，不用手调时间。
用法：python scripts/hf_build.py <工程目录>
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edit import norm, char_range, char_times  # noqa: E402
from captions import width  # noqa: E402
import panels  # noqa: E402
import fonts  # noqa: E402
from common import GSAP  # noqa: E402
W, H = 1080, 1920
VARS = {"paper": "#EFEDE6", "halo": "#FBF8F2", "ink": "#2A2230", "ink2": "#5E5662", "ink3": "#9A9298",
        "gold": "#F2B33D", "gold2": "#E3A12F", "amber": "#B8690A", "line": "#D8D2C6"}


class Anchors:
    """短语里每个字的成片时间；锚点写法：P41 / P41.end / P41@综合 / P41@综合.end / 以上再加 ±秒；END±秒。"""

    def __init__(self, proj):
        tl = json.load(open(proj / "build/timeline.json"))
        from edit import project_paths
        ph = {p["id"]: p for p in json.load(open(project_paths(proj)["phrases"]))}
        self.tl, self.sp, self.proj = tl, tl["speed"], proj
        self.chars = {}
        for s in tl["segments"]:
            for it in s["items"]:
                if it["p"] in self.chars:
                    continue
                p = ph[it["p"]]
                c0, c1 = char_range(p, it.get("keep", ""))
                segs = [g for g in tl["segments"] if any(i["p"] == it["p"] for i in g["items"])]
                self.chars[it["p"]] = [(ch, self.out(a, segs), self.out(b, segs)) for ch, a, b in char_times(p, c0, c1)]

    def out(self, ts, segs):
        for s in segs:
            if s["s_in"] - 0.03 <= ts <= s["s_out"] + 0.03:
                return (s["e_in"] + min(max(ts, s["s_in"]), s["s_out"]) - s["s_in"]) / self.sp
        best = min(segs, key=lambda s: min(abs(ts - s["s_in"]), abs(ts - s["s_out"])))
        edge = best["s_in"] if abs(ts - best["s_in"]) < abs(ts - best["s_out"]) else best["s_out"]
        return (best["e_in"] + edge - best["s_in"]) / self.sp

    def __call__(self, a):
        if isinstance(a, (int, float)):
            return float(a)
        a = a.strip()
        m3 = re.match(r"^SE([+\-][\d.]+)?$", a)   # SE = 人声最后一个字结束的时刻
        if m3:
            import mix, soundfile as sf
            v, _ = sf.read(self.proj / "build/voice.wav", dtype="float32")
            return round(mix.last_speech(v if v.ndim == 1 else v.mean(1)) + (float(m3.group(1)) if m3.group(1) else 0.0), 3)
        m2 = re.match(r"^END([+\-][\d.]+)?$", a)
        if m2:
            return round(self.tl["out_dur"] + (float(m2.group(1)) if m2.group(1) else 0.0), 3)
        m = re.match(r"^(P\d+)(?:@([^+\-.]+))?(\.end)?([+\-][\d.]+)?$", a)
        if not m:
            raise ValueError("锚点写法不对：" + a)
        p, word, end, off = m.groups()
        lst = self.chars[p]
        if word:
            s = "".join(c for c, _, _ in lst)
            i = s.find(norm(word))
            if i < 0:
                raise ValueError(f"{p} 里没有「{word}」")
            t = lst[i + len(norm(word)) - 1][2] if end else lst[i][1]
        else:
            t = lst[-1][2] if end else lst[0][1]
        return round(t + (float(off) if off else 0.0), 3)


CSS = """
:root{%(vars)s}
html,body{margin:0;background:var(--paper);}
#main{position:relative;width:1080px;height:1920px;overflow:hidden;}
#paper{position:absolute;inset:0;background:var(--paper) url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .35  0 0 0 0 .28  0 0 0 0 .2  0 0 0 .55 0'/></filter><rect width='240' height='240' filter='url(%%23n)' opacity='.09'/></svg>\");z-index:0;}
#vwrap{position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:2;transform-origin:0 0;}
#bgv{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;}
#freeze{position:absolute;left:0;top:0;width:1080px;height:1920px;opacity:0;}
.cap{position:absolute;left:40px;width:960px;top:1262px;height:132px;z-index:60;display:flex;align-items:center;justify-content:center;}
.cap .ci{display:block;font-family:"Sans";font-weight:900;font-size:74px;line-height:1.1;color:var(--ink);text-align:center;white-space:nowrap;
  letter-spacing:.01em;-webkit-text-stroke:14px var(--halo);paint-order:stroke fill;
  filter:drop-shadow(0 3px 10px rgba(60,40,20,.20));}
.cap .ci b{color:var(--amber);font-weight:900;}
.cap.quote .ci{font-family:"Kai";font-weight:500;font-size:78px;}
.layer{position:absolute;inset:0;}
"""


def build(proj):
    proj = Path(proj)
    edl = json.load(open(proj / "edl.json"))
    tl = json.load(open(proj / "build/timeline.json"))
    caps = json.load(open(proj / "build/captions.json"))
    A = Anchors(proj)
    end_extra = edl.get("end_extra", 7.0)
    total = round(tl["out_dur"] + end_extra, 3)
    vd = tl["out_dur"]
    hf = proj / "hf"
    (hf / "assets").mkdir(parents=True, exist_ok=True)
    if not GSAP.exists():
        sys.exit(f"缺 {GSAP}：先运行 setup.sh")
    shutil.copy(GSAP, hf / "assets/gsap.min.js")
    # 图形里用到的图片（照片墙、人物出场）统一放在工程的 stills/ 里
    for f in (proj / "stills").glob("*"):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            shutil.copy(f, hf / "assets" / f.name)
    base = proj / "build/base.mp4"
    if base.exists():
        dst = hf / "assets/base.mp4"
        if not dst.exists() or dst.stat().st_mtime < base.stat().st_mtime:
            shutil.copy(base, dst)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.05", "-i", str(base), "-frames:v", "1", "-q:v", "1",
                        str(hf / "assets/freeze.jpg")], check=True)
    (hf / "hyperframes.json").write_text(json.dumps({
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": False}}, indent=1))

    body, js = [], []
    css = [fonts.font_face_css() + CSS % {"vars": "".join(f"--{k}:{v};" for k, v in {**VARS, **edl.get("vars", {})}.items())}]
    body.append(f'<div id="paper" class="clip" data-start="0" data-duration="{total}" data-track-index="0"></div>')
    body.append('<div id="vwrap">'
                f'<video id="bgv" src="assets/base.mp4" data-start="0" data-duration="{vd}" data-track-index="1" muted playsinline></video>'
                '<img id="freeze" src="assets/freeze.jpg"></div>')
    js.append('tl.set("#vwrap",{scale:1,x:0,y:0,clipPath:"inset(0px 0px 0px 0px)"},0);tl.set("#freeze",{opacity:0},0);')

    ctx = {"A": A, "W": W, "H": H, "total": total, "tl": tl, "proj": proj, "hf": hf}
    for k, ov in enumerate(edl.get("overlays", [])):
        h_, c_, j_ = panels.render(ov, k, ctx)
        body.append(h_); css.append(c_); js.append(j_)

    # —— 字幕（题字、金句、大字出现的时段让开）——
    hide = [(A(a), A(b)) for a, b in edl.get("caption_hide", [])]
    n = 0
    for i, c in enumerate(caps):
        mid = (c["t0"] + c["t1"]) / 2
        if any(a <= mid <= b for a, b in hide) or c["t0"] >= vd:
            continue
        d = round(min(c["t1"], vd) - c["t0"], 3)
        wpx = 74 * width(re.sub("<.*?>", "", c["text"]))
        fs = f' style="font-size:{max(60, int(74 * 880 / wpx))}px"' if wpx > 880 else ""
        cls = "clip cap quote" if c.get("style") == "quote" else "clip cap"
        body.append(f'<div id="cap{i}" class="{cls}" data-start="{c["t0"]}" data-duration="{d}" data-track-index="{20 + n % 2}">'
                    f'<span class="ci" id="ci{i}"{fs}>{c["text"]}</span></div>')
        js.append(f'tl.fromTo("#ci{i}",{{opacity:0,y:8}},{{opacity:1,y:0,duration:0.14,ease:"power2.out"}},{c["t0"]:.3f});')
        n += 1

    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{edl.get("title", "talking-head-shorts")}</title>
<style>{''.join(css)}</style></head>
<body>
<div id="main" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{total}">
{chr(10).join(body)}
</div>
<script src="assets/gsap.min.js"></script>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
tl.set({{}}, {{}}, {total});
window.__timelines["main"] = tl;
</script>
</body></html>"""
    (hf / "index.html").write_text(page)
    fonts.main(hf)
    print(f"HyperFrames 工程已生成：{n} 条字幕，{len(edl.get('overlays', []))} 个图形，总长 {total}s")
    return total


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve())
