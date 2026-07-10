"""minxg.screen.ocr.ocr_pipeline — Tesseract OCR → structured UI text.

Turns raw screenshot PNGs into structured text data AI can reason about:
  - word-level bounding boxes (for element matching)
  - line-level text (for reading)
  - confidence scores (for filtering noise)
  - Layout analysis via tesseract's hOCR/iXML modes

Supported Tesseract PSM modes:
  3 = auto (default), 6 = single uniform block, 0 = orientation only
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, List, Dict
from ..constants import OcrEngine, thresholds


def _tesseract_path() -> Optional[str]:
    """Find tesseract binary; returns None if missing."""
    import shutil
    return shutil.which("tesseract")


def tesseract_available() -> bool:
    return _tesseract_path() is not None


def _psm_flag(engine: OcrEngine) -> str:
    """Map OcrEngine enum to tesseract --psm value."""
    mapping = {
        OcrEngine.DEFAULT: "3",
        OcrEngine.LSTM: "3",
        OcrEngine.TESSERACT_ONLY: "3",
        OcrEngine.RAW_LINE: "6",
        OcrEngine.BOX: "0",
    }
    return mapping.get(engine, "3")


def ocr_image(
    image_path: str,
    *,
    engine: str = "default",
    lang: str = "eng",
    psm: int = 3,
    conf_threshold: int = 60,
    max_chars: int = 5000,
) -> dict:
    """Run OCR on a screenshot/int image file.

    Parameters
    ----------
    image_path: str         — path to PNG/JPEG
    engine: str             — 'default', 'lstm', 'tesseract_only', 'raw_line', 'box'
    lang: str               — tesseract lang code ('eng', 'chi_sim', 'jpn', etc.)
    psm: int                — page segmentation mode (0-13)
    conf_threshold: int     — minimum confidence % to include a word
    max_chars: int          — cap total output chars for token efficiency

    Returns: {
      text: str,                  — full recognized text (newline-separated)
      words: [{text, conf, bbox}],— word-level results
      lines: [{text, conf, bbox, words}],
      engine, lang, psm,
      image_path, image_size: {w,h},
      word_count, line_count,
      avg_confidence: float,
      ok, error?
    }
    """
    tess = _tesseract_path()
    if not tess:
        return {"ok": False, "error": "tesseract not installed; pkg install tesseract"}

    img_path = Path(image_path)
    if not img_path.exists():
        return {"ok": False, "error": f"image not found: {image_path}"}

    # Get image size via Pillow
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.open(str(img_path))
        img_size = {"w": pil_img.size[0], "h": pil_img.size[1]}
    except Exception as e:
        img_size = {"w": 0, "h": 0, "error": str(e)}

    out = {"ok": False, "engine": engine, "lang": lang, "psm": psm,
           "image_path": str(img_path), "image_size": img_size}

    # Prepare temp dir for TSV output
    tmp_dir = Path.home() / ".minxg" / "screen" / "ocr"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tsv_base = str(tmp_dir / f"_ocr_tsv_{int(time.time()*1000)}")

    try:
        # Run tesseract with TSV output (gives bbox per word/line)
        cmd = [tess, str(img_path), tsv_base, f"--psm={psm}",
               f"-l", lang, "tsv"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           env={"OMP_THREAD_LIMIT": "2"})
        if r.returncode != 0:
            out["error"] = f"tesseract failed: {r.stderr[:300]}"
            return out

        tsv_path = tsv_base + ".tsv"
        if not Path(tsv_path).exists():
            out["error"] = "tesseract produced no TSV output"
            return out

        tsv_text = Path(tsv_path).read_text(errors="replace")
        lines_raw = tsv_text.strip().splitlines()

        # Parse TSV header
        header = lines_raw[0].split("\t")
        col = {name: i for i, name in enumerate(header)}

        words: List[Dict] = []
        lines_out: List[Dict] = []

        for row in lines_raw[1:]:
            cells = row.split("\t")
            if len(cells) < len(col):
                continue

            level = int(cells[col.get("level", 0)])
            text_content = cells[col.get("text", 1)]
            conf = int(cells[col.get("conf", 2)]) if col.get("conf") is not None else -1
            left = int(cells[col.get("left", 3)]) if col.get("left") is not None else 0
            top = int(cells[col.get("top", 4)]) if col.get("top") is not None else 0
            width = int(cells[col.get("width", 5)]) if col.get("width") is not None else 0
            height = int(cells[col.get("height", 6)]) if col.get("height") is not None else 0

            bbox = {"left": left, "top": top, "right": left + width,
                    "bottom": top + height, "w": width, "h": height}

            if level == 5:  # word
                if conf >= conf_threshold and text_content.strip():
                    words.append({"text": text_content, "conf": conf, "bbox": bbox})
            elif level == 2:  # line
                if text_content.strip():
                    lines_out.append({
                        "text": text_content,
                        "conf": conf if conf > 0 else 0,
                        "bbox": bbox,
                        "words": [],
                    })

        # Associate words with lines by bbox proximity
        for word in words:
            wcx = (word["bbox"]["left"] + word["bbox"]["right"]) // 2
            wcy = (word["bbox"]["top"] + word["bbox"]["bottom"]) // 2
            best_line = None
            best_dist = float("inf")
            for line in lines_out:
                lb = line["bbox"]
                if lb["left"] <= wcx <= lb["right"] and lb["top"] <= wcy <= lb["bottom"]:
                    best_line = line
                    break
                lcx = (lb["left"] + lb["right"]) // 2
                lcy = (lb["top"] + lb["bottom"]) // 2
                dist = (wcx - lcx) ** 2 + (wcy - lcy) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_line = line
            if best_line:
                best_line["words"].append(word)

        # Build full text
        full_text = "\n".join(l["text"] for l in lines_out)
        # Truncate if too long
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n..."

        # Avg confidence
        confs = [w["conf"] for w in words] + [l["conf"] for l in lines_out]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        out.update(
            text=full_text,
            words=words[:max_chars // 4],
            lines=lines_out,
            word_count=len(words),
            line_count=len(lines_out),
            avg_confidence=round(avg_conf, 1),
            ok=True,
            timestamp=time.time(),
        )

        # Cleanup TSV
        try:
            Path(tsv_path).unlink()
        except OSError:
            pass

    except Exception as e:
        out["error"] = f"ocr pipeline error: {e}"

    return out


__all__ = ["tesseract_available", "ocr_image"]
