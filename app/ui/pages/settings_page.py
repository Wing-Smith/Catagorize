"""设置页：语言 / 主题（立即生效）+ 检查更新 + 恢复默认 + 关于。

更新固定从内置 GitHub 源拉取，不提供自定义更新源输入。
布局仿 Catlas 设置页：整宽设置行（标签左、控件右），底部关于区带图标。
"""

from __future__ import annotations

import platform

from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    IconWidget,
    InfoBar,
    InfoBarPosition,
    PushButton,
    StrongBodyLabel,
)

from app.core import config
from app.core.assets import asset
from app.core.config import APP_VERSION, GUI_BASE_NAME, GUI_BASE_VERSION, PORTABLE
from app.core.i18n import language, reset_to_system, set_language, tr
from app.ui.pages.base_page import BasePage
from app.ui.theme import apply_fluent_theme

_THEME_VALUES = ("auto", "light", "dark")


class SettingsPage(BasePage):
    def title(self) -> str:
        return tr("nav.settings")

    def subtitle(self) -> str:
        return tr("settings.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- 设置行（标签左、控件右，整宽） ----
        def setting_row(label_widget, control) -> None:
            row = QHBoxLayout()
            row.setSpacing(16)
            row.addWidget(label_widget)
            row.addStretch(1)
            control.setMinimumWidth(320)
            row.addWidget(control)
            self.body().addLayout(row)

        self.lang_label = BodyLabel("")
        self.lang_combo = ComboBox()
        self.lang_combo.addItem(tr("settings.lang.zh"), userData="zh")
        self.lang_combo.addItem(tr("settings.lang.en"), userData="en")
        self.lang_combo.setCurrentIndex(0 if language() == "zh" else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        setting_row(self.lang_label, self.lang_combo)

        self.theme_label = BodyLabel("")
        self.theme_combo = ComboBox()
        for value in _THEME_VALUES:
            self.theme_combo.addItem("", userData=value)
        self._sync_theme_combo()
        self.theme_combo.currentIndexChanged.connect(self._on_theme)
        setting_row(self.theme_label, self.theme_combo)

        self.check_update_btn = PushButton("")
        self.check_update_btn.clicked.connect(self._on_check_update)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        self.check_update_btn.setMinimumWidth(320)
        btn_row.addWidget(self.check_update_btn)
        self.body().addLayout(btn_row)

        self.reset_btn = PushButton("")
        self.reset_btn.clicked.connect(self._on_reset)
        reset_row = QHBoxLayout()
        reset_row.setSpacing(8)
        reset_row.addStretch(1)
        self.reset_btn.setMinimumWidth(320)
        reset_row.addWidget(self.reset_btn)
        self.body().addLayout(reset_row)

        self.body().addSpacing(12)

        # ---- 关于区 ----
        about = QHBoxLayout()
        about.setSpacing(16)
        icon = IconWidget()
        icon.setIcon(str(asset("icon.png")))
        icon.setFixedSize(48, 48)
        about.addWidget(icon)
        about.addSpacing(4)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.about_title = StrongBodyLabel("")
        texts.addWidget(self.about_title)
        self.about_desc = BodyLabel("")
        self.about_desc.setWordWrap(True)
        self.about_desc.setStyleSheet("color: rgba(128,128,128,0.9);")
        texts.addWidget(self.about_desc)
        self.about_env = BodyLabel("")
        self.about_env.setStyleSheet("color: rgba(128,128,128,0.9);")
        texts.addWidget(self.about_env)
        self.about_gui = BodyLabel("")
        self.about_gui.setStyleSheet("color: rgba(128,128,128,0.9);")
        texts.addWidget(self.about_gui)
        self.about_meta = BodyLabel("")
        self.about_meta.setWordWrap(True)
        self.about_meta.setStyleSheet("color: rgba(128,128,128,0.9);")
        texts.addWidget(self.about_meta)
        about.addLayout(texts, 1)
        self.body().addLayout(about)

        self.body().addStretch(1)
        self.retranslate()

    # ---------- 行为 ----------

    def _sync_theme_combo(self) -> None:
        current = config.theme()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current:
                self.theme_combo.setCurrentIndex(i)
                return

    def _on_language(self, index: int) -> None:
        lang = self.lang_combo.itemData(index)
        if lang and lang != language():
            set_language(lang)  # 持久化 + 通知全部页面 retranslate

    def _on_theme(self, index: int) -> None:
        value = self.theme_combo.itemData(index) or "auto"
        config.set_theme(value)
        apply_fluent_theme(value)

    def _on_check_update(self) -> None:
        request = getattr(self.window(), "request_update_check", None)
        if callable(request):
            request()

    def _on_reset(self) -> None:
        reset_to_system()
        config.set_theme("auto")
        self._sync_theme_combo()
        apply_fluent_theme("auto")
        InfoBar.success(
            tr("settings.reset_done"), "",
            parent=self, position=InfoBarPosition.TOP,
        )

    # ---------- 文案 ----------

    def retranslate(self) -> None:
        super().retranslate()
        self.lang_label.setText(tr("settings.language.instant"))
        self.theme_label.setText(tr("settings.theme.instant"))
        self.check_update_btn.setText(tr("settings.update.check"))
        self.reset_btn.setText(tr("settings.reset"))
        self.about_title.setText(tr("settings.about.title") + f" v{APP_VERSION}")
        self.about_desc.setText(tr("settings.about.desc"))
        self.about_env.setText(
            tr("overview.about.env", py=platform.python_version(), qt=qVersion())
        )
        self.about_gui.setText(
            tr("about.gui_base", name=GUI_BASE_NAME, ver=GUI_BASE_VERSION)
        )
        self.about_meta.setText(
            f"{tr('settings.about.data_dir')}：{config.config_dir()}\n"
            f"portable：{tr('settings.about.portable.on') if PORTABLE else tr('settings.about.portable.off')}\n"
            f"{tr('settings.about.engine')}"
        )
        # 下拉显示名也随语言换（blockSignals 防触发回调）
        self.lang_combo.blockSignals(True)
        self.lang_combo.setItemText(0, tr("settings.lang.zh"))
        self.lang_combo.setItemText(1, tr("settings.lang.en"))
        self.lang_combo.setCurrentIndex(0 if language() == "zh" else 1)
        self.lang_combo.blockSignals(False)
        self.theme_combo.blockSignals(True)
        for i, value in enumerate(_THEME_VALUES):
            self.theme_combo.setItemText(i, tr(f"settings.theme.{value}"))
        self.theme_combo.blockSignals(False)
