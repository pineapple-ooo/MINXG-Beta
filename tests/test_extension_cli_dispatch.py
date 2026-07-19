"""tests/test_extension_cli_dispatch.py — extensions/__init__.py and
extensions/package_cli.py CLI wiring.

Covers three real, chained bugs found while building the multiagent
extension, all in the "an enabled extension's CLI command is
reachable" path — before this pass, NONE of files/adb/root/hello's
`minxg <verb>` commands worked at all (`register_cli_extensions`/
`dispatch_extension` were never called from main.py), and even after
wiring that up, `cmd in ext_map` never matched anything because the
map was keyed by `EXTENSION_NAME` (e.g. "minxg-files") while every
extension's `register_cli` registers a *different*, short argparse
verb ("files"). On top of that, `minxg ext enable/disable` mutated an
in-memory attribute that a fresh CLI process (i.e. every real
invocation) never saw, and `minxg ext list` read that same
never-persisted attribute directly instead of the state-file-aware
`ext.enabled`. Each of the four is covered here independently.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest


EXT_NAME = "minxg-test-cli-ext"
EXT_VERB = "testcliext"  # deliberately different from EXT_NAME, like the real builtins

EXT_SOURCE = '''
EXTENSION_NAME = "{name}"
EXTENSION_DESCRIPTION = "throwaway test extension for CLI dispatch"
EXTENSION_VERSION = "0.0.1"
EXTENSION_ENABLED = False


def handle_command(args) -> int:
    print("dispatched:" + getattr(args, "command", "?"))
    return 0


def register_cli(subparsers) -> None:
    subparsers.add_parser("{verb}", help="test verb")
'''.format(name=EXT_NAME, verb=EXT_VERB)


def _user_dir() -> Path:
    from extensions.loader import _user_state_dir
    return _user_state_dir()


@pytest.fixture
def temp_extension():
    ext_file = _user_dir() / f"{EXT_NAME}.py"
    state_file = _user_dir() / f"{EXT_NAME}.state"
    ext_file.write_text(EXT_SOURCE, encoding="utf-8")
    state_file.unlink(missing_ok=True)

    for k in list(sys.modules):
        # NOT "extensions" itself: popping the top-level package here used
        # to cause a module-identity split for any *other* test that had
        # already done `import extensions.builtin.<x>` normally (see
        # tests/test_multiagent_ext.py) -- re-importing "extensions" fresh
        # doesn't reattach already-cached submodules to the new object.
        if k.startswith("extensions._dynamic"):
            sys.modules.pop(k, None)
    import extensions.loader as loader_mod
    loader_mod._cached = None

    yield

    ext_file.unlink(missing_ok=True)
    state_file.unlink(missing_ok=True)
    loader_mod._cached = None


def _reload():
    import extensions.loader as loader_mod
    loader_mod._cached = None


class TestRegisterCliExtensions_VerbKeying:
    """The register_cli_extensions() rewrite: ext_map keyed by the
    actual registered argparse verb, not EXTENSION_NAME."""

    def test_disabled_extension_registers_nothing(self, temp_extension):
        from extensions import register_cli_extensions
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        ext_map = register_cli_extensions(sub)
        assert EXT_VERB not in ext_map
        assert EXT_VERB not in sub.choices

    def test_enabled_extension_keyed_by_actual_verb_not_name(self, temp_extension):
        from extensions.loader import set_extension_enabled
        set_extension_enabled(EXT_NAME, True)
        _reload()

        from extensions import register_cli_extensions
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        ext_map = register_cli_extensions(sub)

        assert EXT_VERB in ext_map, f"expected key {EXT_VERB!r}, got {list(ext_map)!r}"
        assert EXT_NAME not in ext_map  # the old (wrong) keying
        assert EXT_VERB in sub.choices  # argparse actually knows the verb now

    def test_parser_actually_accepts_the_verb(self, temp_extension):
        from extensions.loader import set_extension_enabled
        set_extension_enabled(EXT_NAME, True)
        _reload()

        from extensions import register_cli_extensions, dispatch_extension
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        ext_map = register_cli_extensions(sub)

        args = parser.parse_args([EXT_VERB])
        assert args.command == EXT_VERB
        rc = dispatch_extension(ext_map, args.command, args)
        assert rc == 0


class TestEnableDisablePersistence:
    """minxg ext enable/disable must survive a fresh process (i.e. a
    fresh discover_extensions() call), not just mutate the in-memory
    module object of the process that ran the command."""

    def test_enable_persists_across_a_fresh_discovery(self, temp_extension):
        from extensions.package_cli import cmd_enable
        from extensions.loader import discover_extensions

        cmd_enable(argparse.Namespace(name=EXT_NAME))

        _reload()
        fresh = discover_extensions()
        match = [e for e in fresh if e.name == EXT_NAME]
        assert match and match[0].enabled is True

    def test_disable_persists_across_a_fresh_discovery(self, temp_extension):
        from extensions.package_cli import cmd_enable, cmd_disable
        from extensions.loader import discover_extensions

        cmd_enable(argparse.Namespace(name=EXT_NAME))
        cmd_disable(argparse.Namespace(name=EXT_NAME))

        _reload()
        fresh = discover_extensions()
        match = [e for e in fresh if e.name == EXT_NAME]
        assert match and match[0].enabled is False

    def test_state_file_actually_written(self, temp_extension):
        from extensions.package_cli import cmd_enable
        cmd_enable(argparse.Namespace(name=EXT_NAME))
        state_file = _user_dir() / f"{EXT_NAME}.state"
        assert state_file.exists()
        assert json.loads(state_file.read_text())["enabled"] is True


class TestExtListReflectsRealState:
    def test_list_shows_enabled_after_cmd_enable(self, temp_extension, capsys):
        from extensions.package_cli import cmd_enable, cmd_list

        cmd_enable(argparse.Namespace(name=EXT_NAME))
        _reload()
        cmd_list(argparse.Namespace())
        out = capsys.readouterr().out
        line = next(l for l in out.splitlines()
                    if EXT_NAME in l and ("[enabled]" in l or "[disabled]" in l))
        assert "[enabled]" in line
        assert "[disabled]" not in line

    def test_list_shows_disabled_by_default(self, temp_extension, capsys):
        from extensions.package_cli import cmd_list
        _reload()
        cmd_list(argparse.Namespace())
        out = capsys.readouterr().out
        line = next(l for l in out.splitlines() if EXT_NAME in l)
        assert "[disabled]" in line
