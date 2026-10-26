"""人像抠像（RobustVideoMatting）：只抠时间线用到的原片帧，透明度存成 build/alpha/%05d.png（编号同帧缓存）。
每段从入点前 0.5 秒开始预热，段与段之间重置记忆，避免跨剪辑点拖影。
用法：python scripts/matte.py <工程目录>
"""
import json, sys
from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).parent))
from edit import project_paths  # noqa: E402
from common import RVM_MODEL as MODEL  # noqa: E402


def main(proj):
    proj = Path(proj).resolve()
    src = project_paths(proj)["source"]
    tl = json.load(open(proj / "build/timeline.json"))
    fps = tl["fps"]
    out = proj / "build/alpha"
    out.mkdir(parents=True, exist_ok=True)
    sess = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
    cap = cv2.VideoCapture(str(src))
    ranges = [(max(0, int(s["s_in"] * fps) - 15), int(s["s_out"] * fps) + 6, int(s["s_in"] * fps) - 4) for s in tl["segments"]]
    done = 0
    for a, b, keep_from in ranges:
        if all((out / f"{i + 1:05d}.png").exists() for i in range(keep_from, b + 1)):
            continue   # 这段以前抠过（只改了字幕/图形时不重抠）
        cap.set(cv2.CAP_PROP_POS_FRAMES, a)
        rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
        for i in range(a, b + 1):
            ok, fr = cap.read()
            if not ok:
                break
            x = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255
            o = sess.run(None, {"src": x, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3],
                                "downsample_ratio": np.array([0.4], np.float32)})
            rec = o[2:6]
            if i >= keep_from:
                cv2.imwrite(str(out / f"{i + 1:05d}.png"), (np.clip(o[1][0, 0], 0, 1) * 255).astype(np.uint8))
                done += 1
    print("抠像帧数", done)


if __name__ == "__main__":
    main(sys.argv[1])
