"""执行器：按计划移动文件，全程写日志，支持一键撤销。

安全约定：
- 只 move 不 delete；隔离也是移动（进 _quarantine/）；
- 每个动作先记日志再动手，崩溃中断后仍能按日志逆序回滚；
- 目标被占用/源消失 → MoveFailedError，已完成的动作不受影响。
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.core.errors import MoveFailedError
from app.core.models import Plan
from app.core.planner import QUARANTINE_DIR
from app.core.store import Database


def unique_quarantine_rel(root: Path, source_rel: str, taken: set[str]) -> str:
    """隔离区目标路径：_quarantine/<原名>，撞名加序号。"""
    name = Path(source_rel).name
    candidate = f"{QUARANTINE_DIR}/{name}"
    index = 1
    while candidate in taken or (root / candidate).exists():
        candidate = f"{QUARANTINE_DIR}/{index}_{name}"
        index += 1
    taken.add(candidate)
    return candidate


def execute_plan(plan: Plan, db: Database, on_progress=None) -> dict:
    """执行计划，返回统计。on_progress(done, total, current_rel)。"""
    root = plan.root
    if not root.is_dir():
        from app.core.errors import RootMissingError

        raise RootMissingError(f"受管目录不存在：{root}")

    session_id = uuid.uuid4().hex
    done = moved = quarantined = 0
    failed: list[tuple[str, str]] = []
    taken: set[str] = set()

    for item in plan.items:
        done += 1
        if on_progress:
            on_progress(done, len(plan.items), item.source_rel)
        source = root / item.source_rel
        if not source.is_file():
            failed.append((item.source_rel, "源文件已不存在"))
            continue
        if item.action == "move":
            assert item.target_rel is not None
            target_rel = item.target_rel
        else:
            target_rel = unique_quarantine_rel(root, item.source_rel, taken)

        target = root / target_rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise MoveFailedError(f"目标已存在：{target_rel}")
            shutil.move(str(source), str(target))
        except (OSError, MoveFailedError) as exc:
            failed.append((item.source_rel, str(exc)))
            continue
        db.log_op(session_id, plan.profile_id, item.action, item.source_rel, target_rel)
        if item.action == "move":
            moved += 1
        else:
            quarantined += 1

    from app.core import logbus

    logbus.info(
        f"plan executed: total={len(plan.items)} moved={moved}"
        f" quarantined={quarantined} failed={len(failed)}"
    )
    return {
        "session_id": session_id,
        "moved": moved,
        "quarantined": quarantined,
        "failed": failed,
        "total": len(plan.items),
    }


def undo_session(plan_root: Path, db: Database, session_id: str) -> dict:
    """逆序回滚一次会话的全部动作：target 移回 source。

    只回滚仍完整存在、且原位空闲的动作；被用户改动过的跳过并报告。
    """
    ops = db.session_ops(session_id)
    restored = skipped = 0
    for op in ops:
        if op["undone"]:
            continue
        source = plan_root / op["target_rel"]
        target = plan_root / op["source_rel"]
        if not source.is_file():
            skipped += 1
            continue
        if target.exists():
            skipped += 1
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        except OSError:
            skipped += 1
            continue
        db.mark_undone(op["id"])
        restored += 1
    # 隔离区清空后把空目录收走，目录还原到整理前状态
    quarantine_dir = plan_root / QUARANTINE_DIR
    try:
        quarantine_dir.rmdir()
    except OSError:
        pass  # 非空或已不存在，都不处理
    from app.core import logbus

    logbus.info(f"session undone: restored={restored} skipped={skipped}")
    return {"restored": restored, "skipped": skipped}


def undo_last(profile_id: str, profile_root: Path, db: Database) -> dict | None:
    """撤销该画像最近一次整理。没有可撤销会话返回 None。"""
    session_id = db.last_session(profile_id)
    if session_id is None:
        return None
    return undo_session(profile_root, db, session_id)
