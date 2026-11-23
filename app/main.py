"""GUI 入口：python -m app.main"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core import config
from app.core.assets import asset
from app.core.config import APP_ID, APP_NAME, APP_VERSION
from app.ui.main_window import MainWindow
from app.ui.theme import apply_fluent_theme

_SINGLE_INSTANCE_MEM = None  # 必须常驻，被 GC 会释放共享内存导致单实例锁失效


def _install_crash_hooks() -> None:
    """未捕获异常 → LogBus + 崩溃文件（exe 无控制台时的唯一取证途径）。"""

    import threading
    import traceback
    from pathlib import Path

    from app.core import logbus
    from app.core.config import config_dir

    def _write_crash(text: str) -> None:
        logbus.error(text.splitlines()[0] if text else "unknown error")
        try:
            (Path(config_dir()) / "catagorize_crash.log").write_text(
                text, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass

    def _hook(exc_type, exc, tb):
        _write_crash("".join(traceback.format_exception(exc_type, exc, tb)))

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        _write_crash(
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )

    sys.excepthook = _hook
    threading.excepthook = _thread_hook


def _activate_existing_instance() -> None:
    """已有实例在运行：把它的窗口拉到前台，然后本进程退出。"""

    try:
        import win32con
        import win32gui

        def _enum(hwnd, _extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.startswith(APP_NAME):
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)

        win32gui.EnumWindows(_enum, None)
    except Exception:
        pass  # 找不到窗口就静默退出


def _ensure_single_instance() -> bool:
    """返回 True 表示本进程可以继续启动；False 表示已有实例在运行。"""

    global _SINGLE_INSTANCE_MEM
    from PySide6.QtCore import QSharedMemory

    mem = QSharedMemory(APP_ID)
    if mem.attach():  # 已存在 → 旧实例还活着（Windows 下进程退出会自动释放）
        mem.detach()
        return False
    if not mem.create(1):
        return False
    _SINGLE_INSTANCE_MEM = mem
    return True


def main() -> int:
    _install_crash_hooks()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("WingNorth")

    if not _ensure_single_instance():
        _activate_existing_instance()
        return 0

    icon = asset("app.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    from app.core import config, logbus
    from app.core.i18n import init_language, language

    init_language()
    apply_fluent_theme(config.theme())
    logbus.info(
        f"Catagorize {APP_VERSION} started | lang={language()} theme={config.theme()}"
        f" portable={config.PORTABLE}"
    )

    window = MainWindow()
    window.setWindowTitle(APP_NAME)  # 标题不挂版本号（版本在设置/关于/更新卡里）
    window.show()
    # 布局定型后立刻居中（Win32 工作区）；300ms 后再校准一次，防首次显示被 DWM 复位
    app.processEvents()
    window.center_on_screen()
    QTimer.singleShot(300, window.center_on_screen)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
