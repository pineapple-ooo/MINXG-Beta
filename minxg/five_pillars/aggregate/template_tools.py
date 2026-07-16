"""
"""
from __future__ import annotations
from typing import Dict
from minxg.base import BaseWorker, tool


class TemplateToolsWorker(BaseWorker):
    facade_alias = "data_tools"
    worker_id = "template_tools"
    tier = "ai"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="Replace {{var}} placeholders", category="render")
    async def render_placeholders(self, template: str, variables: dict) -> Dict:
        import re
        def _repl(m):
            key = m.group(1).strip()
            return str(variables.get(key, m.group(0)))
        result = re.sub(r'\{\{(\w+)\}\}', _repl, template)
        return {"result": result, "variables_used": len(set(re.findall(r'\{\{(\w+)\}\}', template)))}

    @tool(description="Jinja2 template rendering", category="render")
    async def jinja_render(self, template: str, context: dict) -> Dict:
        try:
            from jinja2 import Template
            t = Template(template)
            result = t.render(**context)
            return {"result": result, "engine": "jinja2"}
        except ImportError:
            return {"error": "Jinja2 not installed", "hint": "pip install jinja2"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Generate Python function code template", category="code")
    async def python_function_template(self, name: str, args: str = "", body: str = "pass",
                                        decorator: str = "", docstring: str = "") -> Dict:
        lines = []
        if decorator:
            lines.append(f"@{decorator}")
        lines.append(f"def {name}({args}):")
        if docstring:
            indent = "    "
            lines.append(f'{indent}"""{docstring}"""')
        for line in body.split("\n"):
            lines.append(f"    {line}" if line.strip() else "")
        return {"code": "\n".join(lines), "name": name}

    @tool(description="Generate Python class code template", category="code")
    async def python_class_template(self, name: str, bases: str = "",
                                     methods: str = "", docstring: str = "") -> Dict:
        base_clause = f"({bases})" if bases else ""
        lines = [f"class {name}{base_clause}:"]
        if docstring:
            lines.append(f'    """{docstring}"""')
        if methods:
            for m in methods.split("\n"):
                if m.strip():
                    lines.append(f"    {m}")
        else:
            lines.append("    pass")
        return {"code": "\n".join(lines), "name": name}

    @tool(description="Generate Markdown headings/lists/tables", category="markdown")
    async def markdown_builder(self, element: str, content: str, level: int = 1) -> Dict:
        builders = {
            "h1": f"# {content}",
            "h2": f"## {content}",
            "h3": f"### {content}",
            "bold": f"**{content}**",
            "italic": f"*{content}*",
            "code": f"`{content}`",
            "codeblock": f"```\n{content}\n```",
            "quote": "\n".join(f"> {l}" for l in content.split("\n")),
            "link": f"[{content}]({content})",
            "image": f"![{content}]({content})",
        }
        md = builders.get(element, content)
        return {"markdown": md, "element": element}

    @tool(description="Generate and format Markdown table", category="markdown")
    async def markdown_table(self, headers: str, rows: str) -> Dict:
        h = [c.strip() for c in headers.split(",")]
        r_rows = [r.split(",") for r in rows.split("\n") if r.strip()]
        lines = ["| " + " | ".join(h) + " |"]
        lines.append("| " + " | ".join(["---"] * len(h)) + " |")
        for row in r_rows:
            padded = row + [""] * (len(h) - len(row))
            lines.append("| " + " | ".join(padded) + " |")
        return {"markdown": "\n".join(lines), "columns": len(h), "rows": len(r_rows)}

    @tool(description="Generate HTML email template", category="email")
    async def email_template(self, subject: str, body: str, style: str = "simple") -> Dict:
        templates = {
            "simple": f"""<div style="font-family:Arial;max-width:600px;margin:0 auto;padding:20px">
  <h2>{subject}</h2>
  <hr>
  <p>{body}</p>
  <hr>
  <p style="color:#999;font-size:12px">Sent by MINXG</p>
</div>""",
            "formal": f"""<!DOCTYPE html><html><body style="font-family:Georgia;color:#333">
  <div style="border:1px solid #ddd;padding:30px">
    <h1 style="color:#2c3e50">{subject}</h1>
    <p style="line-height:1.8">{body}</p>
  </div>
</body></html>""",
        }
        return {"html": templates.get(style, templates["simple"]), "subject": subject, "style": style}

    @tool(description="Generate N lines of repeated text", category="generate")
    async def repeat_text(self, text: str, times: int = 5, separator: str = "\n") -> Dict:
        result = separator.join([text for _ in range(max(1, min(times, 1000)))])
        return {"result": result, "times": times, "length": len(result)}

    @tool(description="Generate config template", category="config")
    async def config_template(self, format: str = "json") -> Dict:
        data = {"name": "my_project", "version": "1.0.0", "debug": False,
                "server": {"host": "0.0.0.0", "port": 8080},
                "features": ["logging", "caching", "metrics"]}
        import json as _json
        if format == "json":
            content = _json.dumps(data, indent=2)
        elif format == "yaml":
            content = f"name: my_project\nversion: 1.0.0\ndebug: false\nserver:\n  host: 0.0.0.0\n  port: 8080\nfeatures:\n  - logging\n  - caching\n  - metrics"
        elif format == "toml":
            content = '[project]\nname = "my_project"\nversion = "0.17.1"\ndebug = false\n\n[server]\nhost = "0.0.0.0"\nport = 8080\n\nfeatures = ["logging", "caching", "metrics"]'
        else:
            content = _json.dumps(data, indent=2)
        return {"content": content, "format": format}

    @tool(description="Escape/unescape HTML entities", category="escape")
    async def escape_html(self, text: str, direction: str = "escape") -> Dict:
        import html
        if direction == "escape":
            result = html.escape(text)
        else:
            result = html.unescape(text)
        return {"result": result, "direction": direction}
