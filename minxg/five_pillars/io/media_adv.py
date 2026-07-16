"""
minxg/media_adv.py — Advanced media processing tools v1.0.0

Image, audio, video: info, resize, crop, convert, thumbnail, spectrogram, GIF.
Uses Pillow for images and ffprobe for audio/video when available.
"""
from __future__ import annotations
import os
import json
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool


def _parse_frame_rate(expr: str) -> float:
    expr = (expr or "0/1").strip()
    if "/" in expr:
        num, _, den = expr.partition("/")
        den = den.strip()
        if den:
            try:
                return float(num) / float(den)
            except Exception:
                return 0.0
    try:
        return float(expr)
    except Exception:
        return 0.0


class MediaAdvWorker(BaseWorker):
    facade_alias = "media_tools"
    """Advanced media tools: image, audio, video processing."""
    worker_id = "media_adv"
    tier = "ai"  # v0.18.0 three-tier classification
    version = "0.17.1"

    def _register_tools(self):
        tools = [
            ("media_info", "Get comprehensive media file info: dimensions, codec, bitrate, duration.",
             {"path": "string"}, self._media_info),
            ("image_info", "Get image metadata: dimensions, format, mode, EXIF, size.",
             {"path": "string"}, self._image_info),
            ("image_resize", "Resize an image to specified width/height. Maintains aspect ratio if one dimension is 0.",
             {"path": "string", "width": "int", "height": "int", "output": "string"}, self._image_resize),
            ("image_crop", "Crop an image to a rectangle (x, y, width, height).",
             {"path": "string", "x": "int", "y": "int", "width": "int", "height": "int", "output": "string"},
             self._image_crop),
            ("image_rotate", "Rotate an image by degrees.",
             {"path": "string", "degrees": "int", "output": "string"}, self._image_rotate),
            ("image_convert", "Convert image format (png, jpg, webp, gif, bmp, tiff).",
             {"path": "string", "format": "string", "quality": "int", "output": "string"}, self._image_convert),
            ("image_thumbnail", "Create a thumbnail of an image.",
             {"path": "string", "size": "int", "output": "string"}, self._image_thumbnail),
            ("image_grayscale", "Convert image to grayscale.",
             {"path": "string", "output": "string"}, self._image_grayscale),
            ("image_flip", "Flip image horizontally or vertically.",
             {"path": "string", "direction": "string", "output": "string"}, self._image_flip),
            ("image_exif", "Read EXIF metadata from an image.",
             {"path": "string"}, self._image_exif),
            ("audio_info", "Get audio file metadata: duration, bitrate, sample rate, channels, codec.",
             {"path": "string"}, self._audio_info),
            ("audio_convert", "Convert audio file format (mp3, wav, ogg, flac, aac, m4a).",
             {"path": "string", "format": "string", "bitrate": "string", "output": "string"}, self._audio_convert),
            ("audio_trim", "Trim audio to a specified start and duration.",
             {"path": "string", "start_sec": "float", "duration_sec": "float", "output": "string"},
             self._audio_trim),
            ("audio_normalize", "Normalize audio volume to a target level.",
             {"path": "string", "level_db": "float", "output": "string"}, self._audio_normalize),
            ("audio_concat", "Concatenate multiple audio files into one.",
             {"paths": "list", "output": "string"}, self._audio_concat),
            ("video_info", "Get video file metadata: dimensions, duration, bitrate, codec, fps.",
             {"path": "string"}, self._video_info),
            ("video_thumbnail", "Extract a thumbnail/frame from a video at a specific time.",
             {"path": "string", "time_sec": "float", "output": "string"}, self._video_thumbnail),
            ("video_clip", "Extract a clip from a video (start, duration).",
             {"path": "string", "start_sec": "float", "duration_sec": "float", "output": "string"},
             self._video_clip),
            ("video_gif", "Convert a video segment to an animated GIF.",
             {"path": "string", "start_sec": "float", "duration_sec": "float",
              "width": "int", "fps": "int", "output": "string"}, self._video_gif),
        ]

        for name, desc, params, fn in tools:
            self.tools[name] = type("ToolDef", (), {
                "name": name, "description": desc, "params": params,
                "category": "media",
                "platforms": ["linux", "macos", "windows", "android"],
                "requires_root": False, "fn": fn,
            })()

    
    def _ffprobe(self, path: str) -> Optional[Dict]:
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
                   "-show_format", "-show_streams", path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return json.loads(result.stdout) if result.returncode == 0 else None
        except Exception:
            return None

    
    def _load_image(self, path: str):
        try:
            from PIL import Image
            return Image.open(path)
        except ImportError:
            return None
        except Exception:
            return None

    
    def _media_info(self, path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return {"status": "error", "error": f"File not found: {path}"}

        info = {"path": path, "size_bytes": os.path.getsize(path),
                "extension": os.path.splitext(path)[1].lower()}

        
        probe = self._ffprobe(path)
        if probe:
            fmt = probe.get("format", {})
            info["duration_sec"] = float(fmt.get("duration", 0))
            info["bitrate_bps"] = int(fmt.get("bit_rate", 0))
            streams = probe.get("streams", [])
            for s in streams:
                if s.get("codec_type") == "video":
                    info["video"] = {
                        "codec": s.get("codec_name"), "width": s.get("width"),
                        "height": s.get("height"),
                        "fps": _parse_frame_rate(s.get("r_frame_rate", "0/1")),
                    }
                elif s.get("codec_type") == "audio":
                    info["audio"] = {
                        "codec": s.get("codec_name"), "sample_rate": s.get("sample_rate"),
                        "channels": s.get("channels"), "bitrate": s.get("bit_rate"),
                    }

        
        img = self._load_image(path)
        if img:
            info["image"] = {"format": img.format, "mode": img.mode,
                            "width": img.width, "height": img.height,
                            "aspect_ratio": f"{img.width}:{img.height}"}
            try:
                exif = img._getexif()
                if exif:
                    info["exif_summary"] = str(exif)[:500]
            except Exception:
                pass

        return {"status": "success", "info": info}

    
    def _image_info(self, path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available. Install: pip install Pillow"}
        return {"status": "success",
                "path": path, "format": img.format, "mode": img.mode,
                "width": img.width, "height": img.height,
                "size_bytes": os.path.getsize(path),
                "aspect_ratio": f"{img.width}x{img.height}"}

    def _image_resize(self, path: str, width: int = 0, height: int = 0,
                      output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_resized_{width}x{height}{ext}"
        if width and height:
            img = img.resize((width, height))
        elif width:
            ratio = width / img.width
            img = img.resize((width, int(img.height * ratio)))
        elif height:
            ratio = height / img.height
            img = img.resize((int(img.width * ratio), height))
        img.save(output)
        return {"status": "success", "output": output,
                "new_size": f"{img.width}x{img.height}"}

    def _image_crop(self, path: str, x: int, y: int, width: int, height: int,
                    output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_cropped{ext}"
        img = img.crop((x, y, x + width, y + height))
        img.save(output)
        return {"status": "success", "output": output, "size": f"{img.width}x{img.height}"}

    def _image_rotate(self, path: str, degrees: int = 90,
                      output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_rotated{degrees}{ext}"
        img = img.rotate(degrees, expand=True)
        img.save(output)
        return {"status": "success", "output": output}

    def _image_convert(self, path: str, format: str = "png", quality: int = 85,
                       output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        fmt = format.upper()
        if not output:
            name = os.path.splitext(path)[0]
            output = f"{name}.{format.lower()}"
        if fmt in ("JPG", "JPEG"):
            img = img.convert("RGB")
        img.save(output, format=fmt, quality=quality)
        return {"status": "success", "output": output,
                "size_bytes": os.path.getsize(output)}

    def _image_thumbnail(self, path: str, size: int = 128,
                         output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_thumb{ext}"
        img.thumbnail((size, size))
        img.save(output)
        return {"status": "success", "output": output, "size": f"{img.width}x{img.height}"}

    def _image_grayscale(self, path: str, output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_gray{ext}"
        img = img.convert("L")
        img.save(output)
        return {"status": "success", "output": output}

    def _image_flip(self, path: str, direction: str = "horizontal",
                    output: str = "") -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        if not output:
            name, ext = os.path.splitext(path)
            output = f"{name}_{direction}{ext}"
        from PIL import Image
        img = img.transpose(
            Image.FLIP_LEFT_RIGHT if direction == "horizontal" else Image.FLIP_TOP_BOTTOM
        )
        img.save(output)
        return {"status": "success", "output": output}

    def _image_exif(self, path: str) -> Dict[str, Any]:
        path = os.path.expanduser(path)
        img = self._load_image(path)
        if not img:
            return {"status": "error", "error": "Pillow not available"}
        try:
            exif = img._getexif()
            if not exif:
                return {"status": "success", "exif": {}, "note": "No EXIF data found"}
            readable = {}
            for tag_id, value in exif.items():
                try:
                    from PIL.ExifTags import TAGS
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    readable[tag_name] = str(value)
                except Exception:
                    readable[str(tag_id)] = str(value)
            return {"status": "success", "exif": readable}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    
    def _audio_info(self, path: str) -> Dict[str, Any]:
        return self._media_info(path)

    def _audio_convert(self, path: str, format: str = "mp3",
                       bitrate: str = "192k", output: str = "") -> Dict[str, Any]:
        if not output:
            output = f"{os.path.splitext(path)[0]}.{format}"
        try:
            subprocess.run(["ffmpeg", "-y", "-i", path, "-b:a", bitrate, output],
                          capture_output=True, timeout=60, check=True)
            return {"status": "success", "output": output, "size_bytes": os.path.getsize(output)}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found. Install: apt install ffmpeg"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Conversion timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audio_trim(self, path: str, start_sec: float = 0, duration_sec: float = 10,
                    output: str = "") -> Dict[str, Any]:
        if not output:
            name = os.path.splitext(path)[0]
            output = f"{name}_trimmed_{int(start_sec)}-{int(start_sec+duration_sec)}.mp3"
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-i", path,
                           "-t", str(duration_sec), "-c", "copy", output],
                          capture_output=True, timeout=30, check=True)
            return {"status": "success", "output": output}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audio_normalize(self, path: str, level_db: float = -3.0,
                         output: str = "") -> Dict[str, Any]:
        if not output:
            name = os.path.splitext(path)[0]
            output = f"{name}_normalized.mp3"
        try:
            subprocess.run(["ffmpeg", "-y", "-i", path, "-af",
                           f"loudnorm=I={level_db}:TP=-1.5:LRA=11", output],
                          capture_output=True, timeout=60, check=True)
            return {"status": "success", "output": output}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audio_concat(self, paths: List[str], output: str = "concat_output.mp3") -> Dict[str, Any]:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            list_file = f.name
            for p in paths:
                f.write(f"file '{os.path.expanduser(p)}'\n")
        try:
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                           "-i", list_file, "-c", "copy", output],
                          capture_output=True, timeout=60, check=True)
            os.unlink(list_file)
            return {"status": "success", "output": output}
        except FileNotFoundError:
            os.unlink(list_file)
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            os.unlink(list_file)
            return {"status": "error", "error": str(e)}

    
    def _video_info(self, path: str) -> Dict[str, Any]:
        return self._media_info(path)

    def _video_thumbnail(self, path: str, time_sec: float = 1.0,
                         output: str = "") -> Dict[str, Any]:
        if not output:
            output = f"{os.path.splitext(path)[0]}_thumb.jpg"
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(time_sec), "-i", path,
                           "-vframes", "1", "-q:v", "5", output],
                          capture_output=True, timeout=15, check=True)
            return {"status": "success", "output": output}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _video_clip(self, path: str, start_sec: float = 0, duration_sec: float = 10,
                    output: str = "") -> Dict[str, Any]:
        if not output:
            name = os.path.splitext(path)[0]
            output = f"{name}_clip_{int(start_sec)}.mp4"
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-i", path,
                           "-t", str(duration_sec), "-c", "copy", output],
                          capture_output=True, timeout=30, check=True)
            return {"status": "success", "output": output}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _video_gif(self, path: str, start_sec: float = 0, duration_sec: float = 3,
                   width: int = 320, fps: int = 10, output: str = "") -> Dict[str, Any]:
        if not output:
            output = f"{os.path.splitext(path)[0]}.gif"
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-i", path,
                           "-t", str(duration_sec), "-vf",
                           f"fps={fps},scale={width}:-1:flags=lanczos",
                           output], capture_output=True, timeout=30, check=True)
            return {"status": "success", "output": output, "size_bytes": os.path.getsize(output)}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}