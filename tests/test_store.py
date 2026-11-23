from pathlib import Path

import pytest

from app.core.models import FolderProfile, MatchSpec, Rule
from app.core.store import Database, ProfileStore


@pytest.fixture
def profile(tmp_path: Path, monkeypatch) -> FolderProfile:
    # 把配置目录重定向到临时目录，避免测试污染真实配置
    from app.core import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "cfg")
    monkeypatch.setattr(config, "profiles_dir", lambda: tmp_path / "cfg" / "profiles")
    (tmp_path / "cfg" / "profiles").mkdir(parents=True)
    return FolderProfile(
        name="资料库",
        root=tmp_path / "root",
        mode="archive",
        rules=[
            Rule(
                "文档",
                MatchSpec(extensions={"pdf", "txt"}, older_than_days=30),
                target_rel="docs",
                priority=10,
            )
        ],
    )


def test_profile_roundtrip(profile: FolderProfile):
    store = ProfileStore()
    store.save(profile)
    loaded = store.load(profile.profile_id)
    assert loaded.name == profile.name
    assert loaded.root == profile.root
    assert loaded.mode == profile.mode
    assert loaded.rules[0].match.extensions == {"pdf", "txt"}
    assert loaded.rules[0].match.older_than_days == 30
    assert loaded.rules[0].priority == 10
    assert loaded.rules[0].rule_id == profile.rules[0].rule_id
    assert store.list_all()[0].profile_id == profile.profile_id
    store.delete(profile.profile_id)
    assert store.list_all() == []


def test_fts_search(tmp_path: Path):
    db = Database(tmp_path / "t.db").open()
    rows = [
        {
            "profile_id": "p1",
            "path_rel": "docs/季度报告.pdf",
            "name": "季度报告.pdf",
            "ext": "pdf",
            "size": 100,
            "mtime": 0.0,
            "digest": "",
            "type": "文档",
        },
        {
            "profile_id": "p2",
            "path_rel": "shots/猫的照片.png",
            "name": "猫的照片.png",
            "ext": "png",
            "size": 200,
            "mtime": 0.0,
            "digest": "",
            "type": "图片",
        },
    ]
    db.upsert_files("p1", rows[:1])
    db.upsert_files("p2", rows[1:])

    hits = db.search("季度报告")
    assert len(hits) == 1 and hits[0]["path_rel"] == "docs/季度报告.pdf"
    assert len(db.search("季度")) == 1  # 前缀匹配
    assert len(db.search("照片")) == 1
    assert len(db.search("不存在的词xyz")) == 0
    assert db.search("") == []
    db.close()


def _db(tmp_path: Path) -> Database:
    return Database(tmp_path / "t.db").open()


def test_profile_stats_counts_files_size_digests_and_dup_groups(tmp_path: Path):
    db = _db(tmp_path)
    rows = [
        {"profile_id": "p1", "path_rel": "a.bin", "name": "a.bin", "ext": "bin",
         "size": 100, "mtime": 0.0, "digest": "same", "type": "其他"},
        {"profile_id": "p1", "path_rel": "b.bin", "name": "b.bin", "ext": "bin",
         "size": 200, "mtime": 0.0, "digest": "same", "type": "其他"},
        {"profile_id": "p1", "path_rel": "c.bin", "name": "c.bin", "ext": "bin",
         "size": 50, "mtime": 0.0, "digest": "", "type": "其他"},
    ]
    db.upsert_files("p1", rows)

    stats = db.profile_stats("p1")
    assert stats["files"] == 3
    assert stats["total_size"] == 350
    assert stats["digested"] == 2
    assert stats["dup_groups"] == 1

    # 空画像 / 未知画像
    assert db.profile_stats("nope") == {
        "files": 0, "total_size": 0, "digested": 0, "dup_groups": 0,
    }


def test_last_organize_ts_ignores_undone_and_unknown(tmp_path: Path):
    db = _db(tmp_path)
    assert db.last_organize_ts("p1") is None

    db.log_op("s1", "p1", "move", "a", "docs/a")
    op2 = db.log_op("s2", "p1", "move", "b", "docs/b")
    first = db.last_organize_ts("p1")
    assert first is not None

    db.mark_undone(op2)
    assert db.last_organize_ts("p1") is not None  # s1 仍未撤销
    db.mark_undone(1)
    assert db.last_organize_ts("p1") is None  # 全部撤销后回到“从未整理”


def test_purge_profile_clears_index_fts_and_ops(tmp_path: Path):
    from app.core.planner import records_to_rows
    from app.core.models import FileRecord

    profile = FolderProfile(name="x", root=tmp_path / "root", mode="archive")
    db = Database(tmp_path / "t.db").open()
    records = [
        FileRecord(path_rel="a.txt", size=1, mtime=0.0, digest="d1"),
        FileRecord(path_rel="b.txt", size=2, mtime=0.0, digest="d1"),
    ]
    db.upsert_files(profile.profile_id, records_to_rows(profile.profile_id, records))
    db.log_op("s1", profile.profile_id, "move", "a.txt", "docs/a.txt")
    assert db.profile_stats(profile.profile_id)["files"] == 2

    db.purge_profile(profile.profile_id)
    assert db.profile_stats(profile.profile_id)["files"] == 0
    assert db.search("a.txt", profile.profile_id) == []
    assert db.last_session(profile.profile_id) is None
    db.close()
