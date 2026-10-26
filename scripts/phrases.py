"""把 whisper 逐字结果整理成「短语表」：每句的原片起止时间 + 校正后的文字 + 逐字时间。
同音错字在剪辑表 edl.json 的 "asr_fixes" 里写成 [["错", "对"], …]（必须等长，按整句替换后再切回逐字）。
用法：python scripts/phrases.py <工程目录>
输出：analysis/phrases.json（给程序）和 analysis/phrases.tsv（给人看：编号、起、止、文字）
"""
import json, sys
from pathlib import Path


def main(proj):
    proj = Path(proj).resolve()
    edl = json.load(open(proj / "edl.json"))
    fix = [tuple(p) for p in edl.get("asr_fixes", [])]
    bad = [p for p in fix if len(p[0]) != len(p[1])]
    if bad:
        sys.exit(f"asr_fixes 必须前后等长（逐字时间要一一对应）：{bad}")

    def clean(t):
        for a, b in fix:
            t = t.replace(a, b)
        return t.strip()

    d = json.load(open(proj / "analysis/asr.json"))
    out = []
    for s in d["transcription"]:
        toks = [t for t in s["tokens"] if not t["text"].startswith("[_") and t["text"].strip()]
        if not toks:
            continue
        a = toks[0]["offsets"]["from"] / 1000
        b = toks[-1]["offsets"]["to"] / 1000
        # 校正是等长替换：先在整句上替换，再按原 token 长度切回去（跨 token 的「病|例」也能改到）
        raw = [t["text"] for t in toks]
        fixed = clean("".join(raw)) if len(clean("".join(raw))) == len("".join(raw)) else "".join(raw)
        pieces, k = [], 0
        for r in raw:
            pieces.append(fixed[k:k + len(r)]); k += len(r)
        out.append({"id": f"P{len(out)+1:02d}", "in": round(a, 2), "out": round(b, 2),
                    "text": clean(s["text"]),
                    "chars": [[pc.strip() or pc, t["offsets"]["from"] / 1000, t["offsets"]["to"] / 1000]
                              for pc, t in zip(pieces, toks)]})
    json.dump(out, open(proj / "analysis/phrases.json", "w"), ensure_ascii=False, indent=1)
    with open(proj / "analysis/phrases.tsv", "w") as f:
        for p in out:
            f.write(f"{p['id']}\t{p['in']:.2f}\t{p['out']:.2f}\t{p['text']}\n")
    print(len(out), "句 → analysis/phrases.tsv")


if __name__ == "__main__":
    main(sys.argv[1])
