"""
MINXG Bootstrap - UTF-8 stdio initialization on Windows.

This module MUST be the very first import in any entry point (before even
standard library imports that touch stdin/stdout/stderr).

On POSIX systems this is a no-op. On Windows, it ensures that:
1. sys.stdin, sys.stdout, sys.stderr use UTF-8 text mode so that non-ASCII
   characters (Chinese, emoji, etc.) don't cause UnicodeEncodeError.
2. The console code page is set to UTF-8 (chcp 65001).

Rationale: Before this fix, running MINXG on a US-locale Windows machine
    UnicodeEncodeError: 'charmap' codec can't encode characters

This is applied before any other imports because even `import sys` triggers
attribute access on stdin which can fail if the stream is in the wrong mode.

References:
- PEP 538 (PYTHONCOERCECLOCALE) - CPython's built-in fix for POSIX locales
- PEP 540 (UTF-8 Mode) - CPython's built-in fix for Windows console
- https://github.com/multiligua/multiligua/issues/1
""""

import sys
import os


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes


    try:

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass


    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


    try:
        import locale

        locale.setlocale(locale.LC_ALL, ".UTF8")
    except Exception:
        pass


elif sys.platform != "win32":



    pass




_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
