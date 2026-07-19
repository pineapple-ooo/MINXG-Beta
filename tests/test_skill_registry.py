"""tests/test_skill_registry.py — minxg/core_ops/skill_registry.py, the
engine behind `minxg skill` (install/search/new/publish/list).

Uses a real local git repo (created as a fixture, cloned via a real
`git clone` subprocess) to actually exercise the git-install code path
rather than mocking subprocess — this sandbox can reach github.com, but
pinning a test to a specific external repo's content is flaky by
nature, so a throwaway local repo gets the same code path with zero
external dependency.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from minxg.core_ops import skill_registry as sr


SAMPLE_SKILL_MD = """---
name: test-skill
description: A skill used only by the test suite.
version: 1.2.3
author: pytest
tags: [testing, example]
category: testing
---

# Test Skill

Step one. Step two.
"""


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Every test gets its own ~/.minxg so installs/lockfiles never
    touch the real thing or leak between tests."""
    home = tmp_path / "minxg_home"
    monkeypatch.setenv("MINXG_HOME", str(home))
    yield home


@pytest.fixture
def local_skill_dir(tmp_path):
    d = tmp_path / "authored_skill"
    d.mkdir()
    (d / "SKILL.md").write_text(SAMPLE_SKILL_MD, encoding="utf-8")
    return d


@pytest.fixture
def local_git_repo(tmp_path):
    """A real, throwaway git repo with a SKILL.md at its root, so the
    git-clone install path gets exercised for real."""
    repo = tmp_path / "skill_repo.git_src"
    repo.mkdir()
    (repo / "SKILL.md").write_text(SAMPLE_SKILL_MD, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env=env)
    return repo


class TestParseSkillMd:
    def test_parses_valid_frontmatter_and_body(self):
        m = sr.parse_skill_md(SAMPLE_SKILL_MD)
        assert m.name == "test-skill"
        assert m.version == "1.2.3"
        assert m.tags == ["testing", "example"]
        assert "Step one" in m.body

    def test_missing_frontmatter_block_raises(self):
        with pytest.raises(sr.SkillError, match="frontmatter"):
            sr.parse_skill_md("# just a heading, no frontmatter")

    def test_missing_required_field_raises(self):
        bad = "---\nname: x\n---\nbody"
        with pytest.raises(sr.SkillError, match="description"):
            sr.parse_skill_md(bad)

    def test_malformed_yaml_raises(self):
        bad = "---\nname: [unclosed\n---\nbody"
        with pytest.raises(sr.SkillError):
            sr.parse_skill_md(bad)

    def test_tags_as_comma_string_are_split(self):
        content = "---\nname: x\ndescription: d\ntags: a, b, c\n---\nbody"
        m = sr.parse_skill_md(content)
        assert m.tags == ["a", "b", "c"]


class TestFindSecrets:
    def test_detects_openai_style_key(self):
        assert sr.find_secrets("key = sk-abcdefghijklmnopqrstuvwx")

    def test_detects_aws_key(self):
        assert sr.find_secrets("AKIAABCDEFGHIJKLMNOP")

    def test_detects_private_key_block(self):
        assert sr.find_secrets("-----BEGIN RSA PRIVATE KEY-----\nMII...")

    def test_clean_content_has_no_hits(self):
        assert sr.find_secrets(SAMPLE_SKILL_MD) == []


