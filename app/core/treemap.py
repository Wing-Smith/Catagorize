"""Squarified treemap 布局（Bruls et al. 2000）。

纯逻辑：输入面积列表，输出归一化矩形坐标，UI 层只负责上色和绘制。
性质：矩形长宽比接近方形、面积严格正比、无重叠、填满容器。
"""

from __future__ import annotations

_EPS = 1e-9


def squarify(
    sizes: list[float], width: float = 1.0, height: float = 1.0
) -> list[tuple[int, float, float, float, float]]:
    """返回 [(原始下标, x, y, w, h), ...]，坐标在 [0, width]×[0, height] 内。

    非正面积的元素被跳过（不出现在结果里）；迭代实现，无递归深度限制。
    """
    total = sum(s for s in sizes if s > 0)
    if total <= 0 or width <= 0 or height <= 0:
        return []
    scale = width * height / total
    items = [(i, s * scale) for i, s in enumerate(sizes) if s > 0]

    rects: list[tuple[int, float, float, float, float]] = []
    x, y, w, h = 0.0, 0.0, float(width), float(height)
    row: list[tuple[int, float]] = []
    pos = 0
    while pos < len(items):
        side = min(w, h)
        if side <= _EPS:
            break  # 容器已榨干，剩余项丢弃（现实中不会发生）
        candidate = [a for _, a in row] + [items[pos][1]]
        if not row or _worst(candidate, side) <= _worst([a for _, a in row], side):
            row.append(items[pos])
            pos += 1
        else:
            x, y, w, h = _place_row(row, x, y, w, h, rects)
            row = []
    if row:
        _place_row(row, x, y, w, h, rects)
    return rects


def _worst(areas: list[float], side: float) -> float:
    """当前行放进厚度为 side 的条带后的最差长宽比（越大越方……越小越好）。"""
    s = sum(areas)
    if s <= 0:
        return float("inf")
    rmax = max(areas)
    rmin = min(areas)
    return max(rmax * side * side / (s * s), s * s / (rmin * side * side))


def _place_row(
    row: list[tuple[int, float]],
    x: float,
    y: float,
    w: float,
    h: float,
    rects: list[tuple[int, float, float, float, float]],
) -> tuple[float, float, float, float]:
    """把行铺进贴边的条带，返回剩余矩形。"""
    covered = sum(a for _, a in row)
    if w >= h:  # 横条：占满高 h，元素纵向堆叠
        strip_w = covered / h
        yy = y
        for idx, area in row:
            hh = area / strip_w
            rects.append((idx, x, yy, strip_w, hh))
            yy += hh
        return (x + strip_w, y, w - strip_w, h)
    # 竖条：占满宽 w，元素横向排列
    strip_h = covered / w
    xx = x
    for idx, area in row:
        ww = area / strip_h
        rects.append((idx, xx, y, ww, strip_h))
        xx += ww
    return (x, y + strip_h, w, h - strip_h)
