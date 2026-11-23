"""文件动作服务：删除 / 回收站 / 打开 / 定位 / 迁移。

Qt 无关，可被 UI 与测试共用。删除类操作只在此层实现一次，
UI 负责确认弹窗与结果提示。
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from pathlib import Path

# ---- SHFileOperationW（回收站） ----

_FO_DELETE = 3
_FOF_ALLOWUNDO = 0x0040  # 进回收站，可还原
_FOF_NOCONFIRMATION = 0x0010
_FOF_SILENT = 0x0004
_FOF_NOERRORUI = 0x0400


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("wFunc", ctypes.c_uint),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", ctypes.c_uint),
        ("fAnyOperationsAborted", ctypes.c_bool),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p),
    ]


def trash_files(paths: list[Path]) -> int:
    """移入回收站（可还原）。返回成功个数；调用方需确认 paths 都存在。"""
    existing = [str(p) for p in paths if p.exists()]
    if not existing:
        return 0
    # pFrom 必须双 NUL 结尾
    spec = "\0".join(existing) + "\0\0"
    op = _SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = _FO_DELETE
    op.pFrom = spec
    op.pTo = None
    op.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code != 0 or op.fAnyOperationsAborted:
        return 0
    return sum(1 for p in existing if not Path(p).exists())


def delete_files(paths: list[Path]) -> tuple[int, list[Path]]:
    """永久删除（文件 unlink，空目录 rmdir）。返回 (成功数, 失败列表)。不可恢复。"""
    ok, failed = 0, []
    for p in paths:
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
            ok += 1
        except OSError:
            failed.append(p)
    return ok, failed


def open_with_default(path: Path) -> None:
    """用系统默认应用打开（等价双击）。"""
    os.startfile(str(path))  # noqa: S606 - Windows 专用，路径来自用户自己的受管目录


def reveal_in_folder(path: Path) -> None:
    """在资源管理器中选中该文件。"""
    # explorer 的 "/select," 需要逗号粘在参数里
    subprocess.Popen(  # noqa: S603
        ["explorer", "/select,", str(path)],
        shell=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def migrate_files(paths: list[Path], target_dir: Path) -> tuple[int, list[Path]]:
    """把文件迁移到 target_dir（跨设备自动 copy+unlink）。重名时自动加 " (n)" 后缀。

    返回 (成功数, 失败列表)。原地不动失败项。
    """
    target_dir = Path(target_dir)
    ok, failed = 0, []
    for src in paths:
        try:
            if not src.exists():
                failed.append(src)
                continue
            dest = _free_slot(target_dir / src.name)
            shutil.move(str(src), str(dest))
            ok += 1
        except OSError:
            failed.append(src)
    return ok, failed


def _free_slot(path: Path) -> Path:
    """同名目标被占时，依次尝试 "name (2).ext" "name (3).ext"…"""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(2, 1000):
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"找不到可用文件名：{path.name}")
