"""

HTTP/web tools — delegates HTTP requests to Go gateway when available.
"""
from __future__ import annotations
from typing import Dict, List
import urllib.parse
import re
from minxg.base import BaseWorker, tool

_HAS_GO = False
_go_client = None

try:
    from .go_client import GoGatewayClient
    _go_client = GoGatewayClient()
    if _go_client.ready():
        _HAS_GO = True
except Exception:
    pass


class WebToolsWorker(BaseWorker):
    worker_id = "web_tools"
    version = "1.1.0"

    @tool(description="Parse URL into components", category="url")
    async def url_parse(self, url: str) -> Dict:
        p = urllib.parse.urlparse(url)
        return {"scheme": p.scheme, "hostname": p.hostname, "port": p.port,
                "path": p.path, "query": p.query, "fragment": p.fragment,
                "params": p.params, "netloc": p.netloc}

    @tool(description="Build URL from components", category="url")
    async def url_build(self, scheme: str = "https", host: str = "", path: str = "",
                         query: dict = None) -> Dict:
        qs = urllib.parse.urlencode(query or {})
        url = urllib.parse.urlunparse((scheme, host, path, "", qs, ""))
        return {"url": url}

    @tool(description="Parse URL query parameters", category="url")
    async def url_query_parse(self, url: str) -> Dict:
        p = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(p.query))
        return {"params": params, "count": len(params), "url": url}

    @tool(description="HTTP GET request (Go-native or urllib fallback)", category="http")
    async def http_get(self, url: str, headers: dict = None, timeout: int = 10) -> Dict:
        if _HAS_GO:
            try:
                resp = _go_client.proxy_request(url, "GET", headers=headers, timeout=timeout)
                if "error" not in resp:
                    return {"status": resp["status"], "body_preview": str(resp.get("body",""))[:2000],
                            "content_length": resp.get("body_size", 0), "go_backend": True}
            except Exception:
                pass
        import urllib.request, json as _json
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", headers.get("User-Agent", "MINXG/1.0") if headers else "MINXG/1.0")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.status
            try:
                data = _json.loads(body)
            except Exception:
                data = body[:5000]
            return {"status": status, "body_preview": str(data)[:2000], "content_length": len(body)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="HTTP POST request (Go-native or urllib fallback)", category="http")
    async def http_post(self, url: str, body: str = "{}", headers: dict = None,
                         timeout: int = 10) -> Dict:
        if _HAS_GO:
            try:
                hdrs = headers or {}
                hdrs.setdefault("Content-Type", "application/json")
                resp = _go_client.proxy_request(url, "POST", headers=hdrs, body=body, timeout=timeout)
                if "error" not in resp:
                    return {"status": resp["status"], "result": resp.get("body","")[:2000],
                            "go_backend": True}
            except Exception:
                pass
        import urllib.request, json as _json
        try:
            data = body.encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "MINXG/1.0")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                status = resp.status
            try:
                result = _json.loads(text)
            except Exception:
                result = text[:2000]
            return {"status": status, "result": result}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Check if URL is reachable", category="http")
    async def http_check(self, url: str, timeout: int = 5) -> Dict:
        import urllib.request
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "MINXG/1.0")
            resp = urllib.request.urlopen(req, timeout=timeout)
            return {"reachable": True, "status": resp.status, "url": url}
        except Exception as e:
            return {"reachable": False, "error": str(e), "url": url}

    @tool(description="Generate curl command", category="build")
    async def build_curl(self, url: str, method: str = "GET", headers: dict = None,
                          body: str = "") -> Dict:
        parts = [f"curl -X {method} '{url}'"]
        if headers:
            for k, v in headers.items():
                parts.append(f"-H '{k}: {v}'")
        if body and method != "GET":
            parts.append(f"-d '{body}'")
        return {"curl": " \\\n  ".join(parts)}

    @tool(description="Extract all links from webpage", category="parse")
    async def extract_links(self, html: str, base_url: str = "") -> Dict:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        srcs = re.findall(r'src=["\']([^"\']+)["\']', html)
        links = list(set(hrefs))[:100]
        return {"links": links, "count": len(links), "sources": len(set(srcs))}

    @tool(description="Extract webpage title and meta info", category="parse")
    async def extract_meta(self, html: str) -> Dict:
        title = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I)
        og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        return {
            "title": (title.group(1) if title else og_title.group(1) if og_title else "unknown"),
            "description": desc.group(1) if desc else "",
        }

    @tool(description="Get public IP info", category="network")
    async def my_ip(self) -> Dict:
        import urllib.request, json as _json
        try:
            req = urllib.request.Request("https://httpbin.org/ip")
            resp = urllib.request.urlopen(req, timeout=5)
            data = _json.loads(resp.read())
            return {"ip": data.get("origin", "unknown"), "source": "httpbin.org"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Domain resolution advice", category="dns")
    async def dns_lookup(self, hostname: str) -> Dict:
        import socket
        try:
            ip = socket.gethostbyname(hostname)
            return {"hostname": hostname, "ip": ip}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Generate random User-Agent", category="generate")
    async def random_user_agent(self, browser: str = "chrome") -> Dict:
        agents = {
            "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 Safari/605.1.15",
            "mobile": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
        }
        return {"user_agent": agents.get(browser, agents["chrome"]), "browser": browser}

    @tool(description="HTTP status code description", category="http")
    async def http_status(self, code: int) -> Dict:
        codes = {200:"OK",201:"Created",204:"No Content",301:"Moved",302:"Found",
                 304:"Not Modified",400:"Bad Request",401:"Unauthorized",403:"Forbidden",
                 404:"Not Found",405:"Method Not Allowed",429:"Too Many Requests",
                 500:"Internal Server Error",502:"Bad Gateway",503:"Service Unavailable"}
        return {"code": code, "message": codes.get(code, "Unknown"), "category": "2xx-success" if 200<=code<300 else ("3xx-redirect" if 300<=code<400 else ("4xx-client-error" if 400<=code<500 else "5xx-server-error"))}

    @tool(description="API endpoint test parameter generation", category="api")
    async def api_test_params(self, method: str, path: str, content_type: str = "json") -> Dict:
        import urllib.request, json as _json
        sample = {"json": {"key": "value", "items": [1, 2, 3]},
                  "form": "name=test&email=a@b.com",
                  "multipart": "--boundary\nContent-Disposition: form-data; name='file'\n\n...\n--boundary--"}
        return {"method": method.upper(), "path": path, "content_type": content_type,
                "sample_body": sample.get(content_type, sample["json"]),
                "curl": f"curl -X {method.upper()} 'http://localhost:8080{path}' -H 'Content-Type: application/{content_type}' -d '{_json.dumps(sample['json'])}'"}

    @tool(description="Content-Type detection", category="detect")
    async def content_type(self, filename_or_ext: str) -> Dict:
        mapping = {
            "html": "text/html", "css": "text/css", "js": "application/javascript",
            "json": "application/json", "xml": "application/xml",
            "png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml",
            "pdf": "application/pdf", "zip": "application/zip",
        }
        ext = filename_or_ext.split(".")[-1].lower() if "." in filename_or_ext else filename_or_ext.lower()
        return {"filename": filename_or_ext, "extension": ext, "content_type": mapping.get(ext, "application/octet-stream")}

    @tool(description="Calculate simulated API call cost", category="api")
    async def api_cost_estimate(self, model: str, input_tokens: int, output_tokens: int) -> Dict:
        prices = {
            "gpt-4o": (0.0025, 0.01), "gpt-4o-mini": (0.00015, 0.0006),
            "claude-3-opus": (0.015, 0.075), "claude-sonnet": (0.003, 0.015),
            "deepseek-chat": (0.00027, 0.0011), "qwen-max": (0.0028, 0.0028),
        }
        price = prices.get(model, prices.get(next((k for k in prices if k in model.lower()), ""), (0.001, 0.002)))
        input_cost = (input_tokens / 1000) * price[0]
        output_cost = (output_tokens / 1000) * price[1]
        return {"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
                "input_cost": f"${input_cost:.6f}", "output_cost": f"${output_cost:.6f}",
                "total_cost": f"${input_cost + output_cost:.6f}", "unit": "USD per 1K tokens"}

    @tool
    async def http_retry(self, url: str = "", max_retries: int = 3, delay_s: float = 1.0) -> dict:
        """HTTP GET with automatic retry on failure."""
        import time, urllib.request
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "MINXG/0.0.1"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return {"status": resp.status, "body_preview": resp.read().decode(errors='replace')[:500], "attempt": attempt+1}
            except Exception as e:
                if attempt == max_retries - 1:
                    return {"error": str(e), "attempts": max_retries, "status": "failed"}
                time.sleep(delay_s)
        return {"error": "unreachable"}

    @tool
    async def http_headers(self, url: str = "") -> dict:
        """Fetch only HTTP headers (HEAD request)."""
        import urllib.request
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "MINXG/0.0.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "headers": dict(resp.headers)}
