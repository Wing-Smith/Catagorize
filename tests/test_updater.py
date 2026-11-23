"""updater：版本号解析与比较（网络层不测，离线可跑）。"""

from __future__ import annotations

from app.core import updater
from app.core.config import APP_VERSION
from app.core.updater import UpdateStatus, _parse_ver, is_newer, is_older


def test_parse_ver():
    assert _parse_ver("v1.2.3") == (1, 2, 3)
    assert _parse_ver("1.2") == (1, 2)
    assert _parse_ver("0.1.0") == (0, 1, 0)
    assert _parse_ver("no numbers") == (0,)


def test_is_newer_against_current():
    assert is_newer(f"{_bump(APP_VERSION)}")
    assert not is_newer(APP_VERSION)
    assert not is_newer("0.0.1")


def test_is_older_flags_dev_build():
    assert is_older("0.0.1")  # 本地 0.1.0 > 0.0.1
    assert not is_older("999.0.0")


def _bump(v: str) -> str:
    nums = [int(n) for n in v.split(".")]
    nums[-1] += 1
    return ".".join(str(n) for n in nums)


def test_update_status_defaults():
    s = UpdateStatus(connected=True, latest="1.0.0")
    assert s.current == APP_VERSION
    assert s.url  # 发布页默认有值
    s2 = UpdateStatus(connected=False, error="boom")
    assert not s2.connected
    assert s2.latest is None


def test_api_url_builtin_by_default():
    import app.core.updater as upd

    monkey_none = lambda: ""  # noqa: E731
    old = upd._update_url
    upd._update_url = monkey_none
    try:
        assert upd.api_url() == upd.DEFAULT_UPDATE_API
    finally:
        upd._update_url = old


def test_api_url_custom_override():
    import app.core.updater as upd

    old = upd._update_url
    upd._update_url = lambda: "https://example.com/custom-api"
    try:
        assert upd.api_url() == "https://example.com/custom-api"
    finally:
        upd._update_url = old
