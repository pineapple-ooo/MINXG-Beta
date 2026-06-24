"""minxg.lens — Reverse docstring export.

Implements the "reverse" of docstrings. Given a Python file or a parsed
`OperatorGraph`, the lens produces:

    * source stub files in target languages (zh-CN, zh-TW, ja, ko, en, es)
    * glossary entries (term -> canonical translation) cross-linked
    * a derived `docs/<lang>/<filename>.md` rendering for each language

Each language export is a *projection* — a deterministic transformation
of the source so that humans can re-import the doc-set into their own
editing tooling.
"""
from .glossary import Glossary, Entry, load_default_glossary
from .projector import Lens, LensConfig, export

__all__ = [
    "Glossary", "Entry", "load_default_glossary",
    "Lens", "LensConfig", "export",
]
