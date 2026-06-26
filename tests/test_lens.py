"""Tests for minxg.lens reverse doc projector."""
import pytest
from minxg.lens import (
    Glossary, Entry, load_default_glossary,
    Lens, LensConfig, export,
)


def test_glossary_translates_known_term():
    g = load_default_glossary()
    assert g.translate("operator", "en") == "operator"
    assert g.translate("operator", "zh") == "算子"
    assert g.translate("operator", "ja") == "演算子"


def test_glossary_returns_term_when_unknown():
    g = Glossary()
    assert g.translate("banana", "zh") == "banana"


def test_glossary_supports_runtime_add():
    g = Glossary()
    g.add(Entry(term="kernel", translations={"en": "kernel", "zh": "核心"}))
    assert g.translate("kernel", "zh") == "核心"


def test_lens_renders_one_file_per_language():
    batch = Lens(LensConfig(title_prefix="Test")).render_doc(
        "",
        {"heading": "Overview", "body": "The driver advances the state."},
        {"heading": "Usage", "body": "Workers register cells in the registry."},
    )
    assert set(batch.files) == {"en.md", "zh.md", "zh-TW.md", "ja.md", "ko.md"}


def test_lens_translates_en_words_in_chinese():
    batch = Lens(LensConfig(title_prefix="Test", languages=("zh",))).render_doc(
        "",
        {"heading": "operator", "body": "The driver advances the state."},
    )
    assert "算子" in batch.files["zh.md"]


def test_lens_writes_files_when_output_dir_given(tmp_path):
    batches = Lens(LensConfig(
        title_prefix="X",
        languages=("en", "zh"),
        output_dir=tmp_path,
    )).render_doc(
        "",
        {"heading": "operator", "body": "body"},
    )
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "en.md" in files
    assert "zh.md" in files
    assert "GLOSSARY.md" in files


def test_export_function_returns_batch():
    batch = export([
        {"heading": "driver", "body": "advances the state"},
    ])
    assert "en.md" in batch.files
