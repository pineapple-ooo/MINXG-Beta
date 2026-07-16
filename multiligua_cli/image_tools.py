"""
multiligua_cli/image_tools.py — Image Processing Tools

Tools for image manipulation, format conversion, resizing, filtering,
and analysis. Supports PNG, JPEG, WebP, GIF, BMP, TIFF, and more.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional


class ImageToolsWorker:
    """Image processing and manipulation tools."""

    worker_id = "image_tools"
    version = "0.19.0"
    tier = "code"

    def __init__(self):
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """Register all image tools."""
        # Tools are registered via decorator pattern
        pass

    # ─── Format Conversion ───────────────────────────────────────────────

    def convert_format(
        self,
        input_path: str,
        output_path: str,
        format: str = "png",
        quality: int = 95,
    ) -> Dict[str, Any]:
        """Convert image between formats (PNG, JPEG, WebP, GIF, BMP, TIFF)."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            save_kwargs = {}
            if format.lower() in ("jpg", "jpeg"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            elif format.lower() == "webp":
                save_kwargs["quality"] = quality
            elif format.lower() == "png":
                save_kwargs["optimize"] = True

            img.save(output_path, format=format.upper(), **save_kwargs)

            return {
                "status": "ok",
                "input": input_path,
                "output": output_path,
                "format": format,
                "original_size": Path(input_path).stat().st_size,
                "output_size": Path(output_path).stat().st_size,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Resize ──────────────────────────────────────────────────────────

    def resize(
        self,
        input_path: str,
        output_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        max_size: Optional[int] = None,
        maintain_aspect: bool = True,
    ) -> Dict[str, Any]:
        """Resize image to specified dimensions."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            orig_w, orig_h = img.size

            if max_size:
                scale = min(max_size / orig_w, max_size / orig_h)
                if scale < 1:
                    width = int(orig_w * scale)
                    height = int(orig_h * scale)
                else:
                    width, height = orig_w, orig_h
            elif maintain_aspect:
                if width and not height:
                    ratio = width / orig_w
                    height = int(orig_h * ratio)
                elif height and not width:
                    ratio = height / orig_h
                    width = int(orig_w * ratio)
            elif not width or not height:
                width, height = orig_w, orig_h

            img = img.resize((width, height), Image.LANCZOS)
            img.save(output_path)

            return {
                "status": "ok",
                "original": (orig_w, orig_h),
                "resized": (width, height),
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Thumbnail ───────────────────────────────────────────────────────

    def thumbnail(
        self,
        input_path: str,
        output_path: str,
        size: int = 128,
    ) -> Dict[str, Any]:
        """Create a thumbnail of the image."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            img.thumbnail((size, size), Image.LANCZOS)
            img.save(output_path)

            return {
                "status": "ok",
                "size": img.size,
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Metadata ────────────────────────────────────────────────────────

    def get_metadata(self, image_path: str) -> Dict[str, Any]:
        """Get image metadata (dimensions, format, size, EXIF)."""
        try:
            from PIL import Image
            import os

            img = Image.open(image_path)
            metadata = {
                "path": image_path,
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_bytes": os.path.getsize(image_path),
            }

            # EXIF data
            try:
                exif = img._getexif()
                if exif:
                    from PIL.ExifTags import TAGS
                    metadata["exif"] = {
                        TAGS.get(k, k): v
                        for k, v in exif.items()
                        if k in TAGS
                    }
            except Exception:
                pass

            return metadata
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Compress ────────────────────────────────────────────────────────

    def compress(
        self,
        input_path: str,
        output_path: str,
        quality: int = 80,
        max_size_kb: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compress image to reduce file size."""
        try:
            from PIL import Image
            import os

            img = Image.open(input_path)

            if max_size_kb:
                # Iterative compression
                for q in range(quality, 10, -5):
                    img.save(output_path, quality=q, optimize=True)
                    if os.path.getsize(output_path) <= max_size_kb * 1024:
                        break
                else:
                    img.save(output_path, quality=10, optimize=True)
            else:
                img.save(output_path, quality=quality, optimize=True)

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
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Crop ────────────────────────────────────────────────────────────

    def crop(
        self,
        input_path: str,
        output_path: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> Dict[str, Any]:
        """Crop image to specified region."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            cropped = img.crop((left, top, right, bottom))
            cropped.save(output_path)

            return {
                "status": "ok",
                "size": cropped.size,
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Rotate ──────────────────────────────────────────────────────────

    def rotate(
        self,
        input_path: str,
        output_path: str,
        angle: float,
        expand: bool = True,
    ) -> Dict[str, Any]:
        """Rotate image by specified angle."""
        try:
            from PIL import Image

            img = Image.open(input_path)
            rotated = img.rotate(angle, expand=expand)
            rotated.save(output_path)

            return {
                "status": "ok",
                "angle": angle,
                "size": rotated.size,
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Filters ─────────────────────────────────────────────────────────

    def apply_filter(
        self,
        input_path: str,
        output_path: str,
        filter_name: str = "blur",
    ) -> Dict[str, Any]:
        """Apply filter to image (blur, sharpen, edge_enhance, emboss, etc)."""
        try:
            from PIL import Image, ImageFilter

            filters = {
                "blur": ImageFilter.BLUR,
                "sharpen": ImageFilter.SHARPEN,
                "edge_enhance": ImageFilter.EDGE_ENHANCE,
                "edge_enhance_more": ImageFilter.EDGE_ENHANCE_MORE,
                "emboss": ImageFilter.EMBOSS,
                "contour": ImageFilter.CONTOUR,
                "detail": ImageFilter.DETAIL,
                "smooth": ImageFilter.SMOOTH,
                "smooth_more": ImageFilter.SMOOTH_MORE,
                "find_edges": ImageFilter.FIND_EDGES,
            }

            if filter_name not in filters:
                return {
                    "status": "error",
                    "error": f"Unknown filter: {filter_name}",
                    "available": list(filters.keys()),
                }

            img = Image.open(input_path)
            filtered = img.filter(filters[filter_name])
            filtered.save(output_path)

            return {
                "status": "ok",
                "filter": filter_name,
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Grayscale ───────────────────────────────────────────────────────

    def grayscale(
        self,
        input_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Convert image to grayscale."""
        try:
            from PIL import Image

            img = Image.open(input_path).convert("L")
            img.save(output_path)

            return {"status": "ok", "output": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Histogram ───────────────────────────────────────────────────────

    def histogram(
        self,
        image_path: str,
    ) -> Dict[str, Any]:
        """Get image histogram data."""
        try:
            from PIL import Image

            img = Image.open(image_path)
            hist = img.histogram()

            return {
                "status": "ok",
                "channels": len(hist) // 256,
                "histogram": hist[:256],  # First channel
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Batch Process ───────────────────────────────────────────────────

    def batch_convert(
        self,
        input_dir: str,
        output_dir: str,
        format: str = "png",
        pattern: str = "*.*",
    ) -> Dict[str, Any]:
        """Batch convert all images in a directory."""
        try:
            from PIL import Image
            from pathlib import Path

            input_p = Path(input_dir)
            output_p = Path(output_dir)
            output_p.mkdir(parents=True, exist_ok=True)

            results = {"converted": [], "errors": []}

            for img_path in input_p.glob(pattern):
                try:
                    out_name = img_path.stem + "." + format.lower()
                    out_path = output_p / out_name
                    self.convert_format(str(img_path), str(out_path), format)
                    results["converted"].append(str(out_path))
                except Exception as e:
                    results["errors"].append(f"{img_path.name}: {str(e)}")

            return {
                "status": "ok",
                "total": len(results["converted"]),
                "errors": len(results["errors"]),
                "converted": results["converted"][:20],  # Limit output
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Watermark ───────────────────────────────────────────────────────

    def add_watermark(
        self,
        input_path: str,
        output_path: str,
        text: str,
        position: str = "bottom-right",
        opacity: int = 128,
        font_size: int = 24,
    ) -> Dict[str, Any]:
        """Add text watermark to image."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(input_path).convert("RGBA")
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)

            # Try to use a default font, fall back to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

            # Calculate position
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            padding = 10
            if position == "bottom-right":
                x = img.width - text_w - padding
                y = img.height - text_h - padding
            elif position == "bottom-left":
                x = padding
                y = img.height - text_h - padding
            elif position == "top-right":
                x = img.width - text_w - padding
                y = padding
            elif position == "top-left":
                x = padding
                y = padding
            elif position == "center":
                x = (img.width - text_w) // 2
                y = (img.height - text_h) // 2
            else:
                x, y = padding, padding

            draw.text((x, y), text, font=font, fill=(0, 0, 0, opacity))

            watermarked = Image.alpha_composite(img, txt_layer)
            watermarked.convert("RGB").save(output_path)

            return {"status": "ok", "output": output_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Collage ─────────────────────────────────────────────────────────

    def create_collage(
        self,
        image_paths: List[str],
        output_path: str,
        cols: int = 3,
        rows: Optional[int] = None,
        padding: int = 5,
        bg_color: str = "white",
    ) -> Dict[str, Any]:
        """Create a collage from multiple images."""
        try:
            from PIL import Image

            images = [Image.open(p) for p in image_paths]
            if not images:
                return {"status": "error", "error": "No images provided"}

            if rows is None:
                rows = (len(images) + cols - 1) // cols

            # Calculate thumbnail size
            max_w = max(img.width for img in images)
            max_h = max(img.height for img in images)

            collage_w = cols * (max_w + padding) + padding
            collage_h = rows * (max_h + padding) + padding

            collage = Image.new("RGB", (collage_w, collage_h), bg_color)

            for idx, img in enumerate(images):
                # Resize to max dimensions
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                row = idx // cols
                col = idx % cols
                x = padding + col * (max_w + padding)
                y = padding + row * (max_h + padding)

                collage.paste(img, (x, y))

            collage.save(output_path)

            return {
                "status": "ok",
                "images": len(images),
                "size": collage.size,
                "output": output_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── GIF Creator ─────────────────────────────────────────────────────

    def create_gif(
        self,
        image_paths: List[str],
        output_path: str,
        duration: int = 500,
        loop: int = 0,
    ) -> Dict[str, Any]:
        """Create animated GIF from images."""
        try:
            from PIL import Image

            images = []
            for p in image_paths:
                img = Image.open(p)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                images.append(img)

            if images:
                images[0].save(
                    output_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=duration,
                    loop=loop,
                )

                return {
                    "status": "ok",
                    "frames": len(images),
                    "duration_ms": duration,
                    "output": output_path,
                }

            return {"status": "error", "error": "No images provided"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── EXIF Tools ──────────────────────────────────────────────────────

    def extract_exif(self, image_path: str) -> Dict[str, Any]:
        """Extract all EXIF metadata from image."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            img = Image.open(image_path)
            exif_data = {}

            try:
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "GPSInfo":
                            gps = {}
                            for gps_tag_id, gps_value in value.items():
                                gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                                gps[gps_tag] = gps_value
                            exif_data[tag] = gps
                        else:
                            exif_data[tag] = value
            except Exception:
                pass

            return {"status": "ok", "exif": exif_data}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Color Analysis ──────────────────────────────────────────────────

    def get_dominant_colors(
        self,
        image_path: str,
        num_colors: int = 5,
    ) -> Dict[str, Any]:
        """Get dominant colors in image."""
        try:
            from PIL import Image
            import collections

            img = Image.open(image_path)
            img = img.resize((150, 150))  # Resize for speed
            if img.mode != "RGB":
                img = img.convert("RGB")

            colors = img.getcolors(150 * 150)
            if colors:
                sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)
                dominant = sorted_colors[:num_colors]

                return {
                    "status": "ok",
                    "colors": [
                        {"rgb": c[1], "count": c[0]}
                        for c in dominant
                    ],
                }

            return {"status": "error", "error": "Could not extract colors"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Compare ─────────────────────────────────────────────────────────

    def compare_images(
        self,
        image1_path: str,
        image2_path: str,
    ) -> Dict[str, Any]:
        """Compare two images and return difference metrics."""
        try:
            from PIL import Image
            import numpy as np

            img1 = Image.open(image1_path).convert("L").resize((256, 256))
            img2 = Image.open(image2_path).convert("L").resize((256, 256))

            arr1 = np.array(img1, dtype=float)
            arr2 = np.array(img2, dtype=float)

            diff = np.abs(arr1 - arr2)
            mse = np.mean(diff ** 2)
            rmse = np.sqrt(mse)

            # Simple similarity (0-100%)
            similarity = max(0, 100 - (rmse / 255 * 100))

            return {
                "status": "ok",
                "mse": float(mse),
                "rmse": float(rmse),
                "similarity_percent": round(similarity, 1),
                "identical": mse == 0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Tool Registration ───────────────────────────────────────────────

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "convert_format": {"description": "Convert image between formats", "category": "convert"},
            "resize": {"description": "Resize image to dimensions", "category": "transform"},
            "thumbnail": {"description": "Create thumbnail", "category": "transform"},
            "get_metadata": {"description": "Get image metadata", "category": "info"},
            "compress": {"description": "Compress image", "category": "transform"},
            "crop": {"description": "Crop image region", "category": "transform"},
            "rotate": {"description": "Rotate image", "category": "transform"},
            "apply_filter": {"description": "Apply image filter", "category": "filter"},
            "grayscale": {"description": "Convert to grayscale", "category": "filter"},
            "histogram": {"description": "Get image histogram", "category": "info"},
            "batch_convert": {"description": "Batch convert images", "category": "batch"},
            "add_watermark": {"description": "Add text watermark", "category": "transform"},
            "create_collage": {"description": "Create image collage", "category": "compose"},
            "create_gif": {"description": "Create animated GIF", "category": "compose"},
            "extract_exif": {"description": "Extract EXIF metadata", "category": "info"},
            "get_dominant_colors": {"description": "Get dominant colors", "category": "info"},
            "compare_images": {"description": "Compare two images", "category": "info"},
        }
