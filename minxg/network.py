"""
Network tools — delegates HTTP/DNS/SSL to Go gateway when available.
"""
from __future__ import annotations
import os
import re
import json
import socket
import asyncio
import ipaddress
from typing import Dict, List, Optional
from urllib.parse import urlparse
from .base import BaseWorker, tool

_HAS_GO = False
_go_client = None

try:
    from .go_client import GoGatewayClient
    _go_client = GoGatewayClient()
    if _go_client.ready():
        _HAS_GO = True
except Exception:
    pass

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class NetworkWorker(BaseWorker):
    worker_id = "network"
    version = "1.1.0"

    @tool(description="HTTP request (Go-native or aiohttp/urllib fallback)",
          category="http")
    async def http_request(self, url: str, method: str = "GET", headers: dict = None,
                          body: str = None, timeout: int = 30, follow_redirects: bool = True) -> Dict:
        if _HAS_GO:
            try:
                resp = _go_client.proxy_request(url, method, headers=headers or {},
                                                body=body or "", timeout=timeout,
                                                follow_redirects=follow_redirects)
                if "error" not in resp:
                    return {
                        "url": url, "method": method.upper(), "status": resp["status"],
                        "headers": resp.get("headers", {}), "body": resp.get("body", "")[:50000],
                        "body_truncated": resp.get("truncated", False),
                        "ok": 200 <= resp["status"] < 400,
                        "go_backend": True,
                    }
            except Exception:
                pass
        if not HAS_AIOHTTP:
            return self._urllib_request(url, method, headers or {}, body, timeout, follow_redirects)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                kwargs = {"headers": headers or {}, "allow_redirects": follow_redirects}
                if body and method.upper() in ("POST", "PUT", "PATCH"):
                    kwargs["data"] = body
                async with session.request(method.upper(), url, **kwargs) as r:
                    text = await r.text()
                    return {
                        "url": url, "method": method.upper(), "status": r.status,
                        "headers": dict(r.headers), "body": text[:50000],
                        "body_truncated": len(text) > 50000, "ok": 200 <= r.status < 400,
                    }
        except asyncio.TimeoutError:
            return {"url": url, "error": "timeout", "timeout": timeout}
        except Exception as e:
            return {"url": url, "error": str(e), "error_type": type(e).__name__}

    def _urllib_request(self, url: str, method: str, headers: dict, body: str,
                       timeout: int, follow_redirects: bool) -> Dict:
        import urllib.error
        try:
            req = urllib.request.Request(url, data=body.encode() if body else None,
                                         headers=headers, method=method.upper())
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
                return {"url": url, "method": method.upper(), "status": r.status,
                        "headers": dict(r.headers), "body": text[:50000],
                        "body_truncated": len(text) > 50000, "ok": 200 <= r.status < 400,
                        "note": "urllib fallback"}
        except urllib.error.HTTPError as e:
            return {"url": url, "status": e.code, "error": e.reason}
        except Exception as e:
            return {"url": url, "error": str(e)}

    @tool(description="HTTP HEAD/GET check URL status", category="http")
    async def http_status(self, url: str, method: str = "GET", timeout: int = 10) -> Dict:
        if HAS_AIOHTTP:
            try:
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    async with session.request(method.upper(), url, allow_redirects=True) as r:
                        return {
                            "url": url,
                            "status": r.status,
                            "ok": 200 <= r.status < 400,
                            "reason": r.reason,
                        }
            except Exception as e:
                return {"url": url, "error": str(e)}
        return await self.http_request(url, method, timeout=timeout)

    @tool(description="TCP port check (host/port/timeout)", category="tcp")
    async def port_check(self, host: str, port: int, timeout: float = 3.0) -> Dict:
        try:
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return {"host": host, "port": port, "open": True}
        except asyncio.TimeoutError:
            return {"host": host, "port": port, "open": False, "error": "timeout"}
        except OSError as e:
            return {"host": host, "port": port, "open": False, "error": str(e),
                    "errno": e.errno}

    @tool(description="Ping host (TCP handshake, works without ICMP)",
          category="tcp")
    async def ping(self, host: str, count: int = 4, timeout: int = 10,
                  port: int = 80) -> Dict:
        results = []
        for i in range(count):
            t0 = asyncio.get_event_loop().time()
            try:
                fut = asyncio.open_connection(host, port)
                reader, writer = await asyncio.wait_for(fut, timeout=timeout / count)
                dt = (asyncio.get_event_loop().time() - t0) * 1000
                writer.close()
                results.append({"seq": i + 1, "success": True, "time_ms": round(dt, 2)})
            except Exception as e:
                results.append({"seq": i + 1, "success": False, "error": str(e)})
        success = [r for r in results if r.get("success")]
        return {
            "host": host, "port": port, "count": count,
            "transmitted": count, "received": len(success),
            "loss_percent": round((count - len(success)) / count * 100, 1),
            "times_ms": [r["time_ms"] for r in success],
            "results": results,
        }

    @tool(description="WebSocket client (send message, receive response, close)", category="http")
    async def websocket_connect(self, url: str, message: str = "", timeout: int = 30) -> Dict:
        try:
            import websockets  # type: ignore
        except ImportError:
            return {"hint": "pip install websockets"}
        try:
            async with websockets.connect(url, close_timeout=5) as ws:
                if message:
                    await ws.send(message)
                reply = await asyncio.wait_for(ws.recv(), timeout=timeout)
                return {"url": url, "sent": message, "received": str(reply)[:10000]}
        except Exception as e:
            return {"url": url, "error": str(e), "error_type": type(e).__name__}

    @tool(description="DNS resolution (Go-native or socket fallback)", category="dns")
    async def dns_resolve(self, host: str) -> Dict:
        if _HAS_GO:
            try:
                resp = _go_client.dns_lookup(host)
                if "error" not in resp:
                    return {"host": host, "ips": resp.get("ips", []), "count": len(resp.get("ips", [])),
                            "cname": resp.get("cname", ""), "mx": resp.get("mx", []),
                            "go_backend": True}
            except Exception:
                pass
        try:
            infos = socket.getaddrinfo(host, None)
            ips = sorted(set(i[4][0] for i in infos))
            return {"host": host, "ips": ips, "count": len(ips)}
        except socket.gaierror as e:
            return {"host": host, "error": str(e)}

    @tool(description="Web search (DDG HTML, no key, rate-limited, unstable)",
          category="web")
    async def web_search(self, query: str, limit: int = 5) -> Dict:
        url = "https://lite.duckduckgo.com/lite/"
        try:
            if HAS_AIOHTTP:
                timeout_obj = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    async with session.post(url, data={"q": query}) as r:
                        html = await r.text()
            else:
                import urllib.parse, urllib.request
                data = urllib.parse.urlencode({"q": query}).encode()
                req = urllib.request.Request(url, data=data,
                                             headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    html = r.read().decode("utf-8", errors="replace")
            results = []
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>',
                                html, re.DOTALL):
                href = m.group(1)
                text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if href.startswith("http") and text:
                    results.append({"title": text, "url": href})
                if len(results) >= limit:
                    break
            return {"query": query, "count": len(results), "results": results,
                    "engine": "duckduckgo-lite"}
        except Exception as e:
            return {"query": query, "error": str(e)}

    @tool(description="Download file from URL to local path", category="download")
    async def download_file(self, url: str, output_path: str, timeout: int = 120) -> Dict:
        try:
            op = os.path.expanduser(output_path)
            os.makedirs(os.path.dirname(op) or ".", exist_ok=True)
            if HAS_AIOHTTP:
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    async with session.get(url) as r:
                        r.raise_for_status()
                        with open(op, "wb") as f:
                            async for chunk in r.content.iter_chunked(65536):
                                f.write(chunk)
            else:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=timeout) as r, open(op, "wb") as f:
                    shutil = __import__("shutil")
                    shutil.copyfileobj(r, f)
            size = os.path.getsize(op)
            return {"url": url, "output": op, "bytes": size}
        except Exception as e:
            return {"url": url, "error": str(e), "error_type": type(e).__name__}

    @tool(description="IP address validation (IPv4/IPv6)", category="net")
    async def ip_validate(self, ip: str) -> Dict:
        import socket
        for family, name in [(socket.AF_INET, "IPv4"), (socket.AF_INET6, "IPv6")]:
            try:
                socket.inet_pton(family, ip)
                return {"ip": ip, "valid": True, "version": name}
            except (OSError, ValueError):
                continue
        return {"ip": ip, "valid": False, "error": "not a valid IP"}

    @tool(description="Domain resolution (DNS lookup)", category="dns")
    async def dns_resolve(self, hostname: str) -> Dict:
        import socket
        try:
            ips = socket.getaddrinfo(hostname, None)
            v4 = list(set(a[4][0] for a in ips if a[0] == socket.AF_INET))
            v6 = list(set(a[4][0] for a in ips if a[0] == socket.AF_INET6))
            return {"hostname": hostname, "ipv4": v4, "ipv6": v6, "resolved": bool(v4 or v6)}
        except Exception as e:
            return {"hostname": hostname, "error": str(e), "resolved": False}
