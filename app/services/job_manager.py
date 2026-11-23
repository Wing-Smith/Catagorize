"""后台任务线程：扫描 / 整理 / 索引，进度通过 Qt 信号上报。

从 Catlas 的 job_manager 简化而来：去掉领域耦合，只保留
「QThread + 取消令牌 + 进度信号」的通用骨架。
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class CancelToken:
    """跨线程取消令牌；任务循环里周期性调用 raise_if_cancelled。"""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class JobWorker(QThread):
    """跑任意 callable(progress_cb, token) 的通用工作者。"""

    progress = Signal(int, int, str)  # done, total, 当前项
    finished_ok = Signal(object)  # 函数返回值
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        """fn 签名为 fn(progress, token) -> result；progress 为 (done,total,msg) 可调用对象。"""
        super().__init__(parent)
        self._fn = fn
        self.token = CancelToken()

    def run(self) -> None:  # noqa: N802 - Qt 约定
        def progress(done: int, total: int, msg: str = "") -> None:
            self.progress.emit(done, total, msg)

        try:
            result = self._fn(progress, self.token)
        except Exception as exc:  # noqa: BLE001 - 统一走信号上报
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(result)
