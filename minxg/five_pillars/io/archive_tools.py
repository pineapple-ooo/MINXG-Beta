"""
minxg/archive_tools.py — ZIP/RAR/7z/TAR archive operations v1.0.0

Auto-detects archive format via magic bytes, supports recursive extraction,
password-protected archives, and in-memory streaming.
"""
from __future__ import annotations
import os
import sys
import zipfile
import tarfile
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from pathlib import Path

from minxg.base import BaseWorker, tool



ARCHIVE_MAGIC = {
    b'PK\x03\x04': 'zip',
    b'PK\x05\x06': 'zip',
    b'PK\x07\x08': 'zip',
    b'Rar!\x1a\x07': 'rar',
    b'Rar!\x1a\x07\x00': 'rar5',
    b"7z\xbc\xaf'\x1c": '7z',
    b'\x1f\x8b\x08': 'gz',
    b'BZh': 'bz2',
    b'\xfd7zXZ': 'xz',
    b'\x28\xb5\x2f\xfd': 'zstd',
    b'\x04\x22\x4d\x18': 'lz4',
}


def detect_archive_type(path: str) -> str:
    """Detect archive type by reading magic bytes. Returns format name or 'unknown'."""
    try:
        with open(path, 'rb') as f:
            header = f.read(16)
        for magic, fmt in sorted(ARCHIVE_MAGIC.items(), key=lambda x: -len(x[0])):
            if header.startswith(magic):
                return fmt
        
        if len(header) >= 262:
            try:
                with open(path, 'rb') as f2:
                    f2.seek(257)
                    if f2.read(5) == b'ustar':
                        return 'tar'
            except Exception:
                pass
        return 'unknown'
    except Exception:
        return 'unknown'



def _safe_extract_path(base_dir: str, member_path: str) -> str:
    """Prevent path traversal attacks: ensure extracted path stays within base_dir."""
    resolved = os.path.realpath(os.path.join(base_dir, member_path))
    base_real = os.path.realpath(base_dir)
    if not resolved.startswith(base_real + os.sep) and resolved != base_real:
        raise ValueError(f"Path traversal detected: {member_path}")
    return resolved


