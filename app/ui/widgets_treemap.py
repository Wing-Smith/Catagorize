"""Treemap 绘制控件：文件 = 矩形块，面积 = 大小，颜色深浅 = 大小（对数梯度）。

布局来自 core.treemap.squarify（纯逻辑可测）；本控件只负责
上色、留白缝隙、悬浮提示和大块内的文件名标注。点击色块发出
clicked(FileRecord) 信号，多选由页面级的勾选弹窗负责。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QToolTip, QWidget

from app.core.i18n import tr
from app.core.models import FileRecord, human_size
from app.core.treemap import squarify

# 浅色 → 深色（Fluent 主色阶梯），大小越大颜色越深
_COLOR_LIGHT = QColor("#D9E6F2")
_COLOR_DARK = QColor("#1B3A5C")
_GAP = 1  # 块间留白 px
_MIN_LABEL_W = 70
_MIN_LABEL_H = 16


def _size_color(size: int, lo: float, hi: float) -> QColor:
    """log 维度上的大小 → 深浅插值；单文件/等值时取中档。"""
    if hi <= lo:
        t = 0.6
    else:
        t = (math.log(size) - lo) / (hi - lo)
        t = max(0.0, min(1.0, t))
    return QColor(
        round(_COLOR_LIGHT.red() + (_COLOR_DARK.red() - _COLOR_LIGHT.red()) * t),
        round(_COLOR_LIGHT.green() + (_COLOR_DARK.green() - _COLOR_LIGHT.green()) * t),
        round(_COLOR_LIGHT.blue() + (_COLOR_DARK.blue() - _COLOR_LIGHT.blue()) * t),
    )


class TreemapWidget(QWidget):
    """占用拼图画布。clicked 信号带出点中的 FileRecord。"""

    clicked = Signal(object)  # FileRecord

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self._records: list[FileRecord] = []
        self._rects: list[tuple[int, float, float, float, float]] = []
        self._hover: int | None = None  # rects 下标

    def set_records(self, records: list[FileRecord]) -> None:
        self._records = [r for r in records if r.size > 0 and not r.is_junk]
        self._relayout()
        self.update()

    def clear(self) -> None:
        self._records = []
        self._rects = []
        self.update()

    def records(self) -> list[FileRecord]:
        return list(self._records)

    def _relayout(self) -> None:
        sizes = [float(r.size) for r in self._records]
        self._rects = squarify(sizes, max(self.width(), 1), max(self.height(), 1))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        super().resizeEvent(event)
        self._relayout()

    # ---------- 绘制 ----------

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._rects:
            painter.setPen(QColor("#8A97A3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap.empty_hint"))
            painter.end()
            return

        sizes = [r.size for r in self._records]
        lo = math.log(min(sizes))
        hi = math.log(max(sizes))

        for i, (record_idx, x, y, w, h) in enumerate(self._rects):
            record = self._records[record_idx]
            rect_x, rect_y = x + _GAP, y + _GAP
            rect_w, rect_h = max(w - 2 * _GAP, 0.0), max(h - 2 * _GAP, 0.0)
            if rect_w <= 0 or rect_h <= 0:
                continue
            color = _size_color(record.size, lo, hi)
            if i == self._hover:
                color = color.lighter(112)
            painter.fillRect(rect_x, rect_y, rect_w, rect_h, color)

            # 够大的块写文件名（白字压深色块；块浅时用深色字）
            if rect_w >= _MIN_LABEL_W and rect_h >= _MIN_LABEL_H:
                painter.setPen(QColor("#FFFFFF") if color.lightness() < 140 else QColor("#1B3A5C"))
                name = self._records[record_idx].path_rel
                painter.drawText(
                    rect_x + 6, rect_y + 4, rect_w - 12, rect_h - 8,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextSingleLine,
                    name,
                )
        painter.end()

    @staticmethod
    def _shorten(name: str) -> str:
        return name if len(name) <= 40 else "…" + name[-39:]

    # ---------- 交互 ----------

    def _hit(self, pos: QPoint) -> int | None:
        x, y = pos.x(), pos.y()
        for i, (_idx, rx, ry, rw, rh) in enumerate(self._rects):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return i
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        hit = self._hit(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.update()
        if hit is not None:
            record = self._records[self._rects[hit][0]]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{self._shorten(record.path_rel)}\n{human_size(record.size)}",
                self,
            )
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        self._hover = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        hit = self._hit(event.position().toPoint())
        if hit is not None:
            self.clicked.emit(self._records[self._rects[hit][0]])
        super().mousePressEvent(event)