class TestPreviewAndInstallFromLocalPath:
    def test_preview_does_not_write_anything(self, local_skill_dir):
        m = sr.preview_skill(str(local_skill_dir))
        assert m.name == "test-skill"
        assert not sr.user_skills_dir().exists()

    def test_install_requires_confirm(self, local_skill_dir):
        with pytest.raises(sr.SkillError, match="confirm"):
            sr.install_skill(str(local_skill_dir))

    def test_install_writes_skill_and_lockfile(self, local_skill_dir):
        m = sr.install_skill(str(local_skill_dir), confirm=True)
        assert m.path is not None
        installed_md = sr.user_skills_dir() / "test-skill" / "SKILL.md"
        assert installed_md.exists()
        assert "test-skill" in installed_md.read_text()

        installed = sr.list_installed()
        assert "test-skill" in installed
        assert installed["test-skill"]["version"] == "1.2.3"

    def test_install_rejects_bad_name_override(self, local_skill_dir):
        with pytest.raises(sr.SkillError, match="Invalid skill name"):
            sr.install_skill(str(local_skill_dir), confirm=True,
                              name_override="../../etc/passwd")

    def test_missing_skill_md_raises(self, tmp_path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        with pytest.raises(sr.SkillError, match="No SKILL.md"):
            sr.preview_skill(str(empty))


class TestInstallFromGit:
    def test_install_from_local_git_repo(self, local_git_repo):
        m = sr.install_skill(str(local_git_repo), confirm=True)
        assert m.name == "test-skill"
        installed_md = sr.user_skills_dir() / "test-skill" / "SKILL.md"
        assert installed_md.exists()
        installed = sr.list_installed()
        assert installed["test-skill"]["source"] == str(local_git_repo)

    def test_install_from_nonexistent_git_url_fails_cleanly(self):
        with pytest.raises(sr.SkillError):
            sr.install_skill("/definitely/not/a/real/repo/anywhere", confirm=True)


class TestRemove:
    def test_remove_deletes_files_and_lockfile_entry(self, local_skill_dir):
        sr.install_skill(str(local_skill_dir), confirm=True)
        assert sr.remove_skill("test-skill") is True
        assert not (sr.user_skills_dir() / "test-skill").exists()
        assert "test-skill" not in sr.list_installed()

    def test_remove_nonexistent_returns_false(self):
        assert sr.remove_skill("does-not-exist") is False


class TestCatalog:
    def test_default_catalog_loads_and_has_entries(self):
        entries = sr.load_catalog()
        assert len(entries) >= 1
        assert all("name" in e and "source" in e for e in entries)

    def test_search_catalog_by_query(self):
        results = sr.search_catalog("standup")
        assert any(e["name"] == "daily-standup-notes" for e in results)

    def test_search_catalog_by_tag(self):
        results = sr.search_catalog(tags=["development"])
        names = {e["name"] for e in results}
        assert "writing-minxg-skills" in names
        assert "daily-standup-notes" not in names

    def test_search_catalog_no_match(self):
        assert sr.search_catalog("xyz_no_such_skill_exists") == []

    def test_custom_catalog_file(self, tmp_path):
        custom = tmp_path / "my_catalog.json"
        custom.write_text(json.dumps([
            {"name": "custom-one", "description": "d", "source": "path:/x", "tags": []}
        ]))
        results = sr.search_catalog(source=str(custom))
        assert results[0]["name"] == "custom-one"

    def test_missing_catalog_file_raises(self):
        with pytest.raises(sr.SkillError, match="not found"):
            sr.load_catalog("/no/such/catalog.json")

    def test_install_from_catalog_name(self):
        """Installing by bare name should resolve through the default
        catalog to a bundled skill and actually install it."""
        m = sr.install_skill("daily-standup-notes", confirm=True)
        assert m.name == "daily-standup-notes"
        assert (sr.user_skills_dir() / "daily-standup-notes" / "SKILL.md").exists()


class TestListLocalSkills:
    def test_bundled_skills_are_discovered(self):
        skills = sr.list_local_skills(include_user=False)
        names = {s.name for s in skills}
        assert "writing-minxg-skills" in names
        assert "daily-standup-notes" in names

    def test_user_skills_are_discovered_after_install(self, local_skill_dir):
        sr.install_skill(str(local_skill_dir), confirm=True)
        skills = sr.list_local_skills(include_bundled=False)
        assert any(s.name == "test-skill" for s in skills)


class TestNewSkill:
    def test_creates_template_with_frontmatter(self):
        path = sr.new_skill("my-new-skill", description="does a thing", author="me")
        content = (path / "SKILL.md").read_text()
        m = sr.parse_skill_md(content)
        assert m.name == "my-new-skill"
        assert m.description == "does a thing"
        assert m.author == "me"

    def test_refuses_duplicate(self):
        sr.new_skill("dup-skill")
        with pytest.raises(sr.SkillError, match="already exists"):
            sr.new_skill("dup-skill")

    def test_refuses_invalid_name(self):
        with pytest.raises(sr.SkillError, match="Invalid skill name"):
            sr.new_skill("not a valid name!")


class TestValidateForPublish:
    def test_valid_skill_produces_catalog_entry(self):
        sr.new_skill("publishable", description="ready to go")
        # new_skill() leaves TODO placeholders; overwrite with real content
        skill_md = sr.user_skills_dir() / "publishable" / "SKILL.md"
        skill_md.write_text(SAMPLE_SKILL_MD.replace("test-skill", "publishable"))

        result = sr.validate_for_publish("publishable")
        assert result["catalog_entry"]["name"] == "publishable"
        assert result["catalog_entry"]["source"].startswith("path:")

    def test_refuses_to_publish_secrets(self):
        sr.new_skill("leaky-skill", description="oops")
        skill_md = sr.user_skills_dir() / "leaky-skill" / "SKILL.md"
        skill_md.write_text(
            SAMPLE_SKILL_MD.replace("test-skill", "leaky-skill")
            + "\nAPI key: sk-thisisatotallyrealkeylookingstring12345\n"
        )
        with pytest.raises(sr.SkillError, match="secret"):
            sr.validate_for_publish("leaky-skill")

    def test_nonexistent_skill_raises(self):
        with pytest.raises(sr.SkillError, match="No such local skill"):
            sr.validate_for_publish("never-created")
