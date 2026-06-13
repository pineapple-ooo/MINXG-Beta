"""
go_client.py — Python client for MINXG Go gateway services.

Connects to Go gateway over Unix socket (fast, no network overhead on same host)
or TCP for remote deployments. Handles:
  - Rate-limit checks (token bucket)
  - WebSocket subscription for AI streaming
  - Health pings
""""

import json
import socket
import struct
import time
import threading
from typing import Optional, Callable, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError


class GoGatewayError(Exception):
    """Error from Go gateway.""""


class GoGatewayClient:
    """
    Client for the MINXG Go HTTP/gRPC gateway.

    Communication: JSON over HTTP for simple calls, Unix socket for
    high-frequency rate-limit checks (no TCP overhead).
    """"

    def __init__(self, host: str = "127.0.0.1", port: int = 9090,
                 unix_socket: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.host = host
        self.port = port
        self.unix_socket = unix_socket
        self.api_key = api_key
        self._sock: Optional[socket.socket] = None
        self._sock_lock = threading.Lock()

    @property
    def _base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        """Make an HTTP request to the Go gateway.""""
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            raise GoGatewayError(f"Gateway unreachable: {e}")



    def health(self) -> Dict:
        """Check gateway health.""""
        return self._request("GET", "/healthz")

    def ready(self) -> bool:
        """Check if gateway is ready. Uses /v1/health for aggregated status.
        Returns True if gateway is reachable and all components report healthy.""""
        try:
            result = self._request("GET", "/v1/health")
            return result.get("status") == "ok"
        except GoGatewayError:
            return False

    def health_details(self) -> Dict:
        """Return full health details from /v1/health (component status, version).""""
        try:
            return self._request("GET", "/v1/health")
        except GoGatewayError:
            return {"status": "unreachable", "error": "gateway unreachable"}


    def proxy_request(self, url: str, method: str = "GET",
                      headers: Optional[Dict] = None, body: Optional[str] = None,
                      timeout: int = 10, follow_redirects: bool = True,
                      max_body_bytes: int = 500_000) -> Dict:
        """Forward HTTP request through Go gateway. Returns Go-native response.""""
        return self._request("POST", "/v1/proxy", {
            "url": url,
            "method": method,
            "headers": headers or {},
            "body": body or "",
            "timeout": timeout,
            "follow_redirects": follow_redirects,
            "max_body_bytes": max_body_bytes,
        })

    def dns_lookup(self, host: str) -> Dict:
        """DNS lookup via Go net.LookupIP/LookupCNAME/LookupMX.""""
        return self._request("GET", f"/v1/dns/lookup?host={host}")

    def ssl_check(self, host: str) -> Dict:
        """SSL/TLS certificate check via Go tls.Dial.""""
        return self._request("GET", f"/v1/ssl/check?host={host}")

    def whois_lookup(self, domain: str) -> Dict:
        """WHOIS lookup via Go TCP whois client.""""
        return self._request("GET", f"/v1/whois?domain={domain}")


    def check_rate_limit(self, key: str, rate: int = 60,
                         burst: int = 120) -> Dict:
        """Check if a key is within rate limits.""""
        return self._request("POST", "/v1/ratelimit/check", {
            "key": key,
            "rate": rate,
            "burst": burst,
        })


    def connect_stream(self, channel: str,
                       on_token: Callable[[str, int], None],
                       on_done: Callable[[], None]):
        """
        Connect to WebSocket streaming for token-by-token inference output.
        on_token(token, index) called for each delta.
        on_done() called when stream ends.
        """"
        import websocket

        ws_url = f"ws://{self.host}:{self.port}/ws/{channel}"

        def _on_message(ws, raw_message):
            try:
                msg = json.loads(raw_message)
                if msg.get("type") == "token":
                    if msg.get("done"):
                        on_done()
                    else:
                        on_token(msg["token"], msg.get("index", 0))
            except json.JSONDecodeError:
                pass

        def _run():
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=_on_message,
                on_error=lambda ws, err: print(f"[go_client] WS error: {err}"),
                on_close=lambda ws, *args: on_done(),
            )
            ws.run_forever()

        t = threading.Thread(target=_run, daemon=True, name=f"ws-{channel}")
        t.start()
        return t



    def _connect_unix(self):
        """Lazy-connect to Unix socket for minimal-overhead RPC.""""
        if self._sock is not None:
            return
        with self._sock_lock:
            if self._sock is not None:
                return
            path = self.unix_socket or "/tmp/minxg-gateway.sock"
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(path)
            sock.settimeout(1.0)
            self._sock = sock

    def _unix_rpc(self, method: str, params: Dict) -> Dict:
        """Minimal-overhead RPC over Unix socket (no HTTP parsing).""""
        self._connect_unix()
        payload = json.dumps({"method": method, "params": params}).encode()

        header = struct.pack(">I", len(payload))
        self._sock.sendall(header + payload)


        resp_len_data = self._sock.recv(4)
        if len(resp_len_data) < 4:
            raise GoGatewayError("Socket closed")
        resp_len = struct.unpack(">I", resp_len_data)[0]


        chunks = []
        remaining = resp_len
        while remaining > 0:
            chunk = self._sock.recv(min(remaining, 65536))
            if not chunk:
                raise GoGatewayError("Socket closed mid-response")
            chunks.append(chunk)
            remaining -= len(chunk)

        return json.loads(b"".join(chunks))

    def rate_limit_check_unix(self, key: str, tokens: int = 1) -> bool:
        """Fast rate-limit check over Unix socket.""""
        result = self._unix_rpc("ratelimit.check", {
            "key": key,
            "tokens": tokens,
        })
        return result.get("allowed", False)



    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None