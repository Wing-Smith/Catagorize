"""轻量双语 i18n：简体中文 + English。

- 启动语言：用户上次的选择（配置文件目录下 language 文件）优先，
  否则按系统 UI 语言（中文 → zh，其余 → en）。
- set_language() 立即生效并持久化，通过 add_listener() 通知各页面重刷文案。
- tr() 缺失键回退键名本身，不抛异常；带 {占位符} 的文案用 kwargs 填充。

本模块只用标准库（系统语言检测走 ctypes 的 GetUserDefaultUILanguage），
不依赖 Qt，CLI / GUI / 测试共用。
"""

from __future__ import annotations

import ctypes
import locale
from typing import Callable

_ZH = {
    # ---- 应用 ----
    "app.name": "Catagorize",
    "app.tagline": "文件夹整理工具",
    "splash.loading1": "正在加载索引…",
    "splash.loading2": "正在扫描受管文件夹…",
    "splash.loading3": "正在准备界面…",
    # ---- 导航 ----
    "nav.overview": "总览",
    "nav.profiles": "文件夹",
    "nav.inspect": "体检",
    "nav.treemap": "空间拼图",
    "nav.search": "检索",
    "nav.settings": "设置",
    # ---- 通用 ----
    "common.confirm": "确定",
    "common.ok": "好",
    "common.cancel": "取消",
    "common.select_all": "全选",
    "common.clear_all": "清空",
    "common.none": "无",
    # ---- 设置 ----
    "settings.theme": "主题",
    "settings.language": "语言",
    "settings.language.instant": "语言（立即生效）",
    "settings.theme.instant": "主题（立即生效）",
    "settings.update.check": "检查更新",
    "settings.reset": "恢复默认",
    "settings.reset_done": "已恢复默认设置",
    "settings.about.title": "关于 Catagorize",
    "settings.about.desc": "本地优先的文件夹整理工具：不删文件，先预览，全可撤销。",
    "nav.logs": "日志",
    "logs.subtitle": "记录扫描、整理、更新检查等运行事件，供排障用。",
    "logs.clear": "清空",
    "logs.empty": "（暂无日志）",
    "settings.theme.auto": "跟随系统",
    "settings.theme.light": "浅色",
    "settings.theme.dark": "深色",
    "settings.lang.zh": "简体中文",
    "settings.lang.en": "English",
    "settings.subtitle": "语言与主题跟随系统；所有数据都在本地配置目录，受管文件夹保持干净。",
    "settings.about.version": "版本",
    "settings.about.data_dir": "数据目录",
    "settings.about.portable.on": "已启用（portable.flag）",
    "settings.about.portable.off": "未启用",
    "settings.about.engine": "引擎：core 层零 GUI 依赖，UI / CLI 共用同一份管线。",
    # ---- 总览 ----
    "overview.subtitle": "本地优先的文件夹整理工具：不删文件，先预览，全可撤销。",
    "overview.greeting.night": "夜深了，别整理太晚",
    "overview.greeting.morning": "早上好，来清爽一下文件夹",
    "overview.greeting.afternoon": "下午好，杂物该归位了",
    "overview.greeting.evening": "晚上好，今天还没有整理",
    "overview.tagline": "挑一个文件夹——开始整理。",
    "overview.tagline2": "原地不动 · 先预览 · 全操作可撤销。",
    "overview.shortcut.inspect": "体检",
    "overview.shortcut.inspect.sub": "扫描拿报告：类型 / 体积 / 重复 / 垃圾",
    "overview.shortcut.treemap": "空间拼图",
    "overview.shortcut.treemap.sub": "整目录一块矩形，越大越深",
    "overview.shortcut.search": "检索",
    "overview.shortcut.search.sub": "按文件名秒级找文件",
    "overview.shortcut.profiles": "文件夹",
    "overview.shortcut.profiles.sub": "管理受管文件夹与整理规则",
    "overview.empty": "还没有受管文件夹。点上面的「文件夹」卡片，或到「文件夹」页添加第一个画像。",
    "overview.summary": "共 {n} 个受管文件夹，索引 {files} 个文件，共 {size}。",
    "overview.card.files": "文件",
    "overview.card.size": "体积",
    "overview.card.dup": "重复组",
    "overview.card.pending": "待整理",
    "overview.card.cover": "指纹覆盖",
    "overview.card.last": "最近整理",
    "overview.card.never": "从未整理",
    "overview.card.unreachable": "⚠ 目录不可达",
    "overview.clock.solar_term": "节气 · {term}",
    "overview.indexing": "正在为「{name}」建立索引…",
    "overview.card.data_cache": "数据与缓存",
    "overview.data.config_dir": "配置目录",
    "overview.data.index_size": "索引体积",
    "overview.data.open_dir": "打开配置目录",
    "overview.card.about": "关于",
    "overview.about.line": "Catagorize v{ver} · 本地优先的文件夹整理工具",
    "overview.about.env": "Python {py} · Qt {qt}",
    "overview.about.copyright": "© 2026 Wing North Studio",
    "overview.card.updates": "更新",
    "overview.update.conn": "连接",
    "overview.update.conn.ok": "GitHub 可达",
    "overview.update.conn.fail": "GitHub 不可达",
    "overview.update.conn.checking": "检查中…",
    "overview.update.conn.unknown": "未检查",
    "overview.update.current": "当前版本",
    "overview.update.latest": "GitHub 最新",
    "overview.update.none": "暂无 Release",
    "overview.update.check": "立即检查",
    "overview.update.new_title": "发现新版本",
    "overview.update.new_msg": "Catagorize v{ver} 已发布，当前运行 v{cur}。",
    "overview.update.go_releases": "前往发行版本页面下载发行版本",
    "overview.update.dev_title": "未发行版本提醒",
    "overview.update.dev_msg": "当前您使用的是还未发行的版本，可能存在问题与错误，请您谨慎使用。相关问题可以提交到 GitHub 仓库的 Issues 并标注好版本号，给您带来的不便敬请谅解。\n\n{url}",
    "update.new": "发现新版本 v{v}",
    "update.banner_content": "新版本已发布，点击下方按钮前往下载；关闭本横幅不会影响下次启动提醒。",
    "update.go": "前往下载",
    "update.toast": "新版本已发布：{url}",
    "about.gui_base": "界面框架：{name} {ver}",
    "nav.export": "导出",
    "export.subtitle": "把受管文件夹的目录结构导出成 PowerShell tree 风格文本，可粘贴可存档。",
    "export.profile": "受管文件夹",
    "export.format": "格式",
    "export.format.markdown": "Markdown",
    "export.format.txt": "纯文本",
    "export.show_size": "显示文件大小",
    "export.generate": "生成",
    "export.regenerate": "重新生成",
    "export.copy": "复制",
    "export.save": "另存为…",
    "export.copied": "已复制到剪贴板",
    "export.saved": "已保存到 {path}",
    "export.filter.md": "Markdown 文件 (*.md)",
    "export.filter.txt": "文本文件 (*.txt)",
    "export.empty_hint": "选好画像点「生成」，树形文本就出来了。",
    "export.truncated": "（已截断，仅前 {n} 项）",
    "export.failed": "导出失败",
    "export.no_profile": "还没有受管文件夹，请先到「文件夹」页添加。",
    "weekday.0": "星期日",
    "weekday.1": "星期一",
    "weekday.2": "星期二",
    "weekday.3": "星期三",
    "weekday.4": "星期四",
    "weekday.5": "星期五",
    "weekday.6": "星期六",
    # ---- 文件夹 ----
    "profiles.subtitle": "每个受管文件夹是一份「画像」：模式（流入/存量）、规则集、是否监听。",
    "profiles.delete": "删除",
    "profiles.delete.title": "移除受管文件夹",
    "profiles.delete.msg": "将把「{name}」从 Catagorize 移除管理，{n} 条索引与操作日志一并清除。磁盘上的文件不会被删除。",
    "profiles.delete.done": "已移除「{name}」",
    "profiles.add": "添加文件夹",
    "profiles.refresh": "刷新",
    "profiles.empty": "还没有受管文件夹。点「添加文件夹」把下载目录或资料库指过来。",
    "profiles.mode.flow": "流入型",
    "profiles.mode.archive": "存量型",
    "profiles.rules.count": "{n} 条规则",
    "profiles.rules.none": "无规则",
    "profiles.watching": "监听中",
    "profiles.line": "📁 {name} — {root}（{mode} · {rules}{watch}{missing}）",
    "profiles.dialog.title": "选择要整理的文件夹",
    "profiles.unnamed": "未命名",
    # ---- 检索 ----
    "search.subtitle": "跨全部受管文件夹搜文件名与路径；内容级检索（OCR/全文）在后续版本接入。",
    "search.placeholder": "输入关键词，回车搜索…",
    "search.button": "搜索",
    "search.no_match": "没有匹配「{q}」的文件。",
    "search.result_line": "{path}　（{profile} · {size} 字节）",
    "search.more": "\n… 还有 {n} 条",
    # ---- 体检 ----
    "inspect.subtitle": "只读扫描拿报告，再决定动不动手。整理永远先出预览清单，确认才执行。",
    "inspect.profile": "受管文件夹",
    "inspect.rescan": "重新扫描",
    "inspect.rescan.tip": "切换画像或页面时会自动扫描，这里用于强制刷新",
    "inspect.plan": "生成整理计划",
    "inspect.undo": "撤销上次整理",
    "inspect.no_profile": "没有可用画像，请先在「文件夹」页添加。",
    "inspect.no_profile.warn": "没有可用画像",
    "inspect.no_profile.hint": "请先在「文件夹」页添加受管文件夹。",
    "inspect.root_missing": "{root} 已被移动或删除，请回到「文件夹」页重新指定。",
    "inspect.root_missing.title": "目录不可达",
    "inspect.scanning": "扫描中…",
    "inspect.scan_done": "扫描完成。",
    "inspect.scan_failed": "扫描失败",
    "inspect.summary": "{name}：{n} 个文件，共 {size}，已计算指纹 {digested} 个。",
    "inspect.type_dist": "类型分布",
    "inspect.top10": "体积 Top 10",
    "inspect.dup_groups": "内容重复组（SHA-256 一致）",
    "inspect.junk": "垃圾文件（扫描自动跳过）",
    "inspect.junk.none": "无",
    "inspect.not_scanned": "尚未扫描。",
    "inspect.table.type": "类型",
    "inspect.table.count": "数量",
    "inspect.table.size": "体积",
    "inspect.table.path": "路径",
    "inspect.table.keeper": "保留",
    "inspect.table.dups": "重复份数",
    "inspect.plan.title": "确认执行整理计划？",
    "inspect.plan.intro": "将执行 {total} 个动作：移动 {move}，隔离 {quarantine}。\n全部为移动操作，可随时一键撤销。",
    "inspect.plan.execute": "执行",
    "inspect.plan.item.move": "[移动] {src}  →  {dst}　（{reason}）",
    "inspect.plan.item.quarantine": "[隔离] {src}  →  {dst}　（{reason}）",
    "inspect.plan.more": "… 其余 {n} 条",
    "inspect.plan.quarantine_dir": "_quarantine/",
    "inspect.planning": "整理中…",
    "inspect.plan_failed": "计划生成失败",
    "inspect.plan_empty": "没有规则命中的文件，也没有发现重复内容。",
    "inspect.plan_empty.title": "无需整理",
    "inspect.execute_done": "移动 {moved}，隔离 {quarantined}",
    "inspect.execute_failed_count": "，失败 {n}",
    "inspect.execute_failed_part": "整理完成（部分失败）",
    "inspect.execute_ok": "整理完成",
    "inspect.execute_ok_suffix": "。可随时撤销。",
    "inspect.undo_failed": "撤销失败",
    "inspect.undo_none": "没有可撤销的整理",
    "inspect.undo_done": "已撤销",
    "inspect.undo_result": "回滚 {restored} 个动作，跳过 {skipped} 个。",
    "inspect.profile_load_failed": "画像读取失败",
    "inspect.reason.dup": "重复文件",
    # ---- 空间拼图 ----
    "treemap.subtitle": "整目录一块矩形：越大块的文件越大，颜色越深；点击选中，删除/迁移弹列表复选。",
    "treemap.rescan": "重新扫描",
    "treemap.rescan.tip": "切换画像或页面时会自动拼图，这里用于强制刷新",
    "treemap.profile": "受管文件夹",
    "treemap.empty_hint": "扫描后这里会拼出文件占用图",
    "treemap.trash": "删除",
    "treemap.trash.tip": "弹出列表复选，移入回收站（可还原）",
    "treemap.wipe": "彻底删除",
    "treemap.wipe.tip": "弹出列表复选，直接删除，不可恢复",
    "treemap.open": "使用默认应用打开",
    "treemap.reveal": "打开所在文件夹",
    "treemap.migrate": "迁移…",
    "treemap.pick.none": "未选择文件。",
    "treemap.pick.trash_title": "删除",
    "treemap.pick.trash_intro": "勾选要移入回收站的文件（可还原）：",
    "treemap.pick.wipe_title": "彻底删除",
    "treemap.pick.wipe_intro": "勾选的文件将被直接删除，不可恢复：",
    "treemap.pick.migrate_title": "迁移",
    "treemap.pick.migrate_intro": "勾选要迁移的文件：",
    "treemap.trash_done": "已移入回收站",
    "treemap.trash_count": "{n} 个文件。",
    "treemap.wipe_done": "已彻底删除",
    "treemap.wipe_part": "部分删除失败",
    "treemap.migrate_dest": "选择迁移目标文件夹",
    "treemap.migrate_conflict": "重名自动避让",
    "treemap.migrate_conflict_msg": "{n} 个文件在目标处重名，将自动加 \" (n)\" 后缀。",
    "treemap.migrate_part": "部分迁移失败",
    "treemap.migrate_done": "迁移完成",
    "treemap.migrate_done_msg": "{n} 个文件已移到 {dest}。",
    "treemap.open_failed": "打开失败",
    "treemap.reveal_failed": "打开文件夹失败",
    "treemap.picked": "选中：{path}（{size}）",
    "treemap.done_status": "{name}：{n} 个文件拼完了，共 {size}。",
    "treemap.scan_failed": "扫描失败",
    "treemap.load_failed": "画像读取失败",
    # ---- 弹窗通用 ----
    "dialog.ok_count": "成功 {ok}，失败 {failed}。",
}

