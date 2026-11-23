"""squarified treemap 布局的性质测试：面积守恒、不重叠、不出界、下标保真。"""

import pytest

from app.core.treemap import squarify


def _area(rect):
    return rect[3] * rect[4]


def test_empty_and_degenerate():
    assert squarify([]) == []
    assert squarify([0, 0, -1]) == []
    assert squarify([1], width=0) == []


def test_single_fills_container():
    rects = squarify([42.0])
    assert rects == [(0, 0.0, 0.0, 1.0, 1.0)]


def test_area_conserved_and_proportional():
    sizes = [100.0, 50.0, 25.0, 12.5, 6.25]
    rects = squarify(sizes, 800.0, 600.0)
    total = 800.0 * 600.0
    assert sum(_area(r) for r in rects) == pytest.approx(total, rel=1e-6)
    for i, size in enumerate(sizes):
        rect = next(r for r in rects if r[0] == i)
        assert _area(rect) == pytest.approx(size / sum(sizes) * total, rel=1e-6)


def test_rects_within_bounds_no_overlap():
    sizes = [500.0, 300.0, 200.0, 100.0, 50.0, 20.0, 10.0, 5.0, 3.0, 2.0]
    rects = squarify(sizes, 1000.0, 700.0)
    for _i, x, y, w, h in rects:
        assert x >= -1e-6 and y >= -1e-6
        assert x + w <= 1000.0 + 1e-6
        assert y + h <= 700.0 + 1e-6
        assert w > 0 and h > 0
    # 两两不重叠
    for a in range(len(rects)):
        for b in range(a + 1, len(rects)):
            _, ax, ay, aw, ah = rects[a]
            _, bx, by, bw, bh = rects[b]
            overlap = not (ax + aw <= bx + 1e-6 or bx + bw <= ax + 1e-6
                           or ay + ah <= by + 1e-6 or by + bh <= ay + 1e-6)
            assert not overlap, f"rect {a} overlaps rect {b}"


def test_zero_and_negative_skipped_but_indices_kept():
    sizes = [10.0, 0.0, 30.0, -5.0]
    rects = squarify(sizes)
    assert sorted(r[0] for r in rects) == [0, 2]


def test_many_items_no_recursion_crash():
    sizes = [float((i * 7919) % 1000 + 1) for i in range(20000)]
    rects = squarify(sizes, 1000.0, 1000.0)
    assert len(rects) == len(sizes)
    assert sum(_area(r) for r in rects) == pytest.approx(1000.0 * 1000.0, rel=1e-6)


def test_aspect_ratios_reasonable():
    """squarify 的意义：最差长宽比有界，不会拉出离谱的纸条。"""
    sizes = [100.0, 80.0, 60.0, 40.0, 20.0, 10.0, 5.0]
    rects = squarify(sizes, 100.0, 100.0)
    worst = 0.0
    for _i, _x, _y, w, h in rects:
        ratio = max(w / h, h / w)
        worst = max(worst, ratio)
    assert worst < 4.0
