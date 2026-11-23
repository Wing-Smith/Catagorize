"""文件监听：流入型画像的自动归类触发器。

QFileSystemWatcher + 防抖：目录里文件落盘后静默 2 秒再批量出事件，
避免复制大文件期间触发半成品整理。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer


class FolderWatcher(QObject):
    """单个受管目录的防抖监听。changed(paths) 回调收到的已是稳定文件。"""

    def __init__(self, root, on_stable: Callable[[list[str]], None], parent=None, debounce_ms: int = 2000):
        super().__init__(parent)
        self._root = str(root)
        self._on_stable = on_stable
        self._pending: set[str] = set()
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._flush)
        self._add_tree()

    def _add_tree(self) -> None:
        import os

        for dirpath, dirnames, _ in os.walk(self._root):
            self._watcher.addPath(dirpath)
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if self._root not in self._watcher.directories():
            self._watcher.addPath(self._root)

    def _on_dir_changed(self, path: str) -> None:
        self._add_tree()  # 新建子目录也要挂上监听
        self._flush_later()

    def _on_file_changed(self, path: str) -> None:
        self._pending.add(path)
        self._flush_later()

    def _flush_later(self) -> None:
        self._timer.start()

    def _flush(self) -> None:
        import os

        # 只回调盘上真实存在且大小稳定的文件
        stable = [p for p in self._pending if os.path.isfile(p)]
        self._pending.clear()
        if stable:
            self._on_stable(stable)

    def stop(self) -> None:
        self._timer.stop()
        self._watcher.removePaths(list(self._watcher.directories()))
        self._watcher.removePaths(list(self._watcher.files()))
