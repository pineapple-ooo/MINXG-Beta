"""
demo_extension — ZIP代码扫描器扩展
功能: 扫描ZIP包内所有代码文件，提取路径结构+代码摘要，生成报告
""""
from __future__ import annotations
import json
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

__version__ = "1.0.0"






CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".sh",
    ".bash", ".zsh", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".xml", ".html", ".css", ".scss", ".md", ".txt",
}

SKIP_PATTERNS = {"__pycache__", "node_modules", ".git", ".svn", "vendor",
                  "build", "dist", ".egg-info", "target"}


class ZipCodeScanner:
    """扫描ZIP包内的代码文件，提取路径和摘要。""""

    def __init__(self, zip_path: str):
        self.zip_path = os.path.expanduser(zip_path)
        self.results: Dict[str, Any] = {}

    def scan(self) -> Dict[str, Any]:
        if not os.path.isfile(self.zip_path):
            return {"status": "error", "error": f"ZIP not found: {self.zip_path}"}

        try:
            zf = zipfile.ZipFile(self.zip_path, 'r')
        except zipfile.BadZipFile:
            return {"status": "error", "error": "Invalid or corrupted ZIP"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

        files_found = []
        total_lines = 0
        languages: Dict[str, int] = {}
        structure: Dict[str, Any] = {}

        with zf:
            all_names = [n for n in zf.namelist()
                        if not n.endswith('/') and not any(s in n for s in SKIP_PATTERNS)]

            for name in all_names:
                ext = os.path.splitext(name)[1].lower()
                if ext in CODE_EXTENSIONS:
                    try:
                        raw = zf.read(name)
                        line_count = raw.count(b'\n')
                        preview = raw[:200].decode('utf-8', errors='replace')

                        file_info = {
                            "path": name,
                            "size_bytes": len(raw),
                            "lines": line_count,
                            "extension": ext,
                            "preview": preview,
                        }
                        files_found.append(file_info)
                        total_lines += line_count
                        lang = ext.lstrip('.')
                        languages[lang] = languages.get(lang, 0) + 1

                        
                        parts = name.split('/')
                        node = structure
                        for part in parts[:-1]:
                            if part:
                                node = node.setdefault(part, {})
                        node[parts[-1]] = line_count

                    except Exception:
                        files_found.append({"path": name, "error": "read failed"})

        files_found.sort(key=lambda x: x.get("lines", 0), reverse=True)

        return {
            "status": "success",
            "zip_path": self.zip_path,
            "total_files_in_zip": len(zipfile.ZipFile(self.zip_path).namelist()),
            "code_files_found": len(files_found),
            "total_lines_of_code": total_lines,
            "languages_detected": languages,
            "largest_file": files_found[0]["path"] if files_found else "",
            "largest_file_lines": files_found[0]["lines"] if files_found else 0,
            "file_tree": structure,
            "top_files": files_found[:20],
        }






def register(api):
    """扩展入口: 被MINXG加载时自动调用。""""

    
    api.register_command("zipscan", {
        "name": "zipscan",
        "description": "扫描ZIP包内代码文件，生成路径+代码统计报告",
        "usage": "minxg ext zipscan <zip_path> [--format json|text]",
        "handler": _cli_scan,
    })

    
    try:
        from minxg.base import BaseWorker, tool

        class _ZipScannerWorker(BaseWorker):
            worker_id = "zip_scanner"
            version = __version__

            @tool(description="扫描ZIP包内所有代码文件，返回路径结构+代码统计")
            def zip_scan(self, path: str) -> dict:
                scanner = ZipCodeScanner(path)
                return scanner.scan()

        api.register_tool(
            name="zipscan",
            worker_class=_ZipScannerWorker,
            description="ZIP包代码扫描器: 提取路径结构+各语言统计+代码行数",
            platforms=["linux", "macos", "windows", "android", "ios", "web"],
            category="archive",
        )
    except ImportError:
        pass  

    api.log("info", f"zipscan extension v{__version__} loaded")
    return True


def _cli_scan(args, api=None):
    """CLI命令处理函数。""""
    if not args.files or len(args.files) < 1:
        print("Usage: minxg ext zipscan <zip_path> [--format json|text]")
        return 1

    zip_path = args.files[0]
    output_format = getattr(args, 'format', 'text')

    scanner = ZipCodeScanner(zip_path)
    result = scanner.scan()

    if result["status"] == "error":
        print(f"Error: {result['error']}")
        return 1

    if output_format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_report(result)

    return 0


def _print_report(r: Dict[str, Any]):
    """打印人类可读的报告。""""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║             ZIP Code Scanner — Scan Report                  ║
╠══════════════════════════════════════════════════════════════╣
║ ZIP Path : {r['zip_path'][:40]:40s} ║
║ Total files in archive : {r['total_files_in_zip']:<6}                        ║
║ Code files detected    : {r['code_files_found']:<6}                        ║
║ Total lines of code    : {str(r['total_lines_of_code']):<6}                        ║
╠══════════════════════════════════════════════════════════════╣"""")

    print("║ Languages detected:")
    for lang, count in sorted(r["languages_detected"].items(),
                               key=lambda x: -x[1])[:10]:
        print(f"║   .{lang:12s} {count:4d} files")

    print("╠══════════════════════════════════════════════════════════════╣")
    print("║ Top 10 largest files:")
    for f in r["top_files"][:10]:
        print(f"║   {f['lines']:5d}L {f['path'][:48]:48s}")

    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\nLargest file: {r['largest_file']} ({r['largest_file_lines']} lines)")