"""
checksum_file, count_lines, compress, decompress
"""
from __future__ import annotations
import gzip
import bz2
import lzma
import os
import re
import hashlib
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, List
from minxg.base import BaseWorker, tool


class FsSearchWorker(BaseWorker):
    worker_id = "fs_search"
    version = "0"

    @tool(description="Glob file search (supports **)", category="search")
    async def glob_search(self, pattern: str = "**/*.py", path: str = ".") -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"path not found: {path}"}
        try:
            matches = [str(m) for m in p.glob(pattern)]
            return {"pattern": pattern, "path": str(p), "count": len(matches), "matches": matches[:500]}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Case-insensitive filename substring search", category="search")
    async def search_files(self, query: str, path: str = ".", max_results: int = 200) -> Dict:
        p = Path(path).expanduser()
        if not p.is_dir():
            return {"error": f"not a directory: {path}"}
        try:
            q = query.lower()
            matches = []
            for root, dirs, files in os.walk(p):
                for f in files:
                    if q in f.lower():
                        matches.append(str(Path(root) / f))
                        if len(matches) >= max_results:
                            return {"query": query, "count": len(matches), "matches": matches, "truncated": True}
            return {"query": query, "count": len(matches), "matches": matches}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Regex content search (return line numbers)", category="search")
    async def grep_file(self, pattern: str, path: str, max_results: int = 200,
                       ignore_case: bool = False) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"path not found: {path}"}
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}
        matches = []
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        for f in files:
            try:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            matches.append({"file": str(f), "line": i, "content": line.rstrip()})
                            if len(matches) >= max_results:
                                return {"pattern": pattern, "count": len(matches), "matches": matches, "truncated": True}
            except (PermissionError, OSError):
                continue
        return {"pattern": pattern, "count": len(matches), "matches": matches}

    @tool(description="Find files containing query in tree", category="search")
    async def find_in_files(self, query: str, path: str = ".", max_results: int = 50) -> Dict:
        return await self.grep_file(query, path, max_results)

    @tool(description="Calculate file checksum", category="info")
    async def checksum_file(self, path: str, algorithm: str = "md5") -> Dict:
        p = Path(path).expanduser()
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        algo = algorithm.lower()
        if algo not in ("md5", "sha1", "sha256", "sha512"):
            return {"error": f"unsupported algorithm: {algorithm}"}
        h = hashlib.new(algo)
        try:
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return {"path": str(p), "algorithm": algo, "checksum": h.hexdigest(),
                    "size": p.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Count file lines/words/chars", category="info")
    async def count_lines(self, path: str) -> Dict:
        p = Path(path).expanduser()
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return {"path": str(p), "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
                    "words": len(text.split()), "chars": len(text), "bytes": p.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Compress to archive", category="archive")
    async def compress(self, source: str, output: str, format: str = "zip") -> Dict:
        sp = Path(source); op = Path(output)
        op.parent.mkdir(parents=True, exist_ok=True)
        try:
            if format == "zip":
                with zipfile.ZipFile(op, "w", zipfile.ZIP_DEFLATED) as zf:
                    if sp.is_dir():
                        for f in sp.rglob("*"):
                            zf.write(f, f.relative_to(sp.parent))
                    else:
                        zf.write(sp)
            elif format in ("tar.gz", "tgz"):
                with tarfile.open(op, "w:gz") as tf:
                    tf.add(sp, arcname=sp.name)
            elif format in ("tar.bz2", "tbz2"):
                with tarfile.open(op, "w:bz2") as tf:
                    tf.add(sp, arcname=sp.name)
            elif format in ("tar.xz", "txz"):
                with tarfile.open(op, "w:xz") as tf:
                    tf.add(sp, arcname=sp.name)
            else:
                return {"error": f"unsupported format: {format}"}
            return {"source": source, "output": str(op), "format": format, "size": op.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Extract archive to directory", category="archive")
    async def decompress(self, archive: str, output_dir: str = ".") -> Dict:
        ap = Path(archive); od = Path(output_dir)
        od.mkdir(parents=True, exist_ok=True)
        try:
            name = ap.name.lower()
            if name.endswith(".zip"):
                with zipfile.ZipFile(ap) as zf:
                    zf.extractall(od)
            elif name.endswith((".tar.gz", ".tgz")):
                with tarfile.open(ap, "r:gz") as tf:
                    tf.extractall(od)
            elif name.endswith((".tar.bz2", ".tbz2")):
                with tarfile.open(ap, "r:bz2") as tf:
                    tf.extractall(od)
            elif name.endswith((".tar.xz", ".txz")):
                with tarfile.open(ap, "r:xz") as tf:
                    tf.extractall(od)
            elif name.endswith(".gz"):
                outp = od / ap.stem
                with gzip.open(ap, "rb") as i, outp.open("wb") as o:
                    shutil.copyfileobj(i, o)
                return {"archive": str(ap), "output": str(outp), "format": "gz"}
            elif name.endswith(".bz2"):
                outp = od / ap.stem
                with bz2.open(ap, "rb") as i, outp.open("wb") as o:
                    shutil.copyfileobj(i, o)
                return {"archive": str(ap), "output": str(outp), "format": "bz2"}
            elif name.endswith(".xz"):
                outp = od / ap.stem
                with lzma.open(ap, "rb") as i, outp.open("wb") as o:
                    shutil.copyfileobj(i, o)
                return {"archive": str(ap), "output": str(outp), "format": "xz"}
            else:
                return {"error": f"unsupported format: {ap.name}"}
            return {"archive": str(ap), "output_dir": str(od), "extracted": True}
        except Exception as e:
            return {"error": str(e)}
