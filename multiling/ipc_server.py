"""
MINXG IPC/RPC Server
"""
import os, sys, json, time, asyncio, logging, threading, uuid, hashlib, hmac, base64
import socket, struct, tempfile, shutil, ssl, contextlib, collections, re, math
from typing import Dict, List, Optional, Any, Callable, Tuple, Set, Union, AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import aiohttp
from aiohttp import web, WSMsgType, WSCloseCode
import datetime as _datetime
from datetime import datetime, timedelta

# cryptography is heavy-weight and can fail to import on some platforms
# (e.g. Termux + Python 3.13 where the Rust binding's symbol table is
# incompatible with the interpreter). All actual usage is confined to
# `_generate_ssl_cert`, which only runs when the IPC server is started
# with TLS. Keep the imports lazy so unrelated `minxg` subcommands
# (status, tools, config, etc.) never load it.

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s')
logger = logging.getLogger("ipc_server")

IPC_VERSION = "0.17.1"
MAX_CONNECTIONS = 1000
CONNECTION_TIMEOUT = 300.0
READ_BUFFER_SIZE = 65536
MAX_REQUEST_SIZE = 10 * 1024 * 1024
ENABLE_SSL = os.getenv("IPC_SSL", "false").lower() == "true"
SSL_CERT_PATH = os.getenv("IPC_SSL_CERT", "/tmp/ipc_server.crt")
SSL_KEY_PATH = os.getenv("IPC_SSL_KEY", "/tmp/ipc_server.key")
AUTH_SECRET = os.getenv("IPC_AUTH_SECRET", "minxg-secret-key-change-me")
ENABLE_AUTH = os.getenv("IPC_AUTH", "true").lower() == "true"

class MessageType:
    HANDSHAKE = "handshake"
    REQUEST = "request"
    RESPONSE = "response"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    BROADCAST = "broadcast"
    TASK_DISPATCH = "task_dispatch"
    TASK_RESULT = "task_result"
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"

class RPCCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TASK_NOT_FOUND = -32000
    WORKER_UNAVAILABLE = -32001
    CAPABILITY_MISMATCH = -32002
    AUTH_FAILED = -32003
    RATE_LIMITED = -32004

class MessageCodec:
    @staticmethod
    def encode(msg_type: str, payload: Dict, msg_id: str = None) -> bytes:
        envelope = {
            "version": IPC_VERSION, "type": msg_type,
            "id": msg_id or uuid.uuid4().hex[:16],
            "timestamp": time.time(), "payload": payload
        }
        json_str = json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))
        length = len(json_str.encode('utf-8'))
        header = struct.pack('!I', length)
        return header + json_str.encode('utf-8')
    
    @staticmethod
    def decode(data: bytes) -> Dict:
        if len(data) < 4:
            pass
        length = struct.unpack('!I', data[:4])[0]
        if len(data) < 4 + length:
            pass
        json_str = data[4:4+length].decode('utf-8')
        return json.loads(json_str)
    
    @staticmethod
    def encode_rpc_request(method: str, params: Dict, request_id: str = None) -> bytes:
        return MessageCodec.encode(MessageType.REQUEST, {
            "method": method, "params": params, "jsonrpc": "2.0"
        }, request_id)
    
    @staticmethod
    def encode_rpc_response(result: Any, request_id: str) -> bytes:
        return MessageCodec.encode(MessageType.RESPONSE, {
            "result": result, "jsonrpc": "2.0"
        }, request_id)
    
    @staticmethod
    def encode_rpc_error(code: int, message: str, request_id: str, data: Any = None) -> bytes:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return MessageCodec.encode(MessageType.ERROR, {
            "error": error, "jsonrpc": "2.0"
        }, request_id)

