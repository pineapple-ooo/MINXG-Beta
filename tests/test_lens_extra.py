"""Extra coverage for minxg.lens — glossary, projector, and export."""
import pytest
from minxg.lens import (
    Glossary,
    Entry,
    load_default_glossary,
    Lens,
    LensConfig,
    export,
)


def test_lens_module_imports_cleanly():
    import importlib
    import minxg.lens
    importlib.reload(minxg.lens)


def test_glossary_translates_known_term_monad():
    g = Glossary()
    g.add(Entry(term="monad", translations={"en": "monad", "zh": "单子", "ja": "モナド"}))
    assert g.translate("monad", "zh") == "单子"
    assert g.translate("monad", "ja") == "モナド"
    assert g.translate("monad", "en") == "monad"


def test_glossary_returns_term_unchanged_for_unknown():
    g = load_default_glossary()
    assert g.translate("nonexistent_xyz", "zh") == "nonexistent_xyz"


def test_projector_renders_one_file_per_language(tmp_path):
    batch = Lens(LensConfig(
        title_prefix="Extra",
        languages=("en", "zh", "ja"),
        output_dir=tmp_path,
    )).render_doc(
        "",
        {"heading": "Overview", "body": "The driver advances the state."},
    )
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "en.md" in files
    assert "zh.md" in files
    assert "ja.md" in files
    assert "GLOSSARY.md" in files
    assert len(batch.files) == 3


def test_lens_translates_english_words_in_chinese_context():
    batch = Lens(LensConfig(title_prefix="Test", languages=("zh",))).render_doc(
        "",
        {"heading": "operator", "body": "The driver uses the bridge to call the worker."},
    )
    text = batch.files["zh.md"]
    assert "算子" in text
    assert "驱动引擎" in text
    assert "桥接" in text
    assert "工作器" in text


def test_export_function_returns_batch_with_expected_keys():
    batch = export([
        {"heading": "Intro", "body": "Hello world"},
        {"heading": "Details", "body": "More text here"},
    ])
    assert isinstance(batch, dict) or hasattr(batch, "files")
    assert "en.md" in batch.files
    assert "zh.md" in batch.files


def test_lens_config_default_languages():
    cfg = LensConfig()
    assert cfg.languages == ("en", "zh", "zh-TW", "ja", "ko")
    assert cfg.output_dir is None
    assert cfg.title_prefix == ""
    assert cfg.glossary is None
