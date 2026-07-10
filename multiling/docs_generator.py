"""
MINXG Documentation Generator
"""
import os, sys, json, time, ast, re, inspect, hashlib, textwrap, datetime
import logging, threading, asyncio, pathlib, gzip, base64
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader, select_autoescape
from markdown import markdown
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docs_gen")

DOCS_VERSION = "0.17.0"
BUILD_DATE = "2026-06-01"
OUTPUT_DIR = Path("docs") if Path("docs").exists() else Path(".")
STATIC_DIR = OUTPUT_DIR / "static"
TEMPLATES_DIR = Path("templates") if Path("templates").exists() else OUTPUT_DIR

DOC_CATEGORIES = {
    "http_api": {"icon": "🌐", "title": "HTTP API", "order": 3},
}

@dataclass
class DocPage:
    page_id: str
    title: str
    category: str
    content: str
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    author: str = "MINXG Team"
    last_updated: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    version: str = DOCS_VERSION
    order: int = 0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolDoc:
    name: str
    description: str
    category: str
    parameters: List[Dict]
    returns: str
    examples: List[str]
    notes: List[str] = field(default_factory=list)
    deprecated: bool = False
    since_version: str = "1.0.0"

@dataclass
class PlatformDoc:
    platform_id: str
    name: str
    icon: str
    description: str
    config_keys: List[str]
    setup_steps: List[str]
    features: List[str]
    limitations: List[str]
    examples: List[str]

class CodeParser:
    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path(".")
        self._tool_docs: Dict[str, ToolDoc] = {}
        self._parsed_files: Set[str] = set()
    
    def parse_tools_file(self, filepath: Path) -> List[ToolDoc]:
        if not filepath.exists():
            return []
        try:
            content = filepath.read_text(encoding="utf-8")
            tree = ast.parse(content)
            tools = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "name":
                                    if isinstance(item.value, ast.Constant):
                                        tool_name = item.value.value
                                        tools.append(self._extract_tool_doc(node, tool_name))
            return [t for t in tools if t is not None]
        except Exception as e:
            return []
    
    def _extract_tool_doc(self, class_node: ast.ClassDef, tool_name: str) -> Optional[ToolDoc]:
        try:
            description = ""
            parameters = []
            returns = "str"
            examples = []
            notes = []
            category = "general"
            docstring = ast.get_docstring(class_node)
            if docstring:
                description = docstring.strip()
            for item in class_node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "description" and isinstance(item.value, ast.Constant):
                                description = item.value.value
                            elif target.id == "category" and isinstance(item.value, ast.Constant):
                                category = item.value.value
            for item in class_node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == "run":
                    returns = self._extract_return_type(item)
                    parameters = self._extract_parameters(item)
            return ToolDoc(name=tool_name, description=description, category=category,
                          parameters=parameters, returns=returns, examples=examples, notes=notes)
        except Exception as e:
            return None
    
    def _extract_return_type(self, func_node: ast.AsyncFunctionDef) -> str:
        if func_node.returns:
            try:
                return ast.unparse(func_node.returns)
            except Exception:
                pass
        return "str"
    
    def _extract_parameters(self, func_node: ast.AsyncFunctionDef) -> List[Dict]:
        params = []
        for arg in func_node.args.args:
            if arg.arg == "self":
                continue
            param_info = {"name": arg.arg, "type": "any", "required": True, "default": None}
            if arg.annotation:
                try:
                    param_info["type"] = ast.unparse(arg.annotation)
                except Exception as e:
                    pass
            params.append(param_info)
        defaults = func_node.args.defaults
        offset = len(params) - len(defaults)
        for i, default in enumerate(defaults):
            if i + offset < len(params):
                try:
                    params[i + offset]["default"] = ast.literal_eval(default)
                    params[i + offset]["required"] = False
                except Exception:
                    params[i + offset]["default"] = str(default)
                    params[i + offset]["required"] = False
        return params
    
    def parse_config_file(self, filepath: Path) -> Dict:
        if not filepath.exists():
            return {}
        try:
            content = filepath.read_text(encoding="utf-8")
            if filepath.suffix in (".yaml", ".yml"):
                return yaml.safe_load(content) or {}
            elif filepath.suffix == ".json":
                return json.loads(content)
            elif filepath.name == ".env":
                config = {}
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")
                return config
        except Exception as e:
            pass
        return {}
    
    def parse_readme(self, filepath: Path) -> str:
        if not filepath.exists():
            return ""
        try:
            content = filepath.read_text(encoding="utf-8")
            return markdown(content)
        except Exception as e:
            return ""

