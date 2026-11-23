"""节气：给定日期返回当前节气名。

2026/2027 用逐年精确表（天文台公布日期，已核对）；
其他年份退回通用近似表（每月两气，边界日可能与实际差 1 天，
UI 展示足够；如需精确可再补逐年表）。
"""

from __future__ import annotations

from datetime import date

# 逐年精确表：(月, 日, 节气名)，已按日期排序
_EXACT: dict[int, list[tuple[int, int, str]]] = {
    2026: [
        (1, 5, "小寒"), (1, 20, "大寒"), (2, 4, "立春"), (2, 19, "雨水"),
        (3, 5, "惊蛰"), (3, 20, "春分"), (4, 5, "清明"), (4, 20, "谷雨"),
        (5, 5, "立夏"), (5, 21, "小满"), (6, 5, "芒种"), (6, 21, "夏至"),
        (7, 7, "小暑"), (7, 23, "大暑"), (8, 7, "立秋"), (8, 23, "处暑"),
        (9, 7, "白露"), (9, 23, "秋分"), (10, 8, "寒露"), (10, 23, "霜降"),
        (11, 7, "立冬"), (11, 22, "小雪"), (12, 7, "大雪"), (12, 22, "冬至"),
    ],
    2027: [
        (1, 5, "小寒"), (1, 20, "大寒"), (2, 4, "立春"), (2, 19, "雨水"),
        (3, 6, "惊蛰"), (3, 21, "春分"), (4, 5, "清明"), (4, 20, "谷雨"),
        (5, 6, "立夏"), (5, 21, "小满"), (6, 6, "芒种"), (6, 21, "夏至"),
        (7, 7, "小暑"), (7, 23, "大暑"), (8, 8, "立秋"), (8, 23, "处暑"),
        (9, 8, "白露"), (9, 23, "秋分"), (10, 8, "寒露"), (10, 23, "霜降"),
        (11, 7, "立冬"), (11, 22, "小雪"), (12, 7, "大雪"), (12, 22, "冬至"),
    ],
}

# 通用近似表：无精确表年份使用；边界日可能 ±1 天
_FALLBACK: list[tuple[int, int, str]] = [
    (1, 5, "小寒"), (1, 20, "大寒"), (2, 4, "立春"), (2, 19, "雨水"),
    (3, 5, "惊蛰"), (3, 20, "春分"), (4, 4, "清明"), (4, 19, "谷雨"),
    (5, 5, "立夏"), (5, 20, "小满"), (6, 5, "芒种"), (6, 21, "夏至"),
    (7, 6, "小暑"), (7, 22, "大暑"), (8, 7, "立秋"), (8, 23, "处暑"),
    (9, 7, "白露"), (9, 23, "秋分"), (10, 8, "寒露"), (10, 23, "霜降"),
    (11, 7, "立冬"), (11, 22, "小雪"), (12, 6, "大雪"), (12, 21, "冬至"),
]

_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

# 节气英文名（联合国教科文组织非遗译名）
TERM_EN: dict[str, str] = {
    "小寒": "Minor Cold",
    "大寒": "Major Cold",
    "立春": "Beginning of Spring",
    "雨水": "Rain Water",
    "惊蛰": "Awakening of Insects",
    "春分": "Spring Equinox",
    "清明": "Pure Brightness",
    "谷雨": "Grain Rain",
    "立夏": "Beginning of Summer",
    "小满": "Grain Buds",
    "芒种": "Grain in Ear",
    "夏至": "Summer Solstice",
    "小暑": "Minor Heat",
    "大暑": "Major Heat",
    "立秋": "Beginning of Autumn",
    "处暑": "End of Heat",
    "白露": "White Dew",
    "秋分": "Autumn Equinox",
    "寒露": "Cold Dew",
    "霜降": "Frost's Descent",
    "立冬": "Beginning of Winter",
    "小雪": "Minor Snow",
    "大雪": "Major Snow",
    "冬至": "Winter Solstice",
}


def current_solar_term(today: date) -> str:
    """today 所处的节气（该日或之前最近一个节气）。"""
    terms = _EXACT.get(today.year, _FALLBACK)
    current: str | None = None
    for month, day, name in terms:
        if (today.month, today.day) >= (month, day):
            current = name
        else:
            break
    # 1 月 1 日 ~ 小寒前：仍处上一年的冬至
    return current if current is not None else "冬至"


def weekday_name(today: date) -> str:
    return _WEEKDAYS[today.weekday()]
