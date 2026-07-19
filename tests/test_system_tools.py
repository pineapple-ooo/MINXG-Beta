"""tests/test_system_tools.py — tools/system_tools.py, especially the
no-psutil fallback paths (POSIX /proc and Windows tasklist), which had
no test coverage before this pass and hid two real bugs:

  1. `Path` was used in the /proc fallback but never imported — a
     NameError waiting to happen on any box without psutil installed
     (exactly the box that fallback exists for).
  2. The fallback only ever tried /proc; on Windows it silently
     returned an empty process list instead of listing anything.
"""
from __future__ import annotations

import json
import subprocess

import pytest

import tools.system_tools as st


@pytest.fixture(autouse=True)
def _restore_state():
    """system_tools has a few module-level globals the tests below poke
    at directly; make sure nothing leaks between tests."""
    orig_has_psutil = st.HAS_PSUTIL
    orig_os_name = st.os.name
    orig_run = st.subprocess.run
    yield
    st.HAS_PSUTIL = orig_has_psutil
    st.os.name = orig_os_name
    st.subprocess.run = orig_run


class TestProcessListNoPsutil:
    def test_posix_fallback_reads_proc_without_crashing(self):
        st.HAS_PSUTIL = False
        st.os.name = "posix"
        result = json.loads(st._handle_process_list({"limit": 5}))
        assert "error" not in result
        assert isinstance(result["processes"], list)
        assert result["total"] >= 0

    def test_windows_fallback_parses_tasklist_csv(self):
        st.HAS_PSUTIL = False
        st.os.name = "nt"

        class _FakeResult:
            stdout = (
                '"notepad.exe","1234","Console","1","12,345 K"\r\n'
                '"cmd.exe","999","Console","1","3,000 K"\r\n'
            )
            stderr = ""

        st.subprocess.run = lambda *a, **kw: _FakeResult()

        result = json.loads(st._handle_process_list({"limit": 5, "sort_by": "memory"}))
        assert "error" not in result
        names = {p["name"] for p in result["processes"]}
        assert names == {"notepad.exe", "cmd.exe"}
        pids = {p["pid"] for p in result["processes"]}
        assert pids == {1234, 999}
        # sort_by=memory, descending
        assert result["processes"][0]["name"] == "notepad.exe"
        assert result["processes"][0]["memory"] == 12345

    def test_windows_fallback_survives_tasklist_missing(self):
        st.HAS_PSUTIL = False
        st.os.name = "nt"

        def _raise(*a, **kw):
            raise FileNotFoundError("tasklist not found")

        st.subprocess.run = _raise
        result = json.loads(st._handle_process_list({"limit": 5}))
        assert "error" not in result
        assert result["processes"] == []
        assert result["total"] == 0

    def test_sort_by_pid_works_in_fallback(self):
        st.HAS_PSUTIL = False
        st.os.name = "nt"

        class _FakeResult:
            stdout = (
                '"b.exe","200","Console","1","1 K"\r\n'
                '"a.exe","100","Console","1","1 K"\r\n'
            )
            stderr = ""

        st.subprocess.run = lambda *a, **kw: _FakeResult()
        result = json.loads(st._handle_process_list({"sort_by": "pid"}))
        assert [p["pid"] for p in result["processes"]] == [100, 200]


class TestProcessListWithPsutil:
    def test_uses_psutil_when_available(self):
        if not st.HAS_PSUTIL:
            pytest.skip("psutil not installed in this environment")
        result = json.loads(st._handle_process_list({"limit": 3}))
        assert "error" not in result
        assert isinstance(result["processes"], list)
