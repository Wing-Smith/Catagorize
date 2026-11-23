# -*- coding: utf-8 -*-
"""treemap_page.py 字符串外置补丁：全部用户可见中文走 tr。"""

p = 'app/ui/pages/treemap_page.py'
s = open(p, encoding='utf-8').read()

def rep(old, new):
    global s
    assert old in s, f"NOT FOUND: {old[:60]!r}"
    s = s.replace(old, new)

rep(
    "from app.core.errors import CatagorizeError",
    "from app.core.errors import CatagorizeError\nfrom app.core.i18n import tr",
)
rep('''    def title(self) -> str:
        return "空间拼图"

    def subtitle(self) -> str:
        return "整目录一块矩形：越大块的文件越大，颜色越深；点击选中，删除/迁移弹列表复选。"''',
'''    def title(self) -> str:
        return tr("nav.treemap")

    def subtitle(self) -> str:
        return tr("treemap.subtitle")''')

rep('''        row.addWidget(StrongBodyLabel("受管文件夹"))
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(280)
        row.addWidget(self.profile_combo)
        self.scan_btn = PrimaryPushButton("扫描并拼图")''',
'''        self.profile_label = StrongBodyLabel("")
        row.addWidget(self.profile_label)
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(280)
        row.addWidget(self.profile_combo)
        self.scan_btn = PrimaryPushButton("")''')

rep('''        self.trash_btn = PushButton("删除")
        self.trash_btn.setToolTip("弹出列表复选，移入回收站（可还原）")''',
'''        self.trash_btn = PushButton("")
        self.trash_btn.setToolTip("")''')
rep('''        self.wipe_btn = PushButton("彻底删除")
        self.wipe_btn.setToolTip("弹出列表复选，直接删除，不可恢复")''',
'''        self.wipe_btn = PushButton("")
        self.wipe_btn.setToolTip("")''')
rep('''        self.open_btn = PushButton("使用默认应用打开")
        self.open_btn.clicked.connect(self._open_selected)
        self.reveal_btn = PushButton("打开所在文件夹")
        self.reveal_btn.clicked.connect(self._reveal_selected)
        self.migrate_btn = PushButton("迁移…")''',
'''        self.open_btn = PushButton("")
        self.open_btn.clicked.connect(self._open_selected)
        self.reveal_btn = PushButton("")
        self.reveal_btn.clicked.connect(self._reveal_selected)
        self.migrate_btn = PushButton("")''')
rep('''        self.profile_combo.currentIndexChanged.connect(self._auto_scan)
        self.scan_btn.setText("重新扫描")
        self.scan_btn.setToolTip("切换画像或页面时会自动拼图，这里用于强制刷新")
        self.scan_btn.clicked.connect(lambda: self._start_scan(auto=False))''',
'''        self.profile_combo.currentIndexChanged.connect(self._auto_scan)
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
        self.migrate_btn.setText(tr("treemap.migrate"))''')

rep('''        if profile is None:
            if not auto:  # 自动扫描时静默，避免每次切页都弹窗
                InfoBar.warning("没有可用画像", "请先在「文件夹」页添加受管文件夹。", parent=self,
                                position=InfoBarPosition.TOP)
            self.status.setText("没有可用画像，请先在「文件夹」页添加。")
            return
        if not profile.root.is_dir():
            msg = f"{profile.root} 已被移动或删除，请回到「文件夹」页重新指定。"
            self.status.setText(msg)
            if not auto:
                InfoBar.error("目录不可达", msg, parent=self, position=InfoBarPosition.TOP)
            return''',
'''        if profile is None:
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
            return''')

rep('''        self.status.setText(
            f"{profile.name}：{len(records)} 个文件拼完了，共 {human_size(total_size)}。"
        )''',
'''        self.status.setText(
            tr("treemap.done_status", name=profile.name, n=len(records),
               size=human_size(total_size))
        )''')
rep('InfoBar.error("扫描失败", message, parent=self, position=InfoBarPosition.TOP)',
    'InfoBar.error(tr("treemap.scan_failed"), message, parent=self, position=InfoBarPosition.TOP)')

