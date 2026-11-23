"""空间拼图页：把画像里的文件按大小拼成一块矩形图。

面积 = 文件大小（squarified treemap），颜色深浅 = 大小（对数梯度，
浅色小文件 → 深色大文件）。点击色块单选；删除 / 彻底删除 / 迁移
弹出可复选的文件列表，勾完确认执行。
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QListWidgetItem
from qfluentwidgets import (
    ComboBox,
    FlowLayout,
    InfoBar,
    InfoBarPosition,
    ListWidget,
    MessageBox,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
    setCustomStyleSheet,
)

from app.core.errors import CatagorizeError
from app.core.i18n import tr
from app.core.models import FileRecord, FolderProfile, human_size
from app.core.scanner import scan_with_digests
from app.core.store import ProfileStore
from app.services import file_actions
from app.services.job_manager import JobWorker
from app.ui.pages.base_page import BasePage, ElidedLabel
from app.ui.widgets_treemap import TreemapWidget


class TreemapPage(BasePage):
    def title(self) -> str:
        return tr("nav.treemap")

    def subtitle(self) -> str:
        return tr("treemap.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProfileStore()
        self._records: list[FileRecord] = []
        self._profile: FolderProfile | None = None
        self._selected: FileRecord | None = None  # 点选中的块

        row = QHBoxLayout()
        row.setSpacing(8)
        self.profile_label = StrongBodyLabel("")
        row.addWidget(self.profile_label)
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(280)
        row.addWidget(self.profile_combo)
        self.scan_btn = PrimaryPushButton("")
        row.addWidget(self.scan_btn)
        row.addStretch(1)
        self.body().addLayout(row)

        # ---- 文件操作按钮 ----
        # FlowLayout：窗口窄时自动换行，不给页面强加过宽的最小宽度。
        # 删除/彻底删除用 WinUI 3 警示红：setCustomStyleSheet 叠加在 Fluent
        # 基础样式之上，只改颜色，字体/内边距/圆角与其他按钮保持一致。
        action_row = FlowLayout(needAni=False)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        self.body().addLayout(action_row)

        red_qss = """
            PushButton {
                background-color: #C42B1C;
                color: white;
                border-color: #A5281A;
            }
            PushButton:hover { background-color: #B12718; }
            PushButton:pressed { background-color: #8F2115; }
            PushButton:disabled { background-color: #4A4A4A; border-color: #3A3A3A; color: #9A9A9A; }
        """
        self.trash_btn = PushButton("")
        self.trash_btn.setToolTip("")
        setCustomStyleSheet(self.trash_btn, red_qss, red_qss)
        self.trash_btn.clicked.connect(self._trash_selected)
        self.wipe_btn = PushButton("")
        self.wipe_btn.setToolTip("")
        setCustomStyleSheet(self.wipe_btn, red_qss, red_qss)
        self.wipe_btn.clicked.connect(self._wipe_selected)
        self.open_btn = PushButton("")
        self.open_btn.clicked.connect(self._open_selected)
        self.reveal_btn = PushButton("")
        self.reveal_btn.clicked.connect(self._reveal_selected)
        self.migrate_btn = PushButton("")
        self.migrate_btn.clicked.connect(self._migrate_selected)
        for b in (self.trash_btn, self.wipe_btn, self.open_btn, self.reveal_btn, self.migrate_btn):
            b.setEnabled(False)
            action_row.addWidget(b)

        self.progress = ProgressBar()
        self.progress.setVisible(False)
        self.body().addWidget(self.progress)
        self.status = ElidedLabel("")
        self.body().addWidget(self.status)

        self.map = TreemapWidget()
        self.map.clicked.connect(self._on_pick)
        self.body().addWidget(self.map, 1)

        self._worker: JobWorker | None = None
        self._last_scan_key: str | None = None
        self._last_scan_at = 0.0

        self.profile_combo.currentIndexChanged.connect(self._auto_scan)
        self.scan_btn.clicked.connect(lambda: self._start_scan(auto=False))
        self.retranslate()

    def retranslate(self) -> None:
        super().retranslate()
        self.profile_label.setText(tr("treemap.profile"))
        self.scan_btn.setText(tr("treemap.rescan"))
        self.scan_btn.setToolTip(tr("treemap.rescan.tip"))
        self.trash_btn.setText(tr("treemap.trash"))
        self.trash_btn.setToolTip(tr("treemap.trash.tip"))
        self.wipe_btn.setText(tr("treemap.wipe"))
        self.wipe_btn.setToolTip(tr("treemap.wipe.tip"))
        self.open_btn.setText(tr("treemap.open"))
        self.reveal_btn.setText(tr("treemap.reveal"))
        self.migrate_btn.setText(tr("treemap.migrate"))

    def on_show(self) -> None:
        current = self.profile_combo.currentData()
        # 重建期间屏蔽信号，避免逐条触发自动扫描（可能扫到错误的画像）
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self._store.list_all():
            self.profile_combo.addItem(p.name, userData=p.profile_id)
        if current:
            index = self.profile_combo.findData(current)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._auto_scan()

    def _current_profile(self) -> FolderProfile | None:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return None
        try:
            return self._store.load(profile_id)
        except CatagorizeError as exc:
            InfoBar.error(tr("treemap.load_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return None

    _AUTO_SCAN_THROTTLE = 30.0  # 同一画像 30 秒内不重复自动扫描

    def _auto_scan(self, *_args) -> None:
        """切页 / 换画像时按当前值自动拼图。30 秒节流；扫描器忙时直接让路。"""
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return
        now = time.monotonic()
        if profile_id == self._last_scan_key and now - self._last_scan_at < self._AUTO_SCAN_THROTTLE:
            return
        if self._worker is not None and self._worker.isRunning():
            return  # 有任务在跑，不打断
        self._start_scan(auto=True)

    def _start_scan(self, auto: bool = True) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # 已有扫描在跑
        profile = self._current_profile()
        if profile is None:
            if not auto:  # 自动扫描时静默，避免每次切页都弹窗
                InfoBar.warning(tr("inspect.no_profile.warn"), tr("inspect.no_profile.hint"),
                                parent=self, position=InfoBarPosition.TOP)
            self.status.setText(tr("inspect.no_profile"))
            return
        if not profile.root.is_dir():
            msg = tr("inspect.root_missing", root=profile.root)
            self.status.setText(msg)
            if not auto:
                InfoBar.error(tr("inspect.root_missing.title"), msg, parent=self,
                              position=InfoBarPosition.TOP)
            return

        self.scan_btn.setEnabled(False)
        self.progress.setVisible(True)

        def job(progress, token):
            records = scan_with_digests(profile.root, progress, token)
            return profile, records

        self._worker = JobWorker(job, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int, msg: str) -> None:
        if total:
            self.progress.setValue(int(done / total * 100))
        self.status.setText(msg)

    def _on_done(self, result) -> None:
        profile, records = result
        self._last_scan_key = profile.profile_id
        self._last_scan_at = time.monotonic()
        self._profile = profile
        self._records = records
        self._selected = None
        from app.core import logbus

        logbus.info(f"treemap scan done: {profile.name} -> {len(records)} files")
        self.map.set_records(records)
        self._update_action_buttons()
        total_size = sum(r.size for r in records)
        self.status.setText(
            tr("treemap.done_status", name=profile.name, n=len(records),
               size=human_size(total_size))
        )
        self.scan_btn.setEnabled(True)
        self.progress.setVisible(False)

    def _on_failed(self, message: str) -> None:
        from app.core import logbus

        logbus.warn(f"treemap scan failed: {message}")
        self.scan_btn.setEnabled(True)
        self.progress.setVisible(False)
        InfoBar.error(tr("treemap.scan_failed"), message, parent=self, position=InfoBarPosition.TOP)

    # ---------- 点选 / 目标 ----------

    def _on_pick(self, record: FileRecord) -> None:
        self._selected = record
        self.status.setText(
            tr("treemap.picked", path=record.path_rel, size=human_size(record.size))
        )
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        busy = self._worker is not None and self._worker.isRunning()
        has_records = bool(self._records)
        # 删除/彻底删除/迁移：有文件即可弹列表复选
        for b in (self.trash_btn, self.wipe_btn, self.migrate_btn):
            b.setEnabled(has_records and not busy)
        # 打开/定位：只对点选的单文件直接生效
        single = self._selected is not None and has_records
        self.open_btn.setEnabled(single and not busy)
        self.reveal_btn.setEnabled(single and not busy)

    def _pick_records(self, title: str, intro: str) -> list[FileRecord]:
        """弹出文件复选列表；返回勾选的记录（取消返回空）。"""
        if not self._records:
            return []
        prechecked = {self._selected.path_rel} if self._selected else set()
        dlg = _FilePickDialog(title, intro, self._records, prechecked, self.window())
        if dlg.exec():
            return dlg.chosen()
        return []

    def _abs(self, record: FileRecord) -> Path | None:
        if self._profile is None:
            return None
        return self._profile.root / record.path_rel

    # ---------- 文件操作 ----------

    def _trash_selected(self) -> None:
        picked = self._pick_records(tr("treemap.pick.trash_title"), tr("treemap.pick.trash_intro"))
        if not picked:
            self.status.setText(tr("treemap.pick.none"))
            return
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        gone = file_actions.trash_files(paths)
        InfoBar.success(tr("treemap.trash_done"), tr("treemap.trash_count", n=gone),
                        parent=self, position=InfoBarPosition.TOP)
        self._refresh_after_action()

    def _wipe_selected(self) -> None:
        picked = self._pick_records(tr("treemap.pick.wipe_title"), tr("treemap.pick.wipe_intro"))
        if not picked:
            self.status.setText(tr("treemap.pick.none"))
            return
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        ok, failed = file_actions.delete_files(paths)
        if failed:
            InfoBar.warning(tr("treemap.wipe_part"),
                            tr("dialog.ok_count", ok=ok, failed=len(failed)),
                            parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.success(tr("treemap.wipe_done"), tr("treemap.trash_count", n=ok),
                            parent=self, position=InfoBarPosition.TOP)
        self._refresh_after_action()

    def _open_selected(self) -> None:
        if self._selected is None:
            return
        path = self._abs(self._selected)
        if path is None:
            return
        try:
            file_actions.open_with_default(path)
        except OSError as exc:
            InfoBar.error(tr("treemap.open_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)

    def _reveal_selected(self) -> None:
        if self._selected is None:
            return
        path = self._abs(self._selected)
        if path is None:
            return
        try:
            file_actions.reveal_in_folder(path)
        except OSError as exc:
            InfoBar.error(tr("treemap.reveal_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)

    def _migrate_selected(self) -> None:
        picked = self._pick_records(tr("treemap.pick.migrate_title"),
                                    tr("treemap.pick.migrate_intro"))
        if not picked or self._profile is None:
            if not picked:
                self.status.setText(tr("treemap.pick.none"))
            return
        dest = QFileDialog.getExistingDirectory(
            self, tr("treemap.migrate_dest"), str(self._profile.root.parent)
        )
        if not dest:
            return
        dest_path = Path(dest)
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        conflicts = [p for p in paths if (dest_path / p.name).exists()]
        if conflicts:
            InfoBar.warning(
                tr("treemap.migrate_conflict"),
                tr("treemap.migrate_conflict_msg", n=len(conflicts)),
                parent=self, position=InfoBarPosition.TOP,
            )
        ok, failed = file_actions.migrate_files(paths, dest_path)
        if failed:
            InfoBar.warning(tr("treemap.migrate_part"),
                            tr("dialog.ok_count", ok=ok, failed=len(failed)),
                            parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.success(tr("treemap.migrate_done"),
                            tr("treemap.migrate_done_msg", n=ok, dest=dest_path),
                            parent=self, position=InfoBarPosition.TOP)
        self._refresh_after_action()

    def _refresh_after_action(self) -> None:
        """文件系统已变：清选择并重扫拿新状态。"""
        self._selected = None
        self.map.clear()
        self._update_action_buttons()
        if self._profile is not None:
            self._last_scan_key = None  # 绕过节流，立即重扫
            self._start_scan(auto=True)


class _FilePickDialog(MessageBox):
    """文件复选弹窗：列出当前画像的全部文件，勾选后确认。

    点选中的文件预选；提供全选/清空。
    """

    def __init__(self, title: str, intro: str, records: list[FileRecord],
                 prechecked: set[str], parent=None):
        super().__init__(title, intro, parent)
        self.yesButton.setText(tr("common.confirm"))
        self.cancelButton.setText(tr("common.cancel"))

        self._list = ListWidget()
        self._list.setMinimumHeight(260)
        self._list.setMinimumWidth(460)
        for r in records:
            item = QListWidgetItem(f"{r.path_rel}　（{human_size(r.size)}）")
            item.setData(Qt.ItemDataRole.UserRole, r)
            item.setCheckState(
                Qt.CheckState.Checked if r.path_rel in prechecked else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)
        self.textLayout.addWidget(self._list)

        # 全选 / 清空（叠在列表上方，借用 textLayout 纵向流）
        btns = QHBoxLayout()
        btns.setSpacing(8)
        select_all = PushButton(tr("common.select_all"))
        select_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_all = PushButton(tr("common.clear_all"))
        clear_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        btns.addWidget(select_all)
        btns.addWidget(clear_all)
        btns.addStretch(1)
        # 插到列表之前（textLayout 此时只有列表一个控件）
        self.textLayout.insertLayout(0, btns)

    def _set_all(self, state: Qt.CheckState) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(state)

    def chosen(self) -> list[FileRecord]:
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result
