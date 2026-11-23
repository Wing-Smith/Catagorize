"""规则引擎：给定文件与画像规则集，决定「不动 / 移动 / 隔离」。

匹配语义：单条规则内条件为「且」；规则间按 priority 升序，先命中先生效；
没有任何规则命中 → 留在原地（保守默认，模糊的一律不动）。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.models import FileRecord, MatchSpec, Rule


@dataclass
class RuleHit:
    rule: Rule
    target_rel: str | None  # quarantine 时为 None


def match_spec(spec: MatchSpec, record: FileRecord, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    if spec.extensions and record.ext not in spec.extensions:
        return False
    if spec.name_regex and not re.search(spec.name_regex, Path(record.path_rel).name):
        return False
    if spec.min_size is not None and record.size < spec.min_size:
        return False
    if spec.max_size is not None and record.size > spec.max_size:
        return False
    if spec.older_than_days is not None:
        age_seconds = now - record.mtime
        if age_seconds < spec.older_than_days * 86400:
            return False
    return True


def resolve(record: FileRecord, rules: list[Rule], now: float | None = None) -> RuleHit | None:
    """返回第一个命中的规则；未命中返回 None。"""
    for rule in sorted(rules, key=lambda r: (r.priority, r.rule_id)):
        if rule.enabled and match_spec(rule.match, record, now):
            return RuleHit(rule=rule, target_rel=rule.target_rel or None)
    return None
