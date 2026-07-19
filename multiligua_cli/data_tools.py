"""
multiligua_cli/data_tools.py — Data Processing Tools

Tools for data manipulation: CSV, JSON, XML, YAML processing,
data validation, transformation, and analysis.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional, Union


class DataToolsWorker:
    """Data processing and manipulation tools."""

    worker_id = "data_tools"
    version = "0.19.0"
    tier = "code"

    def __init__(self):
        self.tools = {}
        self._register_tools()

    # ─── CSV Operations ──────────────────────────────────────────────────

    def csv_read(
        self,
        csv_path: str,
        delimiter: str = ",",
        header: bool = True,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Read CSV file and return as list of dicts."""
        try:
            import csv

            rows = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=delimiter) if header else csv.reader(f, delimiter=delimiter)
                for i, row in enumerate(reader):
                    if i >= limit:
                        break
                    rows.append(dict(row) if header else row)

            return {
                "status": "ok",
                "rows": len(rows),
                "data": rows,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def csv_write(
        self,
        data: List[Dict[str, Any]],
        output_path: str,
        delimiter: str = ",",
    ) -> Dict[str, Any]:
        """Write list of dicts to CSV file."""
        try:
            import csv

            if not data:
                return {"status": "error", "error": "Empty data"}

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys(), delimiter=delimiter)
                writer.writeheader()
                writer.writerows(data)

            return {
                "status": "ok",
                "rows_written": len(data),
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def csv_to_json(
        self,
        csv_path: str,
        output_path: str,
        delimiter: str = ",",
    ) -> Dict[str, Any]:
        """Convert CSV to JSON."""
        try:
            import csv
            import json

            data = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    data.append(dict(row))

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {
                "status": "ok",
                "rows": len(data),
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def csv_stats(
        self,
        csv_path: str,
        delimiter: str = ",",
    ) -> Dict[str, Any]:
        """Get CSV statistics."""
        try:
            import csv

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)

            if not rows:
                return {"status": "error", "error": "Empty CSV"}

            columns = list(rows[0].keys())
            stats = {
                "rows": len(rows),
                "columns": len(columns),
                "column_names": columns,
                "column_stats": {},
            }

            for col in columns:
                values = [row[col] for row in rows]
                col_stats = {
                    "non_empty": sum(1 for v in values if v),
                    "empty": sum(1 for v in values if not v),
                }

                # Try numeric stats
                try:
                    nums = [float(v) for v in values if v]
                    if nums:
                        col_stats.update({
                            "min": min(nums),
                            "max": max(nums),
                            "sum": sum(nums),
                            "avg": sum(nums) / len(nums),
                        })
                except ValueError:
                    pass

                stats["column_stats"][col] = col_stats

            return {"status": "ok", "stats": stats}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── JSON Operations ─────────────────────────────────────────────────

    def json_read(self, json_path: str) -> Dict[str, Any]:
        """Read JSON file."""
        try:
            import json

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return {"status": "ok", "data": data, "type": type(data).__name__}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def json_write(
        self,
        data: Any,
        output_path: str,
        indent: int = 2,
    ) -> Dict[str, Any]:
        """Write data to JSON file."""
        try:
            import json

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            return {"status": "ok", "output": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def json_query(
        self,
        json_path: str,
        query: str,
    ) -> Dict[str, Any]:
        """Query JSON data using simple path notation."""
        try:
            import json

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Simple path query (e.g., "users.0.name")
            parts = query.split(".")
            current = data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        current = current[int(part)]
                    except (ValueError, IndexError):
                        return {"status": "error", "error": f"Invalid index: {part}"}
                else:
                    return {"status": "error", "error": f"Cannot access '{part}' on {type(current).__name__}"}

            return {"status": "ok", "result": current}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def json_merge(
        self,
        input_paths: List[str],
        output_path: str,
        merge_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge multiple JSON files."""
        try:
            import json

            merged = []
            for path in input_paths:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        merged.extend(data)
                    else:
                        merged.append(data)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)

            return {
                "status": "ok",
                "files_merged": len(input_paths),
                "total_items": len(merged),
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── YAML Operations ─────────────────────────────────────────────────

    def yaml_read(self, yaml_path: str) -> Dict[str, Any]:
        """Read YAML file."""
        try:
            import yaml

            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            return {"status": "ok", "data": data}
        except ImportError:
            return {"status": "error", "error": "PyYAML not installed. pip install pyyaml"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def yaml_write(
        self,
        data: Any,
        output_path: str,
    ) -> Dict[str, Any]:
        """Write data to YAML file."""
        try:
            import yaml

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            return {"status": "ok", "output": output_path}
        except ImportError:
            return {"status": "error", "error": "PyYAML not installed. pip install pyyaml"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def yaml_to_json(
        self,
        yaml_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Convert YAML to JSON."""
        try:
            import yaml
            import json

            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {"status": "ok", "output": output_path}
        except ImportError:
            return {"status": "error", "error": "PyYAML not installed. pip install pyyaml"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── XML Operations ──────────────────────────────────────────────────

    def xml_read(self, xml_path: str) -> Dict[str, Any]:
        """Read XML file and return as dict."""
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(xml_path)
            root = tree.getroot()

            def element_to_dict(elem):
                d = {elem.tag: {} if elem.attrib else None}
                children = list(elem)
                if children:
                    dd = {}
                    for dc in map(element_to_dict, children):
                        for k, v in dc.items():
                            if k in dd:
                                if not isinstance(dd[k], list):
                                    dd[k] = [dd[k]]
                                dd[k].append(v)
                            else:
                                dd[k] = v
                    d = {elem.tag: dd}
                if elem.attrib:
                    d[elem.tag].update(('@' + k, v) for k, v in elem.attrib.items())
                if elem.text:
                    text = elem.text.strip()
                    if children or elem.attrib:
                        d[elem.tag]['#text'] = text
                    else:
                        d[elem.tag] = text
                return d

            return {"status": "ok", "data": element_to_dict(root)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def xml_to_json(
        self,
        xml_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Convert XML to JSON."""
        try:
            import xml.etree.ElementTree as ET
            import json

            tree = ET.parse(xml_path)
            root = tree.getroot()

            def element_to_dict(elem):
                d = {}
                if elem.attrib:
                    d.update(('@' + k, v) for k, v in elem.attrib.items())
                children = list(elem)
                if children:
                    dd = {}
                    for dc in map(element_to_dict, children):
                        for k, v in dc.items():
                            if k in dd:
                                if not isinstance(dd[k], list):
                                    dd[k] = [dd[k]]
                                dd[k].append(v)
                            else:
                                dd[k] = v
                    d.update(dd)
                if elem.text:
                    text = elem.text.strip()
                    if children or elem.attrib:
                        d['#text'] = text
                    else:
                        return text
                return {elem.tag: d} if d else elem.tag

            data = element_to_dict(root)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {"status": "ok", "output": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Data Validation ─────────────────────────────────────────────────

    def validate_json(self, json_path: str) -> Dict[str, Any]:
        """Validate JSON syntax."""
        try:
            import json

            with open(json_path, "r", encoding="utf-8") as f:
                json.load(f)

            return {"status": "ok", "valid": True}
        except json.JSONDecodeError as e:
            return {"status": "error", "valid": False, "error": str(e), "line": e.lineno, "col": e.colno}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def validate_yaml(self, yaml_path: str) -> Dict[str, Any]:
        """Validate YAML syntax."""
        try:
            import yaml

            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)

            return {"status": "ok", "valid": True}
        except yaml.YAMLError as e:
            return {"status": "error", "valid": False, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Data Transformation ─────────────────────────────────────────────

    def filter_rows(
        self,
        csv_path: str,
        output_path: str,
        column: str,
        value: Any,
        operator: str = "eq",
    ) -> Dict[str, Any]:
        """Filter CSV rows by column value."""
        try:
            import csv

            ops = {
                "eq": lambda a, b: a == b,
                "ne": lambda a, b: a != b,
                "gt": lambda a, b: float(a) > float(b),
                "lt": lambda a, b: float(a) < float(b),
                "ge": lambda a, b: float(a) >= float(b),
                "le": lambda a, b: float(a) <= float(b),
                "contains": lambda a, b: b in a,
                "startswith": lambda a, b: a.startswith(b),
                "endswith": lambda a, b: a.endswith(b),
            }

            if operator not in ops:
                return {"status": "error", "error": f"Unknown operator: {operator}"}

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [row for row in reader if ops[operator](row.get(column, ""), str(value))]

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            return {
                "status": "ok",
                "matched_rows": len(rows),
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def sort_data(
        self,
        csv_path: str,
        output_path: str,
        columns: List[str],
        reverse: bool = False,
    ) -> Dict[str, Any]:
        """Sort CSV data by columns."""
        try:
            import csv

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                fieldnames = reader.fieldnames

            rows.sort(key=lambda r: tuple(r.get(c, "") for c in columns), reverse=reverse)

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            return {"status": "ok", "rows_sorted": len(rows), "output": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Tool Registration ───────────────────────────────────────────────

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "csv_read": {"description": "Read CSV file", "category": "csv"},
            "csv_write": {"description": "Write CSV file", "category": "csv"},
            "csv_to_json": {"description": "Convert CSV to JSON", "category": "convert"},
            "csv_stats": {"description": "CSV statistics", "category": "csv"},
            "json_read": {"description": "Read JSON file", "category": "json"},
            "json_write": {"description": "Write JSON file", "category": "json"},
            "json_query": {"description": "Query JSON data", "category": "json"},
            "json_merge": {"description": "Merge JSON files", "category": "json"},
            "yaml_read": {"description": "Read YAML file", "category": "yaml"},
            "yaml_write": {"description": "Write YAML file", "category": "yaml"},
            "yaml_to_json": {"description": "Convert YAML to JSON", "category": "convert"},
            "xml_read": {"description": "Read XML file", "category": "xml"},
            "xml_to_json": {"description": "Convert XML to JSON", "category": "convert"},
            "validate_json": {"description": "Validate JSON", "category": "validate"},
            "validate_yaml": {"description": "Validate YAML", "category": "validate"},
            "filter_rows": {"description": "Filter CSV rows", "category": "transform"},
            "sort_data": {"description": "Sort CSV data", "category": "transform"},
        }