class AuthManager:
    def __init__(self, secret: str = AUTH_SECRET):
        self.secret = secret
        self._tokens: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._rate_limiter: Dict[str, collections.deque] = {}
        self._rate_window = 60
        self._rate_limit = 100
    
    def generate_token(self, worker_id: str, capabilities: List[str]) -> str:
        token = base64.urlsafe_b64encode(
            f"{worker_id}:{uuid.uuid4().hex}:{int(time.time())}".encode()
        ).decode()
        with self._lock:
            self._tokens[token] = {
                "worker_id": worker_id, "capabilities": capabilities,
                "created_at": time.time(), "last_used": time.time()
            }
        return token
    
    def validate_token(self, token: str, required_capability: str = None) -> Tuple[bool, Dict]:
        with self._lock:
            info = self._tokens.get(token)
            if not info:
                return False, {}
            if time.time() - info["created_at"] > 86400:
                del self._tokens[token]
                return False, {}
            info["last_used"] = time.time()
            if required_capability and required_capability not in info.get("capabilities", []):
                return False, info
            return True, info
    
    def revoke_token(self, token: str):
        with self._lock:
            self._tokens.pop(token, None)
    
    def check_rate_limit(self, token: str) -> bool:
        now = time.time()
        with self._lock:
            if token not in self._rate_limiter:
                self._rate_limiter[token] = collections.deque()
            self._rate_limiter[token].append(now)
            while self._rate_limiter[token] and now - self._rate_limiter[token][0] > self._rate_window:
                self._rate_limiter[token].popleft()
            return len(self._rate_limiter[token]) <= self._rate_limit

class Connection:
    def __init__(self, conn_id: str, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, auth_manager: AuthManager):
        pass
        self.conn_id = conn_id
        self.reader = reader
        self.writer = writer
        self.auth_manager = auth_manager
        self.worker_id: Optional[str] = None
        self.capabilities: List[str] = []
        self.authenticated = False
        self.created_at = time.time()
        self.last_activity = time.time()
        self.metadata: Dict = {}
        self._buffer = bytearray()
        self._lock = asyncio.Lock()
        self._closed = False
    
    async def send(self, msg_type: str, payload: Dict, msg_id: str = None):
        try:
            data = MessageCodec.encode(msg_type, payload, msg_id)
            async with self._lock:
                self.writer.write(data)
                await self.writer.drain()
            self.last_activity = time.time()
        except Exception as e:
            raise
    
    async def receive(self) -> Dict:
        try:
            header_data = await asyncio.wait_for(self.reader.readexactly(4), timeout=10.0)
            length = struct.unpack('!I', header_data)[0]
            if length > MAX_REQUEST_SIZE:
                pass
            body_data = await asyncio.wait_for(self.reader.readexactly(length), timeout=30.0)
            message = MessageCodec.decode(header_data + body_data)
            self.last_activity = time.time()
            return message
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            raise
    
    async def close(self):
        self._closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
    
    def is_alive(self) -> bool:
        return not self._closed and time.time() - self.last_activity < CONNECTION_TIMEOUT

