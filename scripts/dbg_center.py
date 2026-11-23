# -*- coding: utf-8 -*-
"""真实桌面探针：对比 Qt / Win32 坐标系，验证 show 后实际窗口位置。

只运行约 2 秒，自动关闭。用法：
    .venv\\Scripts\\python.exe scripts/dbg_center.py
"""
import ctypes
import sys
import time
from ctypes import wintypes

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

sys.path.insert(0, '.')
from app.ui.main_window import _cursor_work_area, MainWindow  # noqa: E402


def win32_cursor() -> tuple[int, int]:
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    assert ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def main() -> None:
    app = QApplication([])

    print("== QApplication 创建后 ==")
    print("Win32 cursor          :", win32_cursor())
    print("Qt    QCursor.pos()   :", QCursor.pos().x(), QCursor.pos().y())
    for s in QGuiApplication.screens():
        print(f"  screen {s.name()}: geo={s.geometry()} avail={s.availableGeometry()} "
              f"dpi={s.logicalDotsPerInch():.0f} factor={s.devicePixelRatio()}")
    r = _cursor_work_area()
    print("Win32 _cursor_work_area:", r)

    win = MainWindow()
    win.show()
    app.processEvents()
    print("== show 后（未居中）==")
    print("frameGeometry:", win.frameGeometry())
    app.processEvents()
    win.center_on_screen()
    app.processEvents()
    print("== center_on_screen 后 ==")
    print("frameGeometry:", win.frameGeometry())

    def report_and_quit():
        print("== 300ms 后 ==")
        print("frameGeometry:", win.frameGeometry())
        app.quit()

    QTimer.singleShot(300, report_and_quit)
    app.exec()
    time.sleep(0.1)


if __name__ == '__main__':
    main()
