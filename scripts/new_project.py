"""新建一条视频的工程目录：建好子目录、把素材拷进 sources/、写一份带默认设置的 edl.json。
用法：python scripts/new_project.py <工程目录> <口播视频…> [--photos 照片…] [--end-song 片尾歌音频]
之后：python scripts/prepare.py <工程目录>
"""
import json, shutil, sys
from pathlib import Path

TEMPLATE = {
    "title": "",
    "language": "zh",
    "speed": 1.3,
    "fps": 30,
    "gap": 0.38,
    "max_pause": 0.6,
    "min_shot": 2.8,
    "end_extra": 6.8,
    "sources": [],
    "asr_fixes": [],
    "items": [],
    "pages": [],
    "overlays": [],
    "caption_hide": [],
    "music": {
        "lufs": -15.0,
        "tp": -1.5,
        "clips": [
            {"file": "$HOME/music/Wholesome.mp3", "offset": 1.244, "start": 0, "end": "END_SPEECH-7.2",
             "level": -31.2, "duck": True, "lift": 5, "fade_in": 0.8, "fade_out": 2.4},
        ],
    },
}


def main(argv):
    proj = Path(argv[0]).resolve()
    rest = argv[1:]
    photos, song = [], None
    if "--end-song" in rest:
        i = rest.index("--end-song"); song = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
    if "--photos" in rest:
        i = rest.index("--photos"); photos = rest[i + 1:]; rest = rest[:i]
    if (proj / "edl.json").exists():
        sys.exit(f"{proj / 'edl.json'} 已存在，不覆盖")
    for d in ("sources", "stills", "analysis", "build", "out"):
        (proj / d).mkdir(parents=True, exist_ok=True)
    edl = json.loads(json.dumps(TEMPLATE))
    for v in rest:
        shutil.copy(v, proj / "sources" / Path(v).name)
        edl["sources"].append(f"sources/{Path(v).name}")
    for p in photos:   # 图形（照片墙、人物出场）只从 stills/ 取图
        shutil.copy(p, proj / "stills" / Path(p).name)
    if song:
        f = "sources/end_song" + Path(song).suffix
        shutil.copy(song, proj / f)
        # 片尾歌接唱：两个时间点是每首歌各自的（前奏结束秒数、歌手唱出那句的秒数），见 docs/声音.md。
        # 下面是《Don't Worry Be Happy》录音室版的值，换歌必须改 offset。
        edl["music"]["clips"] += [
            {"file": f, "offset": "26.90-8.46", "start": "END_SPEECH-9.0", "end": "END_SPEECH-0.54",
             "level": -37.0, "duck": True, "lift": 6, "fade_in": 1.6, "fade_out": 0.45},
            {"file": f, "offset": 34.85, "start": "END_SPEECH+0.35", "end": "TOTAL",
             "level": -15.7, "fade_in": 0.05, "fade_out": 2.4}]
        print("已加片尾歌。注意：offset 里的两个时间点要按这首歌改（见 docs/声音.md「片尾歌接唱」）")
    json.dump(edl, open(proj / "edl.json", "w"), ensure_ascii=False, indent=1)
    print(f"工程已建好：{proj}\n下一步：scripts/ths prepare {proj}")


if __name__ == "__main__":
    main(sys.argv[1:])
