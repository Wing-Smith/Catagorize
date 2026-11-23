"""主窗口：FluentWindow + Mica 毛玻璃。

导航结构（WinUI 3 NavigationView 规范）：
    顶部：总览 / 文件夹 / 体检 / 空间拼图 / 检索 / 导出
    底部：设置
「规则」是文件夹画像的内部配置，挂在文件夹页里编辑，不做顶级导航。
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication, QIcon
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    FluentWindow,
    InfoBar,
    InfoBarIcon,
    InfoBarPosition,
    MessageBox,
    NavigationItemPosition,
    PushButton,
)

from app.core.assets import asset
from app.core import logbus
from app.core.i18n import add_listener, tr
from app.ui.pages.export_page import ExportPage
from app.ui.pages.inspect_page import InspectPage
from app.ui.pages.logs_page import LogsPage
from app.ui.pages.overview_page import OverviewPage
from app.ui.pages.profiles_page import ProfilesPage
from app.ui.pages.search_page import SearchPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.treemap_page import TreemapPage


def _cursor_work_area() -> QRect | None:
    """用 Win32 API 取光标所在显示器的工作区（rcWork，排除任务栏）。

    返回物理像素 QRect；任何一步失败返回 None，由调用方回退 Qt 方案。
    不缓存：每次调用重新取，多屏热插拔/任务栏变化都能跟上。
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class RECT(ctypes.Structure):
            _fields_ = [(f, wintypes.LONG) for f in ("left", "top", "right", "bottom")]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        pt = POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return None
        monitor = user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return None
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
            return None
        return QRect(
            mi.rcWork.left,
            mi.rcWork.top,
            mi.rcWork.right - mi.rcWork.left,
            mi.rcWork.bottom - mi.rcWork.top,
        )
    except (OSError, AttributeError, ValueError):
        return None


