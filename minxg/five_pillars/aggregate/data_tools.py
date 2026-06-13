"""
minxg/data_tools.py - Data processing tools
JSON/CSV/XML/YAML/TOML parsing, validation, conversion.
CSV tools use C++ backend for performance.
""""
from __future__ import annotations
from typing import Dict, List, Any
import re
import json as _json
from minxg.base import BaseWorker, tool


_HAS_CPP = False
_cpp_csv_info = None
_cpp_csv_cell = None

try:
    from multiling import minxg_core as _mc
    if hasattr(_mc, 'csv_info') and hasattr(_mc, 'csv_cell'):
        _cpp_csv_info = _mc.csv_info
        _cpp_csv_cell = _mc.csv_cell
        _HAS_CPP = True
except ImportError:
    pass


class DataToolsWorker(BaseWorker):
    worker_id = "data_tools"
    version = "1.0.0"

    @tool(description="Validate JSON string and show error location", category="json")
    async def json_validate(self, text: str) -> Dict:
        try:
            data = _json.loads(text)
            return {"valid": True, "type": type(data).__name__, "keys": list(data.keys()) if isinstance(data, dict) else None}
        except _json.JSONDecodeError as e:
            return {"valid": False, "error": str(e), "line": e.lineno, "col": e.colno, "pos": e.pos}

    @tool(description="Pretty-print JSON output", category="json")
    async def json_pretty(self, text: str, indent: int = 2) -> Dict:
        try:
            data = _json.loads(text)
            pretty = _json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True)
            return {"pretty": pretty, "size": len(pretty)}
        except _json.JSONDecodeError as e:
            return {"error": str(e)}

    @tool(description="JsonPath query (dot notation)", category="json")
    async def json_query(self, text: str, path: str) -> Dict:
        try:
            data = _json.loads(text)
            parts = path.strip("$.").split(".")
            cur = data
            for p in parts:
                if isinstance(cur, list):
                    idx = int(p)
                    cur = cur[idx]
                elif isinstance(cur, dict):
                    cur = cur[p]
                else:
                    return {"error": f"cannot traverse into {type(cur).__name__} at '{p}'"}
            return {"result": cur, "type": type(cur).__name__, "path": path}
        except Exception as e:
            return {"error": str(e), "path": path}

    @tool(description="JSON Schema validation (basic type checks)", category="json")
    async def json_schema_validate(self, text: str, schema_str: str) -> Dict:
        try:
            data = _json.loads(text)
            schema = _json.loads(schema_str)
        except _json.JSONDecodeError as e:
            return {"error": f"parse error: {e}"}

        errors = []
        req = schema.get("required", [])
        props = schema.get("properties", {})
        s_type = schema.get("type", "object")

        if s_type == "object":
            for key in req:
                if key not in data:
                    errors.append(f"missing required key: {key}")
            for key, spec in props.items():
                if key in data:
                    expected = spec.get("type", "any")
                    actual = type(data[key]).__name__
                    type_map = {"str": "string", "int": "integer", "float": "number",
                                "bool": "boolean", "list": "array", "dict": "object"}
                    actual_mapped = type_map.get(actual, actual)
                    if expected != "any" and actual_mapped != expected:
                        errors.append(f"type mismatch at '{key}': expected {expected}, got {actual_mapped}")

        return {"valid": len(errors) == 0, "errors": errors, "count": len(errors)}

    @tool(description="Convert JSON to CSV", category="convert")
    async def json_to_csv(self, text: str) -> Dict:
        try:
            data = _json.loads(text)
            if isinstance(data, list) and data:
                headers = list(data[0].keys())
                rows = [",".join(headers)]
                for item in data:
                    rows.append(",".join(str(item.get(h, "")) for h in headers))
                return {"csv": "\n".join(rows), "rows": len(data), "headers": headers}
            elif isinstance(data, dict):
                rows = ["key,value"]
                for k, v in data.items():
                    rows.append(f"{k},{v}")
                return {"csv": "\n".join(rows), "rows": len(data)}
            return {"error": "unsupported JSON structure"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Parse CSV to JSON array", category="csv")
    async def csv_parse(self, text: str, delimiter: str = ",", has_header: bool = True) -> Dict:
        import csv, io
        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return {"error": "empty CSV"}
            if has_header:
                headers = rows[0]
                data = [dict(zip(headers, row)) for row in rows[1:]]
            else:
                data = [{"col" + str(i): v for i, v in enumerate(row)} for row in rows]
            return {"json": _json.dumps(data, ensure_ascii=False), "rows": len(data), "columns": len(data[0]) if data else 0}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="CSV column statistics (count/unique/empty)", category="csv")
    async def csv_stats(self, text: str) -> Dict:
        import csv, io
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return {"error": "need header + at least 1 row"}
        headers = rows[0]
        cols = {h: [] for h in headers}
        for row in rows[1:]:
            for i, h in enumerate(headers):
                cols[h].append(row[i] if i < len(row) else "")
        stats = {}
        for h, values in cols.items():
            stats[h] = {
                "count": len(values), "unique": len(set(values)),
                "empty": sum(1 for v in values if not v.strip()),
                "sample": list(set(values))[:5],
            }
        return {"columns": len(headers), "row_count": len(rows)-1, "stats": stats}

    @tool(description="Get CSV file info (rows, columns, headers, size) via C++", category="csv")
    async def csv_info(self, path: str) -> Dict:
        """CSV file metadata via C++ backend. Falls back to Python stdlib.""""
        if _HAS_CPP:
            try:
                result = _cpp_csv_info(path)
                return result
            except Exception as e:
                pass
        
        import os, csv
        size = os.path.getsize(path) if os.path.exists(path) else 0
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return {"rows": 0, "columns": 0, "headers": [], "size": size}
        headers = rows[0]
        return {
            "rows": len(rows) - 1,
            "columns": len(headers),
            "headers": headers,
            "size": size,
        }

    @tool(description="Get CSV cell value by row/column index via C++", category="csv")
    async def csv_cell(self, path: str, row: int, col: int | str) -> Dict:
        """Get a specific cell from CSV file. C++ backend if available.""""
        if _HAS_CPP:
            try:
                
                if isinstance(col, str):
                    
                    with open(path, newline="", encoding="utf-8", errors="replace") as f:
                        import csv
                        reader = csv.reader(f)
                        headers = next(reader, [])
                        if col in headers:
                            col = headers.index(col)
                        else:
                            return {"error": f"column not found: {col}"}
                result = _cpp_csv_cell(path, row, col)
                return result
            except Exception as e:
                pass
        
        import csv
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
        try:
            value = rows[row][col]
            return {"value": value, "row": row, "col": col}
        except IndexError:
            return {"error": f"cell out of bounds: row={row}, col={col}"}

    @tool(description="Parse XML to simplified dict", category="xml")
    async def xml_parse(self, text: str) -> Dict:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            def _parse(el):
                result = {"tag": el.tag, "attrs": dict(el.attrib)}
                children = [_parse(c) for c in el]
                if children:
                    result["children"] = children
                elif el.text and el.text.strip():
                    result["text"] = el.text.strip()
                return result
            return {"root": _parse(root)}
        except ImportError:
            return {"error": "xml.etree not available"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Convert YAML to JSON", category="yaml")
    async def yaml_to_json(self, text: str) -> Dict:
        try:
            import yaml
            data = yaml.safe_load(text)
            return {"json": _json.dumps(data, ensure_ascii=False), "type": type(data).__name__}
        except ImportError:
            return {"error": "PyYAML not installed", "hint": "pip install pyyaml"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Parse TOML to JSON", category="toml")
    async def toml_parse(self, text: str) -> Dict:
        try:
            import sys, os
            if sys.version_info >= (3, 11):
                import tomllib
                data = tomllib.loads(text)
            else:
                try:
                    import tomli
                    data = tomli.loads(text)
                except ImportError:
                    return {"error": "tomli not installed", "hint": "pip install tomli"}
            return {"json": _json.dumps(data, ensure_ascii=False), "type": type(data).__name__}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Deduplicate data by field", category="clean")
    async def deduplicate(self, json_text: str, by_key: str = "") -> Dict:
        try:
            data = _json.loads(json_text)
            if not isinstance(data, list):
                return {"error": "input must be a JSON array", "original": len(str(data))}
            if by_key:
                seen = set()
                result = []
                for item in data:
                    key = str(item.get(by_key, ""))
                    if key not in seen:
                        seen.add(key)
                        result.append(item)
            else:
                seen, result = [], []
                for item in data:
                    s = _json.dumps(item, sort_keys=True)
                    if s not in seen:
                        seen.append(s)
                        result.append(item)
            return {"original_count": len(data), "deduplicated_count": len(result), "removed": len(data)-len(result)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Sample data randomly or by position", category="sample")
    async def sample_data(self, json_text: str, count: int = 10, method: str = "first") -> Dict:
        try:
            data = _json.loads(json_text)
            if not isinstance(data, list):
                return {"error": "input must be array"}
            import random
            if method == "random":
                sample = random.sample(data, min(count, len(data)))
            elif method == "last":
                sample = data[-count:]
            else:
                sample = data[:count]
            return {"sample": sample, "total": len(data), "sampled": len(sample), "method": method}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Sort data by key", category="sort")
    async def sort_data(self, json_text: str, by_key: str = "", reverse: bool = False) -> Dict:
        try:
            data = _json.loads(json_text)
            if not isinstance(data, list):
                return {"error": "input must be array"}
            if by_key:
                sorted_data = sorted(data, key=lambda x: x.get(by_key, ""), reverse=reverse)
            else:
                sorted_data = sorted(data, reverse=reverse)
            return {"sorted": sorted_data, "count": len(sorted_data), "by_key": by_key}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Group data by key (GROUP BY)", category="group")
    async def group_by(self, json_text: str, by_key: str) -> Dict:
        try:
            data = _json.loads(json_text)
            if not isinstance(data, list):
                return {"error": "input must be array"}
            groups: Dict[str, list] = {}
            for item in data:
                key = str(item.get(by_key, "null"))
                if key not in groups:
                    groups[key] = []
                groups[key].append(item)
            return {"groups": {k: len(v) for k, v in groups.items()}, "total_groups": len(groups), "by_key": by_key}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Filter data with simple conditions", category="filter")
    async def filter_data(self, json_text: str, field: str, operator: str, value: str) -> Dict:
        try:
            data = _json.loads(json_text)
            if not isinstance(data, list):
                return {"error": "input must be array"}
            ops = {
                "eq": lambda a, b: a == b,
                "ne": lambda a, b: a != b,
                "gt": lambda a, b: float(a) > float(b) if a and b else False,
                "lt": lambda a, b: float(a) < float(b) if a and b else False,
                "contains": lambda a, b: b.lower() in str(a).lower(),
                "starts": lambda a, b: str(a).lower().startswith(b.lower()),
            }
            fn = ops.get(operator)
            if not fn:
                return {"error": f"unknown operator: {operator}", "available": list(ops.keys())}
            result = [item for item in data if field in item and fn(str(item[field]), value)]
            return {"filtered": result, "original": len(data), "matched": len(result)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Convert Markdown table to JSON", category="table")
    async def table_convert(self, text: str, direction: str = "md_to_json") -> Dict:
        if direction == "md_to_json":
            lines = text.strip().split("\n")
            if len(lines) < 2:
                return {"error": "need header + separator row"}
            headers = [h.strip() for h in lines[0].strip("|").split("|")]
            rows = []
            for line in lines[2:]:
                if line.strip():
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if len(cells) == len(headers):
                        rows.append(dict(zip(headers, cells)))
            return {"json": _json.dumps(rows, ensure_ascii=False), "rows": len(rows), "columns": len(headers)}
        else:
            return {"error": "only md_to_json supported"}

    @tool(description="Regex pattern extraction", category="regex")
    async def regex_extract(self, text: str, pattern: str, group: int = 0) -> Dict:
        matches = re.findall(pattern, text)
        if matches:
            if isinstance(matches[0], tuple) and group > 0:
                results = [m[group - 1] for m in matches if len(m) >= group]
            else:
                results = matches
            return {"matches": results[:50], "count": len(results), "pattern": pattern}
        return {"matches": [], "count": 0, "pattern": pattern}

    @tool(description="Split text by length/lines/delimiter", category="split")
    async def split_text(self, text: str, method: str = "lines", size: int = 100) -> Dict:
        if method == "lines":
            lines = text.split("\n")
            chunks = ["\n".join(lines[i:i+size]) for i in range(0, len(lines), size)]
        elif method == "chars":
            chunks = [text[i:i+size] for i in range(0, len(text), size)]
        elif method == "delimiter":
            parts = str(text).split(str(size))
            chunks = parts
        else:
            return {"error": f"unknown method: {method}"}
        return {"chunks": len(chunks), "method": method, "texts": chunks}