class TemplateEngine:
    def __init__(self, templates_dir: Path = None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True, lstrip_blocks=True
        )
        self._env.filters['markdown'] = self._markdown_filter
        self._env.filters['tojson'] = self._json_filter
        self._env.filters['truncate'] = self._truncate_filter
        self._create_default_templates()
    
    def _create_default_templates(self):
        layout_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}MINXG Documentation{% endblock %}</title>
    <meta name="version" content="{{ version }}">
    <link rel="stylesheet" href="{{ static_path }}style.css">
    <link rel="icon" type="image/svg+xml" href="{{ static_path }}favicon.svg">
</head>
<body>
    <div class="docs-container">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h1>MINXG</h1>
                <div class="version">v{{ version }}</div>
            </div>
            <nav class="nav">
                {% for cat_id, cat in categories.items() %}
                <div class="nav-section">
                    <div class="nav-section-title">{{ cat.icon }} {{ cat.title }}</div>
                    {% for page in pages %}
                    {% if page.category == cat_id %}
                    <a href="{{ page.page_id }}.html" class="nav-item {% if page.page_id == current_page %}active{% endif %}">
                        {{ page.title }}
                    </a>
                    {% endif %}
                    {% endfor %}
                </div>
                {% endfor %}
            </nav>
        </aside>
        <main class="content">
            <div class="mobile-overlay" id="mobileOverlay" onclick="closeSidebar()"></div>
            <div class="content-header">
                <h1>{% block page_title %}{% endblock %}</h1>
                <div class="breadcrumb">{% block breadcrumb %}{% endblock %}</div>
            </div>
            <div class="markdown-body">{% block content %}{% endblock %}</div>
            <footer>
                <p>MINXG Documentation | Generated by Python Docs Generator</p>
                <p>Build: {{ build_date }} | <a href="https://github.com/minxg/minxg" target="_blank">GitHub</a></p>
            </footer>
        </main>
    </div>
    <script src="{{ static_path }}main.js"></script>
</body>
</html>"""
        (self.templates_dir / "layout.html").write_text(layout_template, encoding="utf-8")
        
        index_template = """{% extends "layout.html" %}
{% block content %}
<div class="hero">
    <div class="feature-grid">
    </div>
</div>
<pre><code>pip install -r requirements.txt
python main.py reset
python main.py start</code></pre>
<pre><code>┌─────────────────────────────────────────────────────────┐
│                    Orchestration Layer                   │
└─────────────────┬───────────────────────────────────────┘
                  │ IPC / RPC
        ┌─────────┼─────────┬─────────────┐
        ↓         ↓         ↓             ↓
┌────────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐
│   C#       │ │  Java   │ │ LuaJIT   │ │   Shell    │
└────────────┘ └─────────┘ └──────────┘ └────────────┘</code></pre>
{% endblock %}"""
        (self.templates_dir / "index.html").write_text(index_template, encoding="utf-8")
    
    def _markdown_filter(self, text: str) -> str:
        try:
            return markdown(text, extensions=['fenced_code', 'tables', 'toc'])
        except Exception:
            return text
    
    def _json_filter(self, obj) -> str:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    
    def _truncate_filter(self, text: str, length: int = 100) -> str:
        if len(text) <= length:
            return text
        return text[:length-3] + "..."
    
    def render(self, template_name: str, context: Dict) -> str:
        try:
            template = self._env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            pass
    def render_string(self, template_string: str, context: Dict) -> str:
        try:
            template = self._env.from_string(template_string)
            return template.render(**context)
        except Exception as e:
            pass
class StaticAssetGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.static_dir = output_dir / "static"
        self.static_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_css(self):
        css_content = """/* MINXG Documentation Styles */
