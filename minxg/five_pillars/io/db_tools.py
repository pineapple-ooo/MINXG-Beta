"""
"""
from __future__ import annotations
from typing import Dict, List
import sqlite3
import json as _json
from minxg.base import BaseWorker, tool


class DbToolsWorker(BaseWorker):
    worker_id = "db_tools"
    tier = "code"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="Open SQLite database and return info", category="sqlite")
    async def sqlite_info(self, path: str) -> Dict:
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return {"path": path, "tables": tables, "table_count": len(tables)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Execute SQL query (read-only SELECT)", category="sqlite")
    async def sqlite_query(self, path: str, sql: str) -> Dict:
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return {"rows": rows, "row_count": len(rows), "sql": sql}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Get SQLite table schema", category="sqlite")
    async def sqlite_schema(self, path: str, table: str) -> Dict:
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = [{"name": r[1], "type": r[2], "nullable": not r[3], "pk": bool(r[5])} for r in cur.fetchall()]
            conn.close()
            return {"table": table, "columns": cols, "column_count": len(cols)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Execute SQL INSERT/UPDATE/DELETE", category="sqlite")
    async def sqlite_execute(self, path: str, sql: str, params: list = None) -> Dict:
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute(sql, params or [])
            conn.commit()
            affected = cur.rowcount
            conn.close()
            return {"affected_rows": affected, "last_rowid": cur.lastrowid, "sql": sql}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Build SQL SELECT statement", category="build")
    async def build_select(self, table: str, columns: str = "*",
                            where: str = "", order_by: str = "", limit: int = 0) -> Dict:
        parts = [f"SELECT {columns} FROM {table}"]
        if where:
            parts.append(f"WHERE {where}")
        if order_by:
            parts.append(f"ORDER BY {order_by}")
        if limit:
            parts.append(f"LIMIT {limit}")
        sql = " ".join(parts)
        return {"sql": sql, "table": table}

    @tool(description="Build SQL INSERT statement", category="build")
    async def build_insert(self, table: str, data: dict) -> Dict:
        keys = list(data.keys())
        placeholders = ["?" for _ in keys]
        sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join(placeholders)})"
        return {"sql": sql, "params": list(data.values()), "table": table}

    @tool(description="JSON file as key-value store query", category="kv")
    async def kv_get(self, path: str, key: str) -> Dict:
        try:
            with open(path, "r") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                value = data.get(key)
                return {"key": key, "value": value, "found": key in data}
            return {"error": "file content is not a dict"}
        except FileNotFoundError:
            return {"key": key, "value": None, "found": False}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="JSON key-value write", category="kv")
    async def kv_set(self, path: str, key: str, value: str) -> Dict:
        try:
            try:
                with open(path, "r") as f:
                    data = _json.load(f)
            except FileNotFoundError:
                data = {}
            if not isinstance(data, dict):
                return {"error": "file content is not a dict"}
            data[key] = value
            with open(path, "w") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            return {"key": key, "value": value, "total_keys": len(data)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="JSON key-value delete", category="kv")
    async def kv_delete(self, path: str, key: str) -> Dict:
        try:
            with open(path, "r") as f:
                data = _json.load(f)
            removed = key in data
            data.pop(key, None)
            with open(path, "w") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            return {"key": key, "removed": removed, "total_keys": len(data)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="JSON key-value list all keys", category="kv")
    async def kv_keys(self, path: str) -> Dict:
        try:
            with open(path, "r") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                return {"keys": list(data.keys()), "count": len(data)}
            return {"error": "not a dict"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="KV batch write", category="kv")
    async def kv_batch_set(self, path: str, items: dict) -> Dict:
        try:
            try:
                with open(path, "r") as f:
                    data = _json.load(f)
            except FileNotFoundError:
                data = {}
            data.update(items)
            with open(path, "w") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            return {"updated": len(items), "total_keys": len(data)}
        except Exception as e:
            return {"error": str(e)}
