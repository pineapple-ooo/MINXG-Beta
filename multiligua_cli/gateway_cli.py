"""
multiligua_cli/gateway_cli.py — OpenHTTP Gateway lifecycle commands.

Commands:
    minxg gateway              Run the gateway in foreground (default)
    minxg gateway --detach     Start gateway as background service
    minxg gateway stop          Stop the gateway service / process
    minxg gateway status       Show gateway status

v0.18.2 — the old `gateway start` sub-command has been removed.
`minxg gateway` with no sub-command IS the start command (foreground
by default, --detach for background).  This is simpler and matches
the user's preference for fewer, cleaner commands.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

from multiligua_cli.utils import (
    HAS_RICH,
    console,
    ensure_config,
    load_config,
    print_banner,
    print_dim,
    print_error,
    print_info,
    print_success,
)


@ensure_config
def gateway_foreground(args) -> int:
    """Run the OpenHTTP Gateway in foreground (blocking).

    This is the default when the user runs `minxg gateway` with no
    sub-command.  If --detach is passed, the caller should have
    already dispatched to gateway_detach() instead — but if we
    somehow get here with --detach, redirect.
    """
    if getattr(args, "detach", False):
        return gateway_detach(args)

    print_banner()
    print_info("Starting OpenHTTP AI Agent Gateway...")
    print_info("Workers: py_workers (19 workers, 177 tools)")
    print_info("Press Ctrl+C to stop\n")

    try:
        from gateway.runner import run_gateway

        asyncio.run(run_gateway())
        return 0
    except KeyboardInterrupt:
        print_info("Gateway stopped.")
        return 0
    except Exception as e:
        print_error(f"Error running gateway: {e}")
        import traceback
        traceback.print_exc()
        return 1


@ensure_config
def gateway_detach(args) -> int:
    """Start the gateway as a background service (systemd or nohup).

    Replaces the old `gateway_start`.  Triggered by `minxg gateway --detach`.
    """
    print_banner()
    print_info("Starting gateway in background mode...\n")

    try:
        # systemd path
        if os.path.exists("/proc/1/comm"):
            with open("/proc/1/comm") as f:
                init = f.read().strip()
            if init == "systemd":
                return _install_systemd_service()

        # nohup fallback
        return _start_background_nohup()

    except Exception as e:
        print_error(f"Error starting gateway in background: {e}")
        return 1


def _install_systemd_service() -> int:
    service_file = os.path.expanduser(
        "~/.config/systemd/user/multiling-gateway.service"
    )
    os.makedirs(os.path.dirname(service_file), exist_ok=True)

    with open(service_file, "w") as f:
        f.write(f"""[Unit]
Description=MINXG OpenHTTP Gateway
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} -m multiligua_cli.main gateway
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
""")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(
        ["systemctl", "--user", "enable", "multiling-gateway"], check=False
    )
    subprocess.run(
        ["systemctl", "--user", "start", "multiling-gateway"], check=False
    )

    print_success("Gateway service installed and started (systemd).")
    print_dim(f"Service file: {service_file}")
    print_dim("Check: systemctl --user status multiling-gateway")
    return 0


def _start_background_nohup() -> int:
    pidfile = os.path.expanduser("~/.multiling/gateway.pid")
    logfile = os.path.expanduser("~/.multiling/gateway.log")
    os.makedirs(os.path.dirname(pidfile), exist_ok=True)

    with open(pidfile, "w") as f:
        f.write("0")

    # Build the argv for the background gateway process.
    # The child re-enters `minxg gateway` (no sub) which runs
    # gateway_foreground() and actually serves.
    argv = [sys.executable, "-m", "multiligua_cli.main", "gateway"]
    proc = subprocess.Popen(
        argv,
        stdout=open(logfile, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    time.sleep(2)

    with open(pidfile, "w") as f:
        f.write(str(proc.pid))

    print_success("Gateway started in background.")
    print_dim(f"PID: {proc.pid}")
    print_dim(f"Log: {logfile}")
    return 0


def gateway_stop(args) -> int:
    """Stop the gateway service / background process."""
    try:
        pidfile = os.path.expanduser("~/.multiling/gateway.pid")

        if os.path.exists("/proc/1/comm"):
            with open("/proc/1/comm") as f:
                if "systemd" in f.read():
                    subprocess.run(
                        ["systemctl", "--user", "stop", "multiling-gateway"],
                        check=False,
                    )
                    print_success("Gateway service stopped (systemd).")
                    return 0

        if os.path.exists(pidfile):
            with open(pidfile) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            os.remove(pidfile)
            print_success(f"Gateway process stopped (PID {pid}).")
            return 0

        print_info("No gateway service or process found.")
        return 0

    except Exception as e:
        print_error(f"Error stopping gateway: {e}")
        return 1


def gateway_status(args) -> int:
    """Show gateway service / process status."""
    try:
        pidfile = os.path.expanduser("~/.multiling/gateway.pid")

        if os.path.exists("/proc/1/comm"):
            with open("/proc/1/comm") as f:
                if "systemd" in f.read():
                    result = subprocess.run(
                        ["systemctl", "--user", "status", "multiling-gateway"],
                        capture_output=True,
                        text=True,
                    )
                    if HAS_RICH:
                        console.print(result.stdout)
                    else:
                        print(result.stdout)
                    return 0

        if os.path.exists(pidfile):
            with open(pidfile) as f:
                pid = int(f.read().strip())
            if os.path.exists(f"/proc/{pid}"):
                print_success(f"Gateway running (PID: {pid})")
            else:
                print_error("Gateway not running (stale PID file)")
                os.remove(pidfile)
            return 0

        print_error("Gateway not running")
        return 0

    except Exception as e:
        print_error(f"Error checking gateway status: {e}")
        return 1


# Backward-compat alias: old code that imported `gateway_start` gets
# redirected to the new detach function.
gateway_start = gateway_detach

# Module-level convenience: `gateway = gateway_foreground` so
# main.py can do `from gateway_cli import gateway`.
gateway = gateway_foreground
