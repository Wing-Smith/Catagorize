"""领域异常：引擎层所有可预期失败都抛这里定义的异常，UI 层负责翻译成人话。"""

from __future__ import annotations


class CatagorizeError(Exception):
    """所有领域异常的基类。"""


class ProfileError(CatagorizeError):
    """资料夹画像配置非法（根目录不存在、规则冲突等）。"""


class RootMissingError(CatagorizeError):
    """受管根目录已被移动/改名/删除。

    约定（沿用 DropDesk 0.3.1 的教训）：绝不自动重建空目录顶替，
    必须让用户重新指定位置。
    """


class RuleError(CatagorizeError):
    """规则定义非法（正则不合法、目标在根目录外等）。"""


class PlanConflictError(CatagorizeError):
    """dry-run 计划里出现冲突（两个文件要落到同一路径等）。"""


class MoveFailedError(CatagorizeError):
    """执行移动时源不存在或目标被占用。"""
