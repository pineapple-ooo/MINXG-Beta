"""Skill Manager Tool - View and manage skills."""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _load_skill_metadata(skill_path: Path) -> Optional[Dict]:
    """Load skill metadata from YAML frontmatter."""
    try:
        content = skill_path.read_text(encoding="utf-8")
        
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1))
            return frontmatter
        
        return {"name": skill_path.stem, "description": content[:200]}
    except Exception as e:
        logger.warning(f"Failed to load skill {skill_path}: {e}")
        return None


def _list_skills(skills_dir: Path = None) -> List[Dict]:
    """List all available skills."""
    if skills_dir is None:
        skills_dir = DEFAULT_SKILLS_DIR
    
    skills = []
    if not skills_dir.exists():
        return skills
    
    for category_dir in skills_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue
        
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                metadata = _load_skill_metadata(skill_md)
                if metadata:
                    metadata["category"] = category_dir.name
                    metadata["path"] = str(skill_dir)
                    skills.append(metadata)
    
    return skills


SKILLS_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "description": "Filter by category"},
    },
}

SKILL_VIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Skill name to view"},
        "category": {"type": "string", "description": "Skill category"},
    },
    "required": ["name"],
}

SKILLS_HUB_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "category": {"type": "string", "description": "Filter by category"},
        "limit": {"type": "integer", "description": "Max results", "default": 10},
    },
}


def _handle_skills_list(args: dict) -> str:
    """List all available skills."""
    category = args.get("category")
    skills = _list_skills()
    
    if category:
        skills = [s for s in skills if s.get("category") == category]
    
    return json.dumps({
        "skills": skills,
        "total": len(skills),
    })


def _handle_skill_view(args: dict) -> str:
    """View a specific skill."""
    name = args.get("name", "")
    category = args.get("category")
    
    if not name:
        return json.dumps({"error": "name is required"})
    
    if category:
        search_paths = [DEFAULT_SKILLS_DIR / category / name]
    else:
        search_paths = []
        for cat_dir in (DEFAULT_SKILLS_DIR.iterdir() if DEFAULT_SKILLS_DIR.exists() else []):
            if cat_dir.is_dir():
                search_paths.append(cat_dir / name)
    
    for skill_path in search_paths:
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            try:
                content = skill_md.read_text(encoding="utf-8")
                match = re.match(r'^---\n.*?\n---\n(.*)', content, re.DOTALL)
                body = match.group(1).strip() if match else content
                
                return json.dumps({
                    "name": name,
                    "category": category or skill_path.parent.name,
                    "content": body,
                    "found": True,
                })
            except Exception as e:
                return json.dumps({"error": f"Failed to read skill: {e}"})
    
    return json.dumps({
        "error": f"Skill not found: {name}",
        "found": False,
    })


def _handle_skills_hub(args: dict) -> str:
    """Search skills hub."""
    query = args.get("query", "").lower()
    category = args.get("category")
    limit = args.get("limit", 10)
    
    skills = _list_skills()
    
    if category:
        skills = [s for s in skills if s.get("category") == category]
    
    if query:
        skills = [
            s for s in skills
            if query in s.get("name", "").lower()
            or query in s.get("description", "").lower()
        ]
    
    return json.dumps({
        "skills": skills[:limit],
        "total": len(skills),
        "query": query,
    })


def _check_skills_reqs() -> bool:
    """Check if skills system is available."""
    return True


from tools.registry import registry

registry.register(
    name="skills_list",
    toolset="skills",
    schema=SKILLS_LIST_SCHEMA,
    handler=_handle_skills_list,
    check_fn=_check_skills_reqs,
    emoji="",
    max_result_size_chars=50000,
)

registry.register(
    name="skill_view",
    toolset="skills",
    schema=SKILL_VIEW_SCHEMA,
    handler=_handle_skill_view,
    check_fn=_check_skills_reqs,
    emoji="👁️",
    max_result_size_chars=100000,
)

registry.register(
    name="skills_hub",
    toolset="skills",
    schema=SKILLS_HUB_SCHEMA,
    handler=_handle_skills_hub,
    check_fn=_check_skills_reqs,
    emoji="",
    max_result_size_chars=50000,
)
