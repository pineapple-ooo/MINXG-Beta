"""Notification tools — send notifications across platforms."""
from minxg.base import BaseWorker, tool

class NotifyWorker(BaseWorker):
    facade_alias = "notify_worker"
    worker_id = "notify_worker"
    version = "0.17.1"

    @tool
    async def notify_terminal(self, message: str = "", title: str = "MINXG") -> dict:
        """Send a terminal notification (bell + message)."""
        print(f"\a[{title}] {message}")
        return {"sent": True, "method": "terminal_bell"}

    @tool
    async def notify_desktop(self, message: str = "", title: str = "MINXG") -> dict:
        """Send desktop notification (Linux notify-send / macOS osascript)."""
        import subprocess, shutil
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], timeout=5)
            return {"sent": True, "method": "notify-send"}
        elif shutil.which("osascript"):
            subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'], timeout=5)
            return {"sent": True, "method": "osascript"}
        return {"sent": False, "reason": "No desktop notifier available"}

    @tool
    async def notify_sound(self, frequency: int = 800, duration_ms: int = 200) -> dict:
        """Play a system beep/sound."""
        import sys
        if sys.platform == "win32":
            import winsound
            winsound.Beep(frequency, duration_ms)
        else:
            print("\a", end="", flush=True)
        return {"played": True, "frequency": frequency, "duration_ms": duration_ms}

    @tool
    async def clipboard_copy(self, text: str) -> dict:
        """Copy text to system clipboard."""
        import subprocess, shutil
        for cmd in [["xclip", "-selection", "clipboard"], ["pbcopy"], ["clip"]]:
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text.encode(), timeout=5)
                return {"copied": True, "method": cmd[0]}
        return {"copied": False, "reason": "No clipboard tool"}

    @tool
    async def clipboard_paste(self) -> dict:
        """Paste text from system clipboard."""
        import subprocess, shutil
        for cmd in [["xclip", "-selection", "clipboard", "-o"], ["pbpaste"], ["powershell", "Get-Clipboard"]]:
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return {"text": r.stdout.strip(), "method": cmd[0]}
        return {"text": "", "reason": "No clipboard tool"}

    @tool
    async def progress_bar(self, current: int = 0, total: int = 100, width: int = 40) -> dict:
        """Render an ASCII progress bar."""
        pct = min(current / max(total, 1), 1.0)
        filled = int(width * pct)
        bar = "█" * filled + "░" * (width - filled)
        return {"bar": f"[{bar}] {pct:.0%}", "percent": round(pct*100)}

    @tool
    async def spinner_frames(self, style: str = "dots") -> dict:
        """Get spinner animation frames."""
        spinners = {
            "dots": ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"],
            "line": ["|","/","-","\\"],
            "grow": ["▁","▃","▄","▅","▆","▇","█","▇","▆","▅","▄","▃"],
            "bounce": ["⠁","⠂","⠄","⡀","⢀","⠠","⠐","⠈"],
        }
        return {"frames": spinners.get(style, spinners["dots"]), "style": style}

    @tool
    async def countdown_timer(self, seconds: int = 5) -> dict:
        """Run a countdown timer."""
        import time
        for i in range(seconds, 0, -1):
            print(f"\r⏱ {i}s remaining...", end="", flush=True)
            time.sleep(1)
        print("\r✅ Done!          ")
        return {"completed": True, "seconds": seconds}
