"""总览页：欢迎头图 + 时钟 + 功能快捷卡片 + 画像健康卡片。

数据全部来自本地存储：画像列表（ProfileStore JSON）、文件索引与
操作日志（SQLite）。打开页面或切到该页时刷新画像区，不碰文件系统。
"""

from __future__ import annotations

import platform
import time as time_mod
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, Signal, qVersion
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon as FIF,
    IconWidget,
    ImageLabel,
    PushButton,
    StrongBodyLabel,
    TitleLabel,
)

from app.core import config
from app.core.assets import asset
from app.core.config import APP_VERSION, GUI_BASE_NAME, GUI_BASE_VERSION
from app.core.i18n import language, tr
from app.core.models import FileRecord, FolderProfile, human_size
from app.core.planner import records_to_rows
from app.core.rules import resolve
from app.core.scanner import scan_with_digests
from app.core.solar_term import TERM_EN, current_solar_term
from app.core.store import Database, ProfileStore
from app.core.updater import UpdateStatus
from app.services.job_manager import JobWorker
from app.ui.pages.base_page import BasePage, ElidedLabel

_WEEKDAY_KEYS = ("weekday.1", "weekday.2", "weekday.3", "weekday.4", "weekday.5", "weekday.6", "weekday.0")


class _ClockWidget(QWidget):
    """右上角时钟：系统时间（精确到秒）+ 日期 + 当前节气。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.time_label = TitleLabel("")
        font = self.time_label.font()
        font.setPointSize(24)
        font.setBold(True)
        self.time_label.setFont(font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)

        self.date_label = BodyLabel("")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label.setStyleSheet("color: rgba(128,128,128,0.9);")
        layout.addWidget(self.date_label)

        self.term_label = BodyLabel("")
        self.term_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.term_label.setStyleSheet("color: rgba(128,128,128,0.9);")
        layout.addWidget(self.term_label)

        self.refresh()

    def refresh(self) -> None:
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M:%S"))
        weekday = tr(_WEEKDAY_KEYS[now.weekday()])
        if language() == "zh":
            self.date_label.setText(f"{now.year} 年 {now.month} 月 {now.day} 日　{weekday}")
        else:
            self.date_label.setText(f"{weekday}, {now.year}-{now.month:02d}-{now.day:02d}")
        term = current_solar_term(now.date())
        if language() == "en":
            term = TERM_EN.get(term, term)
        self.term_label.setText(tr("overview.clock.solar_term", term=term))


class _ShortcutCard(CardWidget):
    """功能入口卡片：蓝色装饰竖线 + 图标 + 标题 + 一句话，点击跳转对应页。"""

    def __init__(self, icon, title_key: str, subtitle_key: str, parent=None):
        super().__init__(parent)
        self._title_key = title_key
        self._subtitle_key = subtitle_key
        self.setMinimumHeight(72)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        # WinUI 3 风格蓝色装饰竖线（跟主题色走：palette(Highlight)）
        accent = QWidget(self)
        accent.setFixedWidth(3)
        accent.setStyleSheet(
            "background: palette(Highlight); border-radius: 1px; background-color: #0078D4;"
        )
        row.addWidget(accent)

        glyph = IconWidget(icon, self)
        glyph.setFixedSize(28, 28)
        row.addWidget(glyph)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title_lbl = StrongBodyLabel("")
        self.sub_lbl = BodyLabel("")
        self.sub_lbl.setStyleSheet("color: rgba(128,128,128,0.9);")
        text.addWidget(self.title_lbl)
        text.addWidget(self.sub_lbl)
        row.addLayout(text, 1)
        self.retranslate()

    def retranslate(self) -> None:
        self.title_lbl.setText(tr(self._title_key))
        self.sub_lbl.setText(tr(self._subtitle_key))


class OverviewPage(BasePage):
    update_check_requested = Signal()  # 「立即检查」→ MainWindow 的后台检查器

    def title(self) -> str:
        return tr("nav.overview")

    def subtitle(self) -> str:
        return tr("overview.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProfileStore()
        self._db = Database().open()

        self._build_header()
        self._build_hero()
        self._build_shortcuts()

        # 画像健康区（on_show 时重建）
        self._grid = QGridLayout()
        self._grid.setSpacing(12)
        self.body().addLayout(self._grid)

        # 后台补扫索引的提示条（默认隐藏）
        self._scan_hint = BodyLabel("")
        self._scan_hint.setStyleSheet("color: rgba(128,128,128,0.9);")
        self._scan_hint.setVisible(False)
        self.body().addWidget(self._scan_hint)

        self.body().addStretch(1)

        # 后台补扫：索引为空的画像逐个扫描入库
        self._worker: JobWorker | None = None
        self._scan_queue: list[FolderProfile] = []

        # 底部信息卡：数据与缓存 / 关于 / 更新
        self._build_footer_cards()

        # 时钟每秒走字
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._clock.refresh)
        self._timer.start()

    # ---------- 静态区 ----------

    def _build_header(self) -> None:
        """把标题/副标题包进横向布局，右侧放时钟。"""
        self._clock = _ClockWidget(self)
        header = QHBoxLayout()
        header.setSpacing(16)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        header.addLayout(texts, 1)
        header.addWidget(self._clock)
        # 替换 BasePage 默认的标题区（先移除旧项再插入）
        self.body().removeWidget(self.title_label)
        self.body().removeWidget(self.subtitle_label)
        self.body().insertLayout(0, header)

    def _build_hero(self) -> None:
        hero = QHBoxLayout()
        hero.setSpacing(16)
        avatar = ImageLabel(str(asset("icon.png")))
        avatar.setFixedSize(64, 64)
        avatar.setBorderRadius(14, 14, 14, 14)
        hero.addWidget(avatar)

        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.greeting_label = TitleLabel("")
        texts.addWidget(self.greeting_label)
        self.hero_tag = BodyLabel("")
        self.hero_tag.setStyleSheet("color: rgba(128,128,128,0.9);")
        texts.addWidget(self.hero_tag)
        hero.addLayout(texts, 1)
        self.body().addLayout(hero)
        self._retranslate_hero()

    def _retranslate_hero(self) -> None:
        self.greeting_label.setText(self._greeting())
        self.hero_tag.setText(tr("overview.tagline") + "\n" + tr("overview.tagline2"))

    @staticmethod
    def _greeting() -> str:
        hour = datetime.now().hour
        if hour < 6:
            return tr("overview.greeting.night")
        if hour < 12:
            return tr("overview.greeting.morning")
        if hour < 18:
            return tr("overview.greeting.afternoon")
        return tr("overview.greeting.evening")

    def _build_shortcuts(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        entries = [
            (FIF.HEART, "overview.shortcut.inspect", "overview.shortcut.inspect.sub", "inspect_page"),
            (FIF.PIE_SINGLE, "overview.shortcut.treemap", "overview.shortcut.treemap.sub", "treemap_page"),
            (FIF.SEARCH, "overview.shortcut.search", "overview.shortcut.search.sub", "search_page"),
            (FIF.FOLDER, "overview.shortcut.profiles", "overview.shortcut.profiles.sub", "profiles_page"),
        ]
        self._shortcut_cards = []
        for i, (icon, title_key, sub_key, attr) in enumerate(entries):
            card = _ShortcutCard(icon, title_key, sub_key)
            card.clicked.connect(lambda _=False, a=attr: self._navigate(a))
            grid.addWidget(card, i // 2, i % 2)
            self._shortcut_cards.append(card)
        self.body().addLayout(grid)

    def _navigate(self, attr: str) -> None:
        window = self.window()
        target = getattr(window, attr, None)
        switch = getattr(window, "switchTo", None)
        if target is not None and callable(switch):
            switch(target)

    # ---------- 底部信息卡（数据与缓存 / 关于 / 更新） ----------

    def _kv(self, layout: QVBoxLayout) -> tuple[BodyLabel, BodyLabel]:
        """一行键值对：灰色键 + 值，返回 (键, 值) 便于重翻译与更新。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        key = BodyLabel("")
        key.setStyleSheet("color: rgba(128,128,128,0.9);")
        value = ElidedLabel("")
        row.addWidget(key)
        row.addWidget(value, 1)
        layout.addLayout(row)
        return key, value

    def _build_footer_cards(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._footer_cards = []

        # 数据与缓存
        card = CardWidget()
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(6)
        self.data_title = StrongBodyLabel("")
        body.addWidget(self.data_title)
        self.data_dir_key, self.data_dir_value = self._kv(body)
        self.data_size_key, self.data_size_value = self._kv(body)
        self.data_open_btn = PushButton("")
        self.data_open_btn.clicked.connect(self._open_config_dir)
        body.addWidget(self.data_open_btn)
        row.addWidget(card, 1)
        self._footer_cards.append(card)

        # 关于
        card = CardWidget()
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(6)
        self.about_title = StrongBodyLabel("")
        body.addWidget(self.about_title)
        self.about_line = BodyLabel("")
        self.about_line.setWordWrap(True)
        body.addWidget(self.about_line)
        self.about_env = BodyLabel("")
        self.about_env.setStyleSheet("color: rgba(128,128,128,0.9);")
        self.about_env.setWordWrap(True)
        body.addWidget(self.about_env)
        self.about_gui = BodyLabel("")
        self.about_gui.setStyleSheet("color: rgba(128,128,128,0.9);")
        self.about_gui.setWordWrap(True)
        body.addWidget(self.about_gui)
        self.about_copyright = BodyLabel("")
        self.about_copyright.setStyleSheet("color: rgba(128,128,128,0.9);")
        self.about_copyright.setWordWrap(True)
        body.addWidget(self.about_copyright)
        row.addWidget(card, 1)
        self._footer_cards.append(card)

        # 更新
        card = CardWidget()
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(6)
        self.update_title = StrongBodyLabel("")
        body.addWidget(self.update_title)
        self.update_conn_key, self.update_conn_value = self._kv(body)
        self.update_cur_key, self.update_cur_value = self._kv(body)
        self.update_latest_key, self.update_latest_value = self._kv(body)
        self.update_check_btn = PushButton("")
        self.update_check_btn.clicked.connect(self._on_check_now)
        body.addWidget(self.update_check_btn)
        row.addWidget(card, 1)
        self._footer_cards.append(card)

        self.body().addLayout(row)
        self._last_update_status: UpdateStatus | None = None
        self._retranslate_footer()
        self._refresh_data_card()

    def _retranslate_footer(self) -> None:
        self.data_title.setText(tr("overview.card.data_cache"))
        self.data_dir_key.setText(tr("overview.data.config_dir"))
        self.data_size_key.setText(tr("overview.data.index_size"))
        self.data_open_btn.setText(tr("overview.data.open_dir"))
        self.about_title.setText(tr("overview.card.about"))
        self.about_line.setText(tr("overview.about.line", ver=APP_VERSION))
        self.about_env.setText(
            tr("overview.about.env", py=platform.python_version(), qt=qVersion())
        )
        self.about_gui.setText(
            tr("about.gui_base", name=GUI_BASE_NAME, ver=GUI_BASE_VERSION)
        )
        self.about_copyright.setText(tr("overview.about.copyright"))
        self.update_title.setText(tr("overview.card.updates"))
        self.update_conn_key.setText(tr("overview.update.conn"))
        self.update_cur_key.setText(tr("overview.update.current"))
        self.update_latest_key.setText(tr("overview.update.latest"))
        self.update_cur_value.setText(f"v{APP_VERSION}")
        self.update_check_btn.setText(tr("overview.update.check"))
        self.show_update_status(self._last_update_status)

    def _refresh_data_card(self) -> None:
        self.data_dir_value.setText(str(config.config_dir()))
        index = config.index_path()
        self.data_size_value.setText(human_size(index.stat().st_size) if index.exists() else "—")

    def _open_config_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.config_dir())))

    # ---------- 更新检查（结果由 MainWindow 的后台线程回送） ----------

    def _on_check_now(self) -> None:
        self.update_check_requested.emit()

    def show_update_status(self, status: UpdateStatus | None) -> None:
        self._last_update_status = status
        self.update_check_btn.setEnabled(status is None or not status.checking)
        if status is None:
            self.update_conn_value.setText(tr("overview.update.conn.unknown"))
            self.update_conn_value.setStyleSheet("color: rgba(128,128,128,0.9);")
            self.update_latest_value.setText("—")
            return
        if status.checking:
            self.update_conn_value.setText(tr("overview.update.conn.checking"))
            self.update_conn_value.setStyleSheet("color: rgba(128,128,128,0.9);")
            return
        if status.connected:
            self.update_conn_value.setText(tr("overview.update.conn.ok"))
            self.update_conn_value.setStyleSheet("color: #2EA043;")
            self.update_conn_value.setToolTip("")
            self.update_latest_value.setText(f"v{status.latest}" if status.latest else tr("overview.update.none"))
        else:
            self.update_conn_value.setText(tr("overview.update.conn.fail"))
            self.update_conn_value.setStyleSheet("color: #C42B1C;")
            self.update_conn_value.setToolTip(status.error)
            self.update_latest_value.setText("—")

    # ---------- 画像健康区 ----------

    def on_show(self) -> None:
        self._refresh_profiles()
        self._refresh_data_card()
        self._ensure_index()

    # ---------- 后台补扫索引 ----------

    def _ensure_index(self) -> None:
        """索引为空的画像后台补扫：不点体检页，总览卡片也能有数据。

        已扫描过的画像不重复扫（避免每次切页都全量哈希），数据保鲜
        由体检页 / 拼图页的人工扫描负责。
        """
        if self._worker is not None and self._worker.isRunning():
            return
        self._scan_queue = [
            p for p in self._store.list_all()
            if p.root.is_dir() and self._db.profile_stats(p.profile_id)["files"] == 0
        ]
        self._pump_scan_queue()

    def _pump_scan_queue(self) -> None:
        if not self._scan_queue:
            self._scan_hint.setVisible(False)
            return
        profile = self._scan_queue.pop(0)
        self._scan_hint.setText(tr("overview.indexing", name=profile.name))
        self._scan_hint.setVisible(True)

        def job(progress, token):
            records = scan_with_digests(profile.root, progress, token)
            return profile, records

        self._worker = JobWorker(job, parent=self)
        self._worker.finished_ok.connect(self._on_index_scan_done)
        self._worker.failed.connect(lambda _msg: self._pump_scan_queue())
        self._worker.start()

    def _on_index_scan_done(self, result) -> None:
        profile, records = result
        self._db.upsert_files(profile.profile_id, records_to_rows(profile.profile_id, records))
        from app.core import logbus

        logbus.info(f"index built in background: {profile.name} -> {len(records)} files")
        self._refresh_profiles()
        self._pump_scan_queue()

    def _pending_count(self, profile: FolderProfile) -> int:
        """索引行里命中已启用规则的文件数。规则匹配是纯计算，量级再大也快。"""
        rules = [r for r in profile.rules if r.enabled]
        if not rules:
            return 0
        count = 0
        for row in self._db.rows_for_profile(profile.profile_id):
            record = FileRecord(
                path_rel=row["path_rel"],
                size=row["size"],
                mtime=row["mtime"],
                ext=row["ext"],
                digest=row["digest"],
            )
            if resolve(record, rules) is not None:
                count += 1
        return count

    def _refresh_profiles(self) -> None:
        # 清空旧卡片（先摘父再 deleteLater：页面未显示时延迟删除不触发，会残留）
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        profiles = self._store.list_all()
        if not profiles:
            hint = BodyLabel(tr("overview.empty"))
            hint.setWordWrap(True)
            self._grid.addWidget(hint, 0, 0)
            return

        total_files = 0
        total_size = 0
        cards = []
        for profile in profiles:
            stats = self._db.profile_stats(profile.profile_id)
            total_files += stats["files"]
            total_size += stats["total_size"]
            cards.append(self._build_card(profile, stats))

        for i, card in enumerate(cards):
            self._grid.addWidget(card, i // 2, i % 2)

        summary = BodyLabel(
            tr("overview.summary", n=len(profiles), files=total_files, size=human_size(total_size))
        )
        summary.setStyleSheet("color: rgba(128,128,128,0.9);")
        self._grid.addWidget(summary, (len(cards) + 1) // 2, 0, 1, 2)

    def _build_card(self, profile: FolderProfile, stats: dict) -> CardWidget:
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
        layout.addLayout(header)

        root_label = ElidedLabel(str(profile.root))
        root_label.setStyleSheet("color: rgba(128,128,128,0.9);")
        layout.addWidget(root_label)

        pending = self._pending_count(profile)
        digested = stats["digested"]
        files = stats["files"]
        cover = f"{digested / files * 100:.0f}%" if files else "—"
        ts = self._db.last_organize_ts(profile.profile_id)
        last = time_mod.strftime("%Y-%m-%d %H:%M", time_mod.localtime(ts)) if ts else tr("overview.card.never")

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addWidget(BodyLabel(f"{tr('overview.card.files')}　{stats['files']}"))
        row1.addWidget(BodyLabel(f"{tr('overview.card.size')}　{human_size(stats['total_size'])}"))
        dup = BodyLabel(f"{tr('overview.card.dup')}　{stats['dup_groups']}")
        if stats["dup_groups"]:
            dup.setStyleSheet("color: #D68F00;")
        row1.addWidget(dup)
        row1.addStretch(1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        pending_label = BodyLabel(f"{tr('overview.card.pending')}　{pending}")
        if pending:
            pending_label.setStyleSheet("color: #0078D4;")
        row2.addWidget(pending_label)
        row2.addWidget(BodyLabel(f"{tr('overview.card.cover')}　{cover}"))
        row2.addWidget(BodyLabel(f"{tr('overview.card.last')}　{last}"))
        row2.addStretch(1)
        layout.addLayout(row2)

        return card

    def retranslate(self) -> None:
        super().retranslate()
        self._retranslate_hero()
        for card in getattr(self, "_shortcut_cards", []):
            card.retranslate()
        self._refresh_profiles()  # 卡片文案全是 tr，直接重建
        self._retranslate_footer()
        self._refresh_data_card()
        self._clock.refresh()
