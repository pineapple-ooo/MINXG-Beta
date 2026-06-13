"""
  python -m py_workers.server --port 19011
  python -m py_workers.server --workers fs_io system network
  python -m py_workers.workers_runner --status
"""
import os
import sys
import asyncio
import logging
import argparse

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(levelname)-7s | %(message)s',
                    handlers=[logging.StreamHandler(sys.stderr)])
log = logging.getLogger("workers_runner")


def check_deps() -> dict:
    result = {"python": True, "aiohttp": False, "py_workers": False}
    try:
        import aiohttp  # noqa
        result["aiohttp"] = True
    except ImportError:
        pass
    try:
        import py_workers  # noqa
        result["py_workers"] = True
    except ImportError:
        pass
    return result


def cmd_status():
    deps = check_deps()
    for k, v in deps.items():
        print(f"  {k}: {'✅' if v else '❌'}")
    if not deps["aiohttp"]:
        pass
    sys.exit(0 if all(deps.values()) else 1)


def main():
    parser = argparse.ArgumentParser(description="py_workers HTTP RPC runner v1.0.0")
    parser.add_argument("--host", default=os.environ.get("WORKER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WORKER_PORT", "19001")))
    parser.add_argument("--workers", nargs="*", default=None)
    args = parser.parse_args()

    if args.status:
        cmd_status()

    deps = check_deps()
    if not deps["aiohttp"]:
        sys.exit(1)

    from py_workers.server import start_server
    try:
        asyncio.run(start_server(args.host, args.port, args.workers))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
