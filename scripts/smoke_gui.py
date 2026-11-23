"""离屏冒烟：不起真窗口，验证 GUI 能构建、导航能切换、画像流程能走通。

用法（项目根目录）:
    .venv\\Scripts\\python.exe scripts\\smoke_gui.py

产物：out\\smoke_main.png（主窗口截图，人工目检用）。
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 保证能 import app

_TMP = Path(tempfile.mkdtemp(prefix="catagorize_smoke_"))

# 配置目录重定向到临时目录，冒烟绝不碰真实用户数据
from app.core import config  # noqa: E402

(_TMP / "cfg" / "profiles").mkdir(parents=True)
(_TMP / "root").mkdir()
config.config_dir = lambda: _TMP / "cfg"
config.profiles_dir = lambda: _TMP / "cfg" / "profiles"
config.index_path = lambda: _TMP / "cfg" / "catagorize.db"

# 固定冒烟语言为中文，避免系统语言影响断言
from app.core import i18n  # noqa: E402

i18n.set_language("zh", persist=False, notify=False)

failures: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        print(f"[PASS] {label}")
    except Exception:
        failures.append(label)
        print(f"[FAIL] {label}")
        traceback.print_exc()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    from app.ui.theme import apply_fluent_theme

    apply_fluent_theme("light")

    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    check("MainWindow 构建（7 个页面实例化）", lambda: None)

    def _walk_pages() -> None:
        for i in range(window.stackedWidget.count()):
            window.stackedWidget.setCurrentIndex(i)
            app.processEvents()

    check("导航逐页切换 + on_show 钩子", _walk_pages)

    def _profile_flow() -> None:
        from app.core.models import FolderProfile
        from app.core.store import ProfileStore

        profile = FolderProfile(name="冒烟测试", root=_TMP / "root", mode="archive")
        ProfileStore().save(profile)
        window.profiles_page.refresh()
        app.processEvents()
        from PySide6.QtWidgets import QLabel

        assert "冒烟测试" in " ".join(
            w.text() for w in window.profiles_page.findChildren(QLabel)
        )

    check("画像保存 → 文件夹页刷新显示", _profile_flow)

    def _search_flow() -> None:
        from app.core.store import Database

        db = Database().open()
        db.upsert_files(
            "p1",
            [
                {
                    "profile_id": "p1",
                    "path_rel": "docs/测试文件.txt",
                    "name": "测试文件.txt",
                    "ext": "txt",
                    "size": 1,
                    "mtime": 0.0,
                    "digest": "",
                    "type": "文档",
                }
            ],
        )
        db.close()
        window.search_page.search_box.setText("测试文件")
        window.search_page._run_search()
        app.processEvents()
        assert "docs/测试文件.txt" in window.search_page.results.text()

    check("索引写入 → 检索页命中", _search_flow)

    def _inspect_flow() -> None:
        from PySide6.QtCore import QEventLoop, QTimer

        root = _TMP / "root"
        (root / "a.txt").write_bytes(b"same-payload")
        (root / "b.txt").write_bytes(b"same-payload")
        (root / "Thumbs.db").write_bytes(b"junk")
        (root / "big.bin").write_bytes(b"x" * 9999)

        page = window.inspect_page
        page.on_show()  # 刷新画像下拉框
        assert page.profile_combo.count() >= 1
        page._start_scan()
        loop = QEventLoop()
        watchdog = QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(loop.quit)
        watchdog.start(15000)
        poller = QTimer()
        poller.timeout.connect(lambda: loop.quit() if "扫描完成" in page.status.text() else None)
        poller.start(200)
        loop.exec()
        poller.stop()

        assert "4 个文件" in page.summary.text(), page.summary.text()
        assert page.dup_table.rowCount() == 1  # 一组重复
        assert "Thumbs.db" in page.junk_label.text()

        # dry-run 计划：重复文件应进隔离区
        profile = page._current_profile()
        from app.core.planner import build_plan

        plan = build_plan(profile, page._records)
        quarantine = [i for i in plan.items if i.action == "quarantine"]
        assert len(quarantine) == 1

        # 执行 + 撤销闭环（不经对话框，直接调引擎）
        from app.core.executor import execute_plan, undo_last

        stats = execute_plan(plan, page._db)
        assert stats["quarantined"] == 1 and (root / "_quarantine").is_dir()
        undo = undo_last(profile.profile_id, profile.root, page._db)
        assert undo["restored"] == 1
        assert (root / "a.txt").is_file() and (root / "b.txt").is_file()

    check("体检页扫描/报告/计划/执行/撤销闭环", _inspect_flow)

    def _overview_flow() -> None:
        from PySide6.QtWidgets import QLabel

        page = window.overview_page
        page.on_show()
        app.processEvents()
        # 已有一个画像（冒烟测试）+ 体检页写入的索引：4 文件、1 重复组、执行过整理
        all_text = " ".join(w.text() for w in page.findChildren(QLabel))
        assert "冒烟测试" in all_text
        assert "文件　4" in all_text, all_text
        assert "重复组　1" in all_text
        # 体检闭环最后是撤销，操作日志全部 undone → 回到“从未整理”
        assert "最近整理　从未整理" in all_text
        # 时钟：时间精确到秒、日期带星期、节气有值
        import re

        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", page._clock.time_label.text())
        assert "星期" in page._clock.date_label.text()
        assert page._clock.term_label.text().startswith("节气 · ")
        # 底部信息卡：数据与缓存 / 关于 / 更新
        assert "数据与缓存" in all_text
        assert "关于" in all_text
        assert "更新" in all_text
        assert "Catagorize v" in all_text
        assert "GitHub" in all_text
        # 更新卡片状态渲染（未检查 → 检查中，不触发真实网络）
        from app.core.updater import UpdateStatus

        page.show_update_status(UpdateStatus(connected=False, checking=True))
        assert "检查中" in page.update_conn_value.text()
        page.show_update_status(UpdateStatus(connected=True, latest="9.9.9"))
        assert "GitHub 可达" in page.update_conn_value.text()
        assert "v9.9.9" in page.update_latest_value.text()
        page.show_update_status(None)
        assert "未检查" in page.update_conn_value.text()

    check("总览页统计卡片 + 时钟", _overview_flow)

    def _treemap_flow() -> None:
        from PySide6.QtCore import Qt
        from app.core.models import FileRecord
        from app.core.store import ProfileStore
        from app.ui.pages.treemap_page import _FilePickDialog

        page = window.treemap_page
        page._profile = ProfileStore().list_all()[0]  # 按钮启用判定需要画像 root
        records = [
            FileRecord(path_rel=f"block_{i}.bin", size=(i + 1) * 3000, mtime=0.0)
            for i in range(15)
        ]
        page._records = records
        page.map.set_records(records)
        app.processEvents()
        assert len(page.map._rects) == 15
        grabbed = page.map.grab()
        assert not grabbed.isNull()
        out = Path("out")
        grabbed.save(str(out / "smoke_treemap.png"))

        # 初始无点选：批量操作可弹列表，单文件打开/定位不可用
        page._update_action_buttons()
        assert page.trash_btn.isEnabled() and page.wipe_btn.isEnabled() and page.migrate_btn.isEnabled()
        assert not page.open_btn.isEnabled() and not page.reveal_btn.isEnabled()

        # 点选 → 打开/定位可用
        page._on_pick(records[0])
        app.processEvents()
        assert page.open_btn.isEnabled() and page.reveal_btn.isEnabled()

        # 复选弹窗：点选项预选，可全选/清空/读取勾选
        dlg = _FilePickDialog("删除", "test", records, {"block_0.bin"}, window)
        assert [r.path_rel for r in dlg.chosen()] == ["block_0.bin"]
        dlg._set_all(Qt.CheckState.Checked)
        assert len(dlg.chosen()) == 15
        dlg._set_all(Qt.CheckState.Unchecked)
        assert dlg.chosen() == []
        dlg.deleteLater()

    check("空间拼图画布渲染 + 复选弹窗", _treemap_flow)

    def _export_flow() -> None:
        page = window.export_page
        page.on_show()
        app.processEvents()
        assert page.profile_combo.count() >= 1
        page.format_combo.setCurrentIndex(1)  # 先切纯文本
        page.size_check.setChecked(True)
        page._generate()
        text = page.preview.toPlainText()
        assert ("├──" in text or "└──" in text), text
        assert page.copy_btn.isEnabled() and page.save_btn.isEnabled()
        # txt 形态不带围栏；切 Markdown 后带 ```text 围栏
        assert not text.startswith("```")
        page.format_combo.setCurrentIndex(0)  # Markdown
        app.processEvents()
        assert page.preview.toPlainText().startswith("```text")

    check("导出页 tree 文本生成（txt / Markdown）", _export_flow)

    def _screenshot() -> None:
        out = Path("out")
        out.mkdir(exist_ok=True)
        window.stackedWidget.setCurrentIndex(0)
        app.processEvents()
        window.grab().save(str(out / "smoke_main.png"))

    check("主窗口截图", _screenshot)

    def _language_flow() -> None:
        from PySide6.QtWidgets import QLabel

        i18n.set_language("en", persist=False)
        app.processEvents()
        item = window.navigationInterface.widget(window.overview_page.objectName())
        assert item is not None and item.text() == "Overview", item.text() if item else "no item"
        overview_text = " ".join(w.text() for w in window.overview_page.findChildren(QLabel))
        assert "Files" in overview_text, overview_text
        # 英文模式：节气译成英文（如 Light Snow / Minor Snow），页脚卡片同步重翻译
        term_text = window.overview_page._clock.term_label.text()
        assert term_text.startswith("Solar term · "), term_text
        assert not any("\u4e00" <= ch <= "\u9fff" for ch in term_text), term_text
        assert "Data & Cache" in overview_text
        assert "Updates" in overview_text
        assert "GitHub" in overview_text

        i18n.set_language("zh", persist=False)
        app.processEvents()
        item = window.navigationInterface.widget(window.overview_page.objectName())
        assert item.text() == "总览", item.text()
        overview_text = " ".join(w.text() for w in window.overview_page.findChildren(QLabel))
        assert "文件" in overview_text, overview_text

    check("语言切换 en↔zh（导航 + 总览重翻译）", _language_flow)

    def _delete_flow() -> None:
        from PySide6.QtWidgets import QLabel

        from app.core.models import FileRecord, FolderProfile
        from app.core.planner import records_to_rows
        from app.core.store import ProfileStore

        page = window.profiles_page
        doomed = FolderProfile(name="待删除", root=_TMP / "root", mode="archive")
        ProfileStore().save(doomed)
        page._db.upsert_files(doomed.profile_id, records_to_rows(doomed.profile_id, [
            FileRecord(path_rel="x.txt", size=1, mtime=0.0),
        ]))
        page.refresh()
        assert "待删除" in " ".join(w.text() for w in page.findChildren(QLabel))
        # 走与删除按钮相同的移除路径（跳过确认弹窗本身）
        page._store.delete(doomed.profile_id)
        page._db.purge_profile(doomed.profile_id)
        page.refresh()
        app.processEvents()
        assert "待删除" not in " ".join(w.text() for w in page.findChildren(QLabel))
        assert page._db.profile_stats(doomed.profile_id)["files"] == 0

    check("文件夹页删除画像（索引同步清除）", _delete_flow)

    def _logs_flow() -> None:
        from app.core import logbus

        page = window.logs_page
        logbus.clear_buffer()
        page._clear()
        logbus.warn("smoke-test warning line")
        app.processEvents()
        assert "smoke-test warning line" in page.view.toPlainText()
        page._clear()
        assert "（暂无日志）" in page.view.toPlainText()
        assert logbus.recent() == []

    check("日志页实时显示 + 清空", _logs_flow)

    def _settings_flow() -> None:
        page = window.settings_page
        page.on_show() if hasattr(page, "on_show") else None
        app.processEvents()
        from PySide6.QtWidgets import QLabel

        texts = " ".join(w.text() for w in page.findChildren(QLabel))
        assert "关于 Catagorize" in texts
        assert "Catopsys GUI Base" in texts  # 关于区标明 GUI 框架
        # 主题持久化
        page.theme_combo.setCurrentIndex(2)  # dark
        from app.core import config

        assert config.theme() == "dark"
        page.theme_combo.setCurrentIndex(0)  # auto

    check("设置页关于区（GUI Base 署名）+ 主题持久化", _settings_flow)

    print(f"\n冒烟目录：{_TMP}")
    if failures:
        print(f"结果：{len(failures)} 项失败：{failures}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
