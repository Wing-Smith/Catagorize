"""日志页：logbus 运行时日志的实时视图，仅供排障。

logbus 回调产生在任意线程，经 Qt 信号（队列连接）切回 GUI 线程再落屏；
WARN/ERROR 按级别着色，Clear 同时清缓冲与视图。
"""

from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, PlainTextEdit, PushButton

from app.core import logbus
from app.core.i18n import tr
from app.ui.pages.base_page import BasePage

_LEVEL_COLORS = {
    "WARN": "#D68F00",
    "ERROR": "#C42B1C",
    "INFO": "#8a8a8a",
    "DEBUG": "#6e7681",
}


class LogsPage(BasePage):
    log_received = Signal(str, str)  # (level, message)，跨线程桥接

    def title(self) -> str:
        return tr("nav.logs")

    def subtitle(self) -> str:
        return tr("logs.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = PlainTextEdit()
        self.view.setReadOnly(True)
        font = self.view.font()
        font.setFamily("Cascadia Mono, Consolas, monospace")
        self.view.setFont(font)
        self.body().addWidget(self.view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.count_label = BodyLabel("")
        bottom.addWidget(self.count_label, 1)
        self.clear_btn = PushButton("")
        self.clear_btn.clicked.connect(self._clear)
        bottom.addWidget(self.clear_btn)
        self.body().addLayout(bottom)

        self.log_received.connect(self._append)
        logbus.subscribe(self._on_bus)
        self.retranslate()
        self._reload()

    def _on_bus(self, level: str, message: str) -> None:
        self.log_received.emit(level, message)

    def _append(self, level: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime())
        color = _LEVEL_COLORS.get(level, "#8a8a8a")
        line = f'<span style="color:#6e7681">[{stamp}]</span> ' \
               f'<span style="color:{color}">{level}</span> ' \
               f'<span style="color:#c9d1d9">{html.escape(message)}</span>'
        self.view.appendHtml(line)
        self._update_count()

    def _reload(self) -> None:
        self.view.clear()
        entries = list(reversed(logbus.recent(logbus._BUFFER_MAX)))
        if not entries:
            self.view.setPlainText(tr("logs.empty"))
        else:
            for _ts, level, message in entries:
                self._append(level, message)
        self._update_count()

    def _update_count(self) -> None:
        self.count_label.setText(f"{len(logbus.recent(logbus._BUFFER_MAX))}")

    def _clear(self) -> None:
        logbus.clear_buffer()
        self.view.clear()
        self.view.setPlainText(tr("logs.empty"))
        self._update_count()

    def retranslate(self) -> None:
        super().retranslate()
        self.clear_btn.setText(tr("logs.clear"))
