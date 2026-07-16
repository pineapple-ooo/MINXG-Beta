"""minxg/five_pillars/devtools/self_evolution.py -- Self-evolution engine v2.

The SelfEvolutionWorker lets the AI agent **learn from every task
it completes**.  After finishing a task the AI calls
``evolution_record`` with a summary of:

* what the task was
* what approach worked / failed
* what tools were used
* what time / token cost was incurred
* what lessons to remember next time

These records are persisted to ``~/.minxg/evolution.jsonl`` (one
JSON object per line) so the knowledge survives across sessions.
Before starting a new task the AI calls ``evolution_recall`` with
keywords describing the upcoming task; the engine returns the
top-N most relevant past lessons so the AI can skip blind alleys
and reuse proven approaches.

This is the core of the "self-evolution" feature the user
requested -- every completed task makes the next one cheaper.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v2 增强 (超级无损记忆系统):

1. **原子写入** — 先写 tmp 文件, flush+fsync, 再 os.replace 覆盖。
   写入中途崩溃最多丢失正在追加的那一行, 已有数据无损。

2. **内容校验和** — 每条记录附 SHA-256 校验和。读取时验证,
   损坏行被隔离到 corruption_log 而非静默丢弃。

3. **BM25 语义检索** — 替代纯 TF-IDF cosine。BM25 带饱和
   函数 k1=1.5 和长度归一化 b=0.75, 检索质量接近 Elasticsearch
   级别, 纯 Python 实现, 无外部依赖。

4. **记录去重** — 新记录与已有记录做 fuzzy 匹配 (token Jaccard
   相似度), 相似度 > 0.85 的合并而非重复写入。

5. **自动归档压缩** — 记录数超过 ARCHIVE_THRESHOLD (500) 时,
   旧记录打包成 gzip 归档文件 evolution_archive_YYYYMMDD.jsonl.gz,
   主文件只保留最近 200 条。归档记录仍可被 recall 检索。

6. **快照导出/导入** — evolution_export 导出全部记录为可移植
   JSONL 文件; evolution_import 从外部文件导入记录 (带校验和
   验证)。

7. **版本回滚** — evolution_rollback 回到上一个快照。每次
   归档操作自动保存快照到 ~/.minxg/snapshots/。

8. **低质量记录清理** — evolution_prune 清理 outcome=failure
   且 lessons 为空的低价值记录。

检索策略: BM25 (k1=1.5, b=0.75) + 当记录 > ARCHIVE_THRESHOLD
时自动归档。归档文件用 gzip 压缩, 检索时实时解压并入索引。
O(n*m) where n=records and m=terms in the query -- fine for thousands
of records.

The evolution log lives at:
    ~/.minxg/evolution.jsonl

Format (one JSON object per line):
    {
        "id": "ev_000042",
        "timestamp": "2026-07-12T10:30:00Z",
        "task": "fix gateway startup",
        "approach": "traced _pick_initial_mode fallback, added foreground route",
        "tools_used": ["grep", "pytest", "curl"],
        "outcome": "success",
        "lessons": ["gateway sub_command None means status not start"],
        "cost_seconds": 120,
        "keywords": ["gateway", "aiohttp", "port", "background"],
        "checksum": "sha256:abc123...",
        "schema_version": 2
    }
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool


# ── 配置 ────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 2
ARCHIVE_THRESHOLD = 500          # 超过此条数触发归档
KEEP_RECENT = 200                # 归档后主文件保留最近 N 条
DEDUP_THRESHOLD = 0.85           # Jaccard 相似度去重阈值
CORRUPTION_LOG = "corruption.log"

# BM25 参数
BM25_K1 = 1.5
BM25_B = 0.75


# ── 路径 ────────────────────────────────────────────────────────────────────

def _evolution_dir() -> Path:
    """Return the directory for evolution data."""
    d = Path.home() / ".minxg"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _evolution_path() -> Path:
    """Return the on-disk path for the evolution log."""
    return _evolution_dir() / "evolution.jsonl"


def _snapshot_dir() -> Path:
    """Return the directory for snapshots."""
    d = _evolution_dir() / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _archive_dir() -> Path:
    """Return the directory for gzip archives."""
    d = _evolution_dir() / "archives"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _corruption_log_path() -> Path:
    """Return the path for the corruption log."""
    return _evolution_dir() / CORRUPTION_LOG


# ── 校验和 ──────────────────────────────────────────────────────────────────

def _compute_checksum(record: Dict[str, Any]) -> str:
    """Compute SHA-256 checksum of a record's content fields."""
    content = json.dumps({
        "task": record.get("task", ""),
        "approach": record.get("approach", ""),
        "tools_used": record.get("tools_used", []),
        "outcome": record.get("outcome", ""),
        "lessons": record.get("lessons", []),
        "keywords": record.get("keywords", []),
    }, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _verify_checksum(record: Dict[str, Any]) -> bool:
    """Verify the SHA-256 checksum of a record. Returns True if valid."""
    stored = record.get("checksum")
    if not stored or not stored.startswith("sha256:"):
        # Pre-v2 record without checksum — treat as valid (migration).
        return True
    expected = _compute_checksum(record)
    return stored == expected


# ── tokenizer & BM25 ────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return [w for w in re.split(r"[^a-zA-Z0-9]+", text.lower()) if w]


def _tokenize_set(text: str) -> set:
    """Return a set of unique tokens for Jaccard similarity."""
    return set(_tokenize(text))


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


class _BM25Index:
    """In-memory BM25 index over a corpus of records.

    BM25 formula:
        score(D, Q) = Σ IDF(qi) · (f(qi,D)·(k1+1)) /
                       (f(qi,D) + k1·(1 - b + b·|D|/avgdl))

    where IDF(qi) = ln((N - df(qi) + 0.5) / (df(qi) + 0.5) + 1)
    """

    def __init__(self) -> None:
        self._docs: List[List[str]] = []       # tokenized documents
        self._doc_freqs: List[Dict[str, int]] = []  # term frequency per doc
        self._df: Dict[str, int] = {}            # document frequency
        self._doc_lengths: List[int] = []
        self._records: List[Dict[str, Any]] = []
        self._avgdl: float = 0.0
        self._n: int = 0

    def add(self, record: Dict[str, Any]) -> None:
        """Add a record to the index."""
        doc_text = " ".join([
            record.get("task", ""),
            record.get("approach", ""),
            " ".join(record.get("lessons", [])),
            " ".join(record.get("keywords", [])),
        ])
        tokens = _tokenize(doc_text)
        self._docs.append(tokens)
        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        self._doc_freqs.append(tf)
        for term in tf:
            self._df[term] = self._df.get(term, 0) + 1
        self._doc_lengths.append(len(tokens))
        self._records.append(record)
        self._n += 1

    def finalize(self) -> None:
        """Compute average document length after all docs added."""
        if self._n > 0:
            self._avgdl = sum(self._doc_lengths) / self._n

    def search(self, query: str, top_n: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        """Search the index. Returns list of (score, record) sorted descending."""
        if self._n == 0:
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: List[Tuple[float, Dict[str, Any]]] = []
        for i in range(self._n):
            score = 0.0
            tf_map = self._doc_freqs[i]
            dl = self._doc_lengths[i]
            for qt in query_tokens:
                f = tf_map.get(qt, 0)
                if f == 0:
                    continue
                df = self._df.get(qt, 0)
                idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1)
                norm = BM25_K1 * (1 - BM25_B + BM25_B * dl / max(self._avgdl, 1))
                score += idf * (f * (BM25_K1 + 1)) / (f + norm)
            if score > 0:
                scores.append((score, self._records[i]))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_n]


