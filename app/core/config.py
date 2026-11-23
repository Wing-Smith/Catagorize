"""全局配置与目录约定。

便携模式：exe 同级（或源码根目录）放置 portable.flag，
配置/索引全部重定向到程序目录下的 CatagorizeData/。
"""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "Catagorize"
APP_NAME_CN = "Catagorize · 文件夹整理"
APP_ID = "Catagorize-SingleInstance-v1"
ORG_NAME = "Wing North Studio"

APP_VERSION = "0.1.8"

# GUI 实现框架的署名（展示在开屏 / 关于区）
GUI_BASE_NAME = "Catopsys GUI Base"
GUI_BASE_VERSION = "1.7.1"


def _portable_root() -> Path | None:
    """检测便携模式标记文件 portable.flag 所在目录。"""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass))
    candidates.append(Path(sys.executable).parent)
    candidates.append(Path(__file__).resolve().parent.parent.parent)
    for root in candidates:
        if (root / "portable.flag").exists():
            return root
    return None


_PORTABLE_ROOT = _portable_root()
PORTABLE = _PORTABLE_ROOT is not None


def config_dir() -> Path:
    """应用配置目录（profile、设置、索引库所在根目录）。"""
    if _PORTABLE_ROOT is not None:
        root = _PORTABLE_ROOT / "CatagorizeData"
    else:
        root = Path(user_config_dir(APP_NAME, ORG_NAME, roaming=True))
    root.mkdir(parents=True, exist_ok=True)
    return root


def profiles_dir() -> Path:
    d = config_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_path() -> Path:
    """SQLite 索引库（文件索引 + 撤销日志 + FTS5）。"""
    return config_dir() / "catagorize.db"


# ---- 简单持久化设置（与 language 文件同风格：配置目录下的纯文本文件） ----

def _read_setting(name: str) -> str:
    try:
        return (config_dir() / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_setting(name: str, value: str) -> None:
    path = config_dir() / name
    if value:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    else:
        try:
            path.unlink()
        except OSError:
            pass


def theme() -> str:
    """用户上次选择的主题：auto / light / dark，默认 auto。"""
    value = _read_setting("theme")
    return value if value in ("auto", "light", "dark") else "auto"


def set_theme(value: str) -> None:
    _write_setting("theme", value if value in ("auto", "light", "dark") else "auto")


def update_url() -> str:
    """自定义更新源（GitHub Releases API 地址）；留空用 updater 内置地址。"""
    return _read_setting("update_url")


def set_update_url(url: str) -> None:
    _write_setting("update_url", url.strip())
