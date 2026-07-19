"""tests/test_extensions.py — extension system smoke tests.

Covers:
  1. Extension discovery (builtin + user)
  2. Built-in opt-in (no ADB/ROOT auto-detect at module load)
  3. Enable / disable state-file persistence
  4. package_cli sub-command surface
  5. Loader reload idempotence

Run with:  python -m pytest tests/test_extensions.py -v
"""
import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))


class TestExtensionDiscovery(unittest.TestCase):
    """Extension discovery on disk."""

    @classmethod
    def setUpClass(cls):
        for k in list(sys.modules):
            if k.startswith("extensions"):
                del sys.modules[k]
        from extensions.loader import discover_extensions
        cls.extensions = discover_extensions()

    def test_at_least_four_extensions_found(self):
        """At least hello, files, adb, root are discovered."""
        self.assertGreaterEqual(
            len(self.extensions), 4,
            f"only {len(self.extensions)} extensions found",
        )

    def test_builtin_extensions_present(self):
        """All four shipped built-ins are discoverable."""
        names = {e.name for e in self.extensions}
        required = {"hello", "minxg-files", "minxg-adb", "minxg-root"}
        missing = required - names
        self.assertEqual(missing, set(), f"missing builtins: {missing}")

    def test_all_extensions_have_names(self):
        """Every discovered extension carries an EXTENSION_NAME."""
        for ext in self.extensions:
            self.assertTrue(ext.name, f"extension missing name (path={ext.path})")

    def test_extensions_have_handler(self):
        """Every discovered extension exposes handle_command."""
        for ext in self.extensions:
            self.assertTrue(
                hasattr(ext.module, "handle_command"),
                f"{ext.name}: no handle_command",
            )


class TestBuiltinOptIn(unittest.TestCase):
    """Built-in extensions must be opt-in; the runner never auto-detects."""

    def _find(self, name):
        from extensions.loader import discover_extensions
        exts = discover_extensions()
        return next((e for e in exts if e.name == name), None)

    def test_adb_ext_opt_in(self):
        adb = self._find("minxg-adb")
        if adb is None:
            return
        self.assertFalse(adb.enabled, "minxg-adb is on by default; should be opt-in")
        self.assertFalse(hasattr(adb.module, "ADB_AVAILABLE"),
                         "minxg-adb still exposes ADB_AVAILABLE at module load")
        self.assertTrue(callable(getattr(adb.module, "_adb_available", None)),
                        "minxg-adb should expose _adb_available() callable")

    def test_root_ext_opt_in(self):
        root = self._find("minxg-root")
        if root is None:
            return
        self.assertFalse(root.enabled, "minxg-root is on by default; should be opt-in")
        self.assertFalse(hasattr(root.module, "ROOT_AVAILABLE"),
                         "minxg-root still exposes ROOT_AVAILABLE at module load")
        self.assertTrue(callable(getattr(root.module, "_root_available", None)),
                        "minxg-root should expose _root_available() callable")

    def test_files_ext_opt_in(self):
        files = self._find("minxg-files")
        if files is None:
            return
        # v0.19.x — files ext is ON by default so the AI can read
        # the file system out of the box. ADB/ROOT stay opt-in.
        self.assertTrue(files.enabled,
                         "minxg-files should be ON by default since v0.19.x")

    def test_builtin_descriptions_english_only(self):
        """Built-in extension descriptions must not contain Chinese chars."""
        import re as _re
        from extensions.loader import discover_extensions
        for ext in discover_extensions():
            desc = ext.description or ""
            matches = _re.findall(r"[\u4e00-\u9fff]", desc)
            self.assertFalse(
                matches,
                f"{ext.name} description has Chinese: {desc!r}",
            )

    def test_builtin_opt_in_via_state_file(self):
        """set_extension_enabled persists opt-in state to extensions/user/."""
        from extensions.loader import (
            set_extension_enabled, reload_extensions, _user_state_dir,
        )
        prev = False
        for ext in reload_extensions():
            if ext.name == "minxg-adb":
                prev = ext.enabled
                break
        state_file = _user_state_dir() / "minxg-adb.state"
        had_previous = state_file.exists()
        previous_contents = (
            state_file.read_text(encoding="utf-8") if had_previous else None
        )
        try:
            set_extension_enabled("minxg-adb", True)
            exts = reload_extensions()
            adb = next((e for e in exts if e.name == "minxg-adb"), None)
            self.assertIsNotNone(adb)
            if adb is not None:
                self.assertTrue(adb.enabled, "opt-in toggle did not stick")
        finally:
            set_extension_enabled("minxg-adb", prev)
            if not had_previous and state_file.exists():
                state_file.unlink()
            elif had_previous and previous_contents is not None:
                state_file.write_text(previous_contents, encoding="utf-8")


class TestPackageCli(unittest.TestCase):
    """Smoke tests for the package_cli surface."""

    def test_package_cli_has_all_subcommands(self):
        from extensions.package_cli import (
            cmd_list, cmd_available, cmd_add, cmd_remove,
            cmd_info, cmd_enable, cmd_disable,
        )
        for fn in (cmd_list, cmd_available, cmd_add, cmd_remove,
                   cmd_info, cmd_enable, cmd_disable):
            self.assertTrue(callable(fn), f"{fn.__name__} is not callable")

    def test_builtin_optional_set_complete(self):
        from extensions.package_cli import BUILTIN_OPTIONAL
        self.assertIn("minxg-adb", BUILTIN_OPTIONAL)
        self.assertIn("minxg-root", BUILTIN_OPTIONAL)
        self.assertIn("minxg-files", BUILTIN_OPTIONAL)
        import re as _re
        for slug, (_mod, desc) in BUILTIN_OPTIONAL.items():
            self.assertFalse(
                _re.findall(r"[\u4e00-\u9fff]", desc),
                f"{slug} desc has Chinese: {desc!r}",
            )


class TestLoaderReload(unittest.TestCase):
    """Hot-reload of the extension loader."""

    def test_reload_returns_extensions(self):
        for k in list(sys.modules):
            if k.startswith("extensions"):
                del sys.modules[k]
        from extensions.loader import reload_extensions
        exts = reload_extensions()
        self.assertGreaterEqual(
            len(exts), 4,
            f"reload returned only {len(exts)} extensions",
        )

    def test_reload_is_idempotent(self):
        exts1 = TestExtensionDiscovery.extensions
        name_set1 = {e.name for e in exts1}
        for k in list(sys.modules):
            if k.startswith("extensions._dynamic"):
                del sys.modules[k]
        from extensions.loader import discover_extensions
        exts2 = discover_extensions()
        name_set2 = {e.name for e in exts2}
        self.assertEqual(
            name_set1, name_set2,
            f"extension sets diverge: {name_set1 ^ name_set2}",
        )


class TestPlatformDetection(unittest.TestCase):
    """platform.system() returns Android on Termux, Linux elsewhere."""

    def test_platform_detect(self):
        import platform as _p
        plat = _p.system()
        self.assertIn(
            plat, ["Android", "Linux", "Darwin", "Windows"],
            f"unknown platform: {plat}",
        )

    def test_android_detection(self):
        import importlib
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        plat = __import__("platform").system()
        if os.path.exists("/data/data/com.termux"):
            self.assertEqual(
                plat, "Android",
                f"Termux env but platform returned: {plat}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
