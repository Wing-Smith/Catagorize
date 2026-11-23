"""导出页：把受管文件夹的目录结构导成 PowerShell tree 风格文本。

格式可选 Markdown（```text 围栏）或纯 txt；可附带文件大小。
生成是即时遍历（只 stat 不读内容，比指纹扫描轻得多），结果进
预览框，一键复制或另存为文件。
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    CheckBox,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from app.core.i18n import tr
from app.core.store import ProfileStore
from app.core.tree_export import MAX_ENTRIES, build_tree, wrap_markdown
from app.ui.pages.base_page import BasePage, ElidedLabel

_FORMAT_MARKDOWN = "markdown"
_FORMAT_TXT = "txt"


class ExportPage(BasePage):
    def title(self) -> str:
        return tr("nav.export")

    def subtitle(self) -> str:
        return tr("export.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProfileStore()

        # ---- 选项行 ----
        opts = QHBoxLayout()
        opts.setSpacing(8)
        self.profile_label = StrongBodyLabel("")
        opts.addWidget(self.profile_label)
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(260)
        opts.addWidget(self.profile_combo)

        self.format_label = StrongBodyLabel("")
        opts.addWidget(self.format_label)
        self.format_combo = ComboBox()
        self.format_combo.setMinimumWidth(140)
        self.format_combo.currentIndexChanged.connect(lambda _i: self._render())
        opts.addWidget(self.format_combo)

        self.size_check = CheckBox("")
        opts.addWidget(self.size_check)

        self.generate_btn = PrimaryPushButton("")
        self.generate_btn.clicked.connect(self._generate)
        opts.addWidget(self.generate_btn)
        opts.addStretch(1)
        self.body().addLayout(opts)

        # ---- 预览 ----
        self.preview = PlainTextEdit()
        self.preview.setReadOnly(True)
        font = self.preview.font()
        font.setFamily("Cascadia Mono, Consolas, monospace")
        self.preview.setFont(font)
        self.body().addWidget(self.preview, 1)

        # ---- 状态 + 复制 / 保存 ----
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.status = ElidedLabel("")
        bottom.addWidget(self.status, 1)
        self.copy_btn = PushButton("")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy)
        bottom.addWidget(self.copy_btn)
        self.save_btn = PushButton("")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        bottom.addWidget(self.save_btn)
        self.body().addLayout(bottom)

        self._tree_text = ""  # 原始树文本（未包 markdown 围栏）
        self._truncated = False
        self.retranslate()

    # ---------- 文案 ----------

    def retranslate(self) -> None:
        super().retranslate()
        self.profile_label.setText(tr("export.profile"))
        self.format_label.setText(tr("export.format"))
        self.size_check.setText(tr("export.show_size"))
        self.generate_btn.setText(tr("export.generate"))
        self.copy_btn.setText(tr("export.copy"))
        self.save_btn.setText(tr("export.save"))
        if not self._tree_text:
            self.status.setText(tr("export.empty_hint"))
        # 下拉显示名走 tr，blockSignals 防止误触发
        current_format = self.format_combo.currentData()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItem(tr("export.format.markdown"), userData=_FORMAT_MARKDOWN)
        self.format_combo.addItem(tr("export.format.txt"), userData=_FORMAT_TXT)
        if current_format:
            index = self.format_combo.findData(current_format)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
        self.format_combo.blockSignals(False)

    def on_show(self) -> None:
        current = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self._store.list_all():
            self.profile_combo.addItem(p.name, userData=p.profile_id)
        if current:
            index = self.profile_combo.findData(current)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    # ---------- 生成 / 复制 / 保存 ----------

    def _generate(self) -> None:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            self.status.setText(tr("export.no_profile"))
            return
        try:
            profile = self._store.load(profile_id)
        except Exception as exc:  # noqa: BLE001 - 统一走 InfoBar
            InfoBar.error(tr("export.failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return
        try:
            tree, truncated = build_tree(profile.root, show_size=self.size_check.isChecked())
        except Exception as exc:  # noqa: BLE001
            InfoBar.error(tr("export.failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return
        self._tree_text = tree
        self._truncated = truncated
        self._render()
        self.generate_btn.setText(tr("export.regenerate"))

    def _render(self) -> None:
        if not self._tree_text:
            return
        if self.format_combo.currentData() == _FORMAT_MARKDOWN:
            shown = wrap_markdown(self._tree_text)
        else:
            shown = self._tree_text
        self.preview.setPlainText(shown)
        status = tr("export.truncated", n=MAX_ENTRIES) if self._truncated else ""
        self.status.setText(status)
        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.preview.toPlainText())
        InfoBar.success(tr("export.copied"), "", parent=self, position=InfoBarPosition.TOP)

    def _save(self) -> None:
        fmt = self.format_combo.currentData()
        if fmt == _FORMAT_MARKDOWN:
            default_name, filter_str = "tree.md", tr("export.filter.md")
        else:
            default_name, filter_str = "tree.txt", tr("export.filter.txt")
        path, _sel = QFileDialog.getSaveFileName(
            self, tr("export.save"), default_name, filter_str
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self.preview.toPlainText())
        except OSError as exc:
            InfoBar.error(tr("export.failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return
        InfoBar.success(tr("export.saved", path=path), "", parent=self, position=InfoBarPosition.TOP)
