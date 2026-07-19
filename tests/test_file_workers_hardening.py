"""tests/test_file_workers_hardening.py — the MCP-surface file workers
(minxg/workers/file/file_workers.py) previously had none of the safety
guards the chat-agent surface (tools/file_tools.py) had. This locks in
the fix: blocked-device-path rejection on every write-capable worker,
plus the read worker refusing to slurp huge/binary files.
"""
from __future__ import annotations

import pytest

from minxg.workers.file.file_workers import (
    FileReadWorker, FileWriteWorker, FileCopyWorker,
    FileMoveWorker, FileDeleteWorker,
)


class TestFileReadWorkerHardening:
    def test_rejects_blocked_device_path(self):
        result = FileReadWorker().execute(path="/dev/zero")
        assert "error" in result
        assert "blocked" in result["error"].lower()

    def test_rejects_binary_file(self, tmp_path):
        f = tmp_path / "img.bin"
        f.write_bytes(b"\x00\x01\x02" * 500)
        result = FileReadWorker().execute(path=str(f))
        assert "error" in result
        assert "binary" in result["error"].lower()

    def test_rejects_oversized_file(self, tmp_path, monkeypatch):
        f = tmp_path / "big.txt"
        f.write_text("x" * 1000)
        monkeypatch.setattr(
            "minxg.core_ops.file_safety.MAX_READABLE_BYTES", 10
        )
        result = FileReadWorker().execute(path=str(f))
        assert "error" in result
        assert "too large" in result["error"].lower()

    def test_reads_normal_text_file(self, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("line1\nline2\nline3\n")
        result = FileReadWorker().execute(path=str(f))
        assert "error" not in result
        assert result["lines"] == 3


class TestFileWriteWorkerHardening:
    def test_rejects_blocked_device_path(self):
        result = FileWriteWorker().execute(path="/dev/null", content="x")
        # /dev/null itself isn't in the blocklist (writing to it is
        # harmless/standard practice), but the guard must still fire
        # for the genuinely dangerous ones:
        result2 = FileWriteWorker().execute(path="/dev/zero", content="x")
        assert "error" in result2
        assert "blocked" in result2["error"].lower()

    def test_writes_normal_file(self, tmp_path):
        f = tmp_path / "out.txt"
        result = FileWriteWorker().execute(path=str(f), content="hello")
        assert "error" not in result
        assert f.read_text() == "hello"


class TestFileCopyMoveDeleteHardening:
    def test_copy_rejects_blocked_src(self, tmp_path):
        result = FileCopyWorker().execute(src="/dev/zero", dst=str(tmp_path / "out"))
        assert "error" in result

    def test_move_rejects_blocked_src(self, tmp_path):
        result = FileMoveWorker().execute(src="/dev/zero", dst=str(tmp_path / "out"))
        assert "error" in result

    def test_delete_rejects_blocked_path(self):
        result = FileDeleteWorker().execute(path="/dev/zero")
        assert "error" in result

    def test_copy_move_delete_still_work_normally(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data")
        dst = tmp_path / "b.txt"

        copy_result = FileCopyWorker().execute(src=str(src), dst=str(dst))
        assert "error" not in copy_result
        assert dst.exists()

        dst2 = tmp_path / "c.txt"
        move_result = FileMoveWorker().execute(src=str(dst), dst=str(dst2))
        assert "error" not in move_result
        assert dst2.exists() and not dst.exists()

        delete_result = FileDeleteWorker().execute(path=str(dst2))
        assert "error" not in delete_result
        assert not dst2.exists()
