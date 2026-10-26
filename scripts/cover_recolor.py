"""封面换底色：只把浅色暖底（米白）和人物头后的暖光晕换成目标色，标题（黑字、金字、白描边）和人物原样不动。
原理：抠像模型定出人物；剩下的像素里，「偏暖、很淡、很亮」的才算底色，按偏暖程度渐变替换，明暗起伏保留。
标题以下放宽到较浓的暖色（头后光晕），标题区只换很淡的米白（保护金字的外发光），中间渐变过渡，没有接缝。
用法：python scripts/cover_recolor.py <原图> <输出.png> "#E6DCEF"
"""
import sys
from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).parent))
from common import RVM_MODEL  # noqa: E402


def main(src, out, color):
    im = cv2.imread(src)
    h, w = im.shape[:2]
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    corners = np.concatenate([lab[:40, :40].reshape(-1, 3), lab[:40, -40:].reshape(-1, 3)])
    bg = np.median(corners, 0)                       # 原底色（取上方两角）
    sess = ort.InferenceSession(str(RVM_MODEL), providers=["CPUExecutionProvider"])
    x = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    for _ in range(4):   # 单张图多跑几遍让记忆稳定
        o = sess.run(None, {"src": x, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3],
                            "downsample_ratio": np.array([0.25], np.float32)})
        rec = o[2:6]
    pha = o[1][0, 0]
    A, B = lab[..., 1] - 128, lab[..., 2] - 128
    chroma = np.hypot(A, B)
    y = np.arange(h)[:, None] / h
    cap = np.broadcast_to(14 + 26 * np.clip((y - 0.34) / 0.10, 0, 1), (h, w)).astype(np.float32)
    wgt = (np.clip((B - 1) / 4, 0, 1) * np.clip((cap - chroma) / 6, 0, 1) * np.clip((lab[..., 0] - 190) / 20, 0, 1)
           * (1 - np.clip(pha * 1.3, 0, 1)))
    wgt = cv2.GaussianBlur(wgt.astype(np.float32), (0, 0), 2.5)
    c = color.lstrip("#")
    tgt = cv2.cvtColor(np.uint8([[[int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    new = lab.copy()
    new[..., 0] = lab[..., 0] + (tgt[0] - bg[0]) * wgt
    new[..., 1] = lab[..., 1] * (1 - wgt) + tgt[1] * wgt
    new[..., 2] = lab[..., 2] * (1 - wgt) + tgt[2] * wgt
    cv2.imwrite(out, cv2.cvtColor(np.clip(new, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR))
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
