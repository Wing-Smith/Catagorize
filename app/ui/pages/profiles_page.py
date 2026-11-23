"""文件夹页：画像卡片列表（每卡片可删除）+ 新建/刷新入口。

删除 = 从 Catagorize 移除管理：画像 JSON、索引行、操作日志一并清除，
磁盘上的文件一律不动（产品底线：不替用户删文件）。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    PushButton,
    StrongBodyLabel,
    setCustomStyleSheet,
)

from app.core.i18n import tr
from app.core.models import FolderProfile
from app.core.store import Database, ProfileStore
from app.ui.pages.base_page import BasePage, ElidedLabel

_DELETE_RED_QSS = """
    PushButton {
        background-color: #C42B1C;
        color: white;
        border-color: #A5281A;
    }
    PushButton:hover { background-color: #B12718; }
    PushButton:pressed { background-color: #8F2115; }
    PushButton:disabled { background-color: #4A4A4A; border-color: #3A3A3A; color: #9A9A9A; }
"""


class ProfilesPage(BasePage):
    def title(self) -> str:
        return tr("nav.profiles")

    def subtitle(self) -> str:
        return tr("profiles.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProfileStore()
        self._db = Database().open()

        row = QHBoxLayout()
        row.setSpacing(8)
        self.add_btn = PushButton("")
        self.add_btn.clicked.connect(self._add_profile)
        self.refresh_btn = PushButton("")
        self.refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.add_btn)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        self.body().addLayout(row)

        # 画像卡片容器（refresh 时重建）
        self._cards = QVBoxLayout()
        self._cards.setSpacing(8)
        self.body().addLayout(self._cards)
        self.body().addStretch(1)
        self.retranslate()
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def retranslate(self) -> None:
        super().retranslate()
        self.add_btn.setText(tr("profiles.add"))
        self.refresh_btn.setText(tr("profiles.refresh"))
        self.refresh()

    # ---------- 列表 ----------

    def refresh(self) -> None:
        # 清空旧卡片（先摘父再 deleteLater：页面未显示时延迟删除不触发，会残留）
        while self._cards.count():
            item = self._cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        profiles = self._store.list_all()
        if not profiles:
            hint = BodyLabel(tr("profiles.empty"))
            hint.setWordWrap(True)
            self._cards.addWidget(hint)
            return
        for p in profiles:
            self._cards.addWidget(self._build_card(p))

    def _build_card(self, profile: FolderProfile) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(StrongBodyLabel(profile.name))
        if not profile.root.is_dir():
            warn = BodyLabel(tr("overview.card.unreachable"))
            warn.setStyleSheet("color: #C42B1C;")
            header.addWidget(warn)
        header.addStretch(1)
        delete_btn = PushButton(tr("profiles.delete"))
        setCustomStyleSheet(delete_btn, _DELETE_RED_QSS, _DELETE_RED_QSS)
        delete_btn.clicked.connect(lambda _=False, p=profile: self._confirm_delete(p))
        header.addWidget(delete_btn)
        layout.addLayout(header)

        root_label = ElidedLabel(str(profile.root))
        root_label.setStyleSheet("color: rgba(128,128,128,0.9);")
        layout.addWidget(root_label)

        mode = tr("profiles.mode.flow") if profile.mode == "flow" else tr("profiles.mode.archive")
        rules = tr("profiles.rules.count", n=len(profile.rules)) if profile.rules else tr("profiles.rules.none")
        watch = f" · {tr('profiles.watching')}" if profile.watch else ""
        meta = BodyLabel(f"{mode} · {rules}{watch}")
        meta.setStyleSheet("color: rgba(128,128,128,0.9);")
        layout.addWidget(meta)
        return card

    # ---------- 删除 ----------

    def _confirm_delete(self, profile: FolderProfile) -> None:
        indexed = self._db.profile_stats(profile.profile_id)["files"]
        box = MessageBox(
            tr("profiles.delete.title"),
            tr("profiles.delete.msg", name=profile.name, n=indexed),
            self.window() or self,
        )
        box.yesButton.setText(tr("common.confirm"))
        box.cancelButton.setText(tr("common.cancel"))
        if not box.exec():
            return
        self._store.delete(profile.profile_id)
        self._db.purge_profile(profile.profile_id)
        from app.core import logbus

        logbus.info(f"profile removed: {profile.name}")
        InfoBar.success(
            tr("profiles.delete.done", name=profile.name), "",
            parent=self, position=InfoBarPosition.TOP,
        )
        self.refresh()

    # ---------- 新建 ----------

    def _add_profile(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("profiles.dialog.title"))
        if not path:
            return
        root = Path(path)
        profile = FolderProfile(
            name=root.name or tr("profiles.unnamed"),
            root=root,
            mode="flow" if "download" in root.name.lower() else "archive",
        )
        self._store.save(profile)
        from app.core import logbus

        logbus.info(f"profile added: {profile.name} ({profile.root})")
        self.refresh()
