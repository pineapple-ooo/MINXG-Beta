"""
rsync_incremental, dedup_files, smart_merge, diff_directories
"""
from __future__ import annotations
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List
from .base import BaseWorker, tool


class FsCopyWorker(BaseWorker):
    worker_id = "fs_copy"
    version = "1.0.0"

    @tool(description="Copy file/directory (preserve=true keeps metadata)", category="write")
    async def copy_file(self, source: str, dest: str, preserve_metadata: bool = True) -> Dict:
        try:
            sp = Path(source); dp = Path(dest)
            if sp.is_dir():
                if preserve_metadata:
                    shutil.copytree(sp, dp)
                else:
                    shutil.copytree(sp, dp, dirs_exist_ok=True)
            else:
                if preserve_metadata:
                    shutil.copy2(sp, dp)
                else:
                    shutil.copy(sp, dp)
            return {"source": source, "dest": dest, "copied": True}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Merge multiple files with separator", category="write")
    async def merge_files(self, paths: list, separator: str = "\n---\n", output: str = None) -> Dict:
        try:
            chunks = []
            for path in paths:
                chunks.append(Path(path).read_text(encoding="utf-8", errors="replace"))
            merged = separator.join(chunks)
            if output:
                Path(output).write_text(merged, encoding="utf-8")
                return {"output": output, "bytes": len(merged), "files_merged": len(paths)}
            return {"content": merged, "bytes": len(merged), "files_merged": len(paths)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Split file by line count", category="write")
    async def split_file(self, path: str, lines_per_chunk: int = 100, output_dir: str = None) -> Dict:
        p = Path(path)
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        od = Path(output_dir) if output_dir else p.parent
        od.mkdir(parents=True, exist_ok=True)
        try:
            chunks = []
            with p.open(encoding="utf-8", errors="replace") as f:
                chunk_lines = []
                for line in f:
                    chunk_lines.append(line)
                    if len(chunk_lines) >= lines_per_chunk:
                        chunks.append(chunk_lines)
                        chunk_lines = []
                if chunk_lines:
                    chunks.append(chunk_lines)
            outputs = []
            for i, chunk in enumerate(chunks):
                outp = od / f"{p.stem}.part{i:04d}{p.suffix}"
                outp.write_text("".join(chunk), encoding="utf-8")
                outputs.append(str(outp))
            return {"source": str(p), "output_dir": str(od), "chunks": len(outputs), "files": outputs}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Directory size statistics", category="info")
    async def disk_usage(self, path: str = ".") -> Dict:
        p = Path(path)
        if not p.exists():
            return {"error": f"not found: {path}"}
        try:
            total = 0
            file_count = 0
            if p.is_file():
                total = p.stat().st_size
                file_count = 1
            else:
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            total += f.stat().st_size
                            file_count += 1
                        except OSError:
                            pass
            return {"path": str(p), "total_bytes": total,
                    "human": _human_size(total), "file_count": file_count}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Incremental sync source to dest", category="sync")
    async def rsync_incremental(self, source: str, dest: str, delete: bool = False) -> Dict:
        sp = Path(source).expanduser()
        dp = Path(dest).expanduser()
        if not sp.exists():
            return {"error": f"source not found: {source}"}
        dp.mkdir(parents=True, exist_ok=True)
        try:
            copied = 0
            skipped = 0
            removed = 0
            for src_file in sp.rglob("*"):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(sp)
                dst_file = dp / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                need_copy = True
                if dst_file.exists():
                    src_hash = hashlib.sha256(src_file.read_bytes()).hexdigest()
                    dst_hash = hashlib.sha256(dst_file.read_bytes()).hexdigest()
                    if src_hash == dst_hash:
                        need_copy = False
                        skipped += 1
                if need_copy:
                    shutil.copy2(src_file, dst_file)
                    copied += 1
            if delete:
                for dst_file in dp.rglob("*"):
                    if not dst_file.is_file():
                        continue
                    rel = dst_file.relative_to(dp)
                    src_file = sp / rel
                    if not src_file.exists():
                        dst_file.unlink()
                        removed += 1
            return {"copied": copied, "skipped": skipped, "removed": removed}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Deduplicate by content in directory", category="dedup")
    async def dedup_files(self, path: str, dry_run: bool = True) -> Dict:
        p = Path(path).expanduser()
        if not p.is_dir():
            return {"error": f"not a directory: {path}"}
        try:
            hashes: Dict[str, List[str]] = {}
            for f in p.rglob("*"):
                if f.is_file():
                    h = hashlib.sha256(f.read_bytes()).hexdigest()
                    hashes.setdefault(h, []).append(str(f))
            dups = {h: files for h, files in hashes.items() if len(files) > 1}
            removed = 0
            if not dry_run:
                for h, files in dups.items():
                    for dup in files[1:]:
                        Path(dup).unlink()
                        removed += 1
            return {"duplicates": dups, "removed": removed, "dry_run": dry_run}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Smart merge files, auto-remove duplicates", category="merge")
    async def smart_merge(self, paths: list, output: str, dedup: bool = True) -> Dict:
        try:
            lines = []
            for path in paths:
                content = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
                lines.extend(content.splitlines())
            if dedup:
                seen = set()
                unique = []
                for line in lines:
                    if line not in seen:
                        seen.add(line)
                        unique.append(line)
                lines = unique
            merged = "\n".join(lines)
            Path(output).expanduser().write_text(merged, encoding="utf-8")
            return {"output": output, "lines": len(lines), "bytes": len(merged)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="List diff between two directories", category="sync")
    async def diff_directories(self, source: str, dest: str) -> Dict:
        sp = Path(source).expanduser()
        dp = Path(dest).expanduser()
        new_files = []
        modified_files = []
        deleted_files = []
        try:
            src_files = {f.relative_to(sp): f for f in sp.rglob("*") if f.is_file()}
            dst_files = {f.relative_to(dp): f for f in dp.rglob("*") if f.is_file()}
            for rel, sf in src_files.items():
                if rel not in dst_files:
                    new_files.append(str(rel))
                else:
                    if hashlib.sha256(sf.read_bytes()).hexdigest() != hashlib.sha256(dst_files[rel].read_bytes()).hexdigest():
                        modified_files.append(str(rel))
            for rel in dst_files:
                if rel not in src_files:
                    deleted_files.append(str(rel))
            return {"new": new_files, "modified": modified_files, "deleted": deleted_files}
        except Exception as e:
            return {"error": str(e)}


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"
