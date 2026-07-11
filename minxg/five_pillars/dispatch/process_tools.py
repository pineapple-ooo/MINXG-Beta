"""
"""
from __future__ import annotations
from typing import Dict
from minxg.base import BaseWorker, tool


class ProcessToolsWorker(BaseWorker):
    facade_alias = "sh_exec"
    worker_id = "process_tools"
    version = "0.17.1"

    @tool(description="Generate process search command", category="ps")
    async def find_process(self, name: str) -> Dict:
        return {
            "pgrep": f"pgrep -f {name}",
            "ps_aux": f"ps aux | grep {name}",
            "pidof": f"pidof {name}",
            "detail": f"ps -p $(pgrep -f {name}) -o pid,ppid,user,%cpu,%mem,cmd 2>/dev/null",
        }

    @tool(description="Check if port is in use", category="port")
    async def port_check(self, port: int) -> Dict:
        return {
            "lsof": f"lsof -i :{port}",
            "ss": f"ss -tlnp | grep :{port}",
            "netstat": f"netstat -tlnp | grep :{port}",
            "fuser": f"fuser {port}/tcp",
            "port": port,
        }

    @tool(description="Generate kill process command", category="kill")
    async def kill_process(self, pid_or_name: str, signal: str = "SIGTERM") -> Dict:
        sig_num = {"SIGTERM": 15, "SIGKILL": 9, "SIGINT": 2, "SIGHUP": 1}
        sig = signal.upper()
        num = sig_num.get(sig, 15)
        is_pid = pid_or_name.isdigit()
        if is_pid:
            cmds = {
                "kill": f"kill -{num} {pid_or_name}",
                "force": f"kill -9 {pid_or_name}",
            }
        else:
            cmds = {
                "pkill": f"pkill -{num} -f '{pid_or_name}'",
                "killall": f"killall -{num} '{pid_or_name}'",
            }
        return {"pid_or_name": pid_or_name, "signal": sig, "signal_num": num,
                "commands": cmds, "is_pid": is_pid}

    @tool(description="Generate system resource monitoring command", category="resources")
    async def system_monitor(self, resource: str = "all") -> Dict:
        cmds = {
            "cpu": "top -bn1 | head -5",
            "memory": "free -h",
            "disk": "df -h",
            "network": "iftop -n -t -s 1 2>/dev/null || netstat -i",
            "io": "iostat -x 1 1 2>/dev/null || vmstat 1 1",
            "processes": "ps aux --sort=-%cpu | head -10",
            "all": "echo '=== CPU ===' && top -bn1 | head -5 && echo '=== MEM ===' && free -h && echo '=== DISK ===' && df -h",
        }
        cmd = cmds.get(resource, cmds["all"])
        return {"resource": resource, "command": cmd}

    @tool(description="Generate background process command", category="background")
    async def background_process(self, command: str, method: str = "nohup",
                                  logfile: str = "app.log") -> Dict:
        methods = {
            "nohup": f"nohup {command} > {logfile} 2>&1 &",
            "screen": f"screen -dmS app {command}",
            "tmux": f"tmux new-session -d -s app '{command}'",
            "disown": f"{command} & disown",
        }
        cmd = methods.get(method, methods["nohup"])
        return {"method": method, "command": cmd, "logfile": logfile,
                "check": f"tail -f {logfile}"}

    @tool(description="Generate crontab task command", category="cron")
    async def cronjob_command(self, schedule: str, command: str) -> Dict:
        return {
            "cron_line": f"{schedule} {command}",
            "add_cmd": f'(crontab -l 2>/dev/null; echo "{schedule} {command}") | crontab -',
            "list_cmd": "crontab -l",
            "remove_cmd": f"crontab -l | grep -v '{command}' | crontab -",
        }

    @tool(description="Adjust process priority", category="nice")
    async def process_priority(self, pid: int, nice_value: int = 0) -> Dict:
        if nice_value < -20 or nice_value > 19:
            return {"error": "nice value must be between -20 and 19"}
        return {
            "pid": pid, "nice": nice_value,
            "command": f"renice {nice_value} -p {pid}",
        }

    @tool(description="Generate systemd service command", category="systemd")
    async def systemd_manage(self, service: str, action: str = "status") -> Dict:
        actions = {
            "start": f"sudo systemctl start {service}",
            "stop": f"sudo systemctl stop {service}",
            "restart": f"sudo systemctl restart {service}",
            "status": f"systemctl status {service}",
            "enable": f"sudo systemctl enable {service}",
            "disable": f"sudo systemctl disable {service}",
            "logs": f"journalctl -u {service} -f",
            "reload": f"sudo systemctl reload {service}",
        }
        cmd = actions.get(action, actions["status"])
        return {"service": service, "action": action, "command": cmd}
