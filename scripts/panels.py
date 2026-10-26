"""图形元件库：每种图形一个函数，返回 (html, css, js)。时间一律用锚点 A("P41@综合")。

设计语言（完整说明见 docs/设计规范.md）：
  - 背后的墙调成纸色（或抠像换成纯色底），纸面版式和人物画面是同一张纸；
  - 墨色字 + 纸白描边；全片只有一个强调色暖金；
  - 宋体做标题和金句，黑体做信息，Instrument Serif 斜体 / Caveat 手写做西文，霞鹜文楷做「别人说的话」和签名；
  - 动效只用缓出位移、淡入和画线（0.3～0.6 秒），不弹跳、不闪、不旋转。
"""
import json
from pathlib import Path

EASE = '"power3.out"'
SWAY = '"power3.inOut"'


def _clip(cid, t0, t1, track, inner, z=30, extra=""):
    return (f'<div id="{cid}" class="clip layer" data-start="{t0:.3f}" data-duration="{max(t1 - t0, 0.05):.3f}" '
            f'data-track-index="{track}" style="z-index:{z};{extra}">{inner}</div>')


def _in(sel, t, y=24, d=0.45, x=0):
    return (f'tl.fromTo("{sel}",{{opacity:0,y:{y},x:{x}}},{{opacity:1,y:0,x:0,duration:{d},ease:{EASE}}},{t:.3f});')


def _out(sel, t, d=0.3):
    return f'tl.fromTo("{sel}",{{opacity:1}},{{opacity:0,duration:{d},ease:"power2.in",immediateRender:false}},{t:.3f});'


def _draw(sel, t, d=0.5, origin="0% 50%"):
    return (f'tl.fromTo("{sel}",{{scaleX:0,transformOrigin:"{origin}"}},{{scaleX:1,duration:{d},ease:{SWAY}}},{t:.3f});')


def _wipe(sel, t, d=0.8):
    """从左往右擦出（写字感）。"""
    return (f'tl.fromTo("{sel}",{{clipPath:"inset(-20% 100% -20% 0%)"}},{{clipPath:"inset(-20% 0% -20% 0%)",'
            f'duration:{d},ease:"power1.inOut"}},{t:.3f});')


LOWER = 'font-family:"Serif";font-weight:900;color:var(--ink);-webkit-text-stroke:14px var(--halo);paint-order:stroke fill;'


