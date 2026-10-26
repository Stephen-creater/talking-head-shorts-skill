"""看一段原片的画面：从起到止每 step 秒抽一帧拼成一张带时间码的图，确认这段有没有镜头掉落、人出画、举着东西。
用法：python scripts/frames.py <工程目录> <起秒> <止秒> [step=1] → build/frames_<起>_<止>.jpg
"""
import sys
from pathlib import Path
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent))
from edit import project_paths  # noqa: E402


def main(proj, a, b, step=1.0, cols=10):
    proj = Path(proj).resolve()
    cap = cv2.VideoCapture(str(project_paths(proj)["source"]))
    tiles = []
    for t in np.arange(a, b + 1e-6, step):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        im = cv2.resize(fr, (150, int(150 * fr.shape[0] / fr.shape[1])))
        cv2.rectangle(im, (0, 0), (64, 20), (0, 0, 0), -1)
        cv2.putText(im, f"{t:.1f}", (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        tiles.append(im)
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    grid = np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(len(tiles) // cols)])
    out = proj / f"build/frames_{a:g}_{b:g}.jpg"
    out.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(out), grid)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]) if len(sys.argv) > 4 else 1.0)
