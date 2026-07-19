"""minxg.screen.ocr — Tesseract OCR pipeline."""
from .ocr_pipeline import ocr_image, tesseract_available

__all__ = ["ocr_image", "tesseract_available"]
