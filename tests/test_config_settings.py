"""config：主题 / 更新源的简单文件持久化。"""

from __future__ import annotations

from pathlib import Path


def test_theme_roundtrip_and_defaults(tmp_path: Path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "cfg")
    assert config.theme() == "auto"  # 无文件 → 默认
    config.set_theme("dark")
    assert config.theme() == "dark"
    config.set_theme("bogus")  # 非法值回退 auto
    assert config.theme() == "auto"
    config.set_theme("")
    assert config.theme() == "auto"  # 清空 = 删文件


def test_update_url_roundtrip(tmp_path: Path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "cfg")
    assert config.update_url() == ""
    config.set_update_url("  https://example.com/x  ")
    assert config.update_url() == "https://example.com/x"  # 去空白
    config.set_update_url("")
    assert config.update_url() == ""