rep('''    def _on_pick(self, record: FileRecord) -> None:
        self._selected = record
        self.status.setText(f"选中：{record.path_rel}（{human_size(record.size)}）")''',
'''    def _on_pick(self, record: FileRecord) -> None:
        self._selected = record
        self.status.setText(
            tr("treemap.picked", path=record.path_rel, size=human_size(record.size))
        )''')

rep('''        picked = self._pick_records("删除", "勾选要移入回收站的文件（可还原）：")
        if not picked:
            self.status.setText("未选择文件。")
            return
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        gone = file_actions.trash_files(paths)
        InfoBar.success("已移入回收站", f"{gone} 个文件。", parent=self, position=InfoBarPosition.TOP)''',
'''        picked = self._pick_records(tr("treemap.pick.trash_title"), tr("treemap.pick.trash_intro"))
        if not picked:
            self.status.setText(tr("treemap.pick.none"))
            return
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        gone = file_actions.trash_files(paths)
        InfoBar.success(tr("treemap.trash_done"), tr("treemap.trash_count", n=gone),
                        parent=self, position=InfoBarPosition.TOP)''')

rep('''        picked = self._pick_records("彻底删除", "勾选的文件将被直接删除，不可恢复：")
        if not picked:
            self.status.setText("未选择文件。")
            return
        paths = [p for p in (self._abs(r) for r in picked) if p is not None]
        ok, failed = file_actions.delete_files(paths)
        if failed:
            InfoBar.warning("部分删除失败", f"成功 {ok}，失败 {len(failed)}。", parent=self,
                            position=InfoBarPosition.TOP)
        else:
            InfoBar.success("已彻底删除", f"{ok} 个文件。", parent=self, position=InfoBarPosition.TOP)''',
'''        picked = self._pick_records(tr("treemap.pick.wipe_title"), tr("treemap.pick.wipe_intro"))
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
                            parent=self, position=InfoBarPosition.TOP)''')

rep('InfoBar.error("打开失败", str(exc), parent=self, position=InfoBarPosition.TOP)',
    'InfoBar.error(tr("treemap.open_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)')
rep('InfoBar.error("打开文件夹失败", str(exc), parent=self, position=InfoBarPosition.TOP)',
    'InfoBar.error(tr("treemap.reveal_failed"), str(exc), parent=self, position=InfoBarPosition.TOP)')

rep('''        picked = self._pick_records("迁移", "勾选要迁移的文件：")
        if not picked or self._profile is None:
            self.status.setText("未选择文件。" if not picked else "")
            return
        dest = QFileDialog.getExistingDirectory(
            self, "选择迁移目标文件夹", str(self._profile.root.parent)
        )''',
'''        picked = self._pick_records(tr("treemap.pick.migrate_title"),
                                    tr("treemap.pick.migrate_intro"))
        if not picked or self._profile is None:
            if not picked:
                self.status.setText(tr("treemap.pick.none"))
            return
        dest = QFileDialog.getExistingDirectory(
            self, tr("treemap.migrate_dest"), str(self._profile.root.parent)
        )''')

rep('''        if conflicts:
            InfoBar.warning(
                "重名自动避让",
                f"{len(conflicts)} 个文件在目标处重名，将自动加 \\" (n)\\" 后缀。",
                parent=self, position=InfoBarPosition.TOP,
            )
        ok, failed = file_actions.migrate_files(paths, dest_path)
        if failed:
            InfoBar.warning("部分迁移失败", f"成功 {ok}，失败 {len(failed)}。", parent=self,
                            position=InfoBarPosition.TOP)
        else:
            InfoBar.success("迁移完成", f"{ok} 个文件已移到 {dest_path}。", parent=self,
                            position=InfoBarPosition.TOP)''',
'''        if conflicts:
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
                            parent=self, position=InfoBarPosition.TOP)''')

rep('''        super().__init__(title, intro, parent)
        self.yesButton.setText("确认")
        self.cancelButton.setText("取消")''',
'''        super().__init__(title, intro, parent)
        self.yesButton.setText(tr("common.confirm"))
        self.cancelButton.setText(tr("common.cancel"))''')

rep('''        select_all = PushButton("全选")
        select_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_all = PushButton("清空")''',
'''        select_all = PushButton(tr("common.select_all"))
        select_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_all = PushButton(tr("common.clear_all"))''')

open(p, 'w', encoding='utf-8').write(s)
print('treemap_page patched')
