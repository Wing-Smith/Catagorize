import time

from app.core.models import FileRecord, MatchSpec, Rule
from app.core.rules import resolve


def rec(name="a.txt", size=10, mtime=None, ext="txt"):
    return FileRecord(
        path_rel=name,
        size=size,
        mtime=mtime if mtime is not None else time.time(),
        ext=ext,
    )


def test_extensions_match():
    rule = Rule("docs", MatchSpec(extensions={"pdf", "txt"}), target_rel="docs")
    assert resolve(rec("x.txt"), [rule]) is not None
    assert resolve(rec("x.exe", ext="exe"), [rule]) is None


def test_size_and_age():
    now = time.time()
    rule = Rule(
        "old-big",
        MatchSpec(min_size=100, older_than_days=30),
        target_rel="old",
    )
    assert resolve(rec(size=200, mtime=now - 40 * 86400), [rule], now) is not None
    assert resolve(rec(size=50, mtime=now - 40 * 86400), [rule], now) is None
    assert resolve(rec(size=200, mtime=now - 5 * 86400), [rule], now) is None


def test_name_regex():
    rule = Rule("screenshot", MatchSpec(name_regex=r"^Screenshot"), target_rel="shots")
    assert resolve(rec("Screenshot_1.png", ext="png"), [rule]) is not None
    assert resolve(rec("photo.png", ext="png"), [rule]) is None


def test_priority_first_wins():
    low = Rule("low", MatchSpec(extensions={"txt"}), target_rel="low", priority=200)
    high = Rule("high", MatchSpec(extensions={"txt"}), target_rel="high", priority=10)
    hit = resolve(rec("x.txt"), [low, high])
    assert hit is not None and hit.target_rel == "high"


def test_disabled_rule_skipped():
    rule = Rule("off", MatchSpec(extensions={"txt"}), target_rel="x", enabled=False)
    assert resolve(rec("x.txt"), [rule]) is None


def test_empty_spec_validates_error():
    import pytest

    from app.core.errors import RuleError

    with pytest.raises(RuleError):
        Rule("bad", MatchSpec(), target_rel="x").validate()


def test_move_target_must_be_relative():
    import pytest

    from app.core.errors import RuleError

    with pytest.raises(RuleError):
        Rule("bad", MatchSpec(extensions={"txt"}), target_rel="../outside").validate()
    with pytest.raises(RuleError):
        Rule("bad", MatchSpec(extensions={"txt"}), target_rel="").validate()
