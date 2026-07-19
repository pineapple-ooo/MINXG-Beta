"""minxg.screen.perception — screen understanding: layout analysis + element detection."""
from .layout_analyzer import (
    parse_uiautomator_xml, merge_xml_and_ocr, build_screen_description,
    find_tappable_elements, find_text_elements,
)
from .element_index import ElementIndex

__all__ = [
    "parse_uiautomator_xml", "merge_xml_and_ocr", "build_screen_description",
    "find_tappable_elements", "find_text_elements", "ElementIndex",
]
