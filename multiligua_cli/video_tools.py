"""
multiligua_cli/video_tools.py — Video Processing Tools

Tools for video manipulation, format conversion, trimming,
merging, and analysis. Supports MP4, AVI, MKV, MOV, WebM, and more.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional


class VideoToolsWorker:
    """Video processing and manipulation tools."""

    worker_id = "video_tools"
    version = "0.19.0"
    tier = "code"

    def __init__(self):
        self.tools = {}
        self._register_tools()

    # ─── Format Conversion ───────────────────────────────────────────────

    def convert_format(
        self,
        input_path: str,
        output_path: str,
        format: str = "mp4",
        quality: str = "medium",
    ) -> Dict[str, Any]:
        """Convert video between formats."""
        try:
            import subprocess

            presets = {
                "high": "slow",
                "medium": "medium",
                "low": "fast",
            }
            preset = presets.get(quality, "medium")

            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264",
                "-preset", preset,
                "-c:a", "aac",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "input": input_path,
                    "output": output_path,
                    "format": format,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found. Install ffmpeg."}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Get Metadata ────────────────────────────────────────────────────

    def get_metadata(self, video_path: str) -> Dict[str, Any]:
        """Get video file metadata."""
        try:
            import subprocess
            import json

            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {"status": "ok", "metadata": data}
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Trim ────────────────────────────────────────────────────────────

    def trim(
        self,
        input_path: str,
        output_path: str,
        start: float,
        end: float,
    ) -> Dict[str, Any]:
        """Trim video to specified duration."""
        try:
            import subprocess

            duration = end - start

            cmd = [
                "ffmpeg", "-i", input_path,
                "-ss", str(start),
                "-t", str(duration),
                "-c", "copy",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "start": start,
                    "end": end,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Merge ───────────────────────────────────────────────────────────

    def merge(
        self,
        input_paths: List[str],
        output_path: str,
    ) -> Dict[str, Any]:
        """Merge multiple video files."""
        try:
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for p in input_paths:
                    f.write(f"file '{p}'\n")
                concat_file = f.name

            cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            Path(concat_file).unlink(missing_ok=True)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "files": len(input_paths),
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Resize ──────────────────────────────────────────────────────────

    def resize(
        self,
        input_path: str,
        output_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resize video to specified dimensions."""
        try:
            import subprocess

            if width and height:
                scale = f"{width}:{height}"
            elif width:
                scale = f"{width}:-1"
            elif height:
                scale = f"-1:{height}"
            else:
                return {"status": "error", "error": "Must specify width or height"}

            cmd = [
                "ffmpeg", "-i", input_path,
                "-vf", f"scale={scale}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "width": width,
                    "height": height,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Extract Frames ──────────────────────────────────────────────────

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        fps: float = 1,
        pattern: str = "frame_%04d.png",
    ) -> Dict[str, Any]:
        """Extract frames from video."""
        try:
            import subprocess
            from pathlib import Path

            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_pattern = str(Path(output_dir) / pattern)

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", f"fps={fps}",
                "-q:v", "2",
                output_pattern,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                frames = list(Path(output_dir).glob("*.png"))
                return {
                    "status": "ok",
                    "fps": fps,
                    "frames_extracted": len(frames),
                    "output_dir": output_dir,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Create Video from Frames ────────────────────────────────────────

    def create_from_frames(
        self,
        frame_dir: str,
        output_path: str,
        fps: float = 24,
        pattern: str = "frame_%04d.png",
    ) -> Dict[str, Any]:
        """Create video from image frames."""
        try:
            import subprocess
            from pathlib import Path

            input_pattern = str(Path(frame_dir) / pattern)

            cmd = [
                "ffmpeg", "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "fps": fps,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Extract Audio ───────────────────────────────────────────────────

    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        format: str = "mp3",
    ) -> Dict[str, Any]:
        """Extract audio track from video."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "libmp3lame",
                "-q:a", "2",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "video": video_path,
                    "audio": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Add Audio ───────────────────────────────────────────────────────

    def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Add or replace audio track in video."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0", "-map", "1:a:0",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Compress ────────────────────────────────────────────────────────

    def compress(
        self,
        input_path: str,
        output_path: str,
        crf: int = 28,
    ) -> Dict[str, Any]:
        """Compress video (lower CRF = higher quality)."""
        try:
            import subprocess
            import os

            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264",
                "-crf", str(crf),
                "-c:a", "copy",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                orig_size = os.path.getsize(input_path)
                comp_size = os.path.getsize(output_path)
                ratio = ((orig_size - comp_size) / orig_size) * 100

                return {
                    "status": "ok",
                    "original_size": orig_size,
                    "compressed_size": comp_size,
                    "reduction_percent": round(ratio, 1),
                    "crf": crf,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Speed ───────────────────────────────────────────────────────────

    def change_speed(
        self,
        input_path: str,
        output_path: str,
        factor: float = 1.0,
    ) -> Dict[str, Any]:
        """Change video playback speed."""
        try:
            import subprocess

            # Video speed filter
            video_speed = 1.0 / factor
            # Audio speed filter (atempo requires 0.5-2.0)
            audio_speed = factor

            cmd = [
                "ffmpeg", "-i", input_path,
                "-filter:v", f"setpts={video_speed}*PTS",
                "-filter:a", f"atempo={audio_speed}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "speed_factor": factor,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Thumbnail ───────────────────────────────────────────────────────

    def create_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp: float = 0,
        width: int = 320,
    ) -> Dict[str, Any]:
        """Create thumbnail from video frame."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-vf", f"scale={width}:-1",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "timestamp": timestamp,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── GIF from Video ──────────────────────────────────────────────────

    def video_to_gif(
        self,
        video_path: str,
        output_path: str,
        start: float = 0,
        duration: float = 5,
        fps: int = 10,
    ) -> Dict[str, Any]:
        """Convert video segment to GIF."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-ss", str(start),
                "-t", str(duration),
                "-i", video_path,
                "-vf", f"fps={fps},scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "start": start,
                    "duration": duration,
                    "fps": fps,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Subtitles ───────────────────────────────────────────────────────

    def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Burn subtitles into video."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", f"subtitles={subtitle_path}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {"status": "ok", "output": output_path}
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Tool Registration ───────────────────────────────────────────────

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "convert_format": {"description": "Convert video format", "category": "convert"},
            "get_metadata": {"description": "Get video metadata", "category": "info"},
            "trim": {"description": "Trim video", "category": "edit"},
            "merge": {"description": "Merge videos", "category": "edit"},
            "resize": {"description": "Resize video", "category": "edit"},
            "extract_frames": {"description": "Extract frames", "category": "extract"},
            "create_from_frames": {"description": "Create video from frames", "category": "create"},
            "extract_audio": {"description": "Extract audio", "category": "extract"},
            "add_audio": {"description": "Add audio track", "category": "edit"},
            "compress": {"description": "Compress video", "category": "edit"},
            "change_speed": {"description": "Change speed", "category": "edit"},
            "create_thumbnail": {"description": "Create thumbnail", "category": "create"},
            "video_to_gif": {"description": "Convert to GIF", "category": "convert"},
            "add_subtitles": {"description": "Add subtitles", "category": "edit"},
        }
