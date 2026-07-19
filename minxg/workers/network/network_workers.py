"""
MINXG Network Workers — Network utilities and HTTP tools.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional


class HTTPGetWorker:
    """Perform HTTP GET requests."""
    worker_id = "http_get"
    version = "0.19.0"

    def execute(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        import requests
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            return {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "content": resp.text[:10000],
                "length": len(resp.content),
                "encoding": resp.encoding,
            }
        except Exception as e:
            return {"error": str(e)}


class HTTPPostWorker:
    """Perform HTTP POST requests."""
    worker_id = "http_post"
    version = "0.19.0"

    def execute(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None,
                headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        import requests
        try:
            resp = requests.post(url, data=data, json=json, headers=headers, timeout=timeout)
            return {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "content": resp.text[:10000],
            }
        except Exception as e:
            return {"error": str(e)}


class DNSLookupWorker:
    """DNS lookup."""
    worker_id = "dns_lookup"
    version = "0.19.0"

    def execute(self, hostname: str, record_type: str = "A") -> Dict[str, Any]:
        try:
            import socket
            if record_type == "A":
                result = socket.getaddrinfo(hostname, None, socket.AF_INET)
                return {"hostname": hostname, "records": list(set(r[4][0] for r in result))}
            elif record_type == "AAAA":
                result = socket.getaddrinfo(hostname, None, socket.AF_INET6)
                return {"hostname": hostname, "records": list(set(r[4][0] for r in result))}
            elif record_type == "MX":
                import dnspython
                return {"error": "MX lookup requires dnspython"}
        except Exception as e:
            return {"error": str(e)}


class PingWorker:
    """Ping a host."""
    worker_id = "ping"
    version = "0.19.0"

    def execute(self, host: str, count: int = 4, timeout: int = 5) -> Dict[str, Any]:
        import subprocess
        import platform
        import re

        if platform.system() == "Windows":
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * count + 10)
            output = result.stdout + result.stderr

            # Parse latency
            latencies = re.findall(r"time[=<](\d+\.?\d*)\s*ms", output)
            if latencies:
                latencies = [float(l) for l in latencies]
                return {
                    "host": host,
                    "packets_sent": count,
                    "packets_received": len(latencies),
                    "packet_loss": ((count - len(latencies)) / count) * 100,
                    "min_ms": min(latencies),
                    "max_ms": max(latencies),
                    "avg_ms": sum(latencies) / len(latencies),
                    "output": output[:2000],
                }
            return {"host": host, "output": output[:2000], "reachable": result.returncode == 0}
        except FileNotFoundError:
            # No `ping` binary on PATH — common on minimal containers and
            # on stock Termux/Android installs (ping needs root or the
            # `inetutils`/`busybox` package there). Fall back to a plain
            # TCP-connect reachability probe instead of just erroring out,
            # so callers still get a usable (if less precise) answer.
            return self._tcp_fallback(host, timeout)
        except subprocess.TimeoutExpired:
            return {"host": host, "error": "ping timed out", "reachable": False}
        except Exception as e:
            return {"host": host, "error": str(e)}

    @staticmethod
    def _tcp_fallback(host: str, timeout: int) -> Dict[str, Any]:
        """Best-effort reachability check via TCP connect, used when the
        `ping` binary itself isn't available. Not a real ICMP echo, so
        latency numbers aren't reported — just reachable/unreachable."""
        import socket
        import time

        for port in (443, 80, 22):
            start = time.monotonic()
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    elapsed_ms = (time.monotonic() - start) * 1000
                    return {
                        "host": host,
                        "reachable": True,
                        "method": "tcp_connect_fallback",
                        "probed_port": port,
                        "latency_ms": round(elapsed_ms, 1),
                        "note": "`ping` binary not found on PATH; used a TCP "
                                "connect probe instead of ICMP.",
                    }
            except OSError:
                continue
        return {
            "host": host,
            "reachable": False,
            "method": "tcp_connect_fallback",
            "note": "`ping` binary not found on PATH, and TCP connect to "
                    "ports 443/80/22 all failed.",
        }


class PortScanWorker:
    """Scan open ports on a host."""
    worker_id = "port_scan"
    version = "0.19.0"

    def execute(self, host: str, ports: List[int] = None, timeout: int = 1) -> Dict[str, Any]:
        import socket

        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 3389, 5432, 8080, 8443]

        open_ports = []
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                if sock.connect_ex((host, port)) == 0:
                    open_ports.append(port)
            finally:
                sock.close()

        return {"host": host, "open_ports": open_ports, "scanned": len(ports)}


class WHOISWorker:
    """WHOIS lookup."""
    worker_id = "whois"
    version = "0.19.0"

    def execute(self, domain: str) -> Dict[str, Any]:
        import subprocess
        try:
            result = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=30)
            return {"domain": domain, "whois": result.stdout[:10000]}
        except FileNotFoundError:
            return {"error": "whois command not found. Install whois package."}
        except Exception as e:
            return {"error": str(e)}


class URLParseWorker:
    """Parse URL components."""
    worker_id = "url_parse"
    version = "0.19.0"

    def execute(self, url: str) -> Dict[str, Any]:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        return {
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
            "params": parsed.params,
            "query": parsed.query,
            "query_dict": parse_qs(parsed.query),
            "fragment": parsed.fragment,
        }


class SSLLookupWorker:
    """Get SSL certificate info."""
    worker_id = "ssl_lookup"
    version = "0.19.0"

    def execute(self, hostname: str, port: int = 443) -> Dict[str, Any]:
        import ssl
        import socket
        from datetime import datetime

        context = ssl.create_default_context()
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                return {
                    "hostname": hostname,
                    "issuer": dict(x[0] for x in cert["issuer"]),
                    "subject": dict(x[0] for x in cert["subject"]),
                    "version": cert["version"],
                    "serial_number": cert["serial_number"],
                    "not_before": not_before.isoformat(),
                    "not_after": not_after.isoformat(),
                    "days_until_expiry": (not_after - datetime.now()).days,
                }


class TCPSocketWorker:
    """Simple TCP socket client."""
    worker_id = "tcp_socket"
    version = "0.19.0"

    def execute(self, host: str, port: int, data: str, timeout: int = 5) -> Dict[str, Any]:
        import socket
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.sendall(data.encode())
                response = sock.recv(4096).decode()
                return {"host": host, "port": port, "sent": len(data), "received": len(response), "response": response}
        except Exception as e:
            return {"error": str(e)}