:root {
    --primary: #4f46e5; --primary-dark: #4338ca; --bg-primary: #ffffff; --bg-secondary: #f9fafb;
    --bg-tertiary: #f3f4f6; --text-primary: #111827; --text-secondary: #374151;
    --text-muted: #6b7280; --border: #e5e7eb; --success: #10b981; --warning: #f59e0b;
    --error: #ef4444; --info: #3b82f6; --sidebar-width: 280px; --header-height: 60px;
    --shadow: 0 1px 3px rgba(0,0,0,0.1); --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg-primary); color: var(--text-primary); line-height: 1.6;
}
.docs-container { display: flex; min-height: 100vh; }
.sidebar {
    width: var(--sidebar-width); background: var(--bg-secondary); border-right: 1px solid var(--border);
    position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; padding: 1.5rem 1rem; z-index: 100;
    transition: transform 0.3s ease;
}
.sidebar-header { padding-bottom: 1rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border); }
.sidebar-header h1 { font-size: 1.5rem; font-weight: 700; color: var(--text-primary); }
.sidebar-header .version { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }
.nav-section { margin-bottom: 1.5rem; }
.nav-section-title {
    font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--text-muted); margin-bottom: 0.75rem; padding-left: 0.5rem;
}
.nav-item {
    display: block; padding: 0.5rem 0.75rem; margin-bottom: 0.25rem; color: var(--text-secondary);
    text-decoration: none; font-size: 0.875rem; font-weight: 500; border-radius: 0.5rem;
    transition: all 0.2s ease;
}
.nav-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.nav-item.active { background: #eef2ff; color: var(--primary); font-weight: 600; }
.content { flex: 1; margin-left: var(--sidebar-width); padding: 2rem 2.5rem; max-width: 1200px; min-width: 0; }
.content-header { margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.content-header h1 { font-size: 2rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem; }
.breadcrumb { font-size: 0.875rem; color: var(--text-muted); }
.breadcrumb a { color: var(--primary); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.markdown-body { font-size: 1rem; }
.markdown-body h1 { font-size: 1.875rem; font-weight: 700; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--border); }
.markdown-body h2 { font-size: 1.5rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; }
.markdown-body h3 { font-size: 1.25rem; font-weight: 600; margin-top: 1.25rem; margin-bottom: 0.5rem; }
.markdown-body p { margin-bottom: 1rem; }
.markdown-body ul, .markdown-body ol { margin-bottom: 1rem; padding-left: 1.5rem; }
.markdown-body li { margin-bottom: 0.25rem; }
.markdown-body pre { background: var(--bg-tertiary); border-radius: 0.5rem; padding: 1rem; margin: 1rem 0; overflow-x: auto; border: 1px solid var(--border); }
.markdown-body code { font-family: 'SF Mono', Monaco, monospace; font-size: 0.875em; background: var(--bg-tertiary); padding: 0.2rem 0.4rem; border-radius: 0.25rem; }
.markdown-body pre code { background: transparent; padding: 0; }
.markdown-body a { color: var(--primary); text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.markdown-body th, .markdown-body td { border: 1px solid var(--border); padding: 0.5rem 0.75rem; text-align: left; }
.markdown-body th { background: var(--bg-secondary); font-weight: 600; }
.hero { text-align: center; padding: 2rem 0; }
.hero h2 { font-size: 1.75rem; margin-bottom: 0.5rem; }
.hero p { color: var(--text-muted); font-size: 1.125rem; }
.feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin: 2rem 0; }
.feature-card {
    background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 0.75rem;
    padding: 1.5rem; text-align: center; transition: transform 0.2s, box-shadow 0.2s;
}
.feature-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.feature-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.feature-card h3 { font-size: 1.125rem; margin-bottom: 0.5rem; }
.feature-card p { color: var(--text-muted); font-size: 0.875rem; }
.menu-toggle { display: none; position: fixed; top: 1rem; left: 1rem; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.5rem 0.75rem; font-size: 1rem; cursor: pointer; z-index: 101; box-shadow: var(--shadow); }
.mobile-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 99; }
@media (max-width: 768px) {
    .sidebar { transform: translateX(-100%); width: 280px; }
    .sidebar.open { transform: translateX(0); }
    .content { margin-left: 0; padding: 1rem 1.25rem; }
    .menu-toggle { display: block; }
    .mobile-overlay.active { display: block; }
}
footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-align: center; font-size: 0.875rem; color: var(--text-muted); }
footer a { color: var(--primary); }
"""
        (self.static_dir / "style.css").write_text(css_content, encoding="utf-8")
        
        js_content = """// MINXG Documentation JavaScript
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
}
function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
}
document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    if (window.innerWidth <= 768 && !sidebar.contains(e.target) && !e.target.classList.contains('menu-toggle')) {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }
});
function initSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    searchInput.addEventListener('input', function(e) {
        const query = e.target.value.toLowerCase();
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(query) ? 'block' : 'none';
        });
    });
}
function highlightCode() {
    document.querySelectorAll('pre code').forEach(block => {
        block.classList.add('language-python');
    });
}
document.addEventListener('DOMContentLoaded', function() {
    initSearch();
    highlightCode();
});
function addCopyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.onclick = function() {
            const code = pre.querySelector('code').textContent;
            navigator.clipboard.writeText(code);
        };
        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}
