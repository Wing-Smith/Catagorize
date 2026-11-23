"""体检页：扫描报告（类型分布 / 体积 Top / 重复组 / 垃圾文件）→ dry-run 计划 → 执行。

第一个完整闭环页。扫描与整理都在后台线程跑，进度显示在状态区；
整理永远先弹预览清单，确认才动手；完成后可一键撤销。
"""

from __future__ import annotations

import time
from collections import defaultdict

from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TableWidget,
    ProgressBar,
)

from app.core.errors import CatagorizeError
from app.core.i18n import tr
from app.core.executor import execute_plan, undo_last
from app.core.models import FileRecord, FolderProfile, Plan, human_size
from app.core.planner import build_plan, records_to_rows
from app.core.scanner import scan_with_digests, type_of
from app.core.store import Database, ProfileStore
from app.services.job_manager import JobWorker
from app.ui.pages.base_page import BasePage, ElidedLabel


def _duplicate_groups(records: list[FileRecord]) -> list[tuple[FileRecord, list[FileRecord]]]:
    """同指纹分组，返回 (保留者, [重复们])。保留策略与 planner 一致：最新 mtime，平手路径短者。"""
    groups: dict[str, list[FileRecord]] = defaultdict(list)
    for r in records:
        if r.digest and r.size > 0:
            groups[r.digest].append(r)
    result = []
    for members in groups.values():
        if len(members) < 2:
            continue
        keeper = min(members, key=lambda r: (-r.mtime, len(r.path_rel)))
        result.append((keeper, [m for m in members if m is not keeper]))
    return result


