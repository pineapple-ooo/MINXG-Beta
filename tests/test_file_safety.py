"""tests/test_file_safety.py — minxg/core_ops/file_safety.py, the shared
guard now used by both tools/file_tools.py (chat-agent) and
minxg/workers/file/file_workers.py (MCP surface). Before this module
existed the MCP surface had none of these guards at all.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from minxg.core_ops.file_safety import (
    is_blocked_path, is_binary_file, check_readable_text_file,
    BLOCKED_DEVICE_PATHS, MAX_READABLE_BYTES,
)


class TestIsBlockedPath:
    @pytest.mark.parametrize("dev", sorted(BLOCKED_DEVICE_PATHS))
    def test_every_listed_device_path_is_blocked(self, dev):
        assert is_blocked_path(dev) is True

    def test_ordinary_file_is_not_blocked(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("hello")
        assert is_blocked_path(str(f)) is False

    def test_nonexistent_path_is_not_blocked(self, tmp_path):
        assert is_blocked_path(str(tmp_path / "does_not_exist.txt")) is False


class TestIsBinaryFile:
    def test_text_file_is_not_binary(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("just some plain text\nwith a few lines\n")
        assert is_binary_file(f) is False

    def test_null_byte_marks_binary(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"hello\x00world")
        assert is_binary_file(f) is True

    def test_mostly_nonprintable_marks_binary(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(bytes(range(200, 256)) * 10)
        assert is_binary_file(f) is True

    def test_empty_file_is_not_binary(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert is_binary_file(f) is False

    def test_missing_file_is_treated_as_binary(self, tmp_path):
        assert is_binary_file(tmp_path / "nope.bin") is True


class TestCheckReadableTextFile:
    def test_ok_for_small_text_file(self, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("fine")
        ok, err = check_readable_text_file(f)
        assert ok is True
        assert err == ""

    def test_rejects_oversized_file(self, tmp_path, monkeypatch):
        f = tmp_path / "big.txt"
        f.write_text("x")
        monkeypatch.setattr(
            "minxg.core_ops.file_safety.MAX_READABLE_BYTES", 0
        )
        ok, err = check_readable_text_file(f)
        assert ok is False
        assert "too large" in err.lower()

    def test_rejects_binary_file(self, tmp_path):
        f = tmp_path / "img.bin"
        f.write_bytes(b"\x00\x01\x02\x03" * 100)
        ok, err = check_readable_text_file(f)
        assert ok is False
        assert "binary" in err.lower()
