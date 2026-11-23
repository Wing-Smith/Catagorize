"""file_actions 服务层测试：永久删除 / 迁移 / 重名避让。

回收站（SHFileOperationW）依赖系统交互与桌面会话，不在离屏环境测。
"""

from __future__ import annotations

from pathlib import Path

from app.services import file_actions


def _mk(root: Path, rel: str, size: int = 16) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    return p


def test_delete_files_removes_and_reports(tmp_path: Path) -> None:
    a = _mk(tmp_path, "a.txt")
    b = _mk(tmp_path, "sub/b.txt")
    missing = tmp_path / "nope.txt"

    ok, failed = file_actions.delete_files([a, b, missing])

    assert ok == 2
    assert failed == [missing]
    assert not a.exists() and not b.exists()


def test_migrate_moves_and_keeps_content(tmp_path: Path) -> None:
    src = _mk(tmp_path / "in", "doc/report.pdf", size=64)
    dest_dir = tmp_path / "out"
    dest_dir.mkdir()

    ok, failed = file_actions.migrate_files([src], dest_dir)

    assert (ok, failed) == (1, [])
    assert not src.exists()
    assert (dest_dir / "report.pdf").read_bytes() == b"x" * 64


def test_migrate_renames_on_conflict(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    a = _mk(src_dir, "photo.jpg")
    b = _mk(src_dir / "other", "photo.jpg")
    dest_dir = tmp_path / "out"
    _mk(dest_dir, "photo.jpg")

    ok, failed = file_actions.migrate_files([a, b], dest_dir)

    assert (ok, failed) == (2, [])
    assert (dest_dir / "photo.jpg").exists()          # 原占用者不动
    assert (dest_dir / "photo (2).jpg").exists()
    assert (dest_dir / "photo (3).jpg").exists()


def test_migrate_missing_source_reported_failed(tmp_path: Path) -> None:
    ghost = tmp_path / "ghost.bin"
    ok, failed = file_actions.delete_files([ghost])  # 先确认不存在
    assert ok == 0

    ok, failed = file_actions.migrate_files([ghost], tmp_path)
    assert (ok, failed) == (0, [ghost])


def test_free_slot_skips_existing(tmp_path: Path) -> None:
    p = _mk(tmp_path, "name.ext")
    assert file_actions._free_slot(p) == tmp_path / "name (2).ext"
