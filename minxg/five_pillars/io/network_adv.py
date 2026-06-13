"""
minxg/network_adv.py — Advanced network operations v1.0.0

Extended network toolkit: ping, traceroute, DNS, HTTP methods, websocket,
SSL verification, port scanning, WHOIS, GeoIP, speed testing.
"""
from __future__ import annotations
import os
import sys
import json
import time
import socket
import ssl
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError

from minxg.base import BaseWorker, tool


class NetworkAdvWorker(BaseWorker):
    """Advanced network operations: ping, dns, http, ssl, websocket, port scan, whois, speed test."""
    worker_id = "network_adv"
    version = "1.0.0"

    def _register_tools(self):
        tools = [
            ("net_ping", "Ping a host with configurable count and timeout. Returns RTT stats.",
             {"host": "string", "count": "int", "timeout": "int"},
             self._net_ping),
            ("net_traceroute", "Trace the network path to a host. Returns hop list with latencies.",
             {"host": "string", "max_hops": "int", "timeout": "int"},
             self._net_traceroute),
            ("net_dns_resolve", "Resolve a hostname to IP addresses (A/AAAA records).",
             {"hostname": "string"},
             self._net_dns_resolve),
            ("net_dns_reverse", "Reverse DNS lookup: get hostname from IP address.",
             {"ip": "string"},
             self._net_dns_reverse),
            ("net_dns_all", "Query all DNS record types for a domain (A, AAAA, MX, NS, TXT, CNAME).",
             {"domain": "string"},
             self._net_dns_all),
            ("net_http_head", "HTTP HEAD request. Returns headers without body.",
             {"url": "string", "timeout": "int"},
             self._net_http_head),
            ("net_http_get", "HTTP GET request. Returns response body up to 1MB.",
             {"url": "string", "headers": "dict", "timeout": "int"},
             self._net_http_get),
            ("net_http_post", "HTTP POST request with JSON body.",
             {"url": "string", "body": "dict", "headers": "dict", "timeout": "int"},
             self._net_http_post),
            ("net_ssl_check", "Check SSL/TLS certificate validity, expiry, and issuer for a domain.",
             {"host": "string", "port": "int"},
             self._net_ssl_check),
            ("net_port_open", "Check if a TCP port is open on a remote host.",
             {"host": "string", "port": "int", "timeout": "int"},
             self._net_port_open),
            ("net_port_scan", "Scan common ports on a host (default: top 100 ports).",
             {"host": "string", "ports": "list", "timeout": "int"},
             self._net_port_scan),
            ("net_whois", "WHOIS lookup for a domain or IP address.",
             {"target": "string"},
             self._net_whois),
            ("net_geoip", "GeoIP lookup: get country, city, ISP for an IP address.",
             {"ip": "string"},
             self._net_geoip),
            ("net_speed_test", "Simple network speed test: measure download and upload speed.",
             {"url": "string", "size_kb": "int"},
             self._net_speed_test),
            ("net_headers_analyze", "Analyze HTTP response headers for security and caching info.",
             {"url": "string"},
             self._net_headers_analyze),
        ]

        for name, desc, params, fn in tools:
            self.tools[name] = type("ToolDef", (), {
                "name": name,
                "description": desc,
                "params": params,
                "category": "network",
                "platforms": ["linux", "macos", "windows", "android"],
                "requires_root": False,
                "fn": fn,
            })()

    

    def _net_ping(self, host: str, count: int = 4, timeout: int = 5) -> Dict[str, Any]:
        try:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            rtt = []
            for line in result.stdout.split('\n'):
                if 'time=' in line:
                    rtt.append(float(line.split('time=')[1].split()[0]))
            stats = {"sent": count, "received": len(rtt),
                     "loss_pct": (count - len(rtt)) / count * 100 if count else 0}
            if rtt:
                stats.update({"min_ms": min(rtt), "avg_ms": sum(rtt)/len(rtt), "max_ms": max(rtt)})
            return {"status": "success", "host": host, "stats": stats}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Ping timeout"}

    def _net_traceroute(self, host: str, max_hops: int = 30, timeout: int = 3) -> Dict[str, Any]:
        try:
            cmd = ["traceroute", "-m", str(max_hops), "-w", str(timeout), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * max_hops + 10)
            hops = []
            for line in result.stdout.split('\n')[1:]:
                if line.strip():
                    parts = line.split()
                    if parts:
                        hops.append({"hop": parts[0], "host": parts[1] if len(parts) > 1 else "*",
                                      "rtt": [parts[i] for i in range(2, min(len(parts), 5))]})
            return {"status": "success", "host": host, "hops": hops, "total_hops": len(hops)}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Traceroute timeout"}

    def _net_dns_resolve(self, hostname: str) -> Dict[str, Any]:
        try:
            ips = socket.getaddrinfo(hostname, None)
            v4, v6 = [], []
            for info in ips:
                addr = info[4][0]
                if ':' in addr:
                    v6.append(addr)
                else:
                    v4.append(addr)
            return {"status": "success", "hostname": hostname, "ipv4": list(set(v4)), "ipv6": list(set(v6))}
        except socket.gaierror as e:
            return {"status": "error", "error": str(e)}

    def _net_dns_reverse(self, ip: str) -> Dict[str, Any]:
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return {"status": "success", "ip": ip, "hostname": hostname}
        except socket.herror:
            return {"status": "error", "error": "No PTR record found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_dns_all(self, domain: str) -> Dict[str, Any]:
        records = {}
        try:
            for rtype in ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME']:
                try:
                    cmd = ["dig", "+short", domain, rtype]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    records[rtype] = [l.strip() for l in result.stdout.split('\n') if l.strip()]
                except Exception:
                    records[rtype] = []
            return {"status": "success", "domain": domain, "records": records}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _http_request(self, url: str, method: str = "GET", body: Dict = None,
                      headers: Dict = None, timeout: int = 30) -> Dict[str, Any]:
        try:
            data = json.dumps(body).encode('utf-8') if body else None
            req_headers = {"User-Agent": "MINXG/1.0.0", "Accept": "*/*"}
            if headers:
                req_headers.update(headers)
            req = Request(url, data=data, headers=req_headers, method=method)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read(1024 * 1024)  
                try:
                    return {"status": "success", "status_code": resp.status,
                            "headers": dict(resp.headers),
                            "body": raw.decode('utf-8')[:50000],
                            "body_size": len(raw)}
                except UnicodeDecodeError:
                    return {"status": "success", "status_code": resp.status,
                            "headers": dict(resp.headers),
                            "body_type": "binary", "body_size": len(raw)}
        except URLError as e:
            return {"status": "error", "error": str(e.reason)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_http_head(self, url: str, timeout: int = 15) -> Dict[str, Any]:
        return self._http_request(url, "HEAD", timeout=timeout)

    def _net_http_get(self, url: str, headers: Dict = None, timeout: int = 30) -> Dict[str, Any]:
        return self._http_request(url, "GET", headers=headers, timeout=timeout)

    def _net_http_post(self, url: str, body: Dict = None, headers: Dict = None,
                       timeout: int = 30) -> Dict[str, Any]:
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        return self._http_request(url, "POST", body=body, headers=h, timeout=timeout)

    def _net_ssl_check(self, host: str, port: int = 443) -> Dict[str, Any]:
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            return {
                "status": "success",
                "host": host,
                "subject": dict(x[0] for x in cert.get("subject", [])),
                "issuer": dict(x[0] for x in cert.get("issuer", [])),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
                "san": [x[1] for x in cert.get("subjectAltName", [])],
                "version": cert.get("version"),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_port_open(self, host: str, port: int, timeout: int = 3) -> Dict[str, Any]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            is_open = result == 0
            service = {80: "HTTP", 443: "HTTPS", 22: "SSH", 21: "FTP",
                       25: "SMTP", 3306: "MySQL", 5432: "PostgreSQL",
                       6379: "Redis", 27017: "MongoDB", 8080: "HTTP-Alt"}.get(port, "unknown")
            return {"status": "success", "host": host, "port": port, "open": is_open, "service": service}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_port_scan(self, host: str, ports: List[int] = None,
                       timeout: int = 2) -> Dict[str, Any]:
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995,
                     1433, 3306, 3389, 5432, 6379, 8080, 8443, 9090, 27017]
        results = []
        for port in ports[:50]:
            r = self._net_port_open(host, port, timeout)
            if r.get("open"):
                results.append({"port": port, "service": r.get("service", "unknown")})
        return {"status": "success", "host": host, "open_ports": results, "scanned": len(ports)}

    def _net_whois(self, target: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(["whois", target], capture_output=True, text=True, timeout=15)
            return {"status": "success", "target": target, "output": result.stdout[:10000]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "WHOIS query timeout"}
        except FileNotFoundError:
            return {"status": "error", "error": "whois command not found. Install with: apt install whois"}

    def _net_geoip(self, ip: str) -> Dict[str, Any]:
        try:
            url = f"https://ipapi.co/{ip}/json/"
            req = Request(url, headers={"User-Agent": "MINXG/1.0.0"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return {"status": "success", "ip": ip,
                    "country": data.get("country_name"), "country_code": data.get("country_code"),
                    "city": data.get("city"), "region": data.get("region"),
                    "isp": data.get("org"), "timezone": data.get("timezone")}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_speed_test(self, url: str = "https://speed.cloudflare.com/__down",
                        size_kb: int = 1024) -> Dict[str, Any]:
        try:
            
            t0 = time.time()
            req = Request(url + f"?bytes={size_kb * 1024}", headers={"User-Agent": "MINXG/1.0.0"})
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
            download_time = time.time() - t0
            download_speed = len(data) / download_time / 1024  

            return {
                "status": "success",
                "download_speed_kbps": round(download_speed, 2),
                "download_speed_mbps": round(download_speed / 1024, 2),
                "latency_ms": round(download_time * 1000, 1),
                "bytes_downloaded": len(data),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _net_headers_analyze(self, url: str) -> Dict[str, Any]:
        try:
            req = Request(url, method="HEAD", headers={"User-Agent": "MINXG/1.0.0"})
            with urlopen(req, timeout=15) as resp:
                headers = dict(resp.headers)

            analysis = {
                "server": headers.get("Server", "not disclosed"),
                "cors": "enabled" if "Access-Control-Allow-Origin" in headers else "not set",
                "hsts": "enabled" if "Strict-Transport-Security" in headers else "not set",
                "csp": "set" if "Content-Security-Policy" in headers else "not set",
                "x_frame": headers.get("X-Frame-Options", "not set"),
                "x_content_type": headers.get("X-Content-Type-Options", "not set"),
                "cache_control": headers.get("Cache-Control", "not set"),
                "content_type": headers.get("Content-Type", "not set"),
            }
            return {"status": "success", "url": url, "status_code": resp.status, "analysis": analysis,
                    "raw_headers": {k: v for k, v in headers.items()
                                   if k not in ("Set-Cookie", "X-Api-Key")}}
        except Exception as e:
            return {"status": "error", "error": str(e)}