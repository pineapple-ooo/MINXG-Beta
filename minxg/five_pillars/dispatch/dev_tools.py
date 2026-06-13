"""
minxg/dev_tools.py — Development & DevOps tools v1.0.0

Git, Docker, package managers (pip, npm, cargo), build systems (make, cmake).
"""
from __future__ import annotations
import os
import subprocess
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


class DevToolsWorker(BaseWorker):
    """Development tools: git, docker, package managers, build systems."""
    worker_id = "dev_tools"
    version = "1.0.0"

    def _register_tools(self):
        tools = [
            ("git_status", "Show git working tree status (modified, staged, untracked files).",
             {"path": "string", "short": "bool"}, self._git_status),
            ("git_log", "Show git commit log history.",
             {"path": "string", "count": "int", "oneline": "bool"}, self._git_log),
            ("git_diff", "Show git diff (unstaged changes).",
             {"path": "string", "staged": "bool", "file": "string"}, self._git_diff),
            ("git_branch", "List git branches, showing current branch.",
             {"path": "string", "remote": "bool"}, self._git_branch),
            ("git_remote", "Show git remote URLs.",
             {"path": "string"}, self._git_remote),
            ("git_last_commit", "Show info about the most recent commit.",
             {"path": "string"}, self._git_last_commit),
            ("docker_ps", "List running Docker containers.",
             {"all": "bool"}, self._docker_ps),
            ("docker_images", "List Docker images.",
             {}, self._docker_images),
            ("docker_logs", "Show logs from a Docker container.",
             {"container": "string", "tail": "int"}, self._docker_logs),
            ("pip_list", "List installed pip packages.",
             {"filter": "string"}, self._pip_list),
            ("pip_install", "Install a pip package.",
             {"package": "string", "upgrade": "bool"}, self._pip_install),
            ("npm_list", "List installed npm packages (global or local).",
             {"path": "string", "depth": "int"}, self._npm_list),
            ("cargo_build", "Run cargo build in a Rust project directory.",
             {"path": "string", "release": "bool"}, self._cargo_build),
            ("make_target", "Run a make target in a project directory.",
             {"path": "string", "target": "string"}, self._make_target),
            ("cmake_build", "Run cmake configure + build in a project directory.",
             {"path": "string", "build_dir": "string"}, self._cmake_build),
            ("shell_command", "Execute a shell command and return output.",
             {"command": "string", "cwd": "string", "timeout": "int"}, self._shell_command),
            ("disk_usage", "Check disk usage of a directory.",
             {"path": "string", "depth": "int", "sort_by_size": "bool"}, self._disk_usage),
            ("find_files", "Find files matching a pattern in a directory.",
             {"path": "string", "pattern": "string", "type": "string"}, self._find_files),
        ]

        for name, desc, params, fn in tools:
            self.tools[name] = type("ToolDef", (), {
                "name": name, "description": desc, "params": params,
                "category": "dev",
                "platforms": ["linux", "macos", "windows", "android"],
                "requires_root": False, "fn": fn,
            })()

    def _run(self, cmd: List[str], cwd: str = "", timeout: int = 30,
             env: Dict = None) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=cwd if cwd else None,
                env=env if env else None,
            )
            return {
                "status": "success",
                "stdout": result.stdout[:20000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Command timeout after {timeout}s"}
        except FileNotFoundError as e:
            return {"status": "error", "error": f"Command not found: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _git_status(self, path: str = ".", short: bool = False) -> Dict[str, Any]:
        cmd = ["git", "-C", path, "status"] + (["--short"] if short else [])
        return self._run(cmd, cwd=path)

    def _git_log(self, path: str = ".", count: int = 10, oneline: bool = False) -> Dict[str, Any]:
        fmt = "--oneline" if oneline else "--format=%h %s (%an, %ar)"
        return self._run(["git", "-C", path, "log", f"-{count}", fmt])

    def _git_diff(self, path: str = ".", staged: bool = False, file: str = "") -> Dict[str, Any]:
        cmd = ["git", "-C", path, "diff"] + (["--staged"] if staged else [])
        if file:
            cmd += ["--", file]
        return self._run(cmd)

    def _git_branch(self, path: str = ".", remote: bool = False) -> Dict[str, Any]:
        cmd = ["git", "-C", path, "branch"] + (["-a"] if remote else [])
        return self._run(cmd)

    def _git_remote(self, path: str = ".") -> Dict[str, Any]:
        return self._run(["git", "-C", path, "remote", "-v"])

    def _git_last_commit(self, path: str = ".") -> Dict[str, Any]:
        return self._run(["git", "-C", path, "log", "-1", "--format=%H|%s|%an|%ai|%b"])

    def _docker_ps(self, all: bool = False) -> Dict[str, Any]:
        return self._run(["docker", "ps"] + (["-a"] if all else []))

    def _docker_images(self) -> Dict[str, Any]:
        return self._run(["docker", "images"])

    def _docker_logs(self, container: str, tail: int = 100) -> Dict[str, Any]:
        return self._run(["docker", "logs", "--tail", str(tail), container])

    def _pip_list(self, filter: str = "") -> Dict[str, Any]:
        return self._run(["pip", "list"] + (["|", "grep", filter] if filter else []))

    def _pip_install(self, package: str, upgrade: bool = False) -> Dict[str, Any]:
        cmd = ["pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        cmd.append(package)
        return self._run(cmd, timeout=120)

    def _npm_list(self, path: str = ".", depth: int = 0) -> Dict[str, Any]:
        return self._run(["npm", "list", f"--depth={depth}"], cwd=path)

    def _cargo_build(self, path: str = ".", release: bool = False) -> Dict[str, Any]:
        cmd = ["cargo", "build"]
        if release:
            cmd.append("--release")
        return self._run(cmd, cwd=path, timeout=120)

    def _make_target(self, path: str = ".", target: str = "") -> Dict[str, Any]:
        cmd = ["make"] + ([target] if target else [])
        return self._run(cmd, cwd=path, timeout=60)

    def _cmake_build(self, path: str = ".", build_dir: str = "build") -> Dict[str, Any]:
        import os as _os
        build_path = _os.path.join(path, build_dir)
        _os.makedirs(build_path, exist_ok=True)
        cfg = self._run(["cmake", ".."], cwd=build_path)
        if cfg["exit_code"] != 0:
            return {"status": "error", "error": f"CMake config failed: {cfg['stderr']}"}
        build = self._run(["cmake", "--build", "."], cwd=build_path, timeout=180)
        return build

    def _shell_command(self, command: str, cwd: str = "", timeout: int = 30) -> Dict[str, Any]:
        return self._run(command, cwd=cwd, timeout=timeout, shell=True)

    def _disk_usage(self, path: str = ".", depth: int = 1, sort_by_size: bool = True) -> Dict[str, Any]:
        args = ["du", "-h", f"--max-depth={depth}"]
        if sort_by_size:
            args += ["|", "sort", "-hr"]
        return self._run(args, cwd=path)

    def _find_files(self, path: str = ".", pattern: str = "*",
                    type: str = "f") -> Dict[str, Any]:
        args = ["find", path, "-type", type, "-name", pattern]
        return self._run(args, timeout=30)