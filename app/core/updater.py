"""自动更新检查：对照 GitHub Releases 最新版本号，只提示、不强制。

复刻自 Catlas 的 updater，HTTP 层从 requests 换成标准库 urllib
（项目不依赖 requests）。超时/网络错误不会抛出到调用方，
绝不影响启动。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import APP_VERSION, update_url as _update_url

TIMEOUT_S = 8

GITHUB_REPO = "Wing-Smith/Catagorize"
DEFAULT_UPDATE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
ISSUES_PAGE = f"https://github.com/{GITHUB_REPO}/issues"

USER_AGENT = f"Catagorize/{APP_VERSION}"


@dataclass
class ReleaseInfo:
    version: str
    url: str  # 发布页（浏览器打开）


@dataclass
class UpdateStatus:
    """一次更新检查的完整结果，供界面展示连接状态与版本对比。"""

    connected: bool              # GitHub API 是否可达
    current: str = APP_VERSION
    latest: str | None = None    # 解析到的最新版本号；连接成功但无 Release 时为 None
    url: str = RELEASES_PAGE     # 最新版本发布页
    error: str = ""              # 连接失败原因（截断）
    checking: bool = field(default=False)  # 正在检查中（界面中间态）


def api_url() -> str:
    """实际使用的 Releases API 地址：设置页自定义优先，否则用内置地址。"""
    return _update_url() or DEFAULT_UPDATE_API


def _parse_ver(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text)
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str) -> bool:
    return _parse_ver(latest) > _parse_ver(APP_VERSION)


def is_older(latest: str) -> bool:
    """本地版本比 GitHub 最新发行版还新（未发行/开发构建）。"""
    return _parse_ver(latest) < _parse_ver(APP_VERSION)


def check_latest(timeout: int = TIMEOUT_S) -> ReleaseInfo | None:
    """拉取最新发布；网络错误或解析失败返回 None（静默）。"""
    status = check_status(timeout)
    if not (status.connected and status.latest):
        return None
    return ReleaseInfo(version=status.latest, url=status.url)


def _repo_reachable(timeout: int) -> bool:
    """仓库本身是否存在（区分「无 Release」与「仓库不可达/私有」）。"""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def check_status(timeout: int = TIMEOUT_S) -> UpdateStatus:
    """带连接状态的一次检查：异常吞掉转为 UpdateStatus.error。

    Releases API 对「仓库存在但无 Release」也返回 404 —— 这种情况
    探测仓库端点，可达则视为已连接、暂无 Release。
    """
    req = urllib.request.Request(
        api_url(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and _repo_reachable(timeout):
            return UpdateStatus(connected=True, latest=None)
        return UpdateStatus(connected=False, error=str(exc)[:120])
    except Exception as exc:  # noqa: BLE001 - 网络层全部静默
        return UpdateStatus(connected=False, error=str(exc)[:120])
    tag = (data.get("tag_name") or "").strip().lstrip("vV") or None
    return UpdateStatus(
        connected=True,
        latest=tag,
        url=data.get("html_url") or RELEASES_PAGE,
    )
