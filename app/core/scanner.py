"""体检扫描：遍历画像根目录，产出 FileRecord 列表。

原则：
- 只读，绝不修改任何文件；
- 跳过系统保留目录与垃圾文件（沿用 DropDesk 的 _SKIP_NAMES 思路）；
- 根目录丢失抛 RootMissingError，绝不自动重建。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterator

from app.core.errors import RootMissingError
from app.core.models import FileRecord

SKIP_DIR_NAMES = {"$RECYCLE.BIN", "System Volume Information", ".git", "node_modules", "__pycache__"}
SKIP_FILE_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}

ProgressFn = Callable[[int, str], None]  # (已处理数, 当前路径)


def scan_profile(root: Path, on_progress: ProgressFn | None = None) -> list[FileRecord]:
    """全量扫描。root 必须存在且是目录。"""
    if not root.is_dir():
        raise RootMissingError(f"受管目录不存在：{root}")
    records: list[FileRecord] = []
    count = 0
    for record in iter_records(root, on_progress):
        records.append(record)
        count += 1
        if on_progress and count % 200 == 0:
            on_progress(count, record.path_rel)
    return records


def scan_with_digests(root: Path, progress=None, token=None) -> list[FileRecord]:
    """扫描 + 为可去重文件算 SHA-256。

    progress(done, total, msg)；token 需有 .cancelled 属性（见
    services.job_manager.CancelToken）。引擎层不 import Qt。
    """
    from app.core.fingerprint import file_digest  # 延迟导入保持模块轻

    records = scan_profile(root, lambda n, cur: progress and progress(n, 0, f"已发现 {n} 个文件：{cur}"))
    total = len(records)
    for i, record in enumerate(records, 1):
        if token is not None and token.cancelled:
            break
        if not record.is_junk and record.size > 0:
            record.digest = file_digest(root / record.path_rel)
        if progress:
            progress(i, total, record.path_rel)
    return records


def iter_records(root: Path, on_progress: ProgressFn | None = None) -> Iterator[FileRecord]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                stat = path.stat()
            except OSError:
                continue  # 扫描期间被移走的文件，跳过即可
            rel = path.relative_to(root).as_posix()
            yield FileRecord(
                path_rel=rel,
                size=stat.st_size,
                mtime=stat.st_mtime,
                ext=path.suffix.lower().lstrip("."),
                is_junk=filename.lower() in SKIP_FILE_NAMES,
            )


def type_of(ext: str) -> str:
    """扩展名 → 大类的粗分类（体检报告用）。"""
    from app.core.models import ARCHIVE_EXTS, DOC_EXTS, IMAGE_EXTS, INSTALLER_EXTS

    if ext in IMAGE_EXTS:
        return "图片"
    if ext in DOC_EXTS:
        return "文档"
    if ext in INSTALLER_EXTS:
        return "安装包"
    if ext in ARCHIVE_EXTS:
        return "压缩包"
    if ext in {"mp4", "mkv", "avi", "mov", "mp3", "wav", "flac"}:
        return "音视频"
    return "其他"
