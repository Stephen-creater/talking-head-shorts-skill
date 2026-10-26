"""起草剪辑表：把短语表里的每一句按原顺序写进 edl.json 的 items（不删任何句子、字幕自动断句），作为手工精剪的起点。
已经有 items 时不覆盖，除非加 --force。
用法：python scripts/draft_edl.py <工程目录> [--force]
"""
import json, sys
from pathlib import Path


def main(proj, force=False):
    proj = Path(proj).resolve()
    edl = json.load(open(proj / "edl.json"))
    if edl.get("items") and not force:
        sys.exit("edl.json 已有 items，不覆盖（要重来加 --force）")
    ph = json.load(open(proj / "analysis/phrases.json"))
    edl["items"] = [{"p": p["id"]} for p in ph]
    if edl["items"]:
        edl["items"][0]["frame"] = "wide"
        edl["items"][-1]["tail"] = 1.6
    json.dump(edl, open(proj / "edl.json", "w"), ensure_ascii=False, indent=1)
    print(f"已写入 {len(ph)} 句。下一步：读 analysis/phrases.tsv 和联系表，删句、写字幕和图形")


if __name__ == "__main__":
    main(sys.argv[1], "--force" in sys.argv)
