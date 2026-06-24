"""Terminal Tool - Shell execution with approval system."""

import json
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

_approval_callback: Optional[Callable] = None
_approval_lock = threading.Lock()


def set_approval_callback(cb: Callable) -> None:
    """Set the callback for dangerous command approval."""
    global _approval_callback
    with _approval_lock:
        _approval_callback = cb


def _get_approval_callback() -> Optional[Callable]:
    with _approval_lock:
        return _approval_callback


DANGEROUS_COMMANDS = frozenset({
    "rm", "del", "rd", "rmdir",
    "shutdown", "halt", "poweroff", "init 0",
    "dd",
    "mkfs", "fdisk", "parted",
    ":(){ :|:& };:",
    "chmod 777", "chmod -R 777",
    "sudo", "su -",
})


def _is_dangerous_command(command: str) -> bool:
    """Check if command is potentially dangerous."""
    lower = command.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if lower == dangerous or lower.startswith(dangerous + " "):
            return True
    for dangerous in ["rm", "del", "dd", "mkfs"]:
        if lower.startswith(dangerous + " ") and ("-rf" in lower or "-r " in lower or "-f" in lower):
            return True
    return False


def _prompt_approval(command: str, description: str) -> str:
    """Prompt user for dangerous command approval."""
    callback = _get_approval_callback()
    if callback:
        return callback(command, description)
    return "deny"


EXECUTE_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to execute"},
        "timeout": {"type": "number", "description": "Max seconds to wait", "default": 60},
        "cwd": {"type": "string", "description": "Working directory"},
    },
    "required": ["command"],
}

EXECUTE_CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Python code to execute"},
        "timeout": {"type": "number", "description": "Max seconds to wait", "default": 60},
    },
    "required": ["code"],
}


def _handle_execute_command(args: dict) -> str:
    """Execute a shell command."""
    command = args.get("command", "")
    if not command:
        return json.dumps({"error": "command is required"})
    
    timeout = args.get("timeout", 60)
    cwd = args.get("cwd")
    
    if _is_dangerous_command(command):
        description = f"Potentially dangerous command: {command[:50]}..."
        approval = _prompt_approval(command, description)
        if approval != "approve" and approval != "once":
            return json.dumps({
                "error": f"Command denied. Set approval to 'approve' or 'once' to allow: {command[:50]}..."
            })
        logger.warning(f"Approved dangerous command: {command[:50]}...")
    
    dangerous_patterns = [
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r"python.*-m\s+pip\s+install.*--user",
    ]
    for pattern in dangerous_patterns:
        import re
        if re.search(pattern, command, re.IGNORECASE):
            return json.dumps({
                "error": f"Command blocked for security: potentially dangerous pattern detected"
            })
    
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        result = subprocess.run(
            command,
            shell=True,
            executable=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**os.environ, "TERM": "xterm-256color"},
        )
        
        output = result.stdout
        if result.stderr and result.returncode != 0:
            output = result.stdout + "\nSTDERR:\n" + result.stderr
        
        return json.dumps({
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:50000],
            "stderr": result.stderr[:10000] if result.stderr else "",
            "command": command,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Command timed out after {timeout}s", "command": command})
    except Exception as e:
        return json.dumps({"error": f"Execution error: {e}", "command": command})


def _handle_execute_code(args: dict) -> str:
    """Execute Python code."""
    code = args.get("code", "")
    if not code:
        return json.dumps({"error": "code is required"})
    
    timeout = args.get("timeout", 60)
    
    try:
        import concurrent.futures
        import sys
        import io
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        
        result_container = {}
        exception_container = {}
        
        def run_code():
            try:
                exec(code, {"__name__": "__main__"})
                result_container["stdout"] = sys.stdout.getvalue()
                result_container["ok"] = True
            except Exception as e:
                exception_container["error"] = f"{type(e).__name__}: {e}"
                result_container["stdout"] = sys.stdout.getvalue()
                result_container["ok"] = False
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_code)
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                return json.dumps({"error": f"Code execution timed out after {timeout}s"})
        
        response = {
            "ok": result_container.get("ok", False),
            "stdout": result_container.get("stdout", "")[:50000],
        }
        if exception_container.get("error"):
            response["error"] = exception_container["error"]
        
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": f"Code execution setup error: {e}"})


def _check_terminal_reqs() -> bool:
    """Check if terminal execution is available."""
    return True


from tools.registry import registry

registry.register(
    name="execute_command",
    toolset="terminal",
    schema=EXECUTE_COMMAND_SCHEMA,
    handler=_handle_execute_command,
    check_fn=_check_terminal_reqs,
    emoji="",
    max_result_size_chars=50000,
)

registry.register(
    name="execute_code",
    toolset="terminal",
    schema=EXECUTE_CODE_SCHEMA,
    handler=_handle_execute_code,
    check_fn=_check_terminal_reqs,
    emoji="",
    max_result_size_chars=50000,
)