class _UpdateChecker(QObject):
    """后台线程跑更新检查，Signal 桥接回主线程（Qt 队列连接线程安全）。"""

    result = Signal(object)  # updater.UpdateStatus

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        from app.core import updater

        self.result.emit(updater.check_status())


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(str(asset("app.ico"))))
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        if avail:
            self.resize(
                min(1180, int(avail.width() * 0.9)),
                min(760, int(avail.height() * 0.85)),
            )
        else:
            self.resize(1180, 760)
        self.setMicaEffectEnabled(True)  # Windows 11 Mica 毛玻璃

        self.overview_page = OverviewPage(self)
        self.profiles_page = ProfilesPage(self)
        self.inspect_page = InspectPage(self)
        self.treemap_page = TreemapPage(self)
        self.search_page = SearchPage(self)
        self.export_page = ExportPage(self)
        self.logs_page = LogsPage(self)
        self.settings_page = SettingsPage(self)

        # (页面, 图标, 文案键) —— retranslate 时按键重刷导航文字
        self._nav = [
            (self.overview_page, FIF.HOME, "nav.overview"),
            (self.profiles_page, FIF.FOLDER, "nav.profiles"),
            (self.inspect_page, FIF.ZOOM, "nav.inspect"),
            (self.treemap_page, FIF.PIE_SINGLE, "nav.treemap"),
            (self.search_page, FIF.SEARCH, "nav.search"),
            (self.export_page, FIF.SHARE, "nav.export"),
            (self.logs_page, FIF.CODE, "nav.logs"),
            (self.settings_page, FIF.SETTING, "nav.settings"),
        ]
        for page, icon, key in self._nav:
            position = (
                NavigationItemPosition.BOTTOM if key == "nav.settings" else NavigationItemPosition.TOP
            )
            self.addSubInterface(page, icon, tr(key), position=position)

        # 页面切换后让各页有机会刷新
        self.stackedWidget.currentChanged.connect(self._on_page_changed)
        add_listener(lambda _lang: self.retranslate())

        # 居中由 main.py 在 show() + 布局定型后显式调用（见 center_on_screen）

        # 更新检查：启动 2.5s 后后台跑一次；网络不通时静默落在主页卡片
        self._dev_notice_shown = False
        self._update_banner = None
        self._update_toast_sent = False
        self._update_checker = _UpdateChecker(self)
        self._update_checker.result.connect(self._on_update_result)
        self.overview_page.update_check_requested.connect(self.request_update_check)
        QTimer.singleShot(2500, self.request_update_check)

    # ---------- 更新检查 ----------

    def request_update_check(self) -> None:
        from app.core.updater import UpdateStatus

        self.overview_page.show_update_status(UpdateStatus(connected=False, checking=True))
        self._update_checker.start()

    def _on_update_result(self, status) -> None:
        from app.core import logbus
        from app.core import updater
        from app.core.updater import UpdateStatus

        if not isinstance(status, UpdateStatus):
            return
        self.overview_page.show_update_status(status)
        if not status.connected:
            logbus.warn(f"update check failed: {status.error}")
            return
        logbus.info(
            f"update check ok: current=v{status.current} latest=v{status.latest} ({status.url})"
        )
        if not status.latest:
            # 仓库还没有任何 Release：同样属于"未发行构建"，弹一次提示
            if not self._dev_notice_shown:
                self._dev_notice_shown = True
                self._show_dev_build_notice()
            return
        if updater.is_older(status.latest) and not self._dev_notice_shown:
            self._dev_notice_shown = True
            self._show_dev_build_notice()
        elif updater.is_newer(status.latest):
            self._show_new_release_bar(status)

    def _show_dev_build_notice(self) -> None:
        """本地是未发行/开发构建：每次启动弹一次（Catlas 同款文案）。

        「好」直接关窗；「前往发行版本页面下载发行版本」关窗后用
        系统默认浏览器打开发布页。
        """
        from app.core.updater import ISSUES_PAGE, RELEASES_PAGE

        box = MessageBox(
            tr("overview.update.dev_title"),
            tr("overview.update.dev_msg", url=ISSUES_PAGE),
            self,
        )
        box.yesButton.setText(tr("overview.update.go_releases"))
        box.cancelButton.setText(tr("common.ok"))
        if box.exec():  # exec 返回时弹窗已关闭
            QDesktopServices.openUrl(QUrl(RELEASES_PAGE))

    def _show_new_release_bar(self, status) -> None:
        """发现新版本：系统通知（一次）+ 总览页顶部可关闭横幅（每次启动默认显示）。

        横幅手动关闭不影响下次启动提醒；重复检查结果不会叠出多条横幅。
        """
        from app.services.notify import notify_system

        if not getattr(self, "_update_toast_sent", False):
            self._update_toast_sent = True
            notify_system(
                tr("update.new", v=status.latest),
                tr("update.toast", url=status.url),
            )
        if getattr(self, "_update_banner", None) is not None:
            return
        bar = InfoBar.warning(
            title=tr("update.new", v=status.latest),
            content=tr("update.banner_content"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            duration=-1,  # 不自动消失，用户手动关闭；下次启动重新出现
            position=InfoBarPosition.TOP,
            parent=self.overview_page,
        )
        btn = PushButton(tr("update.go"))
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(status.url)))
        bar.addWidget(btn)
        bar.show()
        self._update_banner = bar

    def _on_page_changed(self, index: int) -> None:
        widget = self.stackedWidget.widget(index)
        refresh = getattr(widget, "on_show", None)
        if callable(refresh):
            refresh()

    def retranslate(self) -> None:
        """语言切换：导航项 + 全部页面。"""
        for page, _icon, key in self._nav:
            item = self.navigationInterface.widget(page.objectName())
            if item is not None:
                item.setText(tr(key))
            page.retranslate()

    def center_on_screen(self) -> None:
        """把窗口居中到光标所在显示器的工作区中心。

        全部使用 Qt 坐标（QCursor/QScreen），与 widget 几何保证同一坐标系；
        Win32 工作区仅作日志旁证。调用时机：show() 且布局定型之后（main.py）。
        """
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            logbus.warn("center_on_screen: no screen found, keep default position")
            return
        rect = screen.availableGeometry()
        frame = self.frameGeometry()
        x = rect.left() + (rect.width() - frame.width()) // 2
        y = rect.top() + (rect.height() - frame.height()) // 2
        self.move(x, y)
        logbus.info(
            f"center_on_screen: screen={screen.name()} avail=({rect.left()},{rect.top()},"
            f"{rect.width()}x{rect.height()}) win32_work={_cursor_work_area()} "
            f"frame=({frame.width()}x{frame.height()}) → ({x},{y})"
        )
