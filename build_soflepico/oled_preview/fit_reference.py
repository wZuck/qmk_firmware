#!/usr/bin/env python3
"""把参考图（reference.png）矢量化，得出 make_animations.py 里的那套图元参数。

步骤：
  1. Hough 圆检测：头的上半外缘圆（半径 17-21）、两只眼睛的圆（半径 9-13）
  2. 连通域：眼部框里"3x3 全是墨迹"的实心块 = 瞳孔
  3. 最小二乘椭圆拟合：y 52-78 与 90-122 的外轮廓 = 身体
  4. 量手臂所在行、腿的位置
最后按"身体中心对齐 + 64/114 缩放"换算成 make_animations.py 的坐标系，
并把量到的外缘半径减去半个线宽，得到线心半径。

用法： python3 fit_reference.py [参考图路径]
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "reference.png")

# 参考图墨迹宽 114 px -> 模型里手臂张开的 64 px
SCALE = 64.0 / 114.0
BODY_CY = 34.5          # make_animations.py 里的 BODY_CY
STROKE = 4.0            # 参考图的线宽（像素），用来从外缘推线心


def main():
    img = np.array(Image.open(REF).convert("L"))
    ink = img < 128
    h, w = ink.shape
    ys, xs = np.nonzero(ink)
    print("参考图 %dx%d，墨迹 %d px，墨迹框 x %d..%d y %d..%d"
          % (w, h, ink.sum(), xs.min(), xs.max(), ys.min(), ys.max()))

    def hough(radii, cx_range, cy_range, arc=None, min_cover=0.9):
        """圆心/半径搜索；arc=(起,止) 弧度时只按那段弧打分（头只看上半圈）。"""
        best = (0.0, 0.0, 0.0, 0.0)
        for r in radii:
            n = max(64, int(2 * np.pi * r))
            ang = np.linspace(*(arc if arc else (0, 2 * np.pi)), n, endpoint=False)
            cos, sin = np.cos(ang), np.sin(ang)
            for cx in cx_range:
                for cy in cy_range:
                    px = np.rint(cx + r * cos).astype(int)
                    py = np.rint(cy + r * sin).astype(int)
                    ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
                    if ok.sum() < min_cover * n:
                        continue
                    frac = ink[py[ok], px[ok]].mean()
                    if frac > best[3]:
                        best = (float(cx), float(cy), float(r), frac)
        return best

    head = hough(np.arange(17.0, 21.5, 0.5), range(58, 70), range(40, 52),
                 arc=(np.pi * 1.02, np.pi * 1.98))
    eye_l = hough(np.arange(9.0, 13.5, 0.5), range(46, 58), range(32, 44))
    eye_r = hough(np.arange(9.0, 13.5, 0.5), range(66, 80), range(32, 44))
    print("头（外缘）: (%.1f,%.1f) r=%.1f 覆盖 %.2f" % head)
    print("左眼（外缘）: (%.1f,%.1f) r=%.1f 覆盖 %.2f" % eye_l)
    print("右眼（外缘）: (%.1f,%.1f) r=%.1f 覆盖 %.2f" % eye_r)

    # 瞳孔：3x3 全墨迹的实心块，只找眼部框里的
    solid = np.zeros_like(ink)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if ink[y - 1 : y + 2, x - 1 : x + 2].all():
                solid[y, x] = True
    seen = np.zeros_like(solid)
    pupils = []
    for y in range(28, 52):
        for x in range(42, 92):
            if solid[y, x] and not seen[y, x]:
                stack, cc = [(y, x)], []
                seen[y, x] = True
                while stack:
                    cy0, cx0 = stack.pop()
                    cc.append((cy0, cx0))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy0 + dy, cx0 + dx
                            if 28 <= ny < 52 and 42 <= nx < 92 and solid[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                stack.append((ny, nx))
                if len(cc) >= 8:
                    a = np.array(cc)
                    pupils.append((a[:, 1].mean(), a[:, 0].mean(), len(cc)))
    pupils.sort()
    for p in pupils:
        print("瞳孔核心: (%.1f,%.1f) %d px -> r≈%.1f" % (p[0], p[1], p[2], np.sqrt(p[2] / np.pi) + STROKE / 2))

    # 身体：外轮廓做椭圆拟合（跳过手臂那几行）
    pts = []
    for y in list(range(52, 78)) + list(range(90, 122)):
        row = np.nonzero(ink[y])[0]
        if len(row):
            pts += [(row.min(), y), (row.max(), y)]
    pts = np.array(pts, float)
    A = np.stack([pts[:, 1] ** 2, pts[:, 0], pts[:, 1], np.ones(len(pts))], 1)
    coef, *_ = np.linalg.lstsq(A, -(pts[:, 0] ** 2), rcond=None)
    B, C, D, E = coef
    cx_b, cy_b = -C / 2, -D / (2 * B)
    rx_b = np.sqrt(cx_b**2 + B * cy_b**2 - E)
    ry_b = rx_b / np.sqrt(B)
    print("身体（外缘椭圆）: (%.1f,%.1f) rx=%.1f ry=%.1f" % (cx_b, cy_b, rx_b, ry_b))

    arm_rows = np.nonzero(ink[:, 4:20].any(axis=1))[0]
    leg_rows = np.nonzero(ink[:, 38:42].any(axis=1))[0]
    leg_cols = np.nonzero(ink[132:, :].any(axis=0))[0]
    print("手臂行 %s；腿列 %s；腿底 y=%d" % (arm_rows, leg_cols, leg_rows.max()))

    # ---- 换算到 make_animations.py 的坐标系 ---------------------------------
    def my(ref_y):
        return (ref_y - cy_b) * SCALE + BODY_CY

    def mx(ref_x):
        return (ref_x - cx_b) * SCALE

    half = STROKE / 2 * SCALE
    print("\n== make_animations.py 参数（外缘半径 - 半个线宽）==")
    print("HEAD_CY, HEAD_R = %.1f, %.2f" % (my(head[1]), head[2] * SCALE - half))
    print("EYE_DX = %.2f   EYE_CY = %.1f   EYE_R = %.2f"
          % ((abs(mx(eye_l[0])) + abs(mx(eye_r[0]))) / 2,
             (my(eye_l[1]) + my(eye_r[1])) / 2,
             (eye_l[2] + eye_r[2]) / 2 * SCALE - half))
    if len(pupils) >= 2:
        (plx, ply, pln), (prx, pry, prn) = pupils[0], pupils[-1]
        rl = np.sqrt(pln / np.pi) + STROKE / 2
        rr = np.sqrt(prn / np.pi) + STROKE / 2
        print("PUPIL_R = %.2f（左 %.2f / 右 %.2f）  PUPIL_DX ≈ %.2f  PUPIL_DY ≈ %.2f"
              % ((rl + rr) / 2 * SCALE,
                 rl * SCALE, rr * SCALE,
                 ((mx(plx) - mx(eye_l[0])) + (mx(prx) - mx(eye_r[0]))) / 2,
                 ((my(ply) - my(eye_l[1])) + (my(pry) - my(eye_r[1]))) / 2))
    print("BODY_RX = %.2f   BODY_RY = %.2f" % (rx_b * SCALE - half, ry_b * SCALE - half))
    mid = (leg_cols.min() + leg_cols.max()) / 2
    leg_l = leg_cols[leg_cols < mid].mean()
    leg_r = leg_cols[leg_cols > mid].mean()
    print("LEG_DX = %.1f    LEG_Y1 = %.2f" % ((mx(leg_r) - mx(leg_l)) / 2, my(leg_rows.max()) - half))
    print("\n注意：眼睛那两行覆盖只有 ~0.7（眼睛轮廓和头的轮廓、以及两只眼睛互相重叠），"
          "所以量到的 EYE_R 偏小；按原图眼睛几乎和头一样宽来取更合适。")


if __name__ == "__main__":
    main()
