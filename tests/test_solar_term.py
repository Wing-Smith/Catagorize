"""节气计算的锚点测试：精确表年份逐节气边界，回退年份抽查。"""

from __future__ import annotations

from datetime import date

from app.core.solar_term import current_solar_term, weekday_name


def test_2026_exact_anchors() -> None:
    assert current_solar_term(date(2026, 1, 1)) == "冬至"      # 上一年冬至尾
    assert current_solar_term(date(2026, 1, 5)) == "小寒"
    assert current_solar_term(date(2026, 2, 3)) == "大寒"
    assert current_solar_term(date(2026, 2, 4)) == "立春"
    assert current_solar_term(date(2026, 6, 20)) == "芒种"
    assert current_solar_term(date(2026, 6, 21)) == "夏至"
    assert current_solar_term(date(2026, 11, 7)) == "立冬"
    assert current_solar_term(date(2026, 11, 21)) == "立冬"
    assert current_solar_term(date(2026, 11, 22)) == "小雪"
    assert current_solar_term(date(2026, 12, 21)) == "大雪"
    assert current_solar_term(date(2026, 12, 22)) == "冬至"


def test_2027_exact_anchors() -> None:
    assert current_solar_term(date(2027, 3, 5)) == "雨水"
    assert current_solar_term(date(2027, 3, 6)) == "惊蛰"
    assert current_solar_term(date(2027, 5, 5)) == "谷雨"
    assert current_solar_term(date(2027, 5, 6)) == "立夏"
    assert current_solar_term(date(2027, 8, 7)) == "大暑"
    assert current_solar_term(date(2027, 8, 8)) == "立秋"


def test_fallback_years_use_generic_table() -> None:
    # 2028 无精确表 → 通用近似（边界 ±1 天为预期行为，这里取表中锚点）
    assert current_solar_term(date(2028, 5, 5)) == "立夏"
    assert current_solar_term(date(2028, 1, 3)) == "冬至"


def test_weekday_name() -> None:
    assert weekday_name(date(2026, 11, 22)) == "星期日"
    assert weekday_name(date(2026, 11, 23)) == "星期一"


def test_term_en_covers_all_24_terms():
    from app.core.solar_term import TERM_EN, _FALLBACK

    names = {name for _, _, name in _FALLBACK}
    assert len(names) == 24
    missing = names - set(TERM_EN)
    assert not missing, f"缺英文译名: {missing}"
