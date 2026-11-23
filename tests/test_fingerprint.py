from pathlib import Path

from app.core.fingerprint import file_digest, text_digest


def test_file_digest_stable(tmp_path: Path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello" * 1000)
    assert file_digest(f) == file_digest(f)
    assert len(file_digest(f)) == 64


def test_file_digest_content_sensitive(tmp_path: Path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"same-name-different-content-1")
    b.write_bytes(b"same-name-different-content-2")
    assert file_digest(a) != file_digest(b)


def test_text_digest():
    assert text_digest("cat") == text_digest("cat")
    assert text_digest("cat") != text_digest("dog")
