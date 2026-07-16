"""
multiligua_cli/audio_tools.py — Audio Processing Tools

Tools for audio manipulation, format conversion, transcription,
and analysis. Supports MP3, WAV, FLAC, OGG, M4A, and more.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional


class AudioToolsWorker:
    """Audio processing and manipulation tools."""

    worker_id = "audio_tools"
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
        format: str = "mp3",
        bitrate: str = "192k",
    ) -> Dict[str, Any]:
        """Convert audio between formats."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-b:a", bitrate,
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "input": input_path,
                    "output": output_path,
                    "format": format,
                    "bitrate": bitrate,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "error": "ffmpeg not found. Install ffmpeg."}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Get Metadata ────────────────────────────────────────────────────

    def get_metadata(self, audio_path: str) -> Dict[str, Any]:
        """Get audio file metadata."""
        try:
            import subprocess
            import json

            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                audio_path,
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
        duration: float,
    ) -> Dict[str, Any]:
        """Trim audio to specified duration."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-ss", str(start),
                "-t", str(duration),
                "-c", "copy",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "start": start,
                    "duration": duration,
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
        """Merge multiple audio files."""
        try:
            import subprocess
            import tempfile

            # Create concat file
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

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

    # ─── Volume ──────────────────────────────────────────────────────────

    def adjust_volume(
        self,
        input_path: str,
        output_path: str,
        volume_db: float = 0,
    ) -> Dict[str, Any]:
        """Adjust audio volume."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-af", f"volume={volume_db}dB",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "volume_db": volume_db,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Silence Removal ─────────────────────────────────────────────────

    def remove_silence(
        self,
        input_path: str,
        output_path: str,
        threshold: float = -50,
        min_duration: float = 0.5,
    ) -> Dict[str, Any]:
        """Remove silence from audio."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-af", f"silenceremove=start_periods=1:start_threshold={threshold}dB:start_duration={min_duration}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {"status": "ok", "output": output_path}
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
        """Change audio playback speed."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-filter:a", f"atempo={factor}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

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

    # ─── Extract ─────────────────────────────────────────────────────────

    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        format: str = "mp3",
    ) -> Dict[str, Any]:
        """Extract audio from video."""
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

    # ─── Normalize ───────────────────────────────────────────────────────

    def normalize(
        self,
        input_path: str,
        output_path: str,
        target_db: float = -1.0,
    ) -> Dict[str, Any]:
        """Normalize audio volume."""
        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", input_path,
                "-af", f"loudnorm=I={target_db}",
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {"status": "ok", "output": output_path}
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Fade ────────────────────────────────────────────────────────────

    def fade(
        self,
        input_path: str,
        output_path: str,
        fade_in: float = 0,
        fade_out: float = 0,
    ) -> Dict[str, Any]:
        """Apply fade in/out to audio."""
        try:
            import subprocess

            filters = []
            if fade_in > 0:
                filters.append(f"afade=t=in:st=0:d={fade_in}")
            if fade_out > 0:
                filters.append(f"afade=t=out:st=-{fade_out}")

            filter_str = ",".join(filters) if filters else "afade=t=in:st=0:d=0"

            cmd = [
                "ffmpeg", "-i", input_path,
                "-af", filter_str,
                "-y", output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {
                    "status": "ok",
                    "fade_in": fade_in,
                    "fade_out": fade_out,
                    "output": output_path,
                }
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── Tool Registration ───────────────────────────────────────────────

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "convert_format": {"description": "Convert audio format", "category": "convert"},
            "get_metadata": {"description": "Get audio metadata", "category": "info"},
            "trim": {"description": "Trim audio", "category": "edit"},
            "merge": {"description": "Merge audio files", "category": "edit"},
            "adjust_volume": {"description": "Adjust volume", "category": "edit"},
            "remove_silence": {"description": "Remove silence", "category": "edit"},
            "change_speed": {"description": "Change playback speed", "category": "edit"},
            "extract_audio": {"description": "Extract audio from video", "category": "extract"},
            "normalize": {"description": "Normalize volume", "category": "edit"},
            "fade": {"description": "Fade in/out", "category": "edit"},
        }