_EN = {
    "app.name": "Catagorize",
    "app.tagline": "Your folder, tidy and calm",
    "splash.loading1": "Loading index…",
    "splash.loading2": "Scanning managed folders…",
    "splash.loading3": "Preparing interface…",
    "nav.overview": "Overview",
    "nav.profiles": "Folders",
    "nav.inspect": "Inspect",
    "nav.treemap": "Treemap",
    "nav.search": "Search",
    "nav.settings": "Settings",
    "common.confirm": "OK",
    "common.ok": "OK",
    "common.cancel": "Cancel",
    "common.select_all": "Select all",
    "common.clear_all": "Clear",
    "common.none": "None",
    "settings.theme": "Theme",
    "settings.language": "Language",
    "settings.language.instant": "Language (applies instantly)",
    "settings.theme.instant": "Theme (applies instantly)",
    "settings.update.check": "Check for updates",
    "settings.reset": "Reset Defaults",
    "settings.reset_done": "Defaults restored",
    "settings.about.title": "About Catagorize",
    "settings.about.desc": "Local-first folder organizer: nothing deleted, preview first, everything undoable.",
    "nav.logs": "Logs",
    "logs.subtitle": "Records scans, organizes, update checks and other runtime events for troubleshooting.",
    "logs.clear": "Clear",
    "logs.empty": "(no logs yet)",
    "settings.theme.auto": "System",
    "settings.theme.light": "Light",
    "settings.theme.dark": "Dark",
    "settings.lang.zh": "简体中文",
    "settings.lang.en": "English",
    "settings.subtitle": "Language and theme follow the system; all data stays in the local config directory. Managed folders stay clean.",
    "settings.about.version": "Version",
    "settings.about.data_dir": "Data directory",
    "settings.about.portable.on": "Enabled (portable.flag)",
    "settings.about.portable.off": "Disabled",
    "settings.about.engine": "Engine: the core layer has zero GUI dependencies; UI and CLI share the same pipeline.",
    "overview.subtitle": "Local-first folder organizer: nothing deleted, preview first, everything undoable.",
    "overview.greeting.night": "Late night — don't tidy too long",
    "overview.greeting.morning": "Good morning, let's freshen up a folder",
    "overview.greeting.afternoon": "Good afternoon, time to put things away",
    "overview.greeting.evening": "Good evening, nothing tidied today yet",
    "overview.tagline": "Pick a folder — let's tidy it.",
    "overview.tagline2": "In place · preview first · fully undoable.",
    "overview.shortcut.inspect": "Inspect",
    "overview.shortcut.inspect.sub": "Scan for types / sizes / duplicates / junk",
    "overview.shortcut.treemap": "Treemap",
    "overview.shortcut.treemap.sub": "One rectangle for the whole folder, bigger and darker = larger",
    "overview.shortcut.search": "Search",
    "overview.shortcut.search.sub": "Find files by name in milliseconds",
    "overview.shortcut.profiles": "Folders",
    "overview.shortcut.profiles.sub": "Manage managed folders and rules",
    "overview.empty": "No managed folders yet. Click the \"Folders\" card above, or add one on the Folders page.",
    "overview.summary": "{n} managed folder(s), {files} files indexed, {size} in total.",
    "overview.card.files": "Files",
    "overview.card.size": "Size",
    "overview.card.dup": "Dup groups",
    "overview.card.pending": "To tidy",
    "overview.card.cover": "Fingerprinted",
    "overview.card.last": "Last tidy",
    "overview.card.never": "Never",
    "overview.card.unreachable": "⚠ Folder unreachable",
    "overview.clock.solar_term": "Solar term · {term}",
    "overview.indexing": "Indexing \"{name}\" in the background…",
    "overview.card.data_cache": "Data & Cache",
    "overview.data.config_dir": "Config directory",
    "overview.data.index_size": "Index size",
    "overview.data.open_dir": "Open config folder",
    "overview.card.about": "About",
    "overview.about.line": "Catagorize v{ver} · local-first folder organizer",
    "overview.about.env": "Python {py} · Qt {qt}",
    "overview.about.copyright": "© 2026 Wing North Studio",
    "overview.card.updates": "Updates",
    "overview.update.conn": "Connection",
    "overview.update.conn.ok": "GitHub reachable",
    "overview.update.conn.fail": "GitHub unreachable",
    "overview.update.conn.checking": "Checking…",
    "overview.update.conn.unknown": "Not checked yet",
    "overview.update.current": "Current version",
    "overview.update.latest": "Latest on GitHub",
    "overview.update.none": "No releases yet",
    "overview.update.check": "Check now",
    "overview.update.new_title": "New version available",
    "overview.update.new_msg": "Catagorize v{ver} is out; you're running v{cur}.",
    "overview.update.go_releases": "Go to releases page to download",
    "overview.update.dev_title": "Unreleased build notice",
    "overview.update.dev_msg": "You are running a version that has not been officially released. It may contain problems or errors — please use it with caution. Report issues to the GitHub repository's Issues page and include your version number. Sorry for the inconvenience.\n\n{url}",
    "update.new": "New version v{v} available",
    "update.banner_content": "A new version is available. Click below to download. "
        "Closing this banner won't disable the reminder on next launch.",
    "update.go": "Download",
    "update.toast": "New release available: {url}",
    "about.gui_base": "GUI base: {name} {ver}",
    "nav.export": "Export",
    "export.subtitle": "Export a managed folder's structure as PowerShell-style tree text — paste it anywhere or archive it.",
    "export.profile": "Managed folder",
    "export.format": "Format",
    "export.format.markdown": "Markdown",
    "export.format.txt": "Plain text",
    "export.show_size": "Show file sizes",
    "export.generate": "Generate",
    "export.regenerate": "Regenerate",
    "export.copy": "Copy",
    "export.save": "Save as…",
    "export.copied": "Copied to clipboard",
    "export.saved": "Saved to {path}",
    "export.filter.md": "Markdown files (*.md)",
    "export.filter.txt": "Text files (*.txt)",
    "export.empty_hint": "Pick a profile and hit Generate to get the tree text.",
    "export.truncated": " (truncated: first {n} entries)",
    "export.failed": "Export failed",
    "export.no_profile": "No managed folders yet. Add one on the Folders page.",
    "weekday.0": "Sunday",
    "weekday.1": "Monday",
    "weekday.2": "Tuesday",
    "weekday.3": "Wednesday",
    "weekday.4": "Thursday",
    "weekday.5": "Friday",
    "weekday.6": "Saturday",
    "profiles.subtitle": "Each managed folder is a \"profile\": mode (flow/archive), rule set, watch toggle.",
    "profiles.delete": "Delete",
    "profiles.delete.title": "Remove managed folder",
    "profiles.delete.msg": "\"{name}\" will be removed from Catagorize; its {n} index rows and operation logs will be cleared. Files on disk are NOT touched.",
    "profiles.delete.done": "Removed \"{name}\"",
    "profiles.add": "Add folder",
    "profiles.refresh": "Refresh",
    "profiles.empty": "No managed folders yet. Click \"Add folder\" and point at your Downloads or library.",
    "profiles.mode.flow": "Flow",
    "profiles.mode.archive": "Archive",
    "profiles.rules.count": "{n} rule(s)",
    "profiles.rules.none": "No rules",
    "profiles.watching": "watching",
    "profiles.line": "📁 {name} — {root} ({mode} · {rules}{watch}{missing})",
    "profiles.dialog.title": "Choose a folder to manage",
    "profiles.unnamed": "Untitled",
    "search.subtitle": "Search file names and paths across all managed folders; content-level search (OCR/full text) lands in a later version.",
    "search.placeholder": "Type keywords, press Enter…",
    "search.button": "Search",
    "search.no_match": "No files matching \"{q}\".",
    "search.result_line": "{path}　({profile} · {size} bytes)",
    "search.more": "\n… {n} more",
    "inspect.subtitle": "Read-only scan for a report, then decide. Tidying always shows a preview first and only runs after confirmation.",
    "inspect.profile": "Managed folder",
    "inspect.rescan": "Rescan",
    "inspect.rescan.tip": "Auto-scans on page/profile switch; this forces a refresh",
    "inspect.plan": "Build tidy plan",
    "inspect.undo": "Undo last tidy",
    "inspect.no_profile": "No profile available. Add one on the Folders page first.",
    "inspect.no_profile.warn": "No profile",
    "inspect.no_profile.hint": "Add a managed folder on the Folders page first.",
    "inspect.root_missing": "{root} has been moved or deleted. Reassign it on the Folders page.",
    "inspect.root_missing.title": "Folder unreachable",
    "inspect.scanning": "Scanning…",
    "inspect.scan_done": "Scan finished.",
    "inspect.scan_failed": "Scan failed",
    "inspect.summary": "{name}: {n} files, {size} total, {digested} fingerprinted.",
    "inspect.type_dist": "By type",
    "inspect.top10": "Top 10 by size",
    "inspect.dup_groups": "Duplicate groups (same SHA-256)",
    "inspect.junk": "Junk (skipped during scan)",
    "inspect.junk.none": "None",
    "inspect.not_scanned": "Not scanned yet.",
    "inspect.table.type": "Type",
    "inspect.table.count": "Count",
    "inspect.table.size": "Size",
    "inspect.table.path": "Path",
    "inspect.table.keeper": "Keep",
    "inspect.table.dups": "Copies",
    "inspect.plan.title": "Run this tidy plan?",
    "inspect.plan.intro": "About to run {total} action(s): move {move}, quarantine {quarantine}.\nAll actions are moves and can be undone in one click.",
    "inspect.plan.execute": "Run",
    "inspect.plan.item.move": "[Move] {src}  →  {dst}　({reason})",
    "inspect.plan.item.quarantine": "[Quarantine] {src}  →  {dst}　({reason})",
    "inspect.plan.more": "… {n} more",
    "inspect.plan.quarantine_dir": "_quarantine/",
    "inspect.planning": "Tidying…",
    "inspect.plan_failed": "Failed to build plan",
    "inspect.plan_empty": "No files match any rule and no duplicates found.",
    "inspect.plan_empty.title": "Nothing to tidy",
    "inspect.execute_done": "Moved {moved}, quarantined {quarantined}",
    "inspect.execute_failed_count": ", {n} failed",
    "inspect.execute_failed_part": "Tidy finished (partial failures)",
    "inspect.execute_ok": "Tidy finished",
    "inspect.execute_ok_suffix": ". You can undo anytime.",
    "inspect.undo_failed": "Undo failed",
    "inspect.undo_none": "Nothing to undo",
    "inspect.undo_done": "Undone",
    "inspect.undo_result": "Rolled back {restored} action(s), skipped {skipped}.",
    "inspect.profile_load_failed": "Failed to load profile",
    "inspect.reason.dup": "Duplicate",
    "treemap.subtitle": "One rectangle for the whole folder: bigger block = bigger file, darker = larger. Click to select; delete/migrate opens a checklist.",
    "treemap.rescan": "Rescan",
    "treemap.rescan.tip": "Auto-renders on page/profile switch; this forces a refresh",
    "treemap.profile": "Managed folder",
    "treemap.empty_hint": "Run a scan and the folder becomes one rectangle",
    "treemap.trash": "Delete",
    "treemap.trash.tip": "Opens a checklist; moves to the Recycle Bin (recoverable)",
    "treemap.wipe": "Delete permanently",
    "treemap.wipe.tip": "Opens a checklist; deletes for real, no recovery",
    "treemap.open": "Open with default app",
    "treemap.reveal": "Open containing folder",
    "treemap.migrate": "Migrate…",
    "treemap.pick.none": "No files selected.",
    "treemap.pick.trash_title": "Delete",
    "treemap.pick.trash_intro": "Check files to move to the Recycle Bin (recoverable):",
    "treemap.pick.wipe_title": "Delete permanently",
    "treemap.pick.wipe_intro": "Checked files will be deleted for real, no recovery:",
    "treemap.pick.migrate_title": "Migrate",
    "treemap.pick.migrate_intro": "Check files to migrate:",
    "treemap.trash_done": "Moved to Recycle Bin",
    "treemap.trash_count": "{n} file(s).",
    "treemap.wipe_done": "Deleted permanently",
    "treemap.wipe_part": "Some deletions failed",
    "treemap.migrate_dest": "Choose a destination folder",
    "treemap.migrate_conflict": "Name conflicts auto-renamed",
    "treemap.migrate_conflict_msg": "{n} file(s) exist at the destination and will get a \" (n)\" suffix.",
    "treemap.migrate_part": "Some migrations failed",
    "treemap.migrate_done": "Migration finished",
    "treemap.migrate_done_msg": "{n} file(s) moved to {dest}.",
    "treemap.open_failed": "Failed to open",
    "treemap.reveal_failed": "Failed to open folder",
    "treemap.picked": "Selected: {path} ({size})",
    "treemap.done_status": "{name}: {n} files rendered, {size} in total.",
    "treemap.scan_failed": "Scan failed",
    "treemap.load_failed": "Failed to load profile",
    "dialog.ok_count": "{ok} succeeded, {failed} failed.",
}

