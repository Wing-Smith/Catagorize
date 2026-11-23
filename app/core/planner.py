"""计划器：扫描 + 规则 + 去重 → 一份可预览的 dry-run 计划。

核心承诺：plan 阶段只做只读操作（哈希计算除外），
所有动作都是「移动」或「移入隔离区」，**计划里不存在删除**。
冲突在计划阶段就暴露（PlanConflictError），绝不留到执行期。
"""

from __future__ import annotations

import time
from pathlib import Path

from app.core import fingerprint
from app.core.errors import PlanConflictError, RootMissingError
from app.core.models import FileRecord, FolderProfile, Plan, PlanItem
from app.core.rules import resolve
from app.core.scanner import scan_profile, type_of

QUARANTINE_DIR = "_quarantine"


def build_plan(
    profile: FolderProfile,
    records: list[FileRecord] | None = None,
    on_progress=None,
) -> Plan:
    """生成整理计划。records 为 None 时现场扫描。"""
    root = profile.root
    if not root.is_dir():
        raise RootMissingError(f"受管目录不存在：{root}")
    if records is None:
        records = scan_profile(root, on_progress)

    plan = Plan(profile_id=profile.profile_id, root=root)
    _add_dedup_items(profile, records, plan)
    _add_rule_items(profile, records, plan)
    _check_conflicts(root, plan)
    return plan


def _add_dedup_items(profile: FolderProfile, records: list[FileRecord], plan: Plan) -> None:
    """内容级去重：同指纹只留一份（最新 mtime，平手取路径短者），其余进隔离区。"""
    groups: dict[str, list[FileRecord]] = {}
    quarantined = {item.source_rel for item in plan.items}
    for record in records:
        if record.is_junk or record.size == 0 or record.path_rel in quarantined:
            continue
        # 已在计划里要移动的文件不参与去重（它即将离开原位）
        digest = record.digest or fingerprint.file_digest(profile.root / record.path_rel)
        record.digest = digest
        groups.setdefault(digest, []).append(record)

    for digest, members in groups.items():
        if len(members) < 2:
            continue
        keeper = min(members, key=lambda r: (-r.mtime, len(r.path_rel)))
        for dup in members:
            if dup is keeper:
                continue
            plan.items.append(
                PlanItem(
                    source_rel=dup.path_rel,
                    action="quarantine",
                    reason=f"与 {keeper.path_rel} 内容完全相同（SHA-256 一致）",
                )
            )


def _add_rule_items(profile: FolderProfile, records: list[FileRecord], plan: Plan) -> None:
    planned = {item.source_rel for item in plan.items}
    now = time.time()
    for record in records:
        if record.is_junk or record.path_rel in planned:
            continue
        hit = resolve(record, profile.rules, now)
        if hit is None or hit.target_rel is None:
            continue
        # target_rel 是目标目录；落地路径 = 目标目录 + 原文件名
        target_rel = f"{hit.target_rel.strip('/')}/{Path(record.path_rel).name}"
        if target_rel == record.path_rel:
            continue  # 已在目标位置，无事发生
        plan.items.append(
            PlanItem(
                source_rel=record.path_rel,
                action=hit.rule.action,
                target_rel=target_rel,
                rule_id=hit.rule.rule_id,
                rule_name=hit.rule.name,
                reason=f"命中规则「{hit.rule.name}」",
            )
        )


def _check_conflicts(root: Path, plan: Plan) -> None:
    """两个源落到同一路径 / 目标被盘上既有文件占用 → 计划期直接报错。"""
    targets: dict[str, str] = {}
    for item in plan.items:
        if item.action != "move":
            continue
        assert item.target_rel is not None
        prev = targets.get(item.target_rel)
        if prev is not None and prev != item.source_rel:
            raise PlanConflictError(
                f"{prev} 与 {item.source_rel} 将落到同一路径 {item.target_rel}"
            )
        targets[item.target_rel] = item.source_rel
        if (root / item.target_rel).exists():
            raise PlanConflictError(f"目标已被盘上文件占用：{item.target_rel}")


def records_to_rows(profile_id: str, records: list[FileRecord]) -> list[dict]:
    """FileRecord → 索引库行。"""
    rows = []
    for r in records:
        rows.append(
            {
                "profile_id": profile_id,
                "path_rel": r.path_rel,
                "name": Path(r.path_rel).name,
                "ext": r.ext,
                "size": r.size,
                "mtime": r.mtime,
                "digest": r.digest,
                "type": type_of(r.ext),
            }
        )
    return rows
