"""Backward-compat alias for minxg package.

The package was renamed from py_workers to minxg in v0.0.2.
This stub keeps `import py_workers` working by re-exporting from minxg.
"""
import sys
import minxg
sys.modules["py_workers"] = minxg
from minxg import *  # noqa
