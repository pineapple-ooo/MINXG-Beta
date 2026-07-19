"""minxg.screen.perception.element_index — Fuzz-matchable UI element index.

Converts UIAutomator XML + OCR into a searchable index so AI can ask
"where is the login button?" and get coordinates back without vision models.
Supports: text search, fuzzy search, class filter, bounds filter, clickable only.
"""
from __future__ import annotations
import difflib
import re
from typing import Any, Dict, List, Optional

from .layout_analyzer import (
    parse_uiautomator_xml,
    merge_xml_and_ocr,
    build_screen_description,
)
from ..constants import bounds_to_rect


class ElementIndex:
    """Searchable index over screen elements.

    Build once per screen capture, then query multiple times.
    """

    __slots__ = (
        "_elements", "_by_class", "_by_clickable",
        "_screen_w", "_screen_h", "_raw_xml", "_ocr_words", "_ocr_lines",
    )

    def __init__(
        self,
        elements: List[Dict],
        raw_xml: str = "",
        ocr_words: Optional[List[Dict]] = None,
        ocr_lines: Optional[List[Dict]] = None,
        screen_w: int = 0,
        screen_h: int = 0,
    ) -> None:
        self._elements = elements
        self._raw_xml = raw_xml
        self._ocr_words = ocr_words or []
        self._ocr_lines = ocr_lines or []
        self._screen_w = screen_w
        self._screen_h = screen_h

        # Rebuild indexes on every mutation
        self._by_class: Dict[str, List[Dict]] = {}
        self._by_clickable: List[Dict] = []
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._by_class.clear()
        self._by_clickable.clear()
        for el in self._elements:
            cls = el.get("class", "").split(".")[-1].lower()
            self._by_class.setdefault(cls, []).append(el)
            if el.get("clickable") and el.get("enabled", True):
                self._by_clickable.append(el)

    # ── Search API ──────────────────────────────────────────────

    def find_by_text(
        self,
        text: str,
        *,
        fuzzy: bool = True,
        threshold: float = 0.6,
        clickable_only: bool = False,
    ) -> List[Dict]:
        """Find elements whose label/text matches `text`.

        fuzzy=True uses difflib SequenceMatcher; exact match always wins.
        Returns list sorted by match score descending.
        """
        pool = self._by_clickable if clickable_only else self._elements
        results = []
        tl = text.lower()
        for el in pool:
            label = (el.get("label") or el.get("text") or el.get("content_desc") or "").lower()
            if not label:
                continue
            # Exact match
            if tl == label:
                score = 1.0
            elif tl in label:
                score = 0.95
            elif fuzzy:
                score = difflib.SequenceMatcher(None, tl, label).ratio()
            else:
                score = 0.0
            if score >= threshold:
                entry = dict(el)
                entry["_match_score"] = round(score, 4)
                results.append(entry)
        results.sort(key=lambda e: e["_match_score"], reverse=True)
        return results

    def find_by_class(self, class_name: str) -> List[Dict]:
        """Find all elements of a given class (e.g. 'Button', 'EditText')."""
        cls = class_name.lower()
        # Try exact class suffix match first, then broader match
        hits = self._by_class.get(cls, [])
        if not hits:
            hits = [e for e in self._elements if cls in e.get("class", "").lower()]
        return hits

    def find_in_bounds(
        self,
        left: int, top: int, right: int, bottom: int,
        *,
        intersect: bool = True,
    ) -> List[Dict]:
        """Find elements whose bounding box intersects the given region."""
        hits = []
        for el in self._elements:
            b = el.get("bounds", {})
            if not b:
                continue
            el_l, el_t = b.get("left", 0), b.get("top", 0)
            el_r, el_b = b.get("right", 0), b.get("bottom", 0)
            if intersect:
                ok = not (el_r < left or el_l > right or el_b < top or el_t > bottom)
            else:
                ok = (el_l >= left and el_t >= top and el_r <= right and el_b <= bottom)
            if ok:
                hits.append(el)
        return hits

    def find_clickable(self, *, text_filter: str = "") -> List[Dict]:
        """All tappable elements, optionally filtered by text prefix match."""
        pool = self._by_clickable
        if text_filter:
            tfl = text_filter.lower()
            pool = [e for e in pool if tfl in
                    (e.get("label") or e.get("text") or "").lower()]
        return pool

    def find_ocr_words(self, text: str, *, fuzzy: bool = True, threshold: float = 0.6) -> List[Dict]:
        """Find OCR-recognized words matching `text`."""
        if not self._ocr_words:
            return []
        tl = text.lower()
        results = []
        for w in self._ocr_words:
            wt = w.get("text", "").lower()
            if not wt:
                continue
            if tl == wt:
                score = 1.0
            elif fuzzy:
                score = difflib.SequenceMatcher(None, tl, wt).ratio()
            else:
                score = 0.0
            if score >= threshold:
                entry = dict(w)
                entry["_match_score"] = round(score, 4)
                results.append(entry)
        results.sort(key=lambda e: e["_match_score"], reverse=True)
        return results

    def best_match(self, text: str, *, prefer_clickable: bool = True) -> Optional[Dict]:
        """Single best element matching `text`. Returns element with center coords."""
        pool = self._by_clickable if prefer_clickable else self._elements
        hits = self.find_by_text(text, fuzzy=True, clickable_only=prefer_clickable)
        if not hits:
            hits = self.find_ocr_words(text, fuzzy=True)
        if not hits:
            return None
        best = hits[0]
        b = best.get("bounds", {})
        if b:
            best["center_x"] = (b.get("left", 0) + b.get("right", 0)) // 2
            best["center_y"] = (b.get("top", 0) + b.get("bottom", 0)) // 2
        return best

    def describe(self, max_elements: int = 40) -> str:
        """Human-readable screen description (delegates to layout_analyzer.build_screen_description)."""
        from .layout_analyzer import build_screen_description
        return build_screen_description(self._elements, {
            "w": self._screen_w, "h": self._screen_h,
        })

    @property
    def element_count(self) -> int:
        return len(self._elements)

    @property
    def clickable_count(self) -> int:
        return len(self._by_clickable)

    def all_elements(self) -> List[Dict]:
        return list(self._elements)

    def raw_xml(self) -> str:
        return self._raw_xml


__all__ = ["ElementIndex"]