# —————————————————— 开场题字（第 0 帧就完整）——————————————————
def title(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = 0.0, A(ov["to"])
    cid = f"ttl{k}"
    l2 = ov["line2"].replace("[", '<span class="u"><i id="%su"></i><span class="ut">' % cid).replace("]", '</span></span>')
    inner = (f'<div class="tb" id="{cid}b"><div class="tk">{ov["kicker"]}</div>'
             f'<div class="t1">{ov["line1"]}</div><div class="t2">{l2}</div></div>')
    css = (f'#{cid} .tb{{position:absolute;left:40px;width:960px;top:{ov.get("y", 1096)}px;text-align:center;}}'
           f'#{cid} .tk{{font-family:"SansM";font-weight:500;font-size:34px;letter-spacing:.3em;color:var(--ink2);'
           f'-webkit-text-stroke:8px var(--halo);paint-order:stroke fill;margin-bottom:6px;}}'
           f'#{cid} .t1,#{cid} .t2{{{LOWER}font-size:118px;line-height:1.08;}}'
           f'#{cid} .u{{position:relative;display:inline-block;isolation:isolate;}}'
           f'#{cid} .u i{{position:absolute;left:-4px;right:-4px;bottom:4px;height:14px;background:var(--gold);}}'
           f'#{cid} .ut{{position:relative;}}')
    js = [_draw(f"#{cid}u", 0.15, 0.6), _out(f"#{cid}b", t1 - 0.3, 0.3)]
    return _clip(cid, t0, t1, 5, inner, z=45), css, "\n".join(js)


# —————————————————— 转折：「问问题？」被一笔划掉 ——————————————————
def pivot(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"pvt{k}"
    inner = (f'<div class="pb" id="{cid}b"><div class="ps" id="{cid}s">{ov["small"]}</div>'
             f'<div class="pq" id="{cid}q"><span>{ov["big"]}</span>'
             f'<svg id="{cid}x" viewBox="0 0 600 60" preserveAspectRatio="none"><path d="M6 38 C 140 18, 300 46, 594 20" '
             f'stroke="#C0392B" stroke-width="12" fill="none" stroke-linecap="round"/></svg></div></div>')
    css = (f'#{cid} .pb{{position:absolute;left:40px;width:960px;top:{ov.get("y", 1110)}px;text-align:center;}}'
           f'#{cid} .ps{{font-family:"Kai";font-weight:500;font-size:60px;color:var(--ink2);-webkit-text-stroke:10px var(--halo);paint-order:stroke fill;}}'
           f'#{cid} .pq{{position:relative;display:inline-block;{LOWER}font-size:150px;line-height:1.1;}}'
           f'#{cid} svg{{position:absolute;left:-3%;width:106%;top:42%;height:60px;}}')
    js = [_in(f"#{cid}s", t0, y=16, d=0.4), _in(f"#{cid}q", A(ov["big_at"]), y=26, d=0.45),
          f'tl.fromTo("#{cid}x",{{clipPath:"inset(0 100% 0 0)"}},{{clipPath:"inset(0 0% 0 0)",duration:0.35,ease:"power2.out"}},{A(ov["strike_at"]):.3f});',
          _out(f"#{cid}b", t1 - 0.25, 0.25)]
    return _clip(cid, t0, t1, 6, inner, z=45), css, "\n".join(js)


# —————————————————— 金句大字（随她发音逐词出现，代替字幕）——————————————————
def golden(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"gld{k}"
    words = ov["words"]  # [{text, at, gold?, latin?}]
    spans = "".join(f'<span class="w{" g" if w.get("gold") else ""}{" lt" if w.get("latin") else ""}" id="{cid}w{i}">{w["text"]}</span>'
                    for i, w in enumerate(words))
    sub = f'<div class="gs" id="{cid}s">{ov["sub"]}</div>' if ov.get("sub") else ""
    inner = f'<div class="gb" id="{cid}b">{sub}<div class="gl">{spans}</div></div>'
    css = (f'#{cid} .gb{{position:absolute;left:30px;width:980px;top:{ov.get("y", 1200)}px;text-align:center;}}'
           f'#{cid} .gs{{font-family:"Kai";font-weight:500;font-size:52px;color:var(--ink2);-webkit-text-stroke:10px var(--halo);paint-order:stroke fill;margin-bottom:4px;}}'
           f'#{cid} .gl{{{LOWER}font-size:{ov.get("size", 116)}px;line-height:1.1;white-space:nowrap;}}'
           f'#{cid} .w{{display:inline-block;margin:0 .06em;}}'
           f'#{cid} .lt{{font-family:"LatinI";font-style:italic;font-weight:400;font-size:1.12em;-webkit-text-stroke:12px var(--halo);}}'
           f'#{cid} .g{{color:var(--amber);}}')
    js = []
    if ov.get("sub"):
        js.append(_in(f"#{cid}s", t0, y=12, d=0.35))
    for i, w in enumerate(words):
        js.append(_in(f"#{cid}w{i}", A(w["at"]) - 0.04, y=22, d=0.35))
    js.append(_out(f"#{cid}b", t1 - 0.25, 0.25))
    return _clip(cid, t0, t1, 7, inner, z=45), css, "\n".join(js)


# —————————————————— 下三分之一纸条：一周（随时被叫走）/ 广州四天（一口气学满）——————————————————
def strip(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"stp{k}"
    n = ov["cells"]
    cells = "".join(f'<div class="c" id="{cid}c{i}"><i id="{cid}d{i}"></i></div>' for i in range(n))
    head = "".join(f'<span>{h}</span>' for h in ov.get("heads", []))
    lg = f'<div class="lg"><i></i>{ov["legend"]}</div>' if ov.get("legend") else ""
    inner = (f'<div class="sb" id="{cid}b"><div class="sl">{ov["label"]}{lg}</div><div class="sr">'
             f'{"<div class=hd>" + head + "</div>" if head else ""}<div class="row">{cells}</div></div></div>')
    cw = ov.get("cw", 74)
    css = (f'#{cid} .sb{{position:absolute;left:92px;width:788px;top:{ov.get("y", 1146)}px;height:108px;box-sizing:border-box;'
           f'background:rgba(246,243,236,.96);border:2px solid var(--line);box-shadow:0 10px 30px rgba(58,40,22,.14);'
           f'display:flex;align-items:center;padding:0 34px;gap:30px;}}'
           f'#{cid} .sl{{font-family:"Serif";font-weight:900;font-size:50px;line-height:1.05;color:var(--ink);white-space:nowrap;padding-right:28px;border-right:2px solid var(--line);}}'
           f'#{cid} .sr{{flex:1;}}'
           f'#{cid} .hd{{display:flex;justify-content:space-between;font-family:"SansM";font-weight:500;font-size:24px;color:var(--ink2);margin-bottom:4px;}}'
           f'#{cid} .hd span{{width:{cw}px;text-align:center;}}'
           f'#{cid} .row{{display:flex;justify-content:space-between;}}'
           f'#{cid} .c{{position:relative;width:{cw}px;height:{ov.get("ch", 40)}px;border:2px solid var(--ink);box-sizing:border-box;}}'
           f'#{cid} .c i{{position:absolute;inset:4px;background:var(--gold);opacity:0;}}'
           f'#{cid} .lg{{font-family:"SansM";font-weight:500;font-size:24px;color:var(--ink2);margin-top:4px;'
           f'-webkit-text-stroke:7px var(--halo);paint-order:stroke fill;}}'
           f'#{cid} .lg i{{display:inline-block;width:20px;height:20px;background:var(--gold);margin-right:10px;vertical-align:-2px;}}')
    js = [_in(f"#{cid}b", t0, y=18, d=0.4)]
    for f in ov["fills"]:  # [{cell, at}]
        js.append(f'tl.fromTo("#{cid}d{f["cell"]}",{{opacity:0,scale:0.3}},{{opacity:1,scale:1,duration:0.32,ease:{EASE}}},{A(f["at"]):.3f});')
    js.append(_out(f"#{cid}b", t1 - 0.3, 0.3))
    return _clip(cid, t0, t1, 8, inner, z=44), css, "\n".join(js)


# —————————————————— 斜体大字代替字幕（Hands on）——————————————————
def word(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"wrd{k}"
    inner = f'<div class="wb" id="{cid}b"><span>{ov["text"]}</span><i id="{cid}u"></i></div>'
    css = (f'#{cid} .wb{{position:absolute;left:0;width:1040px;top:{ov.get("y", 1240)}px;text-align:center;}}'
           f'#{cid} .wb span{{font-family:"LatinI";font-style:italic;font-size:{ov.get("size", 150)}px;line-height:1;color:var(--ink);'
           f'-webkit-text-stroke:14px var(--halo);paint-order:stroke fill;}}'
           f'#{cid} .wb i{{display:block;width:180px;height:8px;background:var(--gold);margin:4px auto 0;}}')
    js = [_in(f"#{cid}b", t0, y=20, d=0.4), _draw(f"#{cid}u", t0 + 0.25, 0.45, "50% 50%"), _out(f"#{cid}b", t1 - 0.25, 0.25)]
    return _clip(cid, t0, t1, 9, inner, z=45), css, "\n".join(js)


# —————————————————— 画面缩放（片尾相框用）——————————————————
def _vwrap_to(t, d, scale, x, y, clip, back=False):
    """#vwrap（她的整幅画面）从满屏变到小窗；clip 是缩放前坐标里要保留的区域 inset。"""
    full = "inset(0px 0px 0px 0px)"
    a = {"scale": 1, "x": 0, "y": 0, "clipPath": full}
    b = {"scale": scale, "x": x, "y": y, "clipPath": clip}
    fr, to = (b, a) if back else (a, b)
    f = lambda o: ",".join(f'{k_}:{json.dumps(v)}' for k_, v in o.items())
    return f'tl.fromTo("#vwrap",{{{f(fr)}}},{{{f(to)},duration:{d},ease:{SWAY},immediateRender:false}},{t:.3f});'


def window_geom(win, center, base_w=1080, base_h=1920):
    """小窗 win=[x,y,w,h]，人像中心 center=[cx,cy]（满屏坐标）→ scale、位移、clip。"""
    x, y, w, h = win[:4]
    s = win[4] if len(win) > 4 else 0.5
    cw, ch = w / s, h / s
    cx, cy = center
    l = min(max(cx - cw / 2, 0), base_w - cw); t = min(max(cy - ch / 2, 0), base_h - ch)
    clip = f"inset({t:.0f}px {base_w - l - cw:.0f}px {base_h - t - ch:.0f}px {l:.0f}px)"
    return s, x - l * s, y - t * s, clip


def endcard(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), ctx["total"]
    cid = f"end{k}"
    win = ov["win"]
    s, tx, ty, clip = window_geom(win, ov.get("center", [540, 690]))
    x, y, w, h = win[:4]
    inner = (f'<div class="pf" id="{cid}f"></div>'
             f'<div class="sg" id="{cid}s">{ov["name"]}</div>'
             f'<div class="hw"><span id="{cid}h1">{ov.get("say1", "")}</span> <span id="{cid}h2">{ov.get("say2", "")}</span>'
             f'<svg id="{cid}a" viewBox="0 0 420 40" preserveAspectRatio="none"><path d="M6 26 C 120 6, 300 6, 414 22" stroke="var(--gold)" stroke-width="9" fill="none" stroke-linecap="round"/></svg></div>')
    css = (f'#{cid} .pf{{position:absolute;left:{x - 22}px;top:{y - 22}px;width:{w + 44}px;height:{h + 44}px;background:#fff;'
           f'box-shadow:0 26px 70px rgba(58,40,22,.22),0 0 0 1px rgba(42,34,48,.08);}}'
           f'#{cid} .sg{{position:absolute;left:0;width:1080px;top:{y + h + 50}px;text-align:center;font-family:"Kai";font-weight:500;font-size:86px;color:var(--ink);}}'
           f'#{cid} .hw{{position:absolute;left:0;width:1080px;top:{y + h + 170}px;text-align:center;font-family:"Script";font-weight:700;font-size:118px;line-height:1;color:var(--ink);}}'
           f'#{cid} .hw span{{display:inline-block;}}'
           f'#{cid} .hw svg{{position:absolute;left:{540 - 10}px;top:112px;width:400px;height:40px;}}')
    d = 0.7
    js = [_vwrap_to(t0, d, s, tx, ty, clip),
          f'tl.fromTo("#{cid}f",{{opacity:0,scale:1.04}},{{opacity:1,scale:1,duration:0.6,ease:{EASE}}},{t0 + 0.15:.3f});',
          _wipe(f"#{cid}s", A(ov["name_at"]), A(ov["name_end"]) - A(ov["name_at"]) + 0.2),
          *([_wipe(f"#{cid}h1", A(ov["h1_at"]), 0.7), _wipe(f"#{cid}h2", A(ov.get("h2_at", ov["h1_at"])), 0.6),
             f'tl.fromTo("#{cid}a",{{clipPath:"inset(0 100% 0 0)"}},{{clipPath:"inset(0 0% 0 0)",duration:0.6,ease:"power2.out"}},{A(ov["arc_at"]):.3f});']
            if ov.get("say1") or ov.get("say2") else [f'tl.set("#{cid}a",{{opacity:0}},0);']),
          # 定格：底片放完后显示最后一帧，并继续极慢推近
          f'tl.fromTo("#freeze",{{opacity:0}},{{opacity:1,duration:0.01}},{ctx["tl"]["out_dur"] - 0.04:.3f});',
          f'tl.fromTo("#vwrap",{{scale:{s},x:{tx:.1f},y:{ty:.1f}}},{{scale:{s * 1.025:.4f},x:{tx - w * 0.0125:.1f},y:{ty - h * 0.0125:.1f},duration:{t1 - t0 - d:.2f},ease:"none",immediateRender:false}},{t0 + d:.3f});']
    return _clip(cid, t0, t1, 15, inner, z=1), css, "\n".join(js)


TYPES = {"title": title, "pivot": pivot, "golden": golden, "strip": strip, "word": word, "end": endcard}


def render(ov, k, ctx):
    return TYPES[ov["type"]](ov, k, ctx)


# —————————————————— 人物出场：她说到某人时，整屏换成那个人的画面（相框窗）——————————————————
def guest(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"gst{k}"
    x, y, w, h = ov["win"]
    inner = (f'<div class="bg" id="{cid}g"></div>'
             f'<div class="fr" id="{cid}f"><div class="im"><img id="{cid}v" src="assets/{ov["src"]}"></div>'
             f'<div class="tg" id="{cid}t">{ov["tag"]}</div></div>')
    css = (f'#{cid} .bg{{position:absolute;inset:0;background:var(--paper);}}'
           f'#{cid} .fr{{position:absolute;left:{x - 18}px;top:{y - 18}px;width:{w + 36}px;height:{h + 36}px;background:#fff;'
           f'padding:18px;box-sizing:border-box;box-shadow:0 26px 70px rgba(58,40,22,.22);}}'
           f'#{cid} .im{{width:{w}px;height:{h}px;overflow:hidden;}}#{cid} .im img{{width:{w}px;height:{h}px;display:block;object-fit:cover;}}'
           f'#{cid} .tg{{position:absolute;left:-14px;top:40px;background:var(--ink);color:#fff;font-family:"Serif";font-weight:900;'
           f'font-size:60px;padding:8px 26px;}}')
    js = [f'tl.fromTo("#{cid}g",{{opacity:0}},{{opacity:1,duration:0.35}},{t0:.3f});',
          f'tl.fromTo("#{cid}f",{{opacity:0,y:50,rotation:-2.5}},{{opacity:1,y:0,rotation:-1.2,duration:0.55,ease:{EASE}}},{t0 + 0.05:.3f});',
          _in(f"#{cid}t", t0 + 0.45, y=0, x=-30, d=0.4),
          f'tl.fromTo("#{cid}v",{{scale:1}},{{scale:1.06,duration:{t1 - t0:.2f},ease:"none"}},{t0:.3f});',
          _out(f"#{cid}f", t1 - 0.3, 0.3), _out(f"#{cid}g", t1 - 0.25, 0.25)]
    return _clip(cid, t0, t1, 13, inner, z=6), css, "\n".join(js)


TYPES["guest"] = guest


# —————————————————— 照片墙：两张照片像拍立得一样斜放在纸上（开场钩子 / 回扣）——————————————————
def photos(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"pho{k}"
    w, h, top = ov.get("w", 410), ov.get("h", 820), ov.get("top", 360)
    lefts, rots = ov.get("lefts", [92, 560]), ov.get("rots", [-3.0, 2.4])
    head = (f'<div class="hd" id="{cid}h"><div class="hk">{ov["kicker"]}</div><div class="ht">{ov["head"]}</div></div>'
            if ov.get("head") else "")
    frames = "".join(f'<div class="fr" id="{cid}f{i}" style="left:{lefts[i]}px"><img id="{cid}v{i}" src="assets/{s}"></div>'
                     for i, s in enumerate(ov["srcs"]))
    inner = f'<div class="bg" id="{cid}g"></div>{head}{frames}'
    css = (f'#{cid} .bg{{position:absolute;inset:0;background:var(--paper);}}'
           f'#{cid} .hd{{position:absolute;left:0;width:1080px;top:{ov.get("hy", 150)}px;text-align:center;}}'
           f'#{cid} .hk{{font-family:"SansM";font-weight:500;font-size:34px;letter-spacing:.3em;color:var(--ink2);margin-bottom:8px;}}'
           f'#{cid} .ht{{font-family:"Serif";font-weight:900;font-size:{ov.get("hs", 92)}px;line-height:1.1;color:var(--ink);}}'
           f'#{cid} .ht b{{color:var(--amber);font-weight:900;}}'
           f'#{cid} .fr{{position:absolute;top:{top}px;width:{w + 28}px;height:{h + 28}px;background:#fff;padding:14px;box-sizing:border-box;'
           f'box-shadow:0 24px 60px rgba(58,40,22,.22),0 0 0 1px rgba(42,34,48,.06);overflow:hidden;}}'
           f'#{cid} .fr img{{width:{w}px;height:{h}px;display:block;object-fit:cover;object-position:{ov.get("pos", "50% 50%")};}}')
    ats = [A(a) for a in ov.get("ats", [ov["from"], ov["from"]])]
    js = [f'tl.fromTo("#{cid}g",{{opacity:0}},{{opacity:1,duration:0.3}},{t0:.3f});']
    if ov.get("head"):
        js.append(_in(f"#{cid}h", t0 + 0.05, y=16, d=0.45))
    for i in range(len(ov["srcs"])):
        js.append(f'tl.fromTo("#{cid}f{i}",{{opacity:0,y:60,rotation:{rots[i] * 2:.1f}}},'
                  f'{{opacity:1,y:0,rotation:{rots[i]},duration:0.55,ease:{EASE}}},{max(ats[i], t0 + 0.05):.3f});')
        js.append(f'tl.fromTo("#{cid}v{i}",{{scale:1}},{{scale:1.05,duration:{t1 - t0:.2f},ease:"none"}},{t0:.3f});')
    js += [_out(f"#{cid}f{i}", t1 - 0.3, 0.3) for i in range(len(ov["srcs"]))] + [_out(f"#{cid}g", t1 - 0.25, 0.25)]
    if ov.get("head"):
        js.append(_out(f"#{cid}h", t1 - 0.3, 0.3))
    return _clip(cid, t0, t1, 14, inner, z=6), css, "\n".join(js)


# —————————————————— 目录卡：四个方面随她说出逐格出现（代替字幕）——————————————————
def toc(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"toc{k}"
    cells = "".join(f'<div class="c{" s" if it.get("secret") else ""}" id="{cid}c{i}"><span class="n">{i + 1}</span>'
                    f'<span class="l">{it["text"]}</span></div>' for i, it in enumerate(ov["items"]))
    inner = f'<div class="tb" id="{cid}b">{cells}</div>'
    css = (f'#{cid} .tb{{position:absolute;left:92px;width:896px;top:{ov.get("y", 1176)}px;display:grid;'
           f'grid-template-columns:1fr 1fr;gap:14px;}}'
           f'#{cid} .c{{height:118px;background:rgba(246,243,236,.96);border:2px solid var(--line);box-sizing:border-box;'
           f'box-shadow:0 10px 30px rgba(58,40,22,.14);display:flex;align-items:center;padding:0 28px;gap:22px;}}'
           f'#{cid} .n{{font-family:"LatinI";font-style:italic;font-size:92px;line-height:1;color:var(--gold2);width:44px;text-align:center;}}'
           f'#{cid} .l{{font-family:"Serif";font-weight:900;font-size:60px;color:var(--ink);white-space:nowrap;}}'
           f'#{cid} .s{{background:var(--ink);border-color:var(--ink);}}#{cid} .s .l{{color:#fff;}}#{cid} .s .n{{color:var(--gold);}}')
    js = [_in(f"#{cid}c{i}", A(it["at"]) - 0.05, y=20, d=0.4) for i, it in enumerate(ov["items"])]
    js.append(_out(f"#{cid}b", t1 - 0.3, 0.3))
    return _clip(cid, t0, t1, 16, inner, z=44), css, "\n".join(js)


# —————————————————— 章节签：左上角「1/4 口罩」，整段都在 ——————————————————
def chip(ov, k, ctx):
    A = ctx["A"]
    t0, t1 = A(ov["from"]), A(ov["to"])
    cid = f"chp{k}"
    inner = (f'<div class="cb" id="{cid}b"><span class="n">{ov["num"]}<small>/{ov.get("of", 4)}</small></span>'
             f'<span class="l">{ov["text"]}</span></div>')
    css = (f'#{cid} .cb{{position:absolute;left:0;top:{ov.get("y", 214)}px;background:var(--ink);padding:10px 30px 12px 44px;'
           f'display:flex;align-items:baseline;gap:18px;box-shadow:0 10px 26px rgba(42,34,48,.22);}}'
           f'#{cid} .n{{font-family:"LatinI";font-style:italic;font-size:64px;line-height:1;color:var(--gold);}}'
           f'#{cid} .n small{{font-size:34px;color:rgba(255,255,255,.55);margin-left:2px;}}'
           f'#{cid} .l{{font-family:"Serif";font-weight:900;font-size:50px;color:#fff;}}')
    js = [_in(f"#{cid}b", t0, y=0, x=-60, d=0.45), _out(f"#{cid}b", t1 - 0.3, 0.3)]
    return _clip(cid, t0, t1, 17 + k % 2, inner, z=46), css, "\n".join(js)


TYPES.update({"photos": photos, "toc": toc, "chip": chip})
