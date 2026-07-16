"""
multiligua_cli/pdf_tools.py — PDF Processing Tools

Tools for PDF manipulation: merge, split, compress, watermark,
extract text, convert to images, and more.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional


class PDFToolsWorker:
    """PDF processing and manipulation tools."""

    worker_id = "pdf_tools"
    version = "0.19.0"
    tier = "code"

    def __init__(self):
        self.tools = {}
        self._register_tools()

    # ─── Merge ───────────────────────────────────────────────────────────

    def merge(
        self,
        input_paths: List[str],
        output_path: str,
    ) -> Dict[str, Any]:
        """Merge multiple PDF files."""
        try:
            from pypdf import PdfMerger

            merger = PdfMerger()
            for path in input_paths:
                merger.append(path)
            merger.write(output_path)
            merger.close()

            return {
                "status": "ok",
                "files": len(input_paths),
                "output": output_path,
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Split ───────────────────────────────────────────────────────────

    def split(
        self,
        input_path: str,
        output_dir: str,
        pages_per_file: int = 1,
    ) -> Dict[str, Any]:
        """Split PDF into multiple files."""
        try:
            from pypdf import PdfReader, PdfWriter

            Path(output_dir).mkdir(parents=True, exist_ok=True)
            reader = PdfReader(input_path)
            total_pages = len(reader.pages)

            output_files = []
            for i in range(0, total_pages, pages_per_file):
                writer = PdfWriter()
                for j in range(i, min(i + pages_per_file, total_pages)):
                    writer.add_page(reader.pages[j])

                out_name = f"part_{i // pages_per_file + 1}.pdf"
                out_path = Path(output_dir) / out_name
                with open(out_path, "wb") as f:
                    writer.write(f)
                output_files.append(str(out_path))

            return {
                "status": "ok",
                "total_pages": total_pages,
                "files_created": len(output_files),
                "output_dir": output_dir,
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Extract Pages ───────────────────────────────────────────────────

    def extract_pages(
        self,
        input_path: str,
        output_path: str,
        pages: List[int],
    ) -> Dict[str, Any]:
        """Extract specific pages from PDF."""
        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page_num in pages:
                if 0 <= page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])

            with open(output_path, "wb") as f:
                writer.write(f)

            return {
                "status": "ok",
                "pages_extracted": len(pages),
                "output": output_path,
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Extract Text ────────────────────────────────────────────────────

    def extract_text(self, pdf_path: str) -> Dict[str, Any]:
        """Extract all text from PDF."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return {
                "status": "ok",
                "pages": len(reader.pages),
                "text": text[:50000],  # Limit output
                "char_count": len(text),
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Extract Images ──────────────────────────────────────────────────

    def extract_images(
        self,
        pdf_path: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        """Extract images from PDF."""
        try:
            from pypdf import PdfReader

            Path(output_dir).mkdir(parents=True, exist_ok=True)
            reader = PdfReader(pdf_path)
            images = []

            for i, page in enumerate(reader.pages):
                for j, image in enumerate(page.images):
                    img_data = image.data
                    img_name = f"page{i+1}_img{j}.{image.name.split('.')[-1]}"
                    img_path = Path(output_dir) / img_name
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    images.append(str(img_path))

            return {
                "status": "ok",
                "images_extracted": len(images),
                "output_dir": output_dir,
                "images": images[:20],  # Limit output
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Add Watermark ───────────────────────────────────────────────────

    def add_watermark(
        self,
        input_path: str,
        output_path: str,
        watermark_path: str,
    ) -> Dict[str, Any]:
        """Add watermark to PDF."""
        try:
            from pypdf import PdfReader, PdfWriter

            watermark = PdfReader(watermark_path).pages[0]
            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)

            return {"status": "ok", "output": output_path}
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Add Text Watermark ──────────────────────────────────────────────

    def add_text_watermark(
        self,
        input_path: str,
        output_path: str,
        text: str = "CONFIDENTIAL",
        opacity: float = 0.3,
    ) -> Dict[str, Any]:
        """Add text watermark to PDF."""
        try:
            from pypdf import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            import io

            # Create watermark PDF
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            c.setFillColorRGB(0.5, 0.5, 0.5, opacity)
            c.setFont("Helvetica", 50)
            c.drawString(100, 400, text)
            c.save()
            packet.seek(0)

            watermark = PdfReader(packet).pages[0]
            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)

            return {"status": "ok", "output": output_path}
        except ImportError:
            return {"status": "error", "error": "pypdf and reportlab required. pip install pypdf reportlab"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Rotate ──────────────────────────────────────────────────────────

    def rotate(
        self,
        input_path: str,
        output_path: str,
        angle: int = 90,
        pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Rotate PDF pages."""
        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(input_path)
            writer = PdfWriter()

            for i, page in enumerate(reader.pages):
                if pages is None or i in pages:
                    page.rotate(angle)
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)

            return {
                "status": "ok",
                "angle": angle,
                "pages_rotated": len(pages) if pages else len(reader.pages),
                "output": output_path,
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Compress ────────────────────────────────────────────────────────

    def compress(
        self,
        input_path: str,
        output_path: str,
        quality: int = 50,
    ) -> Dict[str, Any]:
        """Compress PDF (requires Ghostscript)."""
        try:
            import subprocess
            import os

            quality_settings = {
                "screen": "/screen",      # 72 dpi
                "ebook": "/ebook",        # 150 dpi
                "printer": "/printer",    # 300 dpi
                "prepress": "/prepress",  # 300 dpi + color preservation
            }
            setting = quality_settings.get(
                {10: "screen", 30: "ebook", 50: "printer", 80: "prepress"}.get(quality, "ebook"),
                "/ebook",
            )

            cmd = [
                "gs", "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={setting}",
                "-dNOPAUSE", "-dBATCH",
                f"-sOutputFile={output_path}",
                input_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                orig_size = os.path.getsize(input_path)
                comp_size = os.path.getsize(output_path)
                ratio = ((orig_size - comp_size) / orig_size) * 100

                return {
                    "status": "ok",
                    "original_size": orig_size,
                    "compressed_size": comp_size,
                    "reduction_percent": round(ratio, 1),
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "error": "Ghostscript not found. Install ghostscript."}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── PDF to Images ───────────────────────────────────────────────────

    def to_images(
        self,
        pdf_path: str,
        output_dir: str,
        dpi: int = 150,
        format: str = "png",
    ) -> Dict[str, Any]:
        """Convert PDF pages to images."""
        try:
            from pdf2image import convert_from_path

            Path(output_dir).mkdir(parents=True, exist_ok=True)
            images = convert_from_path(pdf_path, dpi=dpi)

            output_files = []
            for i, img in enumerate(images):
                out_name = f"page_{i+1}.{format}"
                out_path = Path(output_dir) / out_name
                img.save(out_path, format.upper())
                output_files.append(str(out_path))

            return {
                "status": "ok",
                "pages": len(images),
                "dpi": dpi,
                "format": format,
                "output_dir": output_dir,
                "images": output_files[:20],
            }
        except ImportError:
            return {"status": "error", "error": "pdf2image not installed. pip install pdf2image"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Get Info ────────────────────────────────────────────────────────

    def get_info(self, pdf_path: str) -> Dict[str, Any]:
        """Get PDF metadata and info."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            info = reader.metadata or {}

            return {
                "status": "ok",
                "pages": len(reader.pages),
                "metadata": {k: v for k, v in info.items() if v},
                "is_encrypted": reader.is_encrypted,
            }
        except ImportError:
            return {"status": "error", "error": "pypdf not installed. pip install pypdf"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Tool Registration ───────────────────────────────────────────────

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "merge": {"description": "Merge PDF files", "category": "edit"},
            "split": {"description": "Split PDF", "category": "edit"},
            "extract_pages": {"description": "Extract pages", "category": "edit"},
            "extract_text": {"description": "Extract text", "category": "extract"},
            "extract_images": {"description": "Extract images", "category": "extract"},
            "add_watermark": {"description": "Add PDF watermark", "category": "edit"},
            "add_text_watermark": {"description": "Add text watermark", "category": "edit"},
            "rotate": {"description": "Rotate pages", "category": "edit"},
            "compress": {"description": "Compress PDF", "category": "edit"},
            "to_images": {"description": "Convert to images", "category": "convert"},
            "get_info": {"description": "Get PDF info", "category": "info"},
        }