class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, Connection] = {}
        self._lock = asyncio.Lock()
        self._conn_counter = 0
    
    async def add(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        async with self._lock:
            self._conn_counter += 1
            conn_id = f"conn_{self._conn_counter:06d}"
            conn = Connection(conn_id, reader, writer, AuthManager())
            self._connections[conn_id] = conn
            return conn
    
    async def remove(self, conn_id: str):
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
            if conn:
                await conn.close()
    
    def get(self, conn_id: str) -> Optional[Connection]:
        return self._connections.get(conn_id)
    
    def get_all(self) -> List[Connection]:
        return list(self._connections.values())
    
    def get_by_worker(self, worker_id: str) -> List[Connection]:
        return [c for c in self._connections.values() if c.worker_id == worker_id]
    
    async def cleanup_stale(self):
        stale = []
        for conn_id, conn in self._connections.items():
            if not conn.is_alive():
                stale.append(conn_id)
        for conn_id in stale:
            await self.remove(conn_id)
        if stale:
            pass
    
    def get_stats(self) -> Dict:
        return {
            "total": len(self._connections),
            "authenticated": sum(1 for c in self._connections.values() if c.authenticated),
            "by_worker": {
                wid: len(conns) for wid, conns in 
                collections.Counter(c.worker_id for c in self._connections.values() if c.worker_id).items()
            }
        }

class RPCRegistry:
    def __init__(self):
        self._methods: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._lock = threading.Lock()
    
    def register(self, name: str, func: Callable):
        with self._lock:
            self._methods[name] = func
    
    def unregister(self, name: str):
        with self._lock:
            self._methods.pop(name, None)
    
    def add_middleware(self, middleware: Callable):
        self._middleware.append(middleware)
    
    async def call(self, method: str, params: Dict, context: Dict = None) -> Any:
        with self._lock:
            func = self._methods.get(method)
        if not func:
            pass
        for mw in self._middleware:
            try:
                result = mw(method, params, context)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is False:
                    pass
            except Exception as e:
                pass
        if asyncio.iscoroutinefunction(func):
            return await func(params, context)
        else:
            return func(params, context)
    
    def list_methods(self) -> List[str]:
        return list(self._methods.keys())

class TCPIPCServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 18999,
                 use_ssl: bool = False, cert_path: str = None, key_path: str = None):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.cert_path = cert_path or SSL_CERT_PATH
        self.key_path = key_path or SSL_KEY_PATH
        self._server: Optional[asyncio.base_events.Server] = None
        self._connections = ConnectionManager()
        self._rpc_registry = RPCRegistry()
        self._auth_manager = AuthManager()
        self._running = False
        self._stats = {"connections_accepted": 0, "messages_processed": 0, "errors": 0}
        self._lock = asyncio.Lock()
    
    async def start(self):
        self._running = True
        if self.use_ssl and not (os.path.exists(self.cert_path) and os.path.exists(self.key_path)):
            await self._generate_ssl_cert()
        ssl_context = None
        if self.use_ssl:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(self.cert_path, self.key_path)
        self._server = await asyncio.start_server(
            self._handle_connection, host=self.host, port=self.port,
            ssl=ssl_context, reuse_address=True, reuse_port=True, backlog=128
        )
    
    async def stop(self):
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for conn in self._connections.get_all():
            await conn.close()
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = await self._connections.add(reader, writer)
        peername = writer.get_extra_info('peername')
        try:
            async with self._lock:
                self._stats["connections_accepted"] += 1
            handshake = await conn.receive()
            if handshake.get("type") != MessageType.HANDSHAKE:
                return
            if ENABLE_AUTH:
                token = handshake.get("payload", {}).get("token")
                if not token:
                    return
                valid, info = self._auth_manager.validate_token(token)
                if not valid:
                    return
                conn.worker_id = info.get("worker_id")
                conn.capabilities = info.get("capabilities", [])
                conn.authenticated = True
            await conn.send(MessageType.HANDSHAKE, {
                "status": "accepted", "server_version": IPC_VERSION, "worker_id": conn.worker_id
            })
            while self._running and conn.is_alive():
                try:
                    message = await conn.receive()
                    async with self._lock:
                        self._stats["messages_processed"] += 1
                    response = await self._dispatch_message(conn, message)
                    if response:
                        await conn.send(MessageType.RESPONSE, response, message.get("id"))
                except asyncio.TimeoutError:
                    break
                except ConnectionError:
                    break
                except Exception as e:
                    async with self._lock:
                        self._stats["errors"] += 1
        except Exception as e:
            pass
        finally:
            await self._connections.remove(conn.conn_id)
    
    async def _dispatch_message(self, conn: Connection, message: Dict) -> Any:
        msg_type = message.get("type")
        payload = message.get("payload", {})
        if msg_type == MessageType.PING:
            return {"type": "pong", "timestamp": time.time()}
        elif msg_type == MessageType.HEARTBEAT:
            conn.last_activity = time.time()
            return {"status": "ok"}
        elif msg_type == MessageType.REQUEST:
            method = payload.get("method")
            params = payload.get("params", {})
            request_id = message.get("id")
            try:
                result = await self._rpc_registry.call(method, params, {
                    "worker_id": conn.worker_id, "conn_id": conn.conn_id, "capabilities": conn.capabilities
                })
                return result
            except ValueError as e:
                return {"error": {"code": RPCCode.METHOD_NOT_FOUND, "message": str(e)}}
            except PermissionError as e:
                return {"error": {"code": RPCCode.AUTH_FAILED, "message": str(e)}}
            except Exception as e:
                return {"error": {"code": RPCCode.INTERNAL_ERROR, "message": str(e)}}
        elif msg_type == MessageType.TASK_DISPATCH:
            task_data = payload.get("task", {})
            return {"status": "dispatched", "task_id": task_data.get("task_id")}
        else:
            pass
    async def _generate_ssl_cert(self):
        try:
            # Lazy import: cryptography is heavy and can crash on some
            # platforms (Termux + Python 3.13). Keep it out of cold-start.
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MINXG"),
                x509.NameAttribute(NameOID.COMMON_NAME, "minxg-orchestrator"),
            ])
            cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(
                key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(
                _datetime.datetime.utcnow()).not_valid_after(
                _datetime.datetime.utcnow() + _datetime.timedelta(days=365)
            ).add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False).sign(key, hashes.SHA256())
            with open(self.cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(self.key_path, "wb") as f:
                f.write(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
        except Exception as e:
            logger.warning("SSL cert generation skipped: %s", e)
    def register_rpc(self, name: str, func: Callable):
        self._rpc_registry.register(name, func)
    
    def get_stats(self) -> Dict:
        return {
            "running": self._running, "host": self.host, "port": self.port,
            "connections": self._connections.get_stats(), "stats": self._stats,
            "rpc_methods": self._rpc_registry.list_methods()
        }

class HTTPGateway:
    def __init__(self, host: str = "0.0.0.0", port: int = 18999, orchestrator: "NexusOrchestrator" = None):
        self.host = host
        self.port = port
        self.orchestrator = orchestrator or get_orchestrator()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._running = False
        self._stats = {"requests_total": 0, "requests_success": 0, "requests_failed": 0}
    
    async def start(self):
        self._app = web.Application(client_max_size=MAX_REQUEST_SIZE)
        self._app.middlewares.append(self._error_middleware)
        self._app.middlewares.append(self._logging_middleware)
        self._app.middlewares.append(self._auth_middleware)
        self._setup_routes()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self.host, port=self.port, reuse_address=True, reuse_port=True, backlog=1024)
        await self._site.start()
        self._running = True
    
    async def stop(self):
        self._running = False
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
    
    def _setup_routes(self):
        self._app.router.add_get("/", self._index)
        self._app.router.add_get("/health", self._health)
        self._app.router.add_get("/stats", self._stats_handler)
        self._app.router.add_get("/workers", self._list_workers)
        self._app.router.add_post("/execute", self._execute_tool)
        self._app.router.add_post("/tasks", self._submit_task)
        self._app.router.add_get("/tasks/{task_id}", self._get_task)
        self._app.router.add_post("/rpc", self._rpc_handler)
        self._app.router.add_get("/ws", self._websocket_handler)
    
    @web.middleware
    async def _error_middleware(self, request, handler):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            return web.json_response({"error": {"code": 500, "message": str(e)[:200]}}, status=500)
    
    @web.middleware
    async def _logging_middleware(self, request, handler):
        start = time.time()
        response = await handler(request)
        duration = time.time() - start
        logger.info("%s %s -> %d (%.3fs)", request.method, request.path, response.status, duration)
        return response
    
    @web.middleware
    async def _auth_middleware(self, request, handler):
        if request.path in ("/", "/health", "/docs"):
            return await handler(request)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == AUTH_SECRET or not ENABLE_AUTH:
                return await handler(request)
        if not ENABLE_AUTH:
            return await handler(request)
    
    async def _index(self, request):
        return web.json_response({
            "service": "MINXG Orchestrator", "version": ORCHESTRATOR_VERSION,
            "endpoints": {
                "POST /rpc": "JSON-RPC", "GET /ws": "WebSocket"
            }
        })
    
    async def _health(self, request):
        return web.json_response({
            "status": "healthy", "version": ORCHESTRATOR_VERSION,
            "timestamp": time.time(), "workers": len(self.orchestrator.get_all_workers())
        })
    
    async def _stats_handler(self, request):
        stats = self.orchestrator.get_stats()
        stats["http"] = self._stats
        return web.json_response(stats)
    
    async def _list_workers(self, request):
        workers = []
        for w in self.orchestrator.get_all_workers():
            workers.append({
                "worker_id": w.worker_id, "type": w.worker_type.value,
                "capabilities": w.capabilities, "load": w.current_load,
                "max": w.max_concurrent, "healthy": w.is_healthy, "stats": w.get_stats()
            })
        return web.json_response({"workers": workers, "count": len(workers)})
    
    async def _execute_tool(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": {"code": 400, "message": "Invalid JSON"}}, status=400)
        tool_name = body.get("tool", "")
        input_data = body.get("input", {})
        worker_type = body.get("worker_type")
        if not tool_name:
            return web.json_response({"error": {"code": 400, "message": "tool name required"}}, status=400)
        try:
            from core import WorkerType
            wt = WorkerType(worker_type) if worker_type else None
        except ValueError:
            wt = None
        result = await self.orchestrator.execute_tool(tool_name, input_data, worker_type=wt)
        return web.json_response({
            "task_id": result.task_id, "worker_id": result.worker_id,
            "status": result.status.name, "result": result.result,
            "error": result.error, "duration": result.duration
        })
    
    async def _submit_task(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": {"code": 400, "message": "Invalid JSON"}}, status=400)
        task_data = body.get("task", {})
        if not task_data:
            return web.json_response({"error": {"code": 400, "message": "task data required"}}, status=400)
        try:
            from core import Task, WorkerType, Priority
            task = Task(
                task_id=task_data.get("task_id", uuid.uuid4().hex[:12]),
                worker_type=WorkerType(task_data.get("worker_type", "csharp")),
                tool_name=task_data.get("tool_name", ""),
                input_data=task_data.get("input", {}),
                priority=Priority(task_data.get("priority", 1)),
                timeout=task_data.get("timeout", DEFAULT_TASK_TIMEOUT)
            )
            task_id = await self.orchestrator.submit_task(task)
            return web.json_response({"task_id": task_id, "status": "submitted"})
        except Exception as e:
            return web.json_response({"error": {"code": 400, "message": str(e)}}, status=400)
    
    async def _get_task(self, request):
        task_id = request.match_info.get("task_id")
        result = await self.orchestrator.scheduler.get_result(task_id)
        if result:
            return web.json_response({
                "task_id": result.task_id, "status": result.status.name,
                "result": result.result, "error": result.error, "duration": result.duration
            })
        return web.json_response({"error": {"code": 404, "message": "Task not found"}}, status=404)
    
    async def _rpc_handler(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({
                "jsonrpc": "2.0", "error": {"code": RPCCode.PARSE_ERROR, "message": "Parse error"}, "id": None
            }, status=400)
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        if not method:
            return web.json_response({
                "jsonrpc": "2.0", "error": {"code": RPCCode.INVALID_REQUEST, "message": "Method required"}, "id": request_id
            })
        try:
            result = await self.orchestrator.scheduler._rpc_registry.call(method, params)
            return web.json_response({"jsonrpc": "2.0", "result": result, "id": request_id})
        except ValueError as e:
            return web.json_response({
                "jsonrpc": "2.0", "error": {"code": RPCCode.METHOD_NOT_FOUND, "message": str(e)}, "id": request_id
            })
        except Exception as e:
            return web.json_response({
                "jsonrpc": "2.0", "error": {"code": RPCCode.INTERNAL_ERROR, "message": str(e)}, "id": request_id
            })
    
    async def _websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        response = await self._dispatch_message(None, data)
                        await ws.send_json(response)
                    except Exception as e:
                        await ws.send_json({"error": str(e)})
                elif msg.type == WSMsgType.ERROR:
                    pass
        finally:
            await ws.close()

class GlobalRPCRegistry:
    _instance = None
    _lock = threading.Lock()
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._registry = RPCRegistry()
        return cls._instance
    def register(self, name: str, func: Callable):
        self._registry.register(name, func)
    def get_registry(self) -> RPCRegistry:
        return self._registry

def register_rpc(name: str):
    def decorator(func: Callable):
        GlobalRPCRegistry().register(name, func)
        return func
    return decorator

async def create_server(host: str = "0.0.0.0", port: int = 18999, use_ssl: bool = False) -> TCPIPCServer:
    server = TCPIPCServer(host=host, port=port, use_ssl=use_ssl)
    await server.start()
    return server

async def create_gateway(host: str = "0.0.0.0", port: int = 18999, orchestrator: "NexusOrchestrator" = None) -> HTTPGateway:
    gateway = HTTPGateway(host=host, port=port, orchestrator=orchestrator)
    await gateway.start()
    return gateway

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MINXG IPC/RPC Server")
    parser.add_argument("--mode", choices=["tcp", "http", "both"], default="both")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18999)
    parser.add_argument("--ssl", action="store_true")
    args = parser.parse_args()
    orchestrator = get_orchestrator()
    await orchestrator.initialize()
    servers = []
    if args.mode in ("tcp", "both"):
        tcp_server = await create_server(args.host, args.port, args.ssl)
        servers.append(tcp_server)
    if args.mode in ("http", "both"):
        gateway = await create_gateway(args.host, args.port, orchestrator)
        servers.append(gateway)
    try:
        while True:
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            try:
                await server.stop()
            except Exception as e:
                pass
if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