"""
        (self.static_dir / "main.js").write_text(js_content, encoding="utf-8")
        
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🤖</text></svg>"""
        (self.static_dir / "favicon.svg").write_text(svg_content, encoding="utf-8")
    
    def generate_search_index(self, pages: List[DocPage]) -> str:
        index = []
        for page in pages:
            index.append({
                "id": page.page_id, "title": page.title, "category": page.category,
                "content": page.content[:500], "keywords": page.keywords
            })
        return json.dumps(index, ensure_ascii=False, indent=2)

class DocsBuilder:
    def __init__(self, base_path: Path = None, output_dir: Path = None):
        self.base_path = base_path or Path(".")
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.parser = CodeParser(self.base_path)
        self.template_engine = TemplateEngine(self.output_dir)
        self.static_gen = StaticAssetGenerator(self.output_dir)
        self._pages: Dict[str, DocPage] = {}
        self._tool_docs: Dict[str, ToolDoc] = {}
        self._platform_docs: Dict[str, PlatformDoc] = {}
    
    def discover_pages(self) -> List[DocPage]:
        pages = []
        tools_file = self.base_path / "tools.py"
        if tools_file.exists():
            tool_docs = self.parser.parse_tools_file(tools_file)
            self._tool_docs = {t.name: t for t in tool_docs}
            categories = {}
            for tool in tool_docs:
                cat = tool.category
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(tool)
            for cat, tools in categories.items():
                page = DocPage(
                    content=self._generate_tools_page(cat, tools),
                    order=DOC_CATEGORIES.get("tools", {}).get("order", 5)
                )
                pages.append(page)
        
        config_file = self.base_path / "config.py"
        if config_file.exists():
            config_data = self.parser.parse_config_file(config_file)
            if config_data:
                page = DocPage(
                    content=self._generate_config_page(config_data),
                    order=DOC_CATEGORIES.get("configuration", {}).get("order", 7)
                )
                pages.append(page)
        
        readme = self.base_path / "README.md"
        if readme.exists():
            content = self.parser.parse_readme(readme)
            page = DocPage(
                order=DOC_CATEGORIES.get("getting_started", {}).get("order", 1)
            )
            pages.append(page)
        
        platforms = self._generate_platform_docs()
        pages.extend(platforms)
        
        security_page = self._generate_security_page()
        if security_page:
            pages.append(security_page)
        
        troubleshooting_page = self._generate_troubleshooting_page()
        if troubleshooting_page:
            pages.append(troubleshooting_page)
        
        self._pages = {p.page_id: p for p in pages}
        return pages
    
    def _generate_tools_page(self, category: str, tools: List[ToolDoc]) -> str:
        for tool in tools:
            lines.append(f"<h3>{tool.name}</h3>")
            lines.append(f"<p>{tool.description}</p>")
            if tool.parameters:
                for param in tool.parameters:
                    pass
                lines.append("</table>")
            if tool.examples:
                for ex in tool.examples:
                    lines.append(f"<pre><code>{ex}</code></pre>")
            if tool.notes:
                for note in tool.notes:
                    lines.append(f"<li>{note}</li>")
                lines.append("</ul>")
        return "\n".join(lines)
    
    def _generate_config_page(self, config_data: Dict) -> str:
        for section, values in config_data.items():
            if section.startswith("_"):
                continue
            for key, value in values.items():
                if isinstance(value, dict):
                    val_type = value.get("type", "string")
                    default = value.get("default", "")
                    desc = value.get("help", "")
                else:
                    val_type = type(value).__name__
                    default = str(value)
                    desc = ""
                lines.append(f"<tr><td>{key}</td><td>{val_type}</td><td>{default}</td><td>{desc}</td></tr>")
            lines.append("</table>")
        return "\n".join(lines)
    
    def _generate_platform_docs(self) -> List[DocPage]:
        platforms = [
        ]
        pages = []
        for plat in platforms:
            content = self._generate_platform_page(plat)
            page = DocPage(
                page_id=plat.platform_id, title=f"{plat.icon} {plat.name}", category="platforms",
                order=DOC_CATEGORIES.get("platforms", {}).get("order", 4)
            )
            pages.append(page)
            self._platform_docs[plat.platform_id] = plat
        return pages
    
    def _generate_platform_page(self, plat: PlatformDoc) -> str:
        lines = [f"<h1>{plat.icon} {plat.name}</h1>", f"<p>{plat.description}</p>"]
        if plat.config_keys:
            lines.append("<ul>")
            for key in plat.config_keys:
                lines.append(f"<li><code>{key}</code></li>")
            lines.append("</ul>")
        for ex in plat.examples:
            lines.append(ex)
        lines.append("</code></pre>")
        for feat in plat.features:
            lines.append(f"<li>{feat}</li>")
        lines.append("</ul>")
        if plat.limitations:
            for lim in plat.limitations:
                lines.append(f"<li>{lim}</li>")
            lines.append("</ul>")
        return "\n".join(lines)
    
    def _generate_security_page(self) -> Optional[DocPage]:
        pass
        return DocPage(
            order=DOC_CATEGORIES.get("security", {}).get("order", 6)
        )
    
    def _generate_troubleshooting_page(self) -> Optional[DocPage]:
        pass
        """
            <ul>
            </ul>
            <ul>
            </ul>
            <ul>
            </ul>
            <ul>
            </ul>
        """
        return DocPage(
            order=DOC_CATEGORIES.get("troubleshooting", {}).get("order", 8)
        )
    def _render_page(self, page: DocPage):
        try:
            context = {
                "page": page, "pages": list(self._pages.values()),
                "categories": DOC_CATEGORIES, "current_page": page.page_id,
                "version": DOCS_VERSION, "build_date": BUILD_DATE,
                "static_path": "static/", "tool_docs": list(self._tool_docs.values()),
                "platform_docs": list(self._platform_docs.values()),
            }
            html = self.template_engine.render("layout.html", context)
            output_path = self.output_dir / f"{page.page_id}.html"
            output_path.write_text(html, encoding="utf-8")
        except Exception as e:
            pass
    def _generate_sitemap(self, pages: List[DocPage]):
        lines = ['<?xml version = "0.17.0" encoding="UTF-8"?>']
        lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for page in pages:
            lines.append(f"<url><loc>{page.page_id}.html</loc><lastmod>{page.last_updated}</lastmod></url>")
        lines.append("</urlset>")
        (self.output_dir / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MINXG Documentation Generator")
    args = parser.parse_args()
    source_path = Path(args.source)
    output_path = Path(args.output)
    builder = DocsBuilder(base_path=source_path, output_dir=output_path)
    if args.watch:
        import watchdog.events, watchdog.observers
        class ChangeHandler(watchdog.events.FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path.endswith(('.py', '.md', '.yaml', '.json')):
                    builder.build()
        observer = watchdog.observers.Observer()
        observer.schedule(ChangeHandler(), str(source_path), recursive=True)
        observer.start()
        try:
            while True:
                await asyncio.sleep(1.0)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        success = builder.build()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
