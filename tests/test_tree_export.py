"""tree_export：PowerShell tree 风格文本生成的纯逻辑测试。"""

from __future__ import annotations

import pytest

from app.core.tree_export import build_tree, wrap_markdown


@pytest.fixture
def sample_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_bytes(b"x" * 100)
    (tmp_path / "docs" / "b.txt").write_bytes(b"y" * 2048)
    (tmp_path / "root.txt").write_bytes(b"z")
    return tmp_path


def test_basic_structure(sample_tree):
    text, truncated = build_tree(sample_tree)
    assert not truncated
    lines = text.splitlines()
    assert lines[0] == sample_tree.name
    # 目录在前，文件在后；分支符号正确
    assert f"├── docs/" in text or "└── docs/" in text
    assert "│   ├── a.txt" in text or "│   └── a.txt" in text
    assert "└── root.txt" in text


def test_show_size(sample_tree):
    text, _ = build_tree(sample_tree, show_size=True)
    assert "root.txt (1 B)" in text
    assert "a.txt (100 B)" in text
    assert "b.txt (2.0 KB)" in text
    # 目录不带大小
    assert "docs/ (" not in text


def test_no_size_by_default(sample_tree):
    text, _ = build_tree(sample_tree)
    assert "(" not in text.split("docs/")[1].splitlines()[0]


def test_empty_dir(sample_tree):
    (sample_tree / "empty").mkdir()
    text, _ = build_tree(sample_tree)
    assert "empty/" in text


def test_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_tree(tmp_path / "nope")


def test_truncation(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_bytes(b"x")
    text, truncated = build_tree(tmp_path, max_entries=5)
    assert truncated
    assert "…" in text
    # 未截断时不出现省略行
    text2, truncated2 = build_tree(tmp_path, max_entries=100)
    assert not truncated2
    assert "…" not in text2


def test_wrap_markdown(sample_tree):
    text, _ = build_tree(sample_tree)
    md = wrap_markdown(text)
    assert md.startswith("```text\n")
    assert md.endswith("\n```")
    assert text in md