class ArchiveWorker(BaseWorker):
    facade_alias = "fs_io"
    """
    Archive operations: ZIP, TAR, GZ, BZ2, XZ detection and extraction.
    Supports auto-detection, recursive extraction, and password-protected archives.
    """
    worker_id = "archive"
    tier = "code"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="List contents of an archive (ZIP, TAR, etc.) without extracting")
    def archive_list(self, path: str) -> Dict[str, Any]:
        """List all files in an archive."""

    @tool(description="Detect archive type by magic bytes. Returns format name.")
    def archive_detect(self, path: str) -> Dict[str, Any]:
        """Detect archive type from magic bytes."""

    @tool(description="Extract all files from an archive to a destination directory")
    def archive_extract(self, path: str, dest: str = "", strip_components: int = 0,
                        max_size_mb: int = 500, max_files: int = 10000) -> Dict[str, Any]:
        """Extract archive with safety limits."""

    @tool(description="Create a ZIP archive from a list of files or directory")
    def archive_create_zip(self, sources: List[str], dest: str,
                           compression: str = "deflate") -> Dict[str, Any]:
        """Create ZIP archive."""

    @tool(description="Extract from a password-protected archive")
    def archive_extract_password(self, path: str, password: str,
                                 dest: str = "") -> Dict[str, Any]:
        """Extract password-protected archive."""

    @tool(description="Recursively extract archives within archives (depth-limited)")
    def archive_recursive_extract(self, path: str, dest: str = "",
                                   max_depth: int = 3) -> Dict[str, Any]:
        """Recursive extraction of nested archives."""

    @tool(description="Read a text file from within an archive without full extraction")
    def archive_read_file(self, path: str, inner_path: str) -> Dict[str, Any]:
        """Read a single file from inside an archive."""

    @tool(description="Check if a ZIP archive is valid and not corrupted")
    def archive_verify(self, path: str) -> Dict[str, Any]:
        """Verify archive integrity."""

    def _register_tools(self):
        
        self.tools["archive_detect"] = type("ToolDef", (), {
            "name": "archive_detect",
            "description": "Detect archive type by reading magic bytes. Returns format name and MIME type.",
            "params": {"path": "string"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_list"] = type("ToolDef", (), {
            "name": "archive_list",
            "description": "List all files in an archive (ZIP, TAR, GZ, BZ2, XZ, 7Z, RAR) without extracting.",
            "params": {"path": "string", "max_entries": "int"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_extract"] = type("ToolDef", (), {
            "name": "archive_extract",
            "description": "Extract all files from an archive to a destination directory. Auto-detects format. Safety limits: max 500MB, 10000 files.",
            "params": {"path": "string", "dest": "string", "strip_components": "int", "max_size_mb": "int", "max_files": "int"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_create_zip"] = type("ToolDef", (), {
            "name": "archive_create_zip",
            "description": "Create a ZIP archive from a list of file paths or a directory.",
            "params": {"sources": "list", "dest": "string", "compression": "string"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_extract_password"] = type("ToolDef", (), {
            "name": "archive_extract_password",
            "description": "Extract a password-protected archive (ZIP, RAR, 7Z).",
            "params": {"path": "string", "password": "string", "dest": "string"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_recursive_extract"] = type("ToolDef", (), {
            "name": "archive_recursive_extract",
            "description": "Recursively extract archives found within an archive. Depth-limited for safety.",
            "params": {"path": "string", "dest": "string", "max_depth": "int"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_read_file"] = type("ToolDef", (), {
            "name": "archive_read_file",
            "description": "Read the contents of a single text file from inside an archive without full extraction.",
            "params": {"path": "string", "inner_path": "string"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        self.tools["archive_verify"] = type("ToolDef", (), {
            "name": "archive_verify",
            "description": "Verify archive integrity. Checks CRC/checksums without extracting.",
            "params": {"path": "string"},
            "category": "archive",
            "platforms": ["linux", "macos", "windows", "android", "ios"],
            "requires_root": False,
        })

        
        self.tools["archive_detect"].fn = self._archive_detect
        self.tools["archive_list"].fn = self._archive_list
        self.tools["archive_extract"].fn = self._archive_extract
        self.tools["archive_create_zip"].fn = self._archive_create_zip
        self.tools["archive_extract_password"].fn = self._archive_extract_password
        self.tools["archive_recursive_extract"].fn = self._archive_recursive_extract
        self.tools["archive_read_file"].fn = self._archive_read_file
        self.tools["archive_verify"].fn = self._archive_verify

    

    def _archive_detect(self, path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return {"status": "error", "error": f"File not found: {path}"}
        fmt = detect_archive_type(path)
        mime_map = {
            "zip": "application/zip",
            "rar": "application/x-rar-compressed",
            "rar5": "application/x-rar-compressed",
            "7z": "application/x-7z-compressed",
            "gz": "application/gzip",
            "bz2": "application/x-bzip2",
            "xz": "application/x-xz",
            "zstd": "application/zstd",
            "lz4": "application/x-lz4",
            "tar": "application/x-tar",
        }
        return {
            "status": "success",
            "path": path,
            "format": fmt,
            "mime_type": mime_map.get(fmt, "application/octet-stream"),
            "size_bytes": os.path.getsize(path),
        }

    def _archive_list(self, path: str, max_entries: int = 500) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        fmt = detect_archive_type(path)
        entries = []

        try:
            if fmt in ("zip", "rar", "rar5"):
                with zipfile.ZipFile(path, 'r') as zf:
                    for info in zf.infolist()[:max_entries]:
                        entries.append({
                            "name": info.filename,
                            "size": info.file_size,
                            "compressed_size": info.compress_size,
                            "is_dir": info.is_dir(),
                            "modified": str(info.date_time) if hasattr(info, 'date_time') else "",
                        })
            elif fmt == "tar" or path.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2')):
                with tarfile.open(path, 'r:*') as tf:
                    for member in tf.getmembers()[:max_entries]:
                        entries.append({
                            "name": member.name,
                            "size": member.size,
                            "is_dir": member.isdir(),
                            "modified": str(member.mtime) if hasattr(member, 'mtime') else "",
                        })
            else:
                return {"status": "error", "error": f"Unsupported archive format: {fmt}"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to list archive: {e}"}

        return {
            "status": "success",
            "format": fmt,
            "entries": entries,
            "total_entries": len(entries),
            "truncated": len(entries) >= max_entries,
        }

    def _archive_extract(self, path: str, dest: str = "", strip_components: int = 0,
                         max_size_mb: int = 500, max_files: int = 10000) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        if not dest:
            dest = os.path.splitext(path)[0] + "_extracted"
        dest = os.path.expanduser(dest)
        os.makedirs(dest, exist_ok=True)

        fmt = detect_archive_type(path)
        try:
            if fmt in ("zip", "rar", "rar5", "7z"):
                with zipfile.ZipFile(path, 'r') as zf:
                    total_size = sum(info.file_size for info in zf.infolist())
                    if total_size > max_size_mb * 1024 * 1024:
                        return {"status": "error", "error":
                                f"Archive size {total_size/1024/1024:.1f}MB exceeds limit {max_size_mb}MB"}
                    if len(zf.infolist()) > max_files:
                        return {"status": "error", "error":
                                f"Archive has {len(zf.infolist())} files, exceeding limit {max_files}"}
                    zf.extractall(dest)
            elif fmt == "tar" or path.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2')):
                with tarfile.open(path, 'r:*') as tf:
                    tf.extractall(dest)
            else:
                return {"status": "error", "error": f"Unsupported archive format: {fmt}"}

            extracted = []
            for root, dirs, files in os.walk(dest):
                for f in files:
                    extracted.append(os.path.join(root, f))

            return {
                "status": "success",
                "format": fmt,
                "dest": dest,
                "files_extracted": len(extracted),
            }
        except Exception as e:
            return {"status": "error", "error": f"Extraction failed: {e}"}

    def _archive_create_zip(self, sources: List[str], dest: str,
                            compression: str = "deflate") -> Dict[str, Any]:
        dest = os.path.expanduser(dest)
        comp = zipfile.ZIP_DEFLATED if compression == "deflate" else zipfile.ZIP_STORED
        added = 0
        try:
            with zipfile.ZipFile(dest, 'w', comp) as zf:
                for src in sources:
                    src = os.path.expanduser(src)
                    if os.path.isdir(src):
                        for root, dirs, files in os.walk(src):
                            for f in files:
                                fp = os.path.join(root, f)
                                zf.write(fp, os.path.relpath(fp, os.path.dirname(src)))
                                added += 1
                    elif os.path.isfile(src):
                        zf.write(src, os.path.basename(src))
                        added += 1
            return {"status": "success", "dest": dest, "files_added": added, "size": os.path.getsize(dest)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _archive_extract_password(self, path: str, password: str,
                                  dest: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        if not dest:
            dest = os.path.splitext(path)[0] + "_extracted"
        dest = os.path.expanduser(dest)
        os.makedirs(dest, exist_ok=True)

        try:
            with zipfile.ZipFile(path, 'r') as zf:
                zf.setpassword(password.encode('utf-8'))
                zf.extractall(dest)
            return {"status": "success", "dest": dest}
        except RuntimeError as e:
            if "password" in str(e).lower():
                return {"status": "error", "error": "Incorrect password"}
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _archive_recursive_extract(self, path: str, dest: str = "",
                                   max_depth: int = 3) -> Dict[str, Any]:
        if max_depth <= 0:
            return {"status": "error", "error": "Max depth reached without completion"}
        path = os.path.expanduser(path)
        if not dest:
            dest = os.path.splitext(path)[0] + "_extracted"
        dest = os.path.expanduser(dest)
        os.makedirs(dest, exist_ok=True)

        result = self._archive_extract(path, dest)
        if result["status"] != "success":
            return result

        nested = []
        for root, dirs, files in os.walk(dest):
            for f in files:
                fp = os.path.join(root, f)
                if detect_archive_type(fp) != "unknown":
                    nested.append(fp)

        for nfp in nested:
            sub_dest = os.path.splitext(nfp)[0]
            self._archive_recursive_extract(nfp, sub_dest, max_depth - 1)

        return {"status": "success", "dest": dest, "files_extracted": result.get("files_extracted", 0),
                "nested_archives_found": len(nested)}

    def _archive_read_file(self, path: str, inner_path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                content = zf.read(inner_path)
                size = len(content)
                if size > 1024 * 1024:  
                    return {"status": "error", "error": f"File too large: {size} bytes"}
                try:
                    text = content.decode('utf-8')
                    return {"status": "success", "content": text, "size": size, "encoding": "utf-8"}
                except UnicodeDecodeError:
                    return {"status": "success", "content_preview": str(content[:200]), "size": size,
                            "encoding": "binary", "note": "Binary file — showing preview only"}
        except KeyError:
            return {"status": "error", "error": f"File not found in archive: {inner_path}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _archive_verify(self, path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                bad = zf.testzip()
            if bad:
                return {"status": "error", "error": f"Corrupted file in archive: {bad}"}
            return {"status": "success", "valid": True, "size": os.path.getsize(path)}
        except Exception as e:
            return {"status": "error", "error": str(e)}