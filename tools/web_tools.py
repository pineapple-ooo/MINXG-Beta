"""Web Tools - HTTP fetching and network operations."""

import json
import logging
import socket
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Optional

logger = logging.getLogger(__name__)

FETCH_URL_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "URL to fetch"},
        "method": {"type": "string", "description": "HTTP method", "default": "GET"},
        "headers": {"type": "object", "description": "Custom headers"},
        "body": {"type": "string", "description": "Request body for POST/PUT"},
        "timeout": {"type": "number", "description": "Timeout in seconds", "default": 30},
    },
    "required": ["url"],
}

HTTP_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "URL to check"},
        "timeout": {"type": "number", "description": "Timeout in seconds", "default": 10},
    },
    "required": ["url"],
}

PING_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "host": {"type": "string", "description": "Host to ping"},
        "count": {"type": "integer", "description": "Number of pings", "default": 4},
        "timeout": {"type": "number", "description": "Timeout in seconds", "default": 10},
    },
    "required": ["host"],
}


def _handle_fetch_url(args: dict) -> str:
    """Fetch content from a URL."""
    url = args.get("url", "")
    if not url:
        return json.dumps({"error": "url is required"})
    
    method = args.get("method", "GET").upper()
    headers = args.get("headers", {})
    body = args.get("body")
    timeout = args.get("timeout", 30)
    
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return json.dumps({"error": "Only HTTP/HTTPS URLs are supported"})
    
    if parsed.scheme == "file" or parsed.scheme == "ftp":
        return json.dumps({"error": f"Scheme {parsed.scheme} is not allowed"})
    
    try:
        req = urllib.request.Request(url, method=method)
        for key, value in headers.items():
            req.add_header(key, value)
        
        if body and method in ("POST", "PUT", "PATCH"):
            if isinstance(body, str):
                body = body.encode("utf-8")
            req.data = body
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1", errors="replace")
            
            return json.dumps({
                "ok": True,
                "status_code": response.status,
                "headers": dict(response.headers),
                "content": text[:200000],
            })
    except urllib.error.HTTPError as e:
        return json.dumps({
            "ok": False,
            "error": f"HTTP {e.code}: {e.reason}",
            "status_code": e.code,
        })
    except urllib.error.URLError as e:
        return json.dumps({
            "ok": False,
            "error": f"URL error: {e.reason}",
        })
    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"Fetch error: {e}",
        })


def _handle_http_status(args: dict) -> str:
    """Check HTTP status of a URL."""
    url = args.get("url", "")
    if not url:
        return json.dumps({"error": "url is required"})
    
    timeout = args.get("timeout", 10)
    
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"),
            timeout=timeout
        ) as response:
            return json.dumps({
                "ok": True,
                "status_code": response.status,
                "url": url,
            })
    except urllib.error.HTTPError as e:
        return json.dumps({
            "ok": True,
            "status_code": e.code,
            "url": url,
        })
    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": str(e),
            "url": url,
        })


def _handle_ping_tool(args: dict) -> str:
    """Ping a host using socket connection (simplified ping)."""
    host = args.get("host", "")
    if not host:
        return json.dumps({"error": "host is required"})
    
    count = args.get("count", 4)
    timeout = args.get("timeout", 10)
    
    results = []
    for i in range(count):
        try:
            start = __import__("time").time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, 80 if not ":" in host else int(host.split(":")[-1]) if host.split(":")[-1].isdigit() else 80))
            elapsed = __import__("time").time() - start
            sock.close()
            
            results.append({
                "seq": i + 1,
                "host": host,
                "time": f"{elapsed * 1000:.2f}ms",
                "ok": result == 0,
            })
        except Exception as e:
            results.append({
                "seq": i + 1,
                "host": host,
                "error": str(e),
                "ok": False,
            })
    
    return json.dumps({
        "host": host,
        "packets_sent": count,
        "packets_received": sum(1 for r in results if r["ok"]),
        "results": results,
    })


def _check_web_reqs() -> bool:
    """Check if web tools are available."""
    return True


from tools.registry import registry

registry.register(
    name="fetch_url",
    toolset="web",
    schema=FETCH_URL_SCHEMA,
    handler=_handle_fetch_url,
    check_fn=_check_web_reqs,
    emoji="",
    max_result_size_chars=200000,
)

registry.register(
    name="http_status",
    toolset="web",
    schema=HTTP_STATUS_SCHEMA,
    handler=_handle_http_status,
    check_fn=_check_web_reqs,
    emoji="",
    max_result_size_chars=5000,
)

registry.register(
    name="ping_tool",
    toolset="web",
    schema=PING_TOOL_SCHEMA,
    handler=_handle_ping_tool,
    check_fn=_check_web_reqs,
    emoji="",
    max_result_size_chars=10000,
)
