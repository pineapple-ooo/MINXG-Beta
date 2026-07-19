"""minxg/core_ops/skill_registry.py — the MINXG skill ecosystem engine.

Shared by both the LLM-facing tool surface (tools/skill_manager_tool.py)
and the CLI surface (multiligua_cli/skill_cli.py) — one engine, two
entry points, same pattern as minxg/core_ops/file_safety.py.

Design notes, since this is the direct answer to "ecosystem" being the
one place MINXG was honestly behind OpenClaw's ClawHub:

  - Skills are markdown + YAML frontmatter, **not executable code**.
    That's a real, structural safety advantage over a code-plugin
    marketplace (OpenClaw's ClawHub had 230+ malicious skills uploaded
    in its first week per public research) — a bad skill can feed the
    model misleading instructions, but it can't run arbitrary code on
    install the way a bad extension can. Extensions (tools/*.py-style
    executable plugins) already require an explicit local
    `minxg ext add` and are a separate, more sensitive system on
    purpose; this registry does not touch that.
  - No hosted registry exists (nobody's running one), so "catalog" is
    just a JSON file — local, a raw GitHub URL, or anything else
    reachable over HTTP. Anyone can self-host a catalog with nothing
    more than a git repo, matching the local-first shape of the rest
    of the project. `default_catalog.json` ships one to start from.
  - Every install is content-hashed into a local lockfile
    (~/.minxg/skills/installed.json) so `minxg skill list --installed`
    can show provenance, and re-installing/updating is detectable.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover — yaml is a core dependency, but
    yaml = None       # keep this module importable even if it's ever missing


# ──────────────────────────────────────────────────────── paths / config

def minxg_home() -> Path:
    import os
    return Path(os.environ.get("MINXG_HOME", str(Path.home() / ".minxg")))


def user_skills_dir() -> Path:
    """Where `minxg skill install`/`new` write to."""
    return minxg_home() / "skills" / "user"


def bundled_skills_dir() -> Path:
    """MINXG's own shipped skills (read-only, ships with the package)."""
    return Path(__file__).resolve().parent.parent.parent / "skills"


def lockfile_path() -> Path:
    return minxg_home() / "skills" / "installed.json"


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "skills" / "catalog.json"


REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
MAX_SKILL_MD_BYTES = 512 * 1024  # 512KB — a skill is instructions, not a payload

# Rough courtesy check for `minxg skill publish` — catches the most
# common "oops, my API key is in here" accidents. Not a substitute for
# actually reading what you're about to publish.
_SECRET_LOOKING_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"ghp_[a-zA-Z0-9]{30,}"),
)


class SkillError(Exception):
    """Raised for validation / install failures with a user-facing message."""


@dataclass
class SkillManifest:
    name: str
    description: str
    version: str = "0.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = "user"
    path: Optional[str] = None
    body: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "version": self.version, "author": self.author,
            "tags": self.tags, "category": self.category,
            "path": self.path,
        }


# ──────────────────────────────────────────────────────── parsing

def parse_skill_md(content: str) -> SkillManifest:
    """Parse a SKILL.md's YAML frontmatter + body into a SkillManifest.
    Raises SkillError if required fields are missing or frontmatter is
    malformed — deliberately strict here since this is the boundary
    where third-party content enters the system."""
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        raise SkillError(
            "SKILL.md must start with a YAML frontmatter block "
            "(---\\nname: ...\\n---\\n)"
        )
    if yaml is None:
        raise SkillError("PyYAML is required to parse skill frontmatter")
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise SkillError(f"Invalid YAML frontmatter: {e}")
    if not isinstance(frontmatter, dict):
        raise SkillError("Frontmatter must be a YAML mapping")

    missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if not frontmatter.get(f)]
    if missing:
        raise SkillError(f"SKILL.md frontmatter missing required field(s): {', '.join(missing)}")

    tags = frontmatter.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return SkillManifest(
        name=str(frontmatter["name"]),
        description=str(frontmatter["description"]),
        version=str(frontmatter.get("version") or "0.0.0"),
        author=str(frontmatter.get("author") or ""),
        tags=[str(t) for t in tags],
        category=str(frontmatter.get("category") or "user"),
        body=match.group(2).strip(),
    )


def find_secrets(content: str) -> List[str]:
    """Return a list of pattern descriptions that matched, if any."""
    hits = []
    for pattern in _SECRET_LOOKING_PATTERNS:
        if pattern.search(content):
            hits.append(pattern.pattern)
    return hits


# ──────────────────────────────────────────────────────── discovery (local)

def _scan_dir_for_skills(root: Path, category_hint: Optional[str] = None) -> List[SkillManifest]:
    found = []
    if not root.exists():
        return found
    # Accept both `root/SKILL.md` (single skill dir) and
    # `root/<category>/<name>/SKILL.md` (bundled/community layout).
    direct = root / "SKILL.md"
    if direct.exists():
        try:
            m = parse_skill_md(direct.read_text(encoding="utf-8"))
            m.path = str(root)
            m.category = category_hint or m.category
            found.append(m)
        except SkillError:
            pass
        return found

    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if skill_md.exists():
            try:
                m = parse_skill_md(skill_md.read_text(encoding="utf-8"))
                m.path = str(entry)
                m.category = category_hint or entry.parent.name
                found.append(m)
            except SkillError:
                continue
        else:
            # one level of category nesting: root/<category>/<name>/SKILL.md
            found.extend(_scan_dir_for_skills(entry, category_hint=entry.name))
    return found


def list_local_skills(include_bundled: bool = True, include_user: bool = True) -> List[SkillManifest]:
    skills: List[SkillManifest] = []
    if include_bundled:
        skills.extend(_scan_dir_for_skills(bundled_skills_dir()))
    if include_user:
        skills.extend(_scan_dir_for_skills(user_skills_dir()))
    return skills


# ──────────────────────────────────────────────────────── catalog (remote index)

