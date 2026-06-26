"""Projector — turn operator-graph + docstring into per-language docs."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

from .glossary import Glossary, load_default_glossary


@dataclass
class LensConfig:
    languages: tuple = ("en", "zh", "zh-TW", "ja", "ko")
    title_prefix: str = ""
    output_dir: Optional[Path] = None
    glossary: Optional[Glossary] = None

    def resolved_glossary(self) -> Glossary:
        return self.glossary if self.glossary is not None else load_default_glossary()


@dataclass
class LensBatch:
    files: Dict[str, str] = field(default_factory=dict)
    glossary_dump: str = ""


class Lens:
    def __init__(self, config: LensConfig) -> None:
        self._config = config

    def render_doc(self, source: str, *sections: Dict[str, str]) -> LensBatch:
        files: Dict[str, str] = {}
        glossary = self._config.resolved_glossary()
        for lang in self._config.languages:
            body = self._render_sections(sections, lang, glossary)
            files[f"{lang}.md"] = body
        batch = LensBatch(files=files, glossary_dump=self._dump_glossary(glossary))
        if self._config.output_dir is not None:
            self._write(batch)
        return batch

    def export_graph(self, *graph_descriptions: str) -> LensBatch:
        sections = []
        for i, description in enumerate(graph_descriptions):
            sections.append({"heading": f"Graph {i + 1}", "body": description})
        return self.render_doc("", *sections)

    def _render_sections(self, sections: Iterable[Dict[str, str]], lang: str, glossary: Glossary) -> str:
        out = [f"# {self._config.title_prefix}" if self._config.title_prefix else "# Lens export"]
        out.append("")
        out.append(self._intl("This document was reverse-projected by minxg.lens.", lang))
        out.append("")
        for section in sections:
            heading_raw = section.get("heading", "")
            body = section.get("body", "")
            heading = self._translate(heading_raw, lang, glossary)
            out.append(f"## {heading}")
            out.append("")
            for paragraph in re.split(r"\n\n+", body.strip()):
                if paragraph:
                    out.append(self._translate(paragraph, lang, glossary))
                    out.append("")
        return "\n".join(out).rstrip() + "\n"

    def _translate(self, text: str, lang: str, glossary: Glossary) -> str:
        if lang == "en" or not text:
            return text
        return re.sub(r"[A-Za-z_][A-Za-z0-9_]+", lambda m: glossary.translate(m.group(0), lang), text)

    def _intl(self, text: str, lang: str) -> str:
        if lang == "zh":
            return "本文件由 minxg.lens 反向导出。"
        if lang == "zh-TW":
            return "本檔由 minxg.lens 反向匯出。"
        if lang == "ja":
            return "このドキュメントは minxg.lens によって逆投影されました。"
        if lang == "ko":
            return "이 문서는 minxg.lens 로 역방향 사출되었습니다."
        return text

    def _dump_glossary(self, glossary: Glossary) -> str:
        header = ["# Glossary", "", "| Term | en | zh | zh-TW | ja | ko |"]
        header.append("|---|---|---|---|---|---|")
        for term in sorted(glossary.terms()):
            row = [term]
            for lang in ("en", "zh", "zh-TW", "ja", "ko"):
                row.append(glossary.translate(term, lang))
            header.append("| " + " | ".join(row) + " |")
        return "\n".join(header) + "\n"

    def _write(self, batch: LensBatch) -> None:
        out = Path(self._config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for name, body in batch.files.items():
            (out / name).write_text(body, encoding="utf-8")
        (out / "GLOSSARY.md").write_text(batch.glossary_dump, encoding="utf-8")


def export(
    sections: Iterable[Dict[str, str]],
    config: LensConfig = None,
) -> LensBatch:
    return Lens(config or LensConfig()).render_doc("", *sections)
