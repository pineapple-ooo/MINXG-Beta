"""
"""
from __future__ import annotations
from typing import Dict, List
import re
import math
from minxg.base import BaseWorker, tool


class MediaToolsWorker(BaseWorker):
    facade_alias = "media_tools"
    worker_id = "media_tools"
    version = "0.17.1"

    @tool(description="Get image info: size/format/filesize", category="image")
    async def image_info(self, path: str) -> Dict:
        try:
            from PIL import Image
            img = Image.open(path)
            return {"width": img.width, "height": img.height, "format": img.format,
                    "mode": img.mode, "size_bytes": img.fp.tell() if hasattr(img, 'fp') else 0}
        except ImportError:
            return {"error": "PIL not installed", "hint": "pip install Pillow", "path": path}
        except Exception as e:
            return {"error": str(e), "path": path}

    @tool(description="Calculate scaled image dimensions", category="image")
    async def resize_calculate(self, width: int, height: int,
                                target_width: int = 0, target_height: int = 0,
                                max_dim: int = 0) -> Dict:
        ratio = width / height if height else 1.0
        if max_dim:
            if width > height:
                nw, nh = max_dim, int(max_dim / ratio)
            else:
                nw, nh = int(max_dim * ratio), max_dim
        elif target_width and target_height:
            nw, nh = target_width, target_height
        elif target_width:
            nw, nh = target_width, int(target_width / ratio)
        elif target_height:
            nw, nh = int(target_height * ratio), target_height
        else:
            nw, nh = width, height
        return {"original": {"w": width, "h": height}, "new": {"w": nw, "h": nh}, "ratio": ratio}

    @tool(description="Generate color palette from color list", category="design")
    async def color_palette(self, base_color: str = "#3B82F6", count: int = 5) -> Dict:
        base = base_color.lstrip("#")
        r, g, b = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
        palette = []
        for i in range(count):
            shift = i * 30
            nr = min(255, r + shift)
            ng = min(255, g + shift // 2)
            nb = max(0, b - shift // 3)
            palette.append(f"#{nr:02x}{ng:02x}{nb:02x}")
        return {"base": base_color, "palette": palette, "count": count}

    @tool(description="Calculate aspect ratio", category="image")
    async def aspect_ratio(self, width: int, height: int) -> Dict:
        g = math.gcd(width, height)
        ratio_str = f"{width // g}:{height // g}"
        decimal = round(width / height, 4) if height else 0
        labels = {1.333: "4:3", 1.778: "16:9", 1.6: "16:10", 1.0: "1:1"}
        label = labels.get(round(decimal, 3), ratio_str)
        return {"ratio": ratio_str, "decimal": decimal, "label": label}

    @tool(description="MIME type detection", category="detect")
    async def detect_mime(self, filename: str) -> Dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mapping = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
            "bmp": "image/bmp", "ico": "image/x-icon",
            "mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska",
            "avi": "video/x-msvideo", "mov": "video/quicktime",
            "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
            "flac": "audio/flac", "aac": "audio/aac", "m4a": "audio/mp4",
            "pdf": "application/pdf", "zip": "application/zip",
            "tar": "application/x-tar", "gz": "application/gzip",
            "json": "application/json", "xml": "application/xml",
            "html": "text/html", "css": "text/css", "js": "text/javascript",
            "py": "text/x-python", "txt": "text/plain", "md": "text/markdown",
        }
        mime = mapping.get(ext, "application/octet-stream")
        return {"filename": filename, "extension": ext, "mime_type": mime}

    @tool(description="Build FFmpeg command", category="video")
    async def ffmpeg_command(self, input_file: str, operation: str,
                              params: dict = None) -> Dict:
        params = params or {}
        commands = {
            "convert": f"ffmpeg -i {input_file} {params.get('output', 'output.mp4')}",
            "resize": f"ffmpeg -i {input_file} -vf scale={params.get('w', 1920)}:{params.get('h', 1080)} output.mp4",
            "extract_audio": f"ffmpeg -i {input_file} -vn -acodec copy output.{params.get('fmt', 'mp3')}",
            "compress": f"ffmpeg -i {input_file} -crf {params.get('crf', 23)} -preset medium output.mp4",
            "trim": f"ffmpeg -i {input_file} -ss {params.get('start', '00:00:00')} -t {params.get('dur', 10)} output.mp4",
            "extract_frame": f"ffmpeg -i {input_file} -ss {params.get('at', '00:00:01')} -vframes 1 output.png",
        }
        cmd = commands.get(operation, f"ffmpeg -i {input_file} output.mp4")
        return {"command": cmd, "operation": operation, "input": input_file}

    @tool(description="Generate thumbnail parameters", category="image")
    async def thumbnail_params(self, width: int, height: int, target: int = 256) -> Dict:
        if width > height:
            tw, th = target, int(target * height / width)
        else:
            tw, th = int(target * width / height), target
        return {"thumbnail_size": {"w": tw, "h": th}, "original": {"w": width, "h": height}, "target_max": target}

    @tool(description="Base64 encode image suggestion", category="encode")
    async def base64_encode_image(self, path: str) -> Dict:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else "png"
        mime = f"image/{ext}" if ext in ("jpg","jpeg","png","gif","webp") else "image/png"
        cmd = f"base64 -w 0 {path}"
        return {"command": cmd, "data_uri_prefix": f"data:{mime};base64,", "path": path}

    @tool(description="Base64 decode image suggestion", category="decode")
    async def base64_decode_image(self, data_uri: str, output_path: str = "output.png") -> Dict:
        match = re.match(r'data:([^;]+);base64,(.+)', data_uri)
        if match:
            mime, b64 = match.group(1), match.group(2)
            return {"mime_type": mime, "output_path": output_path,
                    "decode_cmd": f"echo '{b64[:50]}...' | base64 -d > {output_path}"}
        return {"error": "not a valid data URI", "output_path": output_path}

    @tool(description="QR code generation parameters", category="encode")
    async def qr_generate(self, text: str, size: int = 10, border: int = 2) -> Dict:
        cmd = f"qrencode -o qr.png -s {size} -m {border} '{text}'"
        py_code = f"""
import qrcode
img = qrcode.make("{text}")
img.save("qr.png")
img.show()"""
        return {"shell_cmd": cmd, "python_code": py_code.strip(), "text": text, "output": "qr.png"}

    @tool(description="Parse SVG for basic attributes", category="detect")
    async def svg_parse(self, svg: str) -> Dict:
        w_match = re.search(r'width="([^"]+)"', svg)
        h_match = re.search(r'height="([^"]+)"', svg)
        vb_match = re.search(r'viewBox="([^"]+)"', svg)
        tags = re.findall(r'<(\w+)', svg)
        tag_counts = {}
        for t in tags:
            if t != 'svg':
                tag_counts[t] = tag_counts.get(t, 0) + 1
        return {
            "width": w_match.group(1) if w_match else "unknown",
            "height": h_match.group(1) if h_match else "unknown",
            "viewBox": vb_match.group(1) if vb_match else "unknown",
            "element_count": len(tags), "elements": tag_counts,
        }

    @tool(description="Detect media type", category="classify")
    async def classify_media(self, filename: str) -> Dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        image = {"jpg","jpeg","png","gif","webp","svg","bmp","ico","tiff","heic"}
        video = {"mp4","webm","mkv","avi","mov","flv","wmv","m4v"}
        audio = {"mp3","wav","ogg","flac","aac","m4a","wma","opus"}
        if ext in image:
            media_type = "image"
        elif ext in video:
            media_type = "video"
        elif ext in audio:
            media_type = "audio"
        else:
            media_type = "other"
        return {"filename": filename, "extension": ext, "media_type": media_type}

    @tool(description="Calculate optimal image compression", category="image")
    async def compression_quality(self, file_size_bytes: int, target_kb: int = 200) -> Dict:
        quality = max(10, min(95, int(100 * target_kb * 1024 / max(1, file_size_bytes))))
        return {"file_size_bytes": file_size_bytes, "target_kb": target_kb, "quality": quality}

    @tool(description="Video duration format conversion", category="video")
    async def duration_format(self, seconds: float = 0, time_str: str = "") -> Dict:
        if seconds and not time_str:
            h, r = divmod(int(seconds), 3600)
            m, s = divmod(r, 60)
            time_str = f"{h:02d}:{m:02d}:{s:02d}"
        elif time_str:
            parts = list(map(int, time_str.split(":")))
            if len(parts) == 3:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
        return {"seconds": seconds, "formatted": time_str}

    @tool(description="Generate screenshot command", category="image")
    async def screenshot_command(self, platform: str = "android") -> Dict:
        cmds = {
            "android": "screencap -p /sdcard/screenshot.png && echo 'Saved to /sdcard/screenshot.png'",
            "linux": "import -window root screenshot.png  # ImageMagick",
            "mac": "screencapture screenshot.png",
            "windows": "nircmd savescreenshot screenshot.png",
        }
        cmd = cmds.get(platform.lower(), cmds["linux"])
        return {"platform": platform, "command": cmd, "output": "screenshot.png"}