def load_catalog(source: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load a catalog: a JSON list of {name, description, version, source,
    tags}. `source` may be a local path, an http(s) URL, or None (use the
    bundled default catalog)."""
    if source is None:
        source = str(default_catalog_path())

    if source.startswith("http://") or source.startswith("https://"):
        import urllib.request
        try:
            with urllib.request.urlopen(source, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise SkillError(f"Failed to fetch catalog {source}: {e}")
    else:
        p = Path(source)
        if not p.exists():
            raise SkillError(f"Catalog file not found: {source}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SkillError(f"Catalog {source} is not valid JSON: {e}")

    if not isinstance(data, list):
        raise SkillError("Catalog must be a JSON list of skill entries")
    return data


def search_catalog(query: str = "", tags: Optional[List[str]] = None,
                    source: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    entries = load_catalog(source)
    query = query.lower().strip()
    results = []
    for e in entries:
        if query and query not in str(e.get("name", "")).lower() \
                and query not in str(e.get("description", "")).lower():
            continue
        if tags and not (set(tags) & set(e.get("tags", []))):
            continue
        results.append(e)
    return results[:limit]


# ──────────────────────────────────────────────────────── lockfile

def _load_lockfile() -> Dict[str, Any]:
    lf = lockfile_path()
    if not lf.exists():
        return {"installed": {}}
    try:
        return json.loads(lf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"installed": {}}


def _save_lockfile(data: Dict[str, Any]) -> None:
    lf = lockfile_path()
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def list_installed() -> Dict[str, Any]:
    return _load_lockfile()["installed"]


def _record_install(name: str, manifest: SkillManifest, source: str, content_hash: str) -> None:
    data = _load_lockfile()
    data["installed"][name] = {
        "version": manifest.version,
        "source": source,
        "installed_at": time.time(),
        "content_hash": content_hash,
        "path": manifest.path,
    }
    _save_lockfile(data)


def remove_skill(name: str) -> bool:
    """Remove an installed (user) skill. Returns True if something was removed."""
    data = _load_lockfile()
    entry = data["installed"].pop(name, None)
    _save_lockfile(data)
    target = user_skills_dir() / name
    removed_dir = False
    if target.exists():
        shutil.rmtree(target)
        removed_dir = True
    return bool(entry) or removed_dir


# ──────────────────────────────────────────────────────── install

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _fetch_url(url: str, timeout: int = 15) -> str:
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        raw = resp.read()
    if len(raw) > MAX_SKILL_MD_BYTES:
        raise SkillError(f"SKILL.md at {url} exceeds {MAX_SKILL_MD_BYTES} bytes")
    return raw.decode("utf-8")


def _git_clone_shallow(url: str, dest: Path, subdir: str = "") -> Path:
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        raise SkillError("`git` is not installed — required to install from a git URL")
    except subprocess.TimeoutExpired:
        raise SkillError(f"git clone of {url} timed out")
    if result.returncode != 0:
        raise SkillError(f"git clone failed: {result.stderr.strip()[:500]}")
    return dest / subdir if subdir else dest


def resolve_source(source: str) -> str:
    """Resolve a catalog name to its source URL/path, or pass through
    anything that already looks like a path/URL."""
    if source.startswith("bundled:"):
        return str(bundled_skills_dir() / source[len("bundled:"):])
    if source.startswith(("http://", "https://", "git+", "/", "./", "../")) \
            or (len(source) > 1 and source[1] == ":"):  # C:\... on Windows
        return source
    try:
        entries = load_catalog()
    except SkillError:
        return source
    for e in entries:
        if e.get("name") == source:
            resolved = e["source"]
            return str(bundled_skills_dir() / resolved[len("bundled:"):]) \
                if resolved.startswith("bundled:") else resolved
    return source  # not a catalog name either; let install_skill() report the real error


def preview_skill(source: str) -> SkillManifest:
    """Fetch + parse a skill without installing it — used to show the
    person what they're about to install before they confirm."""
    resolved = resolve_source(source)

    if resolved.startswith("git+") or (
        resolved.startswith(("http://", "https://")) and resolved.rstrip("/").endswith(".git")
    ):
        url = resolved[4:] if resolved.startswith("git+") else resolved
        url, _, subdir = url.partition("#")
        with tempfile.TemporaryDirectory(prefix="minxg-skill-") as tmp:
            skill_dir = _git_clone_shallow(url, Path(tmp) / "clone", subdir)
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                raise SkillError(f"No SKILL.md found in {url}" + (f"#{subdir}" if subdir else ""))
            manifest = parse_skill_md(skill_md.read_text(encoding="utf-8"))
    elif resolved.startswith(("http://", "https://")):
        content = _fetch_url(resolved)
        manifest = parse_skill_md(content)
    else:
        p = Path(resolved).expanduser()
        skill_md = p / "SKILL.md" if p.is_dir() else p
        if not skill_md.exists():
            raise SkillError(f"No SKILL.md found at {resolved}")
        manifest = parse_skill_md(skill_md.read_text(encoding="utf-8"))

    manifest.path = None  # not installed yet
    return manifest


def install_skill(source: str, *, name_override: Optional[str] = None,
                   confirm: bool = False) -> SkillManifest:
    """Install a skill from a local path, a raw SKILL.md URL, a git URL
    (optionally `#subdir` for a monorepo), or a name in the default
    catalog. Requires `confirm=True` to actually write files — callers
    (CLI/tool handlers) are expected to preview the skill and get
    explicit user confirmation first; this keeps that policy in one
    place instead of trusting every call site to remember it."""
    if not confirm:
        raise SkillError(
            "install_skill() requires confirm=True — preview the skill "
            "with preview_skill() and get explicit user confirmation first"
        )

    manifest = preview_skill(source)
    name = name_override or manifest.name
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise SkillError(f"Invalid skill name {name!r} — use letters, digits, - and _ only")

    dest = user_skills_dir() / name
    dest.mkdir(parents=True, exist_ok=True)
    skill_md_path = dest / "SKILL.md"
    skill_md_path.write_text(
        f"---\nname: {manifest.name}\ndescription: {manifest.description}\n"
        f"version: {manifest.version}\nauthor: {manifest.author}\n"
        f"tags: {json.dumps(manifest.tags)}\ncategory: {manifest.category}\n---\n\n"
        f"{manifest.body}\n",
        encoding="utf-8",
    )
    manifest.path = str(dest)
    _record_install(name, manifest, source, _content_hash(manifest.body))
    return manifest


# ──────────────────────────────────────────────────────── scaffolding

SKILL_TEMPLATE = """---
name: {name}
description: {description}
version: 0.1.0
author: {author}
tags: []
category: user
---

# {title}

Describe what this skill teaches the agent to do, step by step. Skills
are instructions read by the model, not executed code — write them the
way you'd brief a capable colleague who's never done this task before.

## When to use this

## Steps

1.
2.
3.

## Notes / gotchas
"""


def new_skill(name: str, description: str = "", author: str = "") -> Path:
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise SkillError(f"Invalid skill name {name!r} — use letters, digits, - and _ only")
    dest = user_skills_dir() / name
    if dest.exists():
        raise SkillError(f"Skill {name!r} already exists at {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    content = SKILL_TEMPLATE.format(
        name=name,
        description=description or f"TODO: describe {name}",
        author=author,
        title=name.replace("-", " ").replace("_", " ").title(),
    )
    (dest / "SKILL.md").write_text(content, encoding="utf-8")
    return dest


# ──────────────────────────────────────────────────────── publish

def validate_for_publish(name: str) -> Dict[str, Any]:
    """Validate a locally-authored skill and produce a catalog-entry
    snippet the person can PR into a community catalog repo. Does not
    upload anything anywhere — there's no hosted registry to upload to;
    see the module docstring for why that's a deliberate design choice,
    not a missing feature."""
    skill_dir = user_skills_dir() / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SkillError(f"No such local skill: {name} (looked in {skill_dir})")

    content = skill_md.read_text(encoding="utf-8")
    manifest = parse_skill_md(content)  # raises SkillError if malformed
    secrets = find_secrets(content)
    if secrets:
        raise SkillError(
            "Refusing to prepare this for publishing: content matches "
            f"{len(secrets)} secret-looking pattern(s). Remove any real "
            "credentials/keys before publishing."
        )
    if len(content.encode("utf-8")) > MAX_SKILL_MD_BYTES:
        raise SkillError(f"SKILL.md is over {MAX_SKILL_MD_BYTES} bytes")

    catalog_entry = {
        "name": manifest.name,
        "description": manifest.description,
        "version": manifest.version,
        "author": manifest.author,
        "tags": manifest.tags,
        "source": f"path:{skill_dir}",  # the author should replace this
                                          # with a real git URL when they
                                          # actually host it somewhere
    }
    return {"manifest": manifest.to_dict(), "catalog_entry": catalog_entry}
