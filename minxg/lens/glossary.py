"""Glossary: term -> per-language word.

Loads bundled curated translations for the top terms MINXG uses. The
glossary grows: callers can add entries at runtime via `glossary.add`.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple


@dataclass
class Entry:
    term: str
    translations: Dict[str, str] = field(default_factory=dict)


class Glossary:
    def __init__(self) -> None:
        self._by_term: Dict[str, Dict[str, str]] = {}

    def add(self, entry: Entry) -> None:
        self._by_term[entry.term] = dict(entry.translations)

    def translate(self, term: str, language: str) -> str:
        terms = self._by_term.get(term)
        if not terms:
            return term
        return terms.get(language, terms.get("en", term))

    def terms(self) -> Iterable[str]:
        return self._by_term.keys()


DEFAULT_ENTRIES = [
    ("operator",
     {"en": "operator", "zh": "算子", "zh-TW": "算子", "ja": "演算子", "ko": "연산자"}),
    ("driver",
     {"en": "driver", "zh": "驱动引擎", "zh-TW": "驅動引擎", "ja": "駆動エンジン", "ko": "드라이버"}),
    ("bridge",
     {"en": "bridge", "zh": "桥接", "zh-TW": "橋接", "ja": "ブリッジ", "ko": "브리지"}),
    ("registry",
     {"en": "registry", "zh": "注册中心", "zh-TW": "註冊中心", "ja": "レジストリ", "ko": "레지스트리"}),
    ("cell",
     {"en": "cell", "zh": "细胞单元", "zh-TW": "細胞單元", "ja": "セル", "ko": "셀"}),
    ("port",
     {"en": "port", "zh": "端口", "zh-TW": "埠", "ja": "ポート", "ko": "포트"}),
    ("field",
     {"en": "field", "zh": "向量场", "zh-TW": "向量場", "ja": "場", "ko": "장"}),
    ("state",
     {"en": "state", "zh": "状态", "zh-TW": "狀態", "ja": "状態", "ko": "상태"}),
    ("drift",
     {"en": "drift", "zh": "漂移", "zh-TW": "漂移", "ja": "ドリフト", "ko": "드리프트"}),
    ("blade",
     {"en": "blade", "zh": "叶", "zh-TW": "葉", "ja": "ブレード", "ko": "블레이드"}),
    ("curvature",
     {"en": "curvature", "zh": "曲率", "zh-TW": "曲率", "ja": "曲率", "ko": "곡률"}),
    ("worker",
     {"en": "worker", "zh": "工作器", "zh-TW": "工作器", "ja": "ワーカー", "ko": "워커"}),
    ("twin",
     {"en": "twin", "zh": "孪生", "zh-TW": "孿生", "ja": "ツイン", "ko": "트윈"}),
    ("evolution",
     {"en": "evolution", "zh": "自演进", "zh-TW": "自演進", "ja": "自己進化", "ko": "자기진화"}),
]


def load_default_glossary() -> Glossary:
    g = Glossary()
    for term, translations in DEFAULT_ENTRIES:
        g.add(Entry(term=term, translations=translations))
    return g
