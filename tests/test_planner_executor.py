import time
from pathlib import Path

from app.core.executor import execute_plan, undo_last
from app.core.models import FolderProfile, MatchSpec, Rule
from app.core.planner import build_plan
from app.core.store import Database


def make_profile(root: Path, rules=None) -> FolderProfile:
    profile = FolderProfile(name="test", root=root, mode="archive", rules=rules or [])
    return profile


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db").open()


def test_rule_move_roundtrip(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "report.pdf").write_bytes(b"pdf-content")
    profile = make_profile(
        root,
        [Rule("pdfs", MatchSpec(extensions={"pdf"}), target_rel="docs")],
    )
    plan = build_plan(profile)
    assert len(plan.items) == 1
    assert plan.items[0].target_rel == "docs/report.pdf"

    db = make_db(tmp_path)
    stats = execute_plan(plan, db)
    assert stats["moved"] == 1
    assert (root / "docs" / "report.pdf").is_file()
    assert not (root / "report.pdf").exists()

    undo = undo_last(profile.profile_id, root, db)
    assert undo is not None and undo["restored"] == 1
    assert (root / "report.pdf").is_file()
    assert not (root / "docs" / "report.pdf").exists()


def test_duplicate_quarantine(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    payload = b"identical-payload"
    (root / "a.txt").write_bytes(payload)
    (root / "b.txt").write_bytes(payload)
    profile = make_profile(root)

    plan = build_plan(profile)
    quarantine = [i for i in plan.items if i.action == "quarantine"]
    assert len(quarantine) == 1
    assert "内容完全相同" in quarantine[0].reason

    db = make_db(tmp_path)
    execute_plan(plan, db)
    quarantined_files = list((root / "_quarantine").iterdir())
    assert len(quarantined_files) == 1

    undo = undo_last(profile.profile_id, root, db)
    assert undo["restored"] == 1
    assert (root / "a.txt").is_file() and (root / "b.txt").is_file()
    assert not (root / "_quarantine").exists()


def test_no_rule_no_action(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.txt").write_text("stay")
    plan = build_plan(make_profile(root))
    assert plan.items == []


def test_conflict_same_name_same_target_dir(tmp_path: Path):
    import pytest

    from app.core.errors import PlanConflictError

    root = tmp_path / "root"
    (root / "d1").mkdir(parents=True)
    (root / "d2").mkdir(parents=True)
    (root / "d1" / "same.txt").write_text("A")
    (root / "d2" / "same.txt").write_text("B")
    profile = make_profile(
        root,
        [Rule("txt", MatchSpec(extensions={"txt"}), target_rel="out")],
    )
    with pytest.raises(PlanConflictError):
        build_plan(profile)


def test_target_occupied_conflict(tmp_path: Path):
    import pytest

    from app.core.errors import PlanConflictError

    root = tmp_path / "root"
    (root / "docs").mkdir(parents=True)
    (root / "a.pdf").write_text("new")
    (root / "docs" / "a.pdf").write_text("old-occupant")
    profile = make_profile(
        root,
        [Rule("pdfs", MatchSpec(extensions={"pdf"}), target_rel="docs")],
    )
    with pytest.raises(PlanConflictError):
        build_plan(profile)


def test_missing_root_raises(tmp_path: Path):
    import pytest

    from app.core.errors import RootMissingError

    profile = make_profile(tmp_path / "gone")
    with pytest.raises(RootMissingError):
        build_plan(profile)


def test_junk_files_untouched(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "Thumbs.db").write_bytes(b"junk")
    (root / "real.txt").write_text("real")
    plan = build_plan(make_profile(root))
    assert all("Thumbs.db" not in i.source_rel for i in plan.items)
