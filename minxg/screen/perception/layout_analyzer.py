"""minxg.screen.perception.layout_analyzer — UI understanding from layout + OCR.

Combines UIAutomator XML + OCR text to produce a structured description
AI can reason about. This is the CORE capability that lets AI "understand"
what's on screen without needing a vision model.
"""
from __future__ import annotations

import time
import re
from pathlib import Path
from typing import Optional, List, Dict
from ..constants import LayoutFormat, thresholds, bounds_to_rect


def parse_uiautomator_xml(xml_text: str) -> List[Dict]:
    """Parse UIAutomator XML node tree into structured dicts.

    Returns a list of {class, text, content_desc, res_id, bounds, clickable,
    scrollable, enabled, checked, selected, children: [...]}
    """
    nodes = []
    # Simple regex-based parser — no xml.dom dependency for speed
    # Each <node ... /> attr string
    node_pattern = re.compile(r'<node\s+([^>]+)/>')

    for match in node_pattern.finditer(xml_text):
        attr_str = match.group(1)
        attrs = {}
        for a_match in re.finditer(r'(\w[\w-]*)\s*=\s*"([^"]*)"', attr_str):
            attrs[a_match.group(1)] = a_match.group(2)

        nodes.append({
            "class": attrs.get("class", ""),
            "text": attrs.get("text", ""),
            "content_desc": attrs.get("content-desc", ""),
            "res_id": attrs.get("resource-id", ""),
            "bounds_raw": attrs.get("bounds", ""),
            "clickable": attrs.get("clickable", "false") == "true",
            "scrollable": attrs.get("scrollable", "false") == "true",
            "enabled": attrs.get("enabled", "true") == "true",
            "checked": attrs.get("checked", "false") == "true",
            "selected": attrs.get("selected", "false") == "true",
            "focusable": attrs.get("focusable", "false") == "true",
            "bounds": bounds_to_rect(attrs.get("bounds", "")) or {},
        })

    return nodes


def merge_xml_and_ocr(
    xml_nodes: List[Dict],
    ocr_words: List[Dict],
    ocr_lines: List[Dict],
) -> List[Dict]:
    """Merge UIAutomator XML with OCR results.

    Strategy:
    - XML nodes with text → trust XML text (authoritative)
    - XML nodes with content-desc but no text → use content-desc
    - XML nodes with neither text nor content-desc → look for nearby OCR words
    - OCR-only words (no XML match) → report as "unlabeled_text"
    """
    merged = []
    ocr_used = set()

    for node in xml_nodes:
        n = dict(node)
        # Prefer XML text
        label = n.get("text") or n.get("content_desc", "")

        if label:
            n["label"] = label
        else:
            # Try to match nearby OCR words by bounding box overlap
            nb = n.get("bounds", {})
            if nb:
                cx = nb.get("center_x", 0)
                cy = nb.get("center_y", 0)
                nearby = []
                for i, w in enumerate(ocr_words):
                    if i in ocr_used:
                        continue
                    wb = w.get("bbox", {})
                    if wb and abs(wb.get("center_x", 0) - cx) < 100 and abs(wb.get("center_y", 0) - cy) < 50:
                        nearby.append(w["text"])
                        ocr_used.add(i)
                n["label"] = " ".join(nearby) if nearby else ""
            else:
                n["label"] = ""

        n["data_source"] = "xml+ocr" if label or ocr_used else "xml"
        merged.append(n)

    # Remaining OCR-only words
    for i, w in enumerate(ocr_words):
        if i not in ocr_used:
            merged.append({
                "class": "ocr_only",
                "text": w["text"],
                "label": w["text"],
                "content_desc": "",
                "clickable": False,
                "bounds": w.get("bbox", {}),
                "data_source": "ocr_only",
                "conf": w.get("conf", 0),
            })

    return merged


def build_screen_description(merged_elements: List[Dict], screen_size: Dict) -> str:
    """Build a human-readable + AI-structured description of the screen.

    Output format:
      === Screen: {width}x{height} ({n_elements} elements) ===

      STATUSBAR:
        "9:41  100%  WiFi" (bounds ...)

      ELEMENTS:
        [Button] "Confirm" — bounds [40,200,1040,280], clickable ✓
        [TextView] "Welcome" — bounds [80,400,300,440]
        [EditText] (empty) — bounds [40,800,1040,860], focusable ✓
        ...

      OCR-ONLY:
        (no label)
        "Type a command..."  bounds [40,1080,900,1140], conf=92%
    """
    w = screen_size.get("w", 0)
    h = screen_size.get("h", 0)
    lines = [f"=== Screen: {w}x{h} ({len(merged_elements)} elements) ===", ""]

    # Categorize elements
    status = [e for e in merged_elements if e.get("class", "").lower().startswith("statusbar")]
    elements = [e for e in merged_elements if e not in status and e.get("data_source") != "ocr_only"]
    ocr_only = [e for e in merged_elements if e.get("data_source") == "ocr_only"]

    if status:
        lines.append("STATUS_BAR:")
        for e in status:
            label = e.get("label", "") or e.get("text", "")
            if label:
                lines.append(f'  "{label}"')
        lines.append("")

    lines.append("SCREEN_ELEMENTS:")
    for e in elements:
        cls = e.get("class", "unknown").split(".")[-1]
        label = e.get("label", "") or e.get("text", "")
        bnd = e.get("bounds", {})

        type_tag = cls
        if e.get("clickable"):
            type_tag += " [TAPPABLE]"
        if e.get("scrollable"):
            type_tag += " [SCROLLABLE]"
        if e.get("checked"):
            type_tag += " [CHECKED]"

        bnd_str = ""
        if bnd:
            bnd_str = f" bounds [{bnd.get('left',0)},{bnd.get('top',0)},"
            bnd_str += f"{bnd.get('right',0)},{bnd.get('bottom',0)}]"

        if label:
            lines.append(f'  [{type_tag}] "{label}"{bnd_str}')
        else:
            lines.append(f'  [{type_tag}] (no label){bnd_str}')

    if ocr_only:
        lines.append("")
        lines.append("OCR_ONLY_TEXT (trusted but with no UI element):")
        for e in ocr_only[:20]:  # limit
            label = e.get("label", "")
            conf = e.get("conf", "")
            bnd = e.get("bounds", {})
            bnd_str = f" bounds [{bnd.get('left',0)},{bnd.get('top',0)},"
            bnd_str += f"{bnd.get('right',0)},{bnd.get('bottom',0)}]" if bnd else ""
            conf_str = f", conf={conf}%" if conf else ""
            lines.append(f'  "{label}"{bnd_str}{conf_str}')

    return "\n".join(lines)


def find_tappable_elements(elements: List[Dict], *, search_text: str = "") -> List[Dict]:
    """Find elements that are clickable, optionally filtered by text match."""
    tappable = [e for e in elements if e.get("clickable") and e.get("enabled", True)]
    if search_text:
        tappable = [e for e in tappable if search_text.lower() in
                    (e.get("label", "") or e.get("text", "") or "").lower()]
    return tappable


def find_text_elements(elements: List[Dict], *, search_text: str = "") -> List[Dict]:
    """Find elements containing a specific text string."""
    if not search_text:
        return [e for e in elements if e.get("label") or e.get("text")]
    return [e for e in elements if search_text.lower() in
            (e.get("label", "") or e.get("text", "") or "").lower()]


__all__ = [
    "parse_uiautomator_xml", "merge_xml_and_ocr", "build_screen_description",
    "find_tappable_elements", "find_text_elements",
]