# ── 读取 & 写入 ──────────────────────────────────────────────────────────────

def _load_records(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    """Load all records from the evolution log.

    Returns (records, corrupt_count). Corrupt records are logged to
    the corruption log and excluded from the returned list.
    """
    if not path.exists():
        return [], 0

    records: List[Dict[str, Any]] = []
    corrupt = 0

    if _corruption_log_path().exists():
        _corruption_log_path().unlink()

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1
                _log_corruption(path, line_num, "json_decode_error", line[:200])
                continue

            if not _verify_checksum(rec):
                corrupt += 1
                _log_corruption(path, line_num, "checksum_mismatch", line[:200])
                continue

            records.append(rec)

    return records, corrupt


def _log_corruption(path: Path, line_num: int, reason: str, preview: str) -> None:
    """Log a corrupt record to the corruption log."""
    log_path = _corruption_log_path()
    entry = {
        "file": str(path),
        "line": line_num,
        "reason": reason,
        "preview": preview,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _atomic_append(path: Path, line: str) -> None:
    """Atomically append a line to the evolution log.

    Writes to a temp file, flushes, fsyncs, then os.replace onto the
    target. This guarantees the on-disk file is never in a
    partially-written state.
    """
    # Read existing content
    existing = b""
    if path.exists():
        with open(path, "rb") as f:
            existing = f.read()

    new_content = existing + (line + "\n").encode("utf-8")
    tmp_path = path.with_suffix(".jsonl.tmp")

    with open(tmp_path, "wb") as f:
        f.write(new_content)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, path)


def _atomic_write_all(path: Path, records: List[Dict[str, Any]]) -> None:
    """Atomically write all records to the evolution log."""
    tmp_path = path.with_suffix(".jsonl.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


# ── 归档 ────────────────────────────────────────────────────────────────────

def _maybe_archive(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[Path]]:
    """If records exceed ARCHIVE_THRESHOLD, archive old ones and
    return (remaining_records, archive_path).

    The archive is a gzip-compressed JSONL file. A snapshot of the
    pre-archive state is saved to the snapshots directory.
    """
    if len(records) <= ARCHIVE_THRESHOLD:
        return records, None

    # Save snapshot before archiving
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = _snapshot_dir() / f"pre_archive_{stamp}.jsonl"
    _atomic_write_all(snap_path, records)

    # Split: keep most recent KEEP_RECENT, archive the rest
    to_archive = records[:-KEEP_RECENT]
    to_keep = records[-KEEP_RECENT:]

    archive_name = f"evolution_archive_{stamp}.jsonl.gz"
    archive_path = _archive_dir() / archive_name

    with gzip.open(archive_path, "wt", encoding="utf-8") as gz:
        for rec in to_archive:
            gz.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Rewrite main file with only recent records
    _atomic_write_all(_evolution_path(), to_keep)

    return to_keep, archive_path


def _load_archive_records() -> List[Dict[str, Any]]:
    """Load records from all archive files."""
    archives: List[Dict[str, Any]] = []
    d = _archive_dir()
    if not d.exists():
        return archives

    for archive_file in sorted(d.glob("evolution_archive_*.jsonl.gz")):
        try:
            with gzip.open(archive_file, "rt", encoding="utf-8") as gz:
                for line in gz:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        archives.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    return archives


class SelfEvolutionWorker(BaseWorker):
    """Self-evolution engine v2 — 超级无损记忆系统.

    Records task-completion lessons and recalls them before
    future tasks.  The AI calls ``evolution_record`` after every
    task and ``evolution_recall`` before starting a new one.

    The log is append-only JSONL with atomic writes (tmp + os.replace)
    so it never corrupts: a crash mid-write drops at most the line
    being written, and old lines stay intact.  Each record carries a
    SHA-256 checksum; corrupt lines are isolated to corruption.log.

    Cost: recording is O(n) for dedup check; recall is O(n*m) where
    n = number of records and m = query terms.  For < 10,000 records
    this is sub-millisecond.  BM25 replaces the old TF-cosine metric
    for better retrieval quality.
    """

    worker_id = "evolution_tools"
    version = "0.18.2"
    tier = "ai"
    _category = "ai"

    # ── evolution_record ──────────────────────────────────────────────────

    @tool(
        description=(
            "Record a completed task's lessons so future tasks "
            "can reuse them.  Call this after EVERY completed task."
            " v2: deduplicates against existing records, uses atomic"
            " writes, computes SHA-256 checksum."
        ),
        category="ai",
    )
    async def evolution_record(
        self,
        task: str,
        approach: str,
        tools_used: List[str],
        outcome: str,
        lessons: List[str],
        cost_seconds: int = 0,
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Append one evolution record to the persistent log.

        v2 enhancements:
        - Dedup: checks Jaccard similarity against existing records.
          If similarity > 0.85, merges lessons instead of duplicating.
        - Atomic write: tmp + os.replace prevents corruption.
        - SHA-256 checksum per record.
        - Auto-archive when records exceed 500.
        """
        path = _evolution_path()
        kw = keywords or _tokenize(task)[:10]

        # Build the record
        raw = f"{task}{datetime.datetime.now().isoformat()}"
        eid = "ev_" + hashlib.md5(raw.encode()).hexdigest()[:8]

        record = {
            "id": eid,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "task": task,
            "approach": approach,
            "tools_used": tools_used,
            "outcome": outcome,
            "lessons": lessons,
            "cost_seconds": cost_seconds,
            "keywords": kw,
            "schema_version": SCHEMA_VERSION,
        }
        record["checksum"] = _compute_checksum(record)

        # Load existing records for dedup check
        existing, _ = _load_records(path)

        # Dedup: if a very similar record exists, merge lessons
        new_token_set = _tokenize_set(task + " " + approach)
        merged_into: Optional[str] = None
        for rec in existing:
            rec_text = rec.get("task", "") + " " + rec.get("approach", "")
            rec_token_set = _tokenize_set(rec_text)
            sim = _jaccard(new_token_set, rec_token_set)
            if sim >= DEDUP_THRESHOLD:
                # Merge: add new lessons that aren't already present
                existing_lessons = set(rec.get("lessons", []))
                for lesson in lessons:
                    if lesson not in existing_lessons:
                        rec.setdefault("lessons", []).append(lesson)
                rec["checksum"] = _compute_checksum(rec)
                merged_into = rec.get("id")
                break

        if merged_into:
            # Rewrite the file with the merged record
            _atomic_write_all(path, existing)
            return {
                "status": "ok",
                "action": "merged",
                "merged_into": merged_into,
                "total_records": len(existing),
                "message": f"Record merged into existing entry {merged_into} (similarity >= {DEDUP_THRESHOLD}).",
            }

        # Not a duplicate — append new record
        _atomic_append(path, json.dumps(record, ensure_ascii=False))

        # Check if we need to archive
        all_records, _ = _load_records(path)
        remaining, archive_path = _maybe_archive(all_records)

        total = len(remaining)
        # Also count archived records
        archived_count = len(_load_archive_records()) if archive_path else 0

        msg = f"Lesson recorded. Knowledge base: {total} active"
        if archived_count:
            msg += f" + {archived_count} archived"
        msg += f" = {total + archived_count} total."

        if archive_path:
            msg += f" Auto-archived old records to {archive_path.name}."

        return {
            "status": "ok",
            "action": "recorded",
            "recorded_id": eid,
            "total_records": total,
            "archived_records": archived_count,
            "archive_path": str(archive_path) if archive_path else None,
            "message": msg,
        }

    # ── evolution_recall ──────────────────────────────────────────────────

    @tool(
        description=(
            "Recall past lessons relevant to an upcoming task. "
            "Returns top-N most similar past records using BM25"
            " ranking (replaces v1 TF-cosine). Searches both"
            " active and archived records."
        ),
        category="ai",
    )
    async def evolution_recall(
        self,
        task_description: str,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """Search the evolution log for records similar to the query.

        v2: Uses BM25 ranking instead of TF-cosine. Searches both
        the main log and gzip archives.
        """
        path = _evolution_path()

        # Load active records
        active_records, corrupt = _load_records(path)

        # Load archived records
        archive_records = _load_archive_records()

        all_records = active_records + archive_records

        if not all_records:
            return {
                "status": "ok",
                "total_records": 0,
                "results": [],
                "message": "No evolution records yet. The knowledge base starts with the first completed task.",
            }

        # Build BM25 index
        index = _BM25Index()
        for rec in all_records:
            index.add(rec)
        index.finalize()

        # Search
        scored = index.search(task_description, top_n=top_n)

        results = []
        for score, rec in scored:
            results.append({
                "id": rec.get("id"),
                "score": round(score, 4),
                "task": rec.get("task"),
                "approach": rec.get("approach"),
                "lessons": rec.get("lessons"),
                "tools_used": rec.get("tools_used"),
                "outcome": rec.get("outcome"),
            })

        msg = f"Found {len(results)} relevant past lessons from {len(all_records)} records"
        if corrupt:
            msg += f" ({corrupt} corrupt records skipped)"
        msg += "."

        return {
            "status": "ok",
            "total_records": len(all_records),
            "active_records": len(active_records),
            "archived_records": len(archive_records),
            "corrupt_records": corrupt,
            "query": task_description,
            "results": results,
            "message": msg,
        }

    # ── evolution_stats ───────────────────────────────────────────────────

    @tool(
        description="Get statistics about the evolution knowledge base (v2: includes archive stats).",
        category="ai",
    )
    async def evolution_stats(self) -> Dict[str, Any]:
        """Return stats about the evolution log."""
        path = _evolution_path()
        active_records, corrupt = _load_records(path)
        archive_records = _load_archive_records()

        total_cost = sum(r.get("cost_seconds", 0) for r in active_records + archive_records)
        by_outcome: Dict[str, int] = {}
        for r in active_records + archive_records:
            o = r.get("outcome", "unknown")
            by_outcome[o] = by_outcome.get(o, 0) + 1

        # Archive file stats
        archive_files = list(_archive_dir().glob("evolution_archive_*.jsonl.gz")) if _archive_dir().exists() else []
        archive_size = sum(f.stat().st_size for f in archive_files) if archive_files else 0

        # Snapshot stats
        snapshot_files = list(_snapshot_dir().glob("*.jsonl")) if _snapshot_dir().exists() else []

        return {
            "status": "ok",
            "total_records": len(active_records) + len(archive_records),
            "active_records": len(active_records),
            "archived_records": len(archive_records),
            "corrupt_records": corrupt,
            "file": str(path),
            "total_cost_seconds": total_cost,
            "by_outcome": by_outcome,
            "last_record": active_records[-1] if active_records else None,
            "archive_files": len(archive_files),
            "archive_size_bytes": archive_size,
            "snapshots": len(snapshot_files),
            "schema_version": SCHEMA_VERSION,
        }

    # ── evolution_clear ───────────────────────────────────────────────────

    @tool(
        description="Clear all evolution records. Use with caution.",
        category="ai",
    )
    async def evolution_clear(self, confirm: bool = False) -> Dict[str, Any]:
        """Wipe the evolution log. Requires confirm=True.

        v2: Also clears archives and snapshots (with confirm=True).
        """
        if not confirm:
            return {"status": "error", "error": "set confirm=True to clear the evolution log"}

        path = _evolution_path()
        if path.exists():
            path.unlink()

        # Clear archives
        if _archive_dir().exists():
            for f in _archive_dir().glob("evolution_archive_*.jsonl.gz"):
                f.unlink()

        # Clear snapshots
        if _snapshot_dir().exists():
            for f in _snapshot_dir().glob("*.jsonl"):
                f.unlink()

        # Clear corruption log
        cpath = _corruption_log_path()
        if cpath.exists():
            cpath.unlink()

        return {"status": "ok", "message": "Evolution log, archives, and snapshots cleared."}

    # ── evolution_export (NEW v2) ──────────────────────────────────────────

    @tool(
        description=(
            "Export all evolution records to a portable JSONL file. "
            "Includes both active and archived records. Useful for "
            "backup or migration to another machine."
        ),
        category="ai",
    )
    async def evolution_export(
        self,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export all records to a JSONL file."""
        path = _evolution_path()
        active_records, _ = _load_records(path)
        archive_records = _load_archive_records()
        all_records = active_records + archive_records

        if not all_records:
            return {"status": "ok", "exported": 0, "message": "No records to export."}

        if output_path is None:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(_evolution_dir() / f"evolution_export_{stamp}.jsonl")

        out = Path(output_path)
        _atomic_write_all(out, all_records)

        return {
            "status": "ok",
            "exported": len(all_records),
            "active": len(active_records),
            "archived": len(archive_records),
            "path": str(out),
            "message": f"Exported {len(all_records)} records to {out}.",
        }

    # ── evolution_import (NEW v2) ──────────────────────────────────────────

    @tool(
        description=(
            "Import evolution records from an external JSONL file. "
            "Validates checksums and deduplicates against existing "
            "records. Useful for restoring from backup or merging "
            "knowledge bases."
        ),
        category="ai",
    )
    async def evolution_import(
        self,
        input_path: str,
        merge: bool = True,
    ) -> Dict[str, Any]:
        """Import records from a JSONL file.

        Args:
            input_path: Path to the JSONL file to import.
            merge: If True, deduplicate against existing records.
                   If False, append all records as-is.
        """
        inp = Path(input_path)
        if not inp.exists():
            return {"status": "error", "error": f"File not found: {input_path}"}

        imported = 0
        skipped = 0
        merged = 0
        corrupt = 0

        path = _evolution_path()
        existing_records, _ = _load_records(path) if path.exists() else ([], 0)

        with open(inp, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    corrupt += 1
                    continue

                # Verify checksum if present
                if not _verify_checksum(rec):
                    corrupt += 1
                    continue

                # Ensure schema v2 fields
                if "schema_version" not in rec:
                    rec["schema_version"] = SCHEMA_VERSION
                    rec["checksum"] = _compute_checksum(rec)

                if merge:
                    # Check for duplicates
                    new_tokens = _tokenize_set(
                        rec.get("task", "") + " " + rec.get("approach", "")
                    )
                    is_dup = False
                    for existing in existing_records:
                        existing_tokens = _tokenize_set(
                            existing.get("task", "") + " " + existing.get("approach", "")
                        )
                        if _jaccard(new_tokens, existing_tokens) >= DEDUP_THRESHOLD:
                            is_dup = True
                            # Merge lessons
                            existing_lessons = set(existing.get("lessons", []))
                            for lesson in rec.get("lessons", []):
                                if lesson not in existing_lessons:
                                    existing.setdefault("lessons", []).append(lesson)
                            existing["checksum"] = _compute_checksum(existing)
                            merged += 1
                            break
                    if is_dup:
                        continue

                existing_records.append(rec)
                imported += 1

        # Write back
        _atomic_write_all(path, existing_records)

        # Maybe archive
        remaining, archive_path = _maybe_archive(existing_records)

        msg = f"Imported {imported} records"
        if merged:
            msg += f", merged {merged} duplicates"
        if skipped:
            msg += f", skipped {skipped}"
        if corrupt:
            msg += f", {corrupt} corrupt"
        msg += f". Total: {len(remaining)} active."
        if archive_path:
            msg += f" Auto-archived to {archive_path.name}."

        return {
            "status": "ok",
            "imported": imported,
            "merged": merged,
            "skipped": skipped,
            "corrupt": corrupt,
            "total_active": len(remaining),
            "archive_path": str(archive_path) if archive_path else None,
            "message": msg,
        }

    # ── evolution_rollback (NEW v2) ────────────────────────────────────────

    @tool(
        description=(
            "Roll back the evolution log to a previous snapshot. "
            "Lists available snapshots if no snapshot_path is given."
        ),
        category="ai",
    )
    async def evolution_rollback(
        self,
        snapshot_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Roll back to a snapshot."""
        snap_dir = _snapshot_dir()

        # List snapshots if none specified
        if snapshot_path is None:
            snapshots = sorted(snap_dir.glob("*.jsonl"), reverse=True)
            if not snapshots:
                return {"status": "ok", "message": "No snapshots available.", "snapshots": []}
            snap_list = [{"path": str(s), "name": s.name, "size": s.stat().st_size} for s in snapshots]
            return {
                "status": "ok",
                "message": f"Found {len(snap_list)} snapshots. Specify snapshot_path to roll back.",
                "snapshots": snap_list,
            }

        snap = Path(snapshot_path)
        if not snap.exists():
            return {"status": "error", "error": f"Snapshot not found: {snapshot_path}"}

        # Save current state as a pre-rollback snapshot
        path = _evolution_path()
        if path.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_rollback = snap_dir / f"pre_rollback_{stamp}.jsonl"
            current_records, _ = _load_records(path)
            _atomic_write_all(pre_rollback, current_records)

        # Restore from snapshot
        snap_records, _ = _load_records(snap)
        _atomic_write_all(path, snap_records)

        return {
            "status": "ok",
            "restored_from": str(snap),
            "record_count": len(snap_records),
            "message": f"Rolled back to {snap.name}. {len(snap_records)} records restored. Pre-rollback state saved as snapshot.",
        }

    # ── evolution_prune (NEW v2) ───────────────────────────────────────────

    @tool(
        description=(
            "Prune low-quality evolution records. Removes records "
            "where outcome=failure AND lessons is empty (they provide "
            "no reusable knowledge). Returns count of pruned records."
        ),
        category="ai",
    )
    async def evolution_prune(self, confirm: bool = False) -> Dict[str, Any]:
        """Remove low-value records from the evolution log."""
        path = _evolution_path()
        records, _ = _load_records(path)
        if not records:
            return {"status": "ok", "pruned": 0, "remaining": 0, "message": "No records to prune."}

        kept: List[Dict[str, Any]] = []
        pruned: List[Dict[str, Any]] = []
        for rec in records:
            outcome = rec.get("outcome", "").lower()
            lessons = rec.get("lessons", [])
            if outcome in ("failure", "failed", "error") and (not lessons or all(not l.strip() for l in lessons)):
                pruned.append(rec)
            else:
                kept.append(rec)

        if not pruned:
            return {
                "status": "ok",
                "pruned": 0,
                "remaining": len(records),
                "message": "No low-quality records found. Nothing to prune.",
            }

        if not confirm:
            return {
                "status": "ok",
                "would_prune": len(pruned),
                "remaining": len(kept),
                "message": f"Would prune {len(pruned)} low-quality records. Set confirm=True to execute.",
            }

        # Save snapshot before pruning
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snap_path = _snapshot_dir() / f"pre_prune_{stamp}.jsonl"
        _atomic_write_all(snap_path, records)

        # Write pruned set
        _atomic_write_all(path, kept)

        return {
            "status": "ok",
            "pruned": len(pruned),
            "remaining": len(kept),
            "snapshot": str(snap_path),
            "message": f"Pruned {len(pruned)} low-quality records. {len(kept)} remaining. Snapshot saved.",
        }


__all__ = ["SelfEvolutionWorker"]
