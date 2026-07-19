"""
multiligua_cli/skill_cli.py — `minxg skill ...` subcommand dispatch.

Before this file existed, `minxg skill` wasn't registered with argparse
at all — despite being listed in `CORE_COMMANDS` and advertised in the
README (`minxg skill list`), running it just failed with
"invalid choice: 'skill'". The actual skill logic already existed
behind `tools/skill_manager_tool.py` (only reachable from inside a chat
session via the LLM's function-calling), and the DEFAULT_SKILLS_DIR it
pointed at didn't even exist in the shipped package. This file, plus
minxg/core_ops/skill_registry.py, is the real implementation both of
those gaps were pointing at.

Subcommands:

    minxg skill list [--category NAME] [--installed]
    minxg skill view <name>
    minxg skill search <query> [--tag TAG] [--catalog URL-or-path]
    minxg skill install <source> [--yes] [--as NAME]
    minxg skill new <name> [--description TEXT] [--author TEXT]
    minxg skill remove <name>
    minxg skill publish <name>
"""
from __future__ import annotations

import argparse
from typing import Optional

from minxg.core_ops import skill_registry as sr
from multiligua_cli.utils import (
    print_dim, print_error, print_info, print_success, print_warning,
)


def _show_help() -> int:
    print_info("minxg skill <action> — manage MINXG skills (markdown instruction bundles)")
    print()
    for line in (
        "  list [--category NAME] [--installed]   list available skills",
        "  view <name>                            show a skill's full content",
        "  search <query> [--tag T] [--catalog U]  search a skill catalog",
        "  install <source> [--yes] [--as NAME]    install from path / git URL / catalog name",
        "  new <name> [--description] [--author]   scaffold a new skill",
        "  remove <name>                           uninstall a user skill",
        "  publish <name>                          validate + print a catalog-entry snippet",
    ):
        print(line)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    category = getattr(args, "category", None)
    installed_only = getattr(args, "installed", False)

    if installed_only:
        installed = sr.list_installed()
        if not installed:
            print_info("No skills installed. Try `minxg skill search <topic>`.")
            return 0
        for name, meta in sorted(installed.items()):
            print_success(f"{name}  v{meta.get('version', '?')}  ({meta.get('source', '?')})")
        return 0

    skills = sr.list_local_skills()
    if category:
        skills = [s for s in skills if s.category == category]
    if not skills:
        print_info("No skills found. Bundled skills ship with MINXG; "
                    "install more with `minxg skill install <source>`.")
        return 0
    for s in sorted(skills, key=lambda s: (s.category, s.name)):
        print_success(f"[{s.category}] {s.name}  v{s.version} — {s.description}")
    return 0


def _cmd_view(args: argparse.Namespace) -> int:
    name = args.name
    for s in sr.list_local_skills():
        if s.name == name:
            print_info(f"{s.name}  v{s.version}  ({s.category})")
            print_dim(s.description)
            print()
            print(s.body)
            return 0
    print_error(f"Skill not found: {name}")
    return 1


def _cmd_search(args: argparse.Namespace) -> int:
    tags = [args.tag] if getattr(args, "tag", None) else None
    try:
        results = sr.search_catalog(
            query=getattr(args, "query", "") or "",
            tags=tags,
            source=getattr(args, "catalog", None),
        )
    except sr.SkillError as e:
        print_error(str(e))
        return 1
    if not results:
        print_info("No matching skills in the catalog.")
        return 0
    for e in results:
        tag_str = ", ".join(e.get("tags", []))
        print_success(f"{e['name']}  v{e.get('version', '?')} — {e.get('description', '')}"
                       + (f"  [{tag_str}]" if tag_str else ""))
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    source = args.source
    try:
        manifest = sr.preview_skill(source)
    except sr.SkillError as e:
        print_error(f"Could not preview {source!r}: {e}")
        return 1

    print_info(f"About to install: {manifest.name}  v{manifest.version}")
    print_dim(manifest.description)
    if manifest.author:
        print_dim(f"author: {manifest.author}")
    print()
    print(manifest.body[:2000] + ("..." if len(manifest.body) > 2000 else ""))
    print()

    if not getattr(args, "yes", False):
        print_warning(
            "Nothing has been written yet. Re-run with --yes to actually "
            "install this (skills are markdown instructions, not executable "
            "code, but review before installing anything from a source you "
            "don't control)."
        )
        return 0

    try:
        installed = sr.install_skill(
            source, confirm=True, name_override=getattr(args, "as_name", None),
        )
    except sr.SkillError as e:
        print_error(f"Install failed: {e}")
        return 1
    print_success(f"Installed {installed.name} -> {installed.path}")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    try:
        path = sr.new_skill(
            args.name,
            description=getattr(args, "description", "") or "",
            author=getattr(args, "author", "") or "",
        )
    except sr.SkillError as e:
        print_error(str(e))
        return 1
    print_success(f"Created {path / 'SKILL.md'}")
    print_info("Edit it, then `minxg skill view "
               f"{args.name}` to preview or `minxg skill publish {args.name}` when ready.")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    if sr.remove_skill(args.name):
        print_success(f"Removed {args.name}")
        return 0
    print_error(f"No installed skill named {args.name!r}")
    return 1


def _cmd_publish(args: argparse.Namespace) -> int:
    try:
        result = sr.validate_for_publish(args.name)
    except sr.SkillError as e:
        print_error(str(e))
        return 1
    print_success(f"{args.name} looks good to publish.")
    print_info("There's no hosted MINXG registry — a catalog is just a JSON "
               "file anyone can host. Add this entry to whatever catalog "
               "repo you're contributing to (update `source` to a real git "
               "URL or raw file URL once it's actually hosted somewhere):")
    print()
    import json as _json
    print(_json.dumps(result["catalog_entry"], indent=2))
    return 0


SUB_COMMANDS = {
    "list": _cmd_list,
    "view": _cmd_view,
    "search": _cmd_search,
    "install": _cmd_install,
    "new": _cmd_new,
    "remove": _cmd_remove,
    "publish": _cmd_publish,
}


def dispatch_skill_command(args: argparse.Namespace, action: Optional[str]) -> int:
    """Top-level dispatch used by main.py."""
    if not action:
        return _show_help()
    impl = SUB_COMMANDS.get(action)
    if impl is None:
        print_error(f"Unknown skill action: {action!r}")
        _show_help()
        return 2
    return impl(args)
