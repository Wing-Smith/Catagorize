"""页面骨架：透明底 + 标题区，保证 Mica 背景下不糊一层死白。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel


class ElidedLabel(BodyLabel):
    """单行标签：内容超长时按当前宽度中段加省略号，不把窗口撑宽。

    保存完整文本，宽度变化（含窗口拉伸）时重新裁剪。
    """

    def __init__(self, text: str = "", parent=None):
        self._full_text = text
        super().__init__(parent)
        self.setWordWrap(False)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt 约定
        self._full_text = text
        self.setToolTip(text)
        self._reelide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        self._reelide()
        super().resizeEvent(event)

    def sizeHint(self):  # noqa: N802 - Qt 约定
        """固有宽度封顶，避免布局初期把窗口撑宽（实际显示以 resize 重裁剪为准）。"""
        hint = super().sizeHint()
        fm = self.fontMetrics()
        cap = fm.elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, 240)
        return hint.boundedTo(fm.boundingRect(cap).size())

    def minimumSizeHint(self):  # noqa: N802 - Qt 约定
        fm = self.fontMetrics()
        return fm.boundingRect("…").size()

    def _reelide(self) -> None:
        fm = self.fontMetrics()
        width = max(self.width(), 1)
        # 多行文本逐行裁剪，任何一行都不撑宽窗口
        elided = "\n".join(
            fm.elidedText(line, Qt.TextElideMode.ElideMiddle, width)
            for line in self._full_text.split("\n")
        )
        super().setText(elided)

    def fullText(self) -> str:  # noqa: N802 - Qt 风格命名
        return self._full_text


class BasePage(QWidget):
    """所有导航页的基类：Mica 透明底、统一标题结构、on_show 刷新钩子。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(type(self).__name__)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(36, 28, 36, 24)
        self._layout.setSpacing(12)
        self.title_label = TitleLabel(self.title())
        self.subtitle_label = BodyLabel(self.subtitle())
        self.subtitle_label.setStyleSheet("color: rgba(128,128,128,0.9);")
        self._layout.addWidget(self.title_label)
        self._layout.addWidget(self.subtitle_label)
        self._layout.addSpacing(8)

    def title(self) -> str:
        return ""

    def subtitle(self) -> str:
        return ""

    def body(self) -> QVBoxLayout:
        return self._layout

    def on_show(self) -> None:
        """切到该页时由 MainWindow 调用；默认无事可做。"""

    def retranslate(self) -> None:
        """语言切换时刷新静态文案；子类覆写并调用 super()。"""
        self.title_label.setText(self.title())
        self.subtitle_label.setText(self.subtitle())
