"""按成片里实际出现的字裁字体子集（woff2），放进 HyperFrames 工程的 assets/fonts/，并生成对应的 @font-face。
字体都在 setup.sh 下载到 ~/.cache/talking-head-shorts/fonts；每个家族按顺序找第一个存在的文件
（比如本机有鸿蒙黑就用鸿蒙黑，没有就用开源的思源黑体 Noto Sans SC 可变字重）。
用法：python scripts/fonts.py <hf 目录>   （hf_build.py 会自动调用）
"""
import re, subprocess, sys, html
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FONTS_DIR  # noqa: E402

# 家族名: ([候选文件…], CSS 字重, CSS 字形)
FONTS = {
    "Sans": (["HarmonyOS_Sans_SC_Black.ttf", "NotoSansSC[wght].ttf"], "900", "normal"),
    "SansB": (["HarmonyOS_Sans_SC_Bold.ttf", "NotoSansSC[wght].ttf"], "700", "normal"),
    "SansM": (["HarmonyOS_Sans_SC_Medium.ttf", "NotoSansSC[wght].ttf"], "500", "normal"),
    "Serif": (["NotoSerifSC[wght].ttf", "NotoSerifSC-VF.ttf"], "200 900", "normal"),
    "Kai": (["LXGWWenKai-Medium.ttf"], "500", "normal"),
    "LatinI": (["InstrumentSerif-Italic.ttf"], "400", "italic"),
    "Script": (["Caveat[wght].ttf", "Caveat-VF.ttf"], "400 700", "normal"),
    "Mono": (["DMMono-Medium.ttf"], "500", "normal"),
}
ASCII = "".join(chr(c) for c in range(32, 127))


def font_face_css():
    return "".join(f'@font-face{{font-family:"{n}";src:url("assets/fonts/{n}.woff2") format("woff2");'
                   f'font-weight:{w};font-style:{st};}}\n' for n, (_, w, st) in FONTS.items())


def main(hf):
    hf = Path(hf)
    src = (hf / "index.html").read_text()
    text = html.unescape(re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", src))
    chars = set(text) | set(ASCII) | set("，。、！？：；“”‘’（）《》·—…")
    (hf / "assets/fonts").mkdir(parents=True, exist_ok=True)
    txt = hf / "assets/fonts/_chars.txt"
    txt.write_text("".join(sorted(chars)))
    missing = []
    for name, (cands, _, _) in FONTS.items():
        f = next((FONTS_DIR / c for c in cands if (FONTS_DIR / c).exists()), None)
        if f is None:
            missing.append(cands[-1]); continue
        out = hf / f"assets/fonts/{name}.woff2"
        subprocess.run([sys.executable, "-m", "fontTools.subset", str(f), f"--text-file={txt}", "--flavor=woff2",
                        "--layout-features=*", f"--output-file={out}"], check=True)
    if missing:
        sys.exit(f"缺字体 {missing}：先运行 setup.sh（字体目录 {FONTS_DIR}）")
    print("字体子集完成，共", len(chars), "个字符")


if __name__ == "__main__":
    main(sys.argv[1])
