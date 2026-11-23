"""内容指纹：SHA-256 分块哈希。

沿用了从 DropDesk 逆向确认有效的设计：内容级去重（不是文件名级），
分块读取避免大文件一次性进内存。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024  # 1 MiB


def file_digest(path: Path, chunk: int = _CHUNK) -> str:
    """文件内容的 SHA-256，十六进制小写。文件不存在抛 FileNotFoundError。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
