"""持久化：画像 JSON 存储 + SQLite 索引库（文件索引 / 撤销日志 / FTS5）。

索引库放用户配置目录，受管目录本身永远干净——
目录可以随时脱离工具照常使用，这是产品的核心承诺。
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from app.core import config
from app.core.errors import ProfileError
from app.core.models import FolderProfile, MatchSpec, Rule

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    profile_id TEXT NOT NULL,
    path_rel   TEXT NOT NULL,
    name       TEXT NOT NULL,
    ext        TEXT NOT NULL DEFAULT '',
    size       INTEGER NOT NULL DEFAULT 0,
    mtime      REAL NOT NULL DEFAULT 0,
    digest     TEXT NOT NULL DEFAULT '',
    type       TEXT NOT NULL DEFAULT '其他',
    PRIMARY KEY (profile_id, path_rel)
);

CREATE TABLE IF NOT EXISTS ops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    profile_id  TEXT NOT NULL,
    ts          REAL NOT NULL,
    action      TEXT NOT NULL,           -- move | quarantine
    source_rel  TEXT NOT NULL,
    target_rel  TEXT NOT NULL,
    undone      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_SCHEMA_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    name, path_rel, profile_id, tokenize = 'unicode61'
);
"""


class ProfileStore:
    """每个画像一份 JSON：{profiles_dir}/{profile_id}.json。"""

    def save(self, profile: FolderProfile) -> None:
        profile.validate()
        payload = asdict(profile)
        payload["root"] = str(profile.root)
        # MatchSpec.extensions 是 set，JSON 不支持，转 list
        for rule in payload["rules"]:
            rule["match"]["extensions"] = sorted(rule["match"]["extensions"])
        path = self._path(profile.profile_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, profile_id: str) -> FolderProfile:
        path = self._path(profile_id)
        if not path.is_file():
            raise ProfileError(f"画像不存在：{profile_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._from_dict(data)

    def list_all(self) -> list[FolderProfile]:
        profiles = []
        for path in sorted(config.profiles_dir().glob("*.json")):
            try:
                profiles.append(self._from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, ProfileError, KeyError, TypeError):
                continue  # 坏文件跳过，不拖垮启动
        return profiles

    def delete(self, profile_id: str) -> None:
        self._path(profile_id).unlink(missing_ok=True)

    @staticmethod
    def _path(profile_id: str) -> Path:
        safe = "".join(c for c in profile_id if c.isalnum() or c in "-_")
        return config.profiles_dir() / f"{safe}.json"

    @staticmethod
    def _from_dict(data: dict) -> FolderProfile:
        rules = [
            Rule(
                name=r["name"],
                match=MatchSpec(
                    extensions=set(r["match"].get("extensions", [])),
                    name_regex=r["match"].get("name_regex", ""),
                    min_size=r["match"].get("min_size"),
                    max_size=r["match"].get("max_size"),
                    older_than_days=r["match"].get("older_than_days"),
                ),
                action=r.get("action", "move"),
                target_rel=r.get("target_rel", ""),
                enabled=r.get("enabled", True),
                priority=r.get("priority", 100),
                rule_id=r.get("rule_id", ""),
            )
            for r in data.get("rules", [])
        ]
        return FolderProfile(
            name=data["name"],
            root=Path(data["root"]),
            mode=data.get("mode", "archive"),
            rules=rules,
            watch=data.get("watch", False),
            profile_id=data.get("profile_id", ""),
        )


class Database:
    """SQLite（WAL）：文件索引 + 操作日志 + 全文检索。"""

    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else config.index_path()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("数据库尚未打开")
        return self._conn

    def open(self) -> "Database":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        try:
            conn.executescript(_SCHEMA_FTS)
        except sqlite3.OperationalError:
            pass  # 极简 Python 编译缺 FTS5 时降级为无全文检索
        self._conn = conn
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---- 文件索引 ----

    def upsert_files(self, profile_id: str, rows: list[dict]) -> None:
        """rows: FileRecord 转来的 dict（含 name/type）。整画像对账式重建。"""
        with self.conn:
            self.conn.execute("DELETE FROM files WHERE profile_id = ?", (profile_id,))
            self.conn.execute("DELETE FROM files_fts WHERE profile_id = ?", (profile_id,))
            self.conn.executemany(
                "INSERT INTO files (profile_id, path_rel, name, ext, size, mtime, digest, type)"
                " VALUES (:profile_id, :path_rel, :name, :ext, :size, :mtime, :digest, :type)",
                rows,
            )
            self.conn.executemany(
                "INSERT INTO files_fts (name, path_rel, profile_id) VALUES (:name, :path_rel, :profile_id)",
                rows,
            )

    def purge_profile(self, profile_id: str) -> None:
        """移除画像的全部痕迹：文件索引、FTS 行、操作日志。磁盘文件不动。"""
        with self.conn:
            self.conn.execute("DELETE FROM files WHERE profile_id = ?", (profile_id,))
            self.conn.execute("DELETE FROM files_fts WHERE profile_id = ?", (profile_id,))
            self.conn.execute("DELETE FROM ops WHERE profile_id = ?", (profile_id,))

    def mark_missing(self, profile_id: str, existing_rels: set[str]) -> list[str]:
        """把已不在盘上的路径标出（返回丢失列表）；索引与磁盘对账。"""
        rows = self.conn.execute(
            "SELECT path_rel FROM files WHERE profile_id = ?", (profile_id,)
        ).fetchall()
        missing = [r["path_rel"] for r in rows if r["path_rel"] not in existing_rels]
        return missing

    # ---- 操作日志（撤销依据） ----

    def log_op(self, session_id: str, profile_id: str, action: str, source_rel: str, target_rel: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO ops (session_id, profile_id, ts, action, source_rel, target_rel)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, profile_id, time.time(), action, source_rel, target_rel),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def mark_undone(self, op_id: int) -> None:
        self.conn.execute("UPDATE ops SET undone = 1 WHERE id = ?", (op_id,))
        self.conn.commit()

    def session_ops(self, session_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM ops WHERE session_id = ? ORDER BY id DESC", (session_id,)
        ).fetchall()

    def last_session(self, profile_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT session_id FROM ops WHERE profile_id = ? AND undone = 0"
            " ORDER BY id DESC LIMIT 1",
            (profile_id,),
        ).fetchone()
        return row["session_id"] if row else None

    def last_organize_ts(self, profile_id: str) -> float | None:
        """最近一次未撤销的整理时间（epoch 秒）；从未整理返回 None。"""
        row = self.conn.execute(
            "SELECT MAX(ts) AS ts FROM ops WHERE profile_id = ? AND undone = 0",
            (profile_id,),
        ).fetchone()
        return row["ts"] if row and row["ts"] is not None else None

    def profile_stats(self, profile_id: str) -> dict:
        """索引库里的画像统计（总览页用）。"""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS total,"
            " COALESCE(SUM(CASE WHEN digest != '' THEN 1 ELSE 0 END), 0) AS digested"
            " FROM files WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        dup = self.conn.execute(
            "SELECT COUNT(*) AS groups FROM ("
            " SELECT digest FROM files WHERE profile_id = ? AND digest != ''"
            " GROUP BY digest HAVING COUNT(*) > 1)",
            (profile_id,),
        ).fetchone()
        return {
            "files": row["n"],
            "total_size": row["total"],
            "digested": row["digested"],
            "dup_groups": dup["groups"],
        }

    def rows_for_profile(self, profile_id: str) -> list[dict]:
        """画像的全部索引行（规则匹配统计用）。"""
        return self.conn.execute(
            "SELECT * FROM files WHERE profile_id = ?", (profile_id,)
        ).fetchall()

    # ---- 全文检索 ----

    def search(self, query: str, profile_id: str | None = None, limit: int = 200) -> list[dict]:
        """子串检索文件名与路径。

        文件名检索用 LIKE 子串匹配：CJK 在 unicode61 分词下整段粘连成
        单个 token，FTS5 做不了中文子串；LIKE 对十万级行数毫无压力。
        FTS5 虚表保留给后续「文件内容」全文索引。
        """
        query = query.strip()
        if not query:
            return []
        like = f"%{query}%"
        if profile_id:
            rows = self.conn.execute(
                "SELECT * FROM files WHERE profile_id = ? AND (name LIKE ? OR path_rel LIKE ?) LIMIT ?",
                (profile_id, like, like, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM files WHERE name LIKE ? OR path_rel LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
        return [dict(r) for r in rows]
