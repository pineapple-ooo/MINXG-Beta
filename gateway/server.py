"""
gateway/server.py — MINXG OpenHTTP AI Agent Gateway v1.0.0

Core OpenAI-compatible API server, chaining:
  - WorkerRouter       : Worker routing layer (py_workers + legacy)
  - StructuredWorkspace: Structured workspace (O(1) context)
  - HybridRAG          : Hybrid retrieval augmentation (BM25 + Semantic)
  - InferenceDispatcher: Lightweight inference optimization (L1/L2/L3 tiers)

API endpoints:
  GET  /health                   → Service status + routing info
  GET  /v1/models                → Available model list
  POST /v1/chat/completions      → OpenAI-compatible chat (with tool_calls)
  GET  /workspace/{session_id}   → Workspace status
  POST /rag/add                  → Add knowledge chunks
  POST /rag/search               → Search knowledge
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
import secrets
import hashlib
from typing import Dict, List, Optional, Any, Union

from .config import GatewayConfig, DEFAULT_GATEWAY_HOST, DEFAULT_GATEWAY_PORT

logger = logging.getLogger("gateway.server")


# Backwards compatible alias: older callers pass a plain dict.
_ConfigLike = Union[Dict[str, Any], GatewayConfig, None]


def _coerce_config(config: _ConfigLike) -> GatewayConfig:
    """Accept either a :class:`GatewayConfig` or a raw dict.

    This shim is the *only* place the old ``Dict[str, Any]`` API meets the
    new :class:`GatewayConfig`. Anywhere else in the codebase should
    pass the structured config.
    """
    if isinstance(config, GatewayConfig):
        return config
    if config is None:
        return GatewayConfig.from_sources()
    if isinstance(config, dict):
        return GatewayConfig.from_dict(config)
    raise TypeError(
        f"GatewayServer config must be GatewayConfig or dict, got {type(config).__name__}"
    )




class GatewayServer:
    """
    OpenAI-compatible Gateway server.
    Each session maintains a StructuredWorkspace for infinite context.

    New in v0.16.0: the constructor takes either a ``GatewayConfig`` or a
    raw dict (auto-coerced). Every internal component is wired from the
    same config object — there is no longer any place where the gateway
    silently falls back to env-vars or kubectl-style hot-patches mid-request.
    """

    def __init__(self, config: _ConfigLike = None):
        self.cfg = _coerce_config(config)
        gw_cfg = self.cfg.gateway
        ai_cfg = self.cfg.ai
        wk_cfg = self.cfg.workers

        self.host: str = gw_cfg.host
        self.port: int = gw_cfg.port
        self.version = "0.17.0"

        self.ai_provider: str = ai_cfg.provider
        self.ai_model: str = ai_cfg.model
        self.ai_base_url: str = ai_cfg.base_url
        self.ai_api_key: str = ai_cfg.api_key
        self.default_api_key = self.cfg.auth_token or secrets.token_hex(16)

        self.py_worker_url: str = wk_cfg.url
        self.enable_legacy = bool(self.cfg.legacy.get("enable", False))
        self.legacy_routes = list(self.cfg.legacy.get("routes", []) or [])

        # Legacy nested-dict view is built at the END of ``__init__`` (see
        # below). Putting it here would trip ``_flat_dict`` on attributes
        # like ``_schema_ttl`` that are only set later — the failing test
        # ``tests/test_gateway_runner.py::TestGatewayServerInstantiation``
        # catches exactly this ordering bug.
        self.config: Dict[str, Any] = {}

        self.router: Optional[Any] = None
        self.dispatcher: Optional[Any] = None
        self.rag: Optional[Any] = None
        self.channel_manager: Optional[Any] = None

        self._workspaces: Dict[str, Any] = {}
        self._ws_lock = asyncio.Lock()

        self._tool_schemas: List[Dict] = []
        self._schema_ts: float = 0.0
        self._schema_ttl: float = float(self.cfg.schema_cache_ttl)

        self._request_count: int = 0
        self._tool_call_count: int = 0

        # Now that every slot is populated, render the legacy view once.
        self.config = self._flat_dict()

    def _flat_dict(self) -> Dict[str, Any]:
        """Produce the legacy nested-dict view that pre-0.14 code expected."""
        return {
            "ai": {
                "provider": self.ai_provider,
                "model": self.ai_model,
                "base_url": self.ai_base_url,
                "api_key": self.ai_api_key,
            },
            "gateway": {"host": self.host, "port": self.port},
            "workers": {"host": self.cfg.workers.host, "port": self.cfg.workers.port},
            "legacy": {
                "enable": self.enable_legacy,
                "routes": list(self.legacy_routes),
            },
            "channels": [
                {"name": c.name, "enabled": c.enabled, "adapter": c.adapter,
                 "options": dict(c.options)}
                for c in self.cfg.channels
            ],
            "auth_token": self.default_api_key,
            "schema_cache_ttl": self._schema_ttl,
        }

    async def initialize(self):
        """Initialize all core components."""
        from gateway.router import WorkerRouter
        from gateway.rag import HybridRAG
        from gateway.inference import InferenceDispatcher, ModelProfile

        
        self.router = WorkerRouter(
            py_url=self.py_worker_url,
            legacy_routes=self.legacy_routes,
            enable_legacy=self.enable_legacy,
        )
        logger.info("WorkerRouter initialized: %d routes", len(self.router.routes))

        
        self.rag = HybridRAG()
        
        agents_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "AGENTS.md")
        if os.path.exists(agents_path):
            with open(agents_path) as f:
                self.rag.add_chunk("agents_md", f.read())
            logger.info("Loaded AGENTS.md into RAG")

        
        self.dispatcher = InferenceDispatcher()
        
        self.dispatcher.register(ModelProfile(
            name=self.ai_model, base_url=self.ai_base_url,
            api_key=self.ai_api_key, provider=self.ai_provider, level=1,
            max_tokens=4096, timeout=60,
        ))
        
        models_cfg = self.config.get("models", {})
        for level_key, model_cfg in models_cfg.items():
            level = int(level_key.replace("l", "").replace("L", ""))
            self.dispatcher.register(ModelProfile(
                name=model_cfg.get("model", self.ai_model),
                base_url=model_cfg.get("base_url", self.ai_base_url),
                api_key=model_cfg.get("api_key", self.ai_api_key),
                provider=model_cfg.get("provider", self.ai_provider),
                level=level,
                max_tokens=model_cfg.get("max_tokens", 4096),
                timeout=model_cfg.get("timeout", 90),
            ))
        logger.info("InferenceDispatcher: %d model levels", len(self.dispatcher.models))

        from gateway.channels import ChannelManager
        self.channel_manager = ChannelManager(
            self.cfg.channels, self._handle_channel_message,
        )

        await self._refresh_tool_schemas()

        logger.info("GatewayServer v%s initialized", self.version)

    async def _get_workspace(self, session_id: str) -> Any:
        """Get or create workspace for a session."""
        from gateway.workspace import StructuredWorkspace
        async with self._ws_lock:
            if session_id not in self._workspaces:
                self._workspaces[session_id] = StructuredWorkspace(session_id=session_id)
            return self._workspaces[session_id]

    async def _refresh_tool_schemas(self):
        """Refresh tool schema cache."""
        now = time.time()
        if self._tool_schemas and (now - self._schema_ts) < self._schema_ttl:
            return
        if self.router is None:
            return
        self._tool_schemas = await self.router.fetch_tools()
        self._schema_ts = now
        logger.info("Refreshed tool schemas: %d tools", len(self._tool_schemas))

    def _cleanup_stale_workspaces(self, max_age: float = 7200):
        """Remove workspaces older than max_age seconds."""
        now = time.time()
        stale = [sid for sid, ws in self._workspaces.items()
                 if (now - ws.created_at) > max_age]
        for sid in stale:
            del self._workspaces[sid]
        if stale:
            logger.info("Cleaned %d stale workspaces", len(stale))

    async def _handle_channel_message(self, msg) -> str:
        """Dispatch one inbound channel message through the OpenAI chat path."""
        from gateway.channels import ChannelMessage
        if not isinstance(msg, ChannelMessage):
            return "[error: invalid message envelope]"
        if self.dispatcher is None or self.rag is None or self.router is None:
            return "[error: gateway not initialized]"

        session_id = msg.session_id or f"ch_{uuid.uuid4().hex[:8]}"
        ws = await self._get_workspace(session_id)
        if ws.turn_count == 0:
            ws.set_objective(msg.content)

        from gateway.inference import TaskGrader
        task_level = TaskGrader.grade(msg.content, ws.tool_calls_count, ws.turn_count)
        model_profile = self.dispatcher.select(task_level)

        final_messages = ws.build_context(include_workspace=True, include_recent=True)
        rag_text = self.rag.inject_context(msg.content, max_tokens=500)
        if rag_text:
            final_messages.append({"role": "system", "content": rag_text})
        final_messages.append({"role": "user", "content": msg.content})

        await self._refresh_tool_schemas()
        try:
            llm_response = await self.dispatcher.chat_completion(
                messages=final_messages,
                model=model_profile,
                tools=self._tool_schemas,
                stream=False,
                temperature=0.7,
            )
        except Exception as exc:
            logger.exception("Channel LLM call failed")
            return f"[error: {exc}]"

        choice = (llm_response.get("choices") or [{}])[0]
        content = str(choice.get("message", {}).get("content", ""))
        ws.add_message("assistant", content)
        ws.advance_turn()
        return content






async def _build_app(gw: GatewayServer) -> Any:
    """Build aiohttp Application and bind routes."""
    from aiohttp import web

    app = web.Application()

    
    async def health(req: web.Request) -> web.Response:
        routes_info = gw.router.get_routes_summary() if gw.router else []
        health_data = await gw.router.health_all() if gw.router else []
        ws_count = len(gw._workspaces)
        return web.json_response({
            "status": "ok",
            "version": gw.version,
            "gateway": f"{gw.host}:{gw.port}",
            "routes": routes_info,
            "workers_health": health_data,
            "active_sessions": ws_count,
            "tool_schemas_cached": len(gw._tool_schemas),
            "requests_served": gw._request_count,
            "tool_calls_served": gw._tool_call_count,
        })

    
    async def list_models(req: web.Request) -> web.Response:
        models = []
        for level, profile in gw.dispatcher.models.items():
            models.append({
                "id": profile.name,
                "object": "model",
                "owned_by": profile.provider,
                "level": f"L{level}",
            })
        return web.json_response({
            "object": "list",
            "data": models,
        })

    def _parse_tool_arguments(func: Dict[str, Any]) -> Dict[str, Any]:
        raw = func.get("arguments", "{}")
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {"raw": raw}

    def _preview(value: Any, max_chars: int = 1200) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
        return text[:max_chars] + ("..." if len(text) > max_chars else "")

    def _make_tool_card(tc: Dict[str, Any], arguments: Dict[str, Any],
                        result: Dict[str, Any], elapsed_ms: float) -> Dict[str, Any]:
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        status = result.get("status", "success") if isinstance(result, dict) else "success"
        if isinstance(result, dict) and result.get("error"):
            status = "error"
        return {
            "id": tc.get("id") or f"call_{uuid.uuid4().hex[:10]}",
            "type": "tool_card",
            "tool": tool_name,
            "worker": result.get("worker") if isinstance(result, dict) else None,
            "status": status,
            "title": f"{tool_name} ({status})" if tool_name else f"tool ({status})",
            "arguments": arguments,
            "result": result,
            "result_preview": _preview(result),
            "elapsed_ms": elapsed_ms,
            "created_at": time.time(),
        }

    async def _execute_tool_call(tc: Dict[str, Any]) -> Dict[str, Any]:
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        arguments = _parse_tool_arguments(func)
        t_tool = time.time()
        gw._tool_call_count += 1
        try:
            result = await gw.router.execute_tool(tool_name, dict(arguments))
        except Exception as e:
            logger.exception("Tool call failed: %s", tool_name)
            result = {"status": "error", "worker": None, "tool": tool_name, "error": str(e)}
        elapsed_ms = round((time.time() - t_tool) * 1000, 2)
        return {
            "tool_call": tc,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "card": _make_tool_card(tc, arguments, result, elapsed_ms),
        }

    async def _execute_tool_calls_parallel(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tool_calls:
            return []
        return await asyncio.gather(*[_execute_tool_call(tc) for tc in tool_calls])

    
    async def chat_completions(req: web.Request) -> web.Response:
        gw._request_count += 1
        t0 = time.time()

        try:
            body = await req.json()
        except json.JSONDecodeError as e:
            return web.json_response({"error": {"message": f"Invalid JSON: {e}", "type": "invalid_request_error"}},
                                     status=400)

        
        model_name = body.get("model", gw.ai_model)
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 4096)
        session_id = body.get("session_id", None) or req.headers.get("X-Session-ID", "")
        requested_tools = body.get("tools", None)

        
        if not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        
        ws = await gw._get_workspace(session_id)

        
        if ws.turn_count == 0 and messages:
            for m in messages:
                if m.get("role") == "user":
                    ws.set_objective(m["content"])
                    break

        
        from gateway.inference import TaskGrader
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
        task_level = TaskGrader.grade(last_user_msg, ws.tool_calls_count, ws.turn_count)
        model_profile = gw.dispatcher.select(task_level)

        
        
        ws_messages = ws.build_context(include_workspace=True, include_recent=True)
        
        rag_text = gw.rag.inject_context(last_user_msg, max_tokens=500)
        if rag_text:
            ws_messages.append({"role": "system", "content": rag_text})

        
        
        final_messages = ws_messages
        
        ws_recent_content = {m.get("content", "") for m in ws._recent_messages}
        for m in messages:
            if m.get("role") == "user" and m.get("content", "") not in ws_recent_content:
                final_messages.append({"role": m["role"], "content": m["content"]})

        
        await gw._refresh_tool_schemas()
        tools_to_use = requested_tools or gw._tool_schemas

        
        try:
            llm_response = await gw.dispatcher.chat_completion(
                messages=final_messages,
                model=model_profile,
                tools=tools_to_use,
                stream=stream,
                temperature=temperature,
            )
        except Exception as e:
            logger.exception("LLM call failed")
            return web.json_response({
                "error": {"message": f"LLM call failed: {str(e)[:500]}",
                          "type": "api_error", "level": task_level},
            }, status=500)

        
        if not stream and isinstance(llm_response, dict):
            choice = llm_response.get("choices", [{}])[0]
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            tool_cards: List[Dict[str, Any]] = []
            if tool_calls:
                
                ws.advance_turn()
                tool_outputs = await _execute_tool_calls_parallel(tool_calls)

                
                final_messages.append(message)
                for item in tool_outputs:
                    tc = item["tool_call"]
                    result = item["result"]
                    tool_name = item["tool_name"]
                    ws.add_tool_result(tool_name, result)
                    tool_cards.append(item["card"])
                    final_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(result, ensure_ascii=False)[:2000],
                    })

                
                try:
                    llm_response = await gw.dispatcher.chat_completion(
                        messages=final_messages,
                        model=model_profile,
                        tools=tools_to_use,
                        stream=False,
                        temperature=temperature,
                    )
                except Exception as e:
                    logger.exception("LLM retry after tool_calls failed")
                    return web.json_response({
                        "error": {"message": f"LLM retry failed: {str(e)[:500]}",
                                  "type": "api_error"},
                    }, status=500)

                
                final_choice = llm_response.get("choices", [{}])[0]
                final_msg = final_choice.get("message", {})
                final_content = final_msg.get("content", "")
                ws.add_message("assistant", final_content)
                ws.advance_turn()

            else:
                
                content = message.get("content", "")
                ws.add_message("assistant", content)
                ws.advance_turn()

            
            elapsed = round((time.time() - t0) * 1000, 2)
            
            if "model" in llm_response:
                llm_response["model"] = model_name
            
            if "usage" not in llm_response:
                llm_response["usage"] = {
                    "prompt_tokens": ws.estimate_tokens(),
                    "completion_tokens": 0,
                    "total_tokens": ws.estimate_tokens(),
                }
            
            llm_response["session_id"] = session_id
            llm_response["task_level"] = f"L{task_level}"
            llm_response["elapsed_ms"] = elapsed
            llm_response["tool_cards"] = tool_cards

            return web.json_response(llm_response)

        elif stream:
            
            resp = web.StreamResponse()
            resp.content_type = "text/event-stream"
            resp.headers["Cache-Control"] = "no-cache"
            resp.headers["X-Accel-Buffering"] = "no"
            await resp.prepare(req)

            streamed_tool_calls: Dict[int, Dict[str, Any]] = {}
            async for chunk in llm_response:
                
                if isinstance(chunk, dict):
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta", {}) or {}
                        for tc_delta in delta.get("tool_calls", []) or []:
                            idx = tc_delta.get("index", len(streamed_tool_calls))
                            acc = streamed_tool_calls.setdefault(
                                idx,
                                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                            )
                            if tc_delta.get("id"):
                                acc["id"] = tc_delta.get("id")
                            func_delta = tc_delta.get("function", {}) or {}
                            if func_delta.get("name"):
                                acc["function"]["name"] += func_delta.get("name", "")
                            if func_delta.get("arguments"):
                                acc["function"]["arguments"] += func_delta.get("arguments", "")

                
                if "model" in chunk:
                    chunk["model"] = model_name
                data = json.dumps(chunk, ensure_ascii=False)
                await resp.write(f"data: {data}\n\n".encode("utf-8"))

            if streamed_tool_calls:
                tool_calls = [streamed_tool_calls[i] for i in sorted(streamed_tool_calls)]
                tool_outputs = await _execute_tool_calls_parallel(tool_calls)
                final_messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

                for item in tool_outputs:
                    tc = item["tool_call"]
                    result = item["result"]
                    ws.add_tool_result(item["tool_name"], result)
                    card_event = {
                        "id": f"toolcard-{uuid.uuid4().hex[:12]}",
                        "object": "tool.card",
                        "session_id": session_id,
                        "tool_card": item["card"],
                    }
                    await resp.write(f"data: {json.dumps(card_event, ensure_ascii=False)}\n\n".encode("utf-8"))
                    final_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(result, ensure_ascii=False)[:2000],
                    })

                retry_response = await gw.dispatcher.chat_completion(
                    messages=final_messages,
                    model=model_profile,
                    tools=tools_to_use,
                    stream=False,
                    temperature=temperature,
                )
                final_choice = retry_response.get("choices", [{}])[0]
                final_msg = final_choice.get("message", {})
                final_content = final_msg.get("content", "")
                if final_content:
                    content_chunk = {
                        "id": retry_response.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
                        "object": "chat.completion.chunk",
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {"content": final_content}, "finish_reason": None}],
                    }
                    await resp.write(f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
                    ws.add_message("assistant", final_content)

            await resp.write("data: [DONE]\n\n".encode("utf-8"))
            if not streamed_tool_calls:
                ws.add_message("assistant", "[streaming response]")
            ws.advance_turn()
            return resp

        else:
            
            return web.json_response(llm_response)

    
    async def get_workspace(req: web.Request) -> web.Response:
        session_id = req.match_info.get("session_id", "")
        if session_id not in gw._workspaces:
            return web.json_response({"error": "session not found"}, status=404)
        ws = gw._workspaces[session_id]
        return web.json_response(ws.to_dict())

    
    async def list_workspaces(req: web.Request) -> web.Response:
        sessions = []
        for sid, ws in gw._workspaces.items():
            sessions.append({
                "session_id": sid,
                "turn_count": ws.turn_count,
                "tool_calls_count": ws.tool_calls_count,
                "tokens_estimate": ws.estimate_tokens(),
                "created_at": ws.created_at,
            })
        return web.json_response({"sessions": sessions, "total": len(sessions)})

    
    async def rag_add(req: web.Request) -> web.Response:
        try:
            body = await req.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid JSON"}, status=400)
        chunk_id = body.get("id", f"chunk_{uuid.uuid4().hex[:8]}")
        text = body.get("text", "")
        if not text:
            return web.json_response({"error": "text required"}, status=400)
        gw.rag.add_chunk(chunk_id, text)
        return web.json_response({"status": "added", "id": chunk_id})

    
    async def rag_search(req: web.Request) -> web.Response:
        try:
            body = await req.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid JSON"}, status=400)
        query = body.get("query", "")
        top_k = body.get("top_k", 5)
        if not query:
            return web.json_response({"error": "query required"}, status=400)
        results = gw.rag.search(query, top_k=top_k)
        return web.json_response({"results": results})

    
    async def get_tool_schemas(req: web.Request) -> web.Response:
        await gw._refresh_tool_schemas()
        return web.json_response({"tools": gw._tool_schemas, "total": len(gw._tool_schemas)})

    
    async def gateway_stats(req: web.Request) -> web.Response:
        return web.json_response({
            "version": gw.version,
            "requests_served": gw._request_count,
            "tool_calls_served": gw._tool_call_count,
            "active_sessions": len(gw._workspaces),
            "tool_schemas_cached": len(gw._tool_schemas),
            "rag_chunks": len(gw.rag._contents) if gw.rag else 0,
            "model_levels": {f"L{k}": v.name for k, v in gw.dispatcher.models.items()} if gw.dispatcher else {},
        })

    
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", list_models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    app.router.add_get("/workspace", list_workspaces)
    app.router.add_get("/workspace/{session_id}", get_workspace)
    app.router.add_post("/rag/add", rag_add)
    app.router.add_post("/rag/search", rag_search)
    app.router.add_get("/tools", get_tool_schemas)
    app.router.add_get("/stats", gateway_stats)

    if gw.channel_manager is not None:
        gw.channel_manager.add_routes(app)

    
    async def cleanup_middleware(app, handler):
        async def middleware_handler(req):
            
            if gw._request_count % 100 == 0:
                gw._cleanup_stale_workspaces()
            return await handler(req)
        return middleware_handler

    app.middlewares.append(cleanup_middleware)

    
    async def on_startup(app):
        await gw.initialize()
        if gw.channel_manager is not None:
            await gw.channel_manager.start()
        logger.info("GatewayServer started and initialized")

    app.on_startup.append(on_startup)

    
    async def on_cleanup(app):
        if gw.channel_manager is not None:
            await gw.channel_manager.stop()
        if gw.router:
            await gw.router.close()
        logger.info("GatewayServer shutdown complete")

    app.on_cleanup.append(on_cleanup)

    
    app["gateway"] = gw
    return app


async def start_gateway(host: str = "0.0.0.0", port: int = 18080,
                        config: Dict[str, Any] = None) -> Any:
    """Start Gateway server and return (app, runner, site)."""
    from aiohttp import web

    gw = GatewayServer(config=config)
    gw.host = host
    gw.port = port

    app = await _build_app(gw)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port, reuse_address=True)
    try:
        await site.start()
    except OSError as e:
        logger.error("Cannot bind %s:%d — %s", host, port, e)
        raise

    total_tools = len(gw._tool_schemas)
    routes_count = len(gw.router.routes) if gw.router else 0
    banner = f"""
╔═════════════════════════════════════════════════════════════════╗
║  MINXG OpenHTTP Gateway v{gw.version}                          ║
║                                                                 ║
║  Endpoints:                                                     ║
║    GET  /health              Service status                     ║
║    GET  /v1/models           Model list (L1/L2/L3)             ║
║    POST /v1/chat/completions OpenAI-compatible chat             ║
║    GET  /workspace           Session workspaces                 ║
║    GET  /workspace/{{session_id}}  Workspace detail                   ║
║    POST /rag/add             Add knowledge chunks               ║
║    POST /rag/search          Search knowledge (BM25+Semantic)   ║
║    GET  /tools               Tool schemas                       ║
║    GET  /stats               Gateway statistics                 ║
║                                                                 ║
║  Workers: {routes_count} routes, {total_tools} tools cached                       ║
║  Models:  {len(gw.dispatcher.models)} levels (L1/L2/L3)                           ║
║  Listening: {host}:{port}                                        ║
╚═════════════════════════════════════════════════════════════════╝
"""
    print(banner, file=__import__("sys").stderr)
    logger.info("Gateway listening on %s:%d", host, port)

    return app, runner, site


__all__ = ["GatewayServer", "start_gateway", "_build_app"]

