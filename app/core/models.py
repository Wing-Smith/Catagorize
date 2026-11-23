"""领域模型：画像 / 规则 / 文件记录 / 整理计划。

core 层只依赖这些 dataclass 与标准库，UI 与 CLI 共用同一份定义。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ProfileMode = Literal["flow", "archive"]
"""flow = 流入型（下载目录，监听 + 自动归类）；archive = 存量型（资料库，体检 + 检索）。"""

RuleAction = Literal["move", "quarantine"]
"""move = 移动到规则目录；quarantine = 移入隔离区（去重/可疑文件，永不直接删）。"""

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "ico", "tif", "tiff"}
DOC_EXTS = {"pdf", "doc", "docx", "txt", "md", "xls", "xlsx", "ppt", "pptx", "csv"}
INSTALLER_EXTS = {"exe", "msi", "msix", "apk"}
ARCHIVE_EXTS = {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"}


def new_id() -> str:
    return uuid.uuid4().hex


def human_size(size: int) -> str:
    """字节数 → 人话体积。"""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


@dataclass
class MatchSpec:
    """规则匹配条件，全部字段为「且」关系；空字段不参与匹配。

    extensions: 扩展名集合（小写、不含点）
    name_regex: 文件名正则（re.search）
    min_size / max_size: 字节
    older_than_days: 最后修改时间早于 N 天
    """

    extensions: set[str] = field(default_factory=set)
    name_regex: str = ""
    min_size: int | None = None
    max_size: int | None = None
    older_than_days: int | None = None

    def is_empty(self) -> bool:
        return not (
            self.extensions
            or self.name_regex
            or self.min_size is not None
            or self.max_size is not None
            or self.older_than_days is not None
        )


@dataclass
class Rule:
    name: str
    match: MatchSpec
    action: RuleAction = "move"
    target_rel: str = ""  # action=move 时必填，根目录内相对路径
    enabled: bool = True
    priority: int = 100  # 小者优先
    rule_id: str = field(default_factory=new_id)

    def validate(self) -> None:
        from app.core.errors import RuleError

        if self.match.is_empty():
            raise RuleError(f"规则「{self.name}」没有任何匹配条件")
        if self.action == "move":
            target = Path(self.target_rel)
            if not self.target_rel or target.is_absolute() or ".." in target.parts:
                raise RuleError(f"规则「{self.name}」的目标必须是根目录内的相对路径")
        if self.match.name_regex:
            import re

            try:
                re.compile(self.match.name_regex)
            except re.error as exc:
                raise RuleError(f"规则「{self.name}」正则非法：{exc}") from exc


@dataclass
class FolderProfile:
    """一个受管文件夹的全部配置。JSON 持久化在 profiles 目录。"""

    name: str
    root: Path
    mode: ProfileMode = "archive"
    rules: list[Rule] = field(default_factory=list)
    watch: bool = False
    profile_id: str = field(default_factory=new_id)

    def validate(self) -> None:
        from app.core.errors import ProfileError

        if not self.root.is_absolute():
            raise ProfileError("根目录必须是绝对路径")
        seen = set()
        for rule in self.rules:
            rule.validate()
            if rule.rule_id in seen:
                raise ProfileError(f"规则 ID 重复：{rule.rule_id}")
            seen.add(rule.rule_id)


@dataclass
class FileRecord:
    """扫描产物 / 索引行。path_rel 恒为根目录内 POSIX 相对路径。"""

    path_rel: str
    size: int
    mtime: float
    ext: str = ""
    digest: str = ""  # 空串 = 未计算
    is_junk: bool = False  # thumbs.db / .DS_Store / desktop.ini 等


@dataclass
class PlanItem:
    """dry-run 计划的一行：对一个文件将要做什么、为什么。"""

    source_rel: str
    action: RuleAction
    reason: str  # 人话说明，展示在预览清单里
    rule_id: str = ""
    rule_name: str = ""
    target_rel: str | None = None  # quarantine 时由执行器生成


@dataclass
class Plan:
    profile_id: str
    root: Path
    items: list[PlanItem] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"move": 0, "quarantine": 0}
        for item in self.items:
            counts[item.action] = counts.get(item.action, 0) + 1
        counts["total"] = len(self.items)
        return counts
