"""
Gateway Runner - OpenHTTP AI Agent Gateway v1.0.0


"""
from __future__ import annotations
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("gateway.runner")


def _load_config(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            import yaml
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            logger.warning("PyYAML not installed, using defaults")
        except Exception as e:
            logger.warning("Failed to load %s: %s", path, e)
    return {}


async def run_gateway(
    config_path: str = None,
    host: str = None,
    port: int = None,
    enable_legacy: bool = False,
) -> None:

    if config_path is None:
        config_path = os.environ.get(
            "MULTILING_CONFIG",
            str(Path(__file__).parent.parent / "config.yaml"),
        )

    config: Dict[str, Any] = _load_config(config_path)
    gw_cfg = config.get("gateway", {})

    host = host or gw_cfg.get("host", "0.0.0.0")
    port = port or gw_cfg.get("port", 18080)

    if enable_legacy:
        legacy_cfg = config.get("legacy", {})
        legacy_cfg["enable"] = True
        config["legacy"] = legacy_cfg

    from gateway.server import start_gateway

    app, runner, site = await start_gateway(
        host=host, port=port, config=config,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except (NotImplementedError, ValueError):
            pass  

    await stop_event.wait()

    logger.info("Shutting down gateway...")
    await runner.cleanup()
    logger.info("Gateway shutdown complete")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MINXG OpenHTTP Gateway v1.0.0")
    parser.add_argument("--host", default=None, help="Gateway bind host (default: from config)")
    parser.add_argument("--port", type=int, default=None, help="Gateway bind port (default: 18080)")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--legacy", action="store_true",
                        help="Enable legacy workers (C#/Java/Lua/Shell)")
    parser.add_argument("--status", action="store_true",
                        help="Check environment without starting")
    args = parser.parse_args()

    if args.status:
        print("=== Gateway Environment Check ===")
        deps = {"python": True, "aiohttp": False, "yaml": False}
        try:
            import aiohttp  
            deps["aiohttp"] = True
        except ImportError:
            pass
        try:
            import yaml  
            deps["yaml"] = True
        except ImportError:
            pass
        for k, v in deps.items():
            print(f"  {k}: {'✅' if v else '❌'}")
        if not deps["aiohttp"]:
            print("\n  Install: pip install aiohttp")
        sys.exit(0 if all(deps.values()) else 1)

    try:
        asyncio.run(run_gateway(
            config_path=args.config,
            host=args.host,
            port=args.port,
            enable_legacy=args.legacy,
        ))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

__all__ = ["run_gateway"]