_STRINGS = {"zh": _ZH, "en": _EN}
_current_lang = "zh"
_listeners: list[Callable[[str], None]] = []


def _system_lang() -> str:
    """按系统 UI 语言推断默认语言：中文 → zh，其余 → en。"""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = lang_id & 0x3FF  # 主语言 ID；0x04 = LANG_CHINESE（简/繁统一按 zh）
        return "zh" if primary == 0x04 else "en"
    except (OSError, AttributeError):
        pass
    try:
        loc = locale.getlocale()[0] or ""
        return "zh" if loc.lower().startswith("zh") else "en"
    except ValueError:
        return "en"


def _lang_file():
    """持久化文件：配置目录下的 language，内容为 zh / en。"""
    from app.core.config import config_dir

    return config_dir() / "language"


def init_language() -> str:
    """启动时确定语言：用户上次的选择 > 系统语言。返回生效语言。"""
    global _current_lang
    try:
        saved = _lang_file().read_text(encoding="utf-8").strip()
        if saved in _STRINGS:
            _current_lang = saved
            return _current_lang
    except OSError:
        pass
    _current_lang = _system_lang()
    return _current_lang


def language() -> str:
    return _current_lang


def set_language(lang: str, *, persist: bool = True, notify: bool = True) -> None:
    """切换语言：写持久化文件并通知所有已注册界面刷新文案。"""
    global _current_lang
    if lang not in _STRINGS:
        lang = "zh"
    _current_lang = lang
    if persist:
        try:
            _lang_file().parent.mkdir(parents=True, exist_ok=True)
            _lang_file().write_text(lang, encoding="utf-8")
        except OSError:
            pass
    if notify:
        for cb in list(_listeners):
            cb(lang)


def add_listener(callback: Callable[[str], None]) -> None:
    """语言切换时回调；UI 层注册 retranslate。"""
    _listeners.append(callback)


def reset_to_system(*, persist: bool = True, notify: bool = True) -> None:
    """清掉用户选择，回到系统语言（「恢复默认」用）。"""
    global _current_lang
    try:
        _lang_file().unlink()
    except OSError:
        pass
    _current_lang = _system_lang()
    if persist:
        pass  # 系统语言不落盘，保持“未选择”状态
    if notify:
        for cb in list(_listeners):
            cb(_current_lang)


def tr(key: str, **kwargs) -> str:
    """取当前语言文案；缺失先回退中文，再回退键名本身。"""
    text = _STRINGS.get(_current_lang, {}).get(key)
    if text is None:
        text = _ZH.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
