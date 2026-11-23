"""导出 PowerShell `tree` 风格的目录结构文本。

纯逻辑、不依赖 Qt，方便单测。用方框字符（├── └── │）画树，
可选附带文件大小；超过 max_entries 行截断并置 truncated 标志，
避免把整个磁盘 dump 进剪贴板。
"""

from __future__ import annotations

from pathlib import Path

from app.core.models import human_size

MAX_ENTRIES = 20000


def build_tree(root: Path, *, show_size: bool = False,
               max_entries: int = MAX_ENTRIES) -> tuple[str, bool]:
    """返回 (tree 文本, 是否截断)。root 不存在时抛出 FileNotFoundError。"""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(str(root))

    lines: list[str] = [root.name or str(root)]
    state = {"count": 0, "truncated": False}

    def walk(dir_path: Path, prefix: str) -> None:
        if state["truncated"]:
            return
        try:
            # 目录在前、同类型按名称排，结构稳定好 diff
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.casefold()))
        except OSError:
            lines.append(prefix + "└── <error>")
            return
        for i, entry in enumerate(entries):
            if state["count"] >= max_entries:
                state["truncated"] = True
                lines.append(prefix + "└── …")
                return
            last = i == len(entries) - 1
            branch = "└── " if last else "├── "
            if entry.is_dir():
                label = entry.name + "/"
            else:
                label = entry.name
                if show_size:
                    try:
                        label += f" ({human_size(entry.stat().st_size)})"
                    except OSError:
                        pass
            lines.append(prefix + branch + label)
            state["count"] += 1
            if entry.is_dir():
                walk(entry, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines), state["truncated"]


def wrap_markdown(tree_text: str) -> str:
    """Markdown 版本：整段包进 ```text 围栏，贴进 MD 文档即所得。"""
    return f"```text\n{tree_text}\n```"