class InspectPage(BasePage):
    def title(self) -> str:
        return tr("nav.inspect")

    def subtitle(self) -> str:
        return tr("inspect.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProfileStore()
        self._db = Database().open()
        self._records: list[FileRecord] = []
        self._plan: Plan | None = None
        self._worker: JobWorker | None = None
        self._last_scan_key: str | None = None
        self._last_scan_at = 0.0

        # ---- 工具行 ----
        row = QHBoxLayout()
        row.setSpacing(8)
        self.profile_label = StrongBodyLabel("")
        row.addWidget(self.profile_label)
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(280)
        self.profile_combo.currentIndexChanged.connect(self._auto_scan)
        row.addWidget(self.profile_combo)
        self.scan_btn = PrimaryPushButton("")
        self.scan_btn.clicked.connect(lambda: self._start_scan(auto=False))
        self.plan_btn = PushButton("")
        self.plan_btn.setEnabled(False)
        self.plan_btn.clicked.connect(self._make_plan)
        self.undo_btn = PushButton("")
        self.undo_btn.clicked.connect(self._undo_last)
        row.addWidget(self.scan_btn)
        row.addWidget(self.plan_btn)
        row.addWidget(self.undo_btn)
        row.addStretch(1)
        self.body().addLayout(row)

        self.progress = ProgressBar()
        self.progress.setVisible(False)
        self.body().addWidget(self.progress)
        self.status = ElidedLabel("")
        self.body().addWidget(self.status)

        # ---- 报告区 ----
        self.summary = StrongBodyLabel("")
        self.body().addWidget(self.summary)

        report_row = QHBoxLayout()
        report_row.setSpacing(16)

        left = QVBoxLayout()
        self.type_label = BodyLabel("")
        left.addWidget(self.type_label)
        self.type_table = self._make_table([tr("inspect.table.type"), tr("inspect.table.count"), tr("inspect.table.size")])
        left.addWidget(self.type_table)
        self.junk_title = BodyLabel("")
        left.addWidget(self.junk_title)
        self.junk_label = ElidedLabel("—")
        left.addWidget(self.junk_label)

        right = QVBoxLayout()
        self.top_label = BodyLabel("")
        right.addWidget(self.top_label)
        self.top_table = self._make_table([tr("inspect.table.path"), tr("inspect.table.size")])
        right.addWidget(self.top_table, 1)
        self.dup_label = BodyLabel("")
        right.addWidget(self.dup_label)
        self.dup_table = self._make_table([tr("inspect.table.keeper"), tr("inspect.table.dups")])
        right.addWidget(self.dup_table, 1)

        report_row.addLayout(left, 1)
        report_row.addLayout(right, 1)
        self.body().addLayout(report_row, 1)
        self.retranslate()

    # ---------- 工具 ----------

    def _make_table(self, headers: list[str]) -> TableWidget:
        table = TableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().hide()
        table.setBorderVisible(True)
        table.setBorderRadius(8)
        return table

    def retranslate(self) -> None:
        super().retranslate()
        self.profile_label.setText(tr("inspect.profile"))
        self.scan_btn.setText(tr("inspect.rescan"))
        self.scan_btn.setToolTip(tr("inspect.rescan.tip"))
        self.plan_btn.setText(tr("inspect.plan"))
        self.undo_btn.setText(tr("inspect.undo"))
        self.summary.setText(tr("inspect.not_scanned"))
        self.type_label.setText(tr("inspect.type_dist"))
        self.junk_title.setText(tr("inspect.junk"))
        self.top_label.setText(tr("inspect.top10"))
        self.dup_label.setText(tr("inspect.dup_groups"))
        self.type_table.setHorizontalHeaderLabels(
            [tr("inspect.table.type"), tr("inspect.table.count"), tr("inspect.table.size")]
        )
        self.top_table.setHorizontalHeaderLabels([tr("inspect.table.path"), tr("inspect.table.size")])
        self.dup_table.setHorizontalHeaderLabels([tr("inspect.table.keeper"), tr("inspect.table.dups")])
        # 报告数据全部用 tr，语言切换后重扫当前画像（无画像则清空）
        if self._records and self._last_scan_key:
            profile = self._current_profile(silent=True)
            if profile is not None:
                self._render_report(profile, self._records)

    def on_show(self) -> None:
        current = self.profile_combo.currentData()
        # 重建期间屏蔽信号，避免逐条触发自动扫描（可能扫到错误的画像）
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self._store.list_all():
            self.profile_combo.addItem(p.name, userData=p.profile_id)
        # 尽量保持之前选中的画像
        if current:
            index = self.profile_combo.findData(current)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._auto_scan()

    def _current_profile(self, silent: bool = False) -> FolderProfile | None:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return None
        try:
            return self._store.load(profile_id)
        except CatagorizeError as exc:
            if not silent:
                InfoBar.error(tr("inspect.profile_load_failed"), str(exc), parent=self,
                              position=InfoBarPosition.TOP)
            return None

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.scan_btn.setEnabled(not busy)
        self.plan_btn.setEnabled(not busy and bool(self._records))
        self.progress.setVisible(busy)
        self.status.setText(text)

    # ---------- 扫描 ----------

    _AUTO_SCAN_THROTTLE = 30.0  # 同一画像 30 秒内不重复自动扫描

    def _auto_scan(self, *_args) -> None:
        """切页 / 换画像时按当前值自动扫描。30 秒节流；扫描器忙时直接让路。"""
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
            # DropDesk 教训：目录丢失绝不假装没事
            msg = tr("inspect.root_missing", root=profile.root)
            self.status.setText(msg)
            if not auto:
                InfoBar.error(tr("inspect.root_missing.title"), msg, parent=self,
                              position=InfoBarPosition.TOP)
            return

        self._set_busy(True, tr("inspect.scanning"))

        def job(progress, token):
            records = scan_with_digests(profile.root, progress, token)
            return profile, records

        self._worker = JobWorker(job, parent=self)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished_ok.connect(self._on_scan_done)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_scan_progress(self, done: int, total: int, msg: str) -> None:
        if total:
            self.progress.setValue(int(done / total * 100))
        self.status.setText(msg)

    def _on_scan_done(self, result) -> None:
        profile, records = result
        self._last_scan_key = profile.profile_id
        self._last_scan_at = time.monotonic()
        self._records = records
        from app.core import logbus

        logbus.info(f"inspect scan done: {profile.name} -> {len(records)} files")
        # 同步进索引库，检索页立刻可用
        self._db.upsert_files(profile.profile_id, records_to_rows(profile.profile_id, records))
        self._render_report(profile, records)
        self._set_busy(False, tr("inspect.scan_done"))
        self.plan_btn.setEnabled(bool(records))

    def _on_scan_failed(self, message: str) -> None:
        from app.core import logbus

        logbus.warn(f"inspect scan failed: {message}")
        self._set_busy(False)
        InfoBar.error(tr("inspect.scan_failed"), message, parent=self, position=InfoBarPosition.TOP)

    def _render_report(self, profile: FolderProfile, records: list[FileRecord]) -> None:
        total_size = sum(r.size for r in records)
        self.summary.setText(
            tr("inspect.summary", name=profile.name, n=len(records),
               size=human_size(total_size), digested=sum(1 for r in records if r.digest))
        )

        # 类型分布
        by_type: dict[str, list[FileRecord]] = defaultdict(list)
        for r in records:
            by_type[type_of(r.ext)].append(r)
        self.type_table.setRowCount(len(by_type))
        for row, (kind, members) in enumerate(
            sorted(by_type.items(), key=lambda kv: -sum(r.size for r in kv[1]))
        ):
            self.type_table.setItem(row, 0, QTableWidgetItem(kind))
            self.type_table.setItem(row, 1, QTableWidgetItem(str(len(members))))
            self.type_table.setItem(row, 2, QTableWidgetItem(human_size(sum(r.size for r in members))))

        # 体积 Top 10
        top = sorted(records, key=lambda r: -r.size)[:10]
        self.top_table.setRowCount(len(top))
        for row, r in enumerate(top):
            self.top_table.setItem(row, 0, QTableWidgetItem(r.path_rel))
            self.top_table.setItem(row, 1, QTableWidgetItem(human_size(r.size)))

        # 重复组
        groups = _duplicate_groups(records)
        self.dup_table.setRowCount(len(groups))
        for row, (keeper, dups) in enumerate(groups):
            self.dup_table.setItem(row, 0, QTableWidgetItem(keeper.path_rel))
            self.dup_table.setItem(row, 1, QTableWidgetItem(str(len(dups))))

        # 垃圾文件
        junk = [r.path_rel for r in records if r.is_junk]
        self.junk_label.setText("\n".join(junk) if junk else "无")

    # ---------- 计划 / 执行 / 撤销 ----------

    def _make_plan(self) -> None:
        profile = self._current_profile()
        if profile is None or not self._records:
            return
        try:
            plan = build_plan(profile, self._records)
        except CatagorizeError as exc:
            InfoBar.error(tr("inspect.plan_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return

        if not plan.items:
            InfoBar.info(tr("inspect.plan_empty.title"), tr("inspect.plan_empty"), parent=self,
                         position=InfoBarPosition.TOP)
            return

        self._plan = plan
        dialog = _PlanDialog(plan, self.window())
        if dialog.exec():  # 用户确认 → 后台执行
            self.run_plan()

    def run_plan(self) -> None:
        """由 _PlanDialog 确认后调用。执行在后台线程。"""
        if self._plan is None:
            return
        plan = self._plan
        self._set_busy(True, tr("inspect.planning"))

        def job(progress, token):
            return execute_plan(plan, self._db, lambda d, t, cur: progress(d, t, cur))

        self._worker = JobWorker(job, parent=self)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished_ok.connect(self._on_execute_done)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_execute_done(self, stats: dict) -> None:
        self._set_busy(False)
        failed = stats["failed"]
        text = tr("inspect.execute_done", moved=stats["moved"], quarantined=stats["quarantined"])
        if failed:
            text += tr("inspect.execute_failed_count", n=len(failed))
            InfoBar.warning(tr("inspect.execute_failed_part"), text, parent=self,
                            position=InfoBarPosition.TOP)
        else:
            InfoBar.success(tr("inspect.execute_ok"), text + tr("inspect.execute_ok_suffix"),
                            parent=self, position=InfoBarPosition.TOP)
        self._records = []  # 目录已变，旧记录作废，重新扫描拿新状态
        self.plan_btn.setEnabled(False)

    def _undo_last(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        try:
            result = undo_last(profile.profile_id, profile.root, self._db)
        except CatagorizeError as exc:
            InfoBar.error(tr("inspect.undo_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)
            return
        if result is None:
            InfoBar.info(tr("inspect.undo_none"), parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.success(tr("inspect.undo_done"),
                            tr("inspect.undo_result", restored=result["restored"],
                               skipped=result["skipped"]),
                            parent=self, position=InfoBarPosition.TOP)


class _PlanDialog(MessageBox):
    """dry-run 预览确认框：清单 + 汇总，确认才真正动手。"""

    def __init__(self, plan: Plan, parent=None):
        summary = plan.summary()
        content = (
            f"将执行 {summary['total']} 个动作："
            f"移动 {summary['move']}，隔离 {summary['quarantine']}。\n"
            "全部为移动操作，可随时一键撤销。"
        )
        super().__init__("确认执行整理计划？", content, parent)
        self.plan = plan
        self.yesButton.setText("执行")
        self.cancelButton.setText("取消")

        # MessageBox 之上再补一个明细表太重，骨架阶段先给前 20 条明细文本
        lines = []
        for item in plan.items[:20]:
            target = item.target_rel or "_quarantine/"
            verb = "移动" if item.action == "move" else "隔离"
            lines.append(f"[{verb}] {item.source_rel}  →  {target}　（{item.reason}）")
        if len(plan.items) > 20:
            lines.append(f"… 其余 {len(plan.items) - 20} 条")
        from qfluentwidgets import TextEdit

        detail = TextEdit()
        detail.setReadOnly(True)
        detail.setPlainText("\n".join(lines))
        detail.setMinimumHeight(220)
        # MessageBox.textLayout 是私有布局，直接叠到按钮前
        self.textLayout.addWidget(detail)
