"""Markdown processing tools."""
from minxg.base import BaseWorker, tool

class MarkdownWorker(BaseWorker):
    facade_alias = "markdown_worker"
    worker_id = "markdown_worker"
    version = "0.17.1"

    @tool
    async def markdown_to_text(self, markdown: str = "") -> dict:
        """Strip markdown formatting, return plain text."""
        import re
        text = re.sub(r'#{1,6}\s*', '', markdown)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'[\*_~>|-]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return {"text": text.strip(), "length": len(text)}

    @tool
    async def markdown_extract_code(self, markdown: str = "", language: str = "") -> dict:
        """Extract code blocks from markdown."""
        import re
        blocks = re.findall(r'```(\w*)\n(.*?)```', markdown, re.DOTALL)
        if language:
            blocks = [(lang, code) for lang, code in blocks if lang == language]
        return {"blocks": [{"language": lang, "code": code.strip()} for lang, code in blocks], "count": len(blocks)}

    @tool
    async def markdown_extract_links(self, markdown: str = "") -> dict:
        """Extract all links from markdown."""
        import re
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown)
        return {"links": [{"text": t, "url": u} for t, u in links], "count": len(links)}

    @tool
    async def markdown_table_of_contents(self, markdown: str = "") -> dict:
        """Generate table of contents from markdown headings."""
        import re
        headings = re.findall(r'^(#{1,6})\s+(.+)$', markdown, re.MULTILINE)
        toc = []
        for level_markers, title in headings:
            level = len(level_markers)
            indent = "  " * (level - 1)
            anchor = title.lower().replace(" ", "-").replace(".","")
            toc.append(f"{indent}- [{title.strip()}](#{anchor})")
        return {"toc": toc, "headings_count": len(headings)}

    @tool
    async def markdown_stats(self, markdown: str = "") -> dict:
        """Get markdown document statistics."""
        import re
        words = len(re.findall(r'\b\w+\b', markdown))
        lines = markdown.count('\n') + 1
        headings = len(re.findall(r'^#{1,6}\s', markdown, re.MULTILINE))
        code_blocks = len(re.findall(r'```', markdown)) // 2
        links = len(re.findall(r'\[([^\]]+)\]\(', markdown))
        return {
            "words": words, "lines": lines, "headings": headings,
            "code_blocks": code_blocks, "links": links,
        }

    @tool
    async def markdown_to_html(self, markdown: str = "") -> dict:
        """Convert markdown to HTML (basic)."""
        import re
        html = markdown
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        return {"html": html}
