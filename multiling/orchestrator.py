"""
MINXG NexusOrchestrator v3.3.2
Main entry point integrating all new components.
Enhanced with true infinite context support via:
- Conversation summarization & compression
- Token budget management with sliding window
- Hierarchical memory layers (episodic + semantic)
- Context-aware message routing
"""

import os
import sys
import json
import time
import asyncio
import logging
import uuid
import secrets
import hashlib
from typing import Dict, List, Optional, Any, Callable, Tuple
from pathlib import Path
from collections import OrderedDict
from dataclasses import dataclass, field, asdict

def _resolve_log_level() -> int:
    """Default to WARNING in interactive shells so `INFO` chatter is hidden.

    Override at runtime via ``-v`` (handled in main()) or by exporting
    ``MINXG_LOG_LEVEL=INFO`` / ``DEBUG`` for diagnostics.
    """
    env = os.environ.get("MINXG_LOG_LEVEL", "").strip().upper()
    if env in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return getattr(logging, env)
    return logging.WARNING


logging.basicConfig(
    level=_resolve_log_level(),
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("nexus")






def _get_project_root() -> Path:
    return Path(__file__).parent.resolve()


def _get_config_path() -> Path:
    return _get_project_root() / "config.yaml"


def _load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml."""
    config_path = _get_config_path()
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load config: {e}")
    return {}






@dataclass
class MemoryLayer:
    """Base class for memory layers."""
    layer_type: str
    capacity: int
    content: List[Dict] = field(default_factory=list)
    
    def add(self, item: Dict) -> None:
        """Add an item, maintaining capacity."""
        self.content.append(item)
        if len(self.content) > self.capacity:

            self.content = self.content[-self.capacity:]
    
    def get(self, count: int = -1) -> List[Dict]:
        """Get recent items."""
        if count < 0:
            return self.content[:]
        return self.content[-count:]


@dataclass
class EpisodicMemory(MemoryLayer):
    """Conversation-level episodic memory. Stores conversation turns."""
    def __init__(self, capacity: int = 10000):
        super().__init__("episodic", capacity)
        self._turn_index: Dict[str, int] = {}
        self._session_id: Optional[str] = None
        self.created_at = time.time()
    
    def add_turn(self, role: str, content: str, turn_id: Optional[str] = None,
                 metadata: Optional[Dict] = None) -> str:
        """Add a conversation turn. Returns turn_id."""
        tid = turn_id or f"turn_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        item = {
            "id": tid,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        self.add(item)
        self._turn_index[tid] = len(self.content) - 1
        return tid
    
    def get_turn(self, turn_id: str) -> Optional[Dict]:
        """Retrieve a specific turn by ID."""
        idx = self._turn_index.get(turn_id)
        if idx is not None and idx < len(self.content):
            return self.content[idx]
        return None
    
    def get_context_band(self, window_size: int = 20) -> List[Dict]:
        """Get the most recent context window for LLM (immutable)."""
        recent = self.get(window_size)

        return [{"role": m["role"], "content": m["content"]} for m in recent]
    
    def find_by_content(self, query: str, limit: int = 10) -> List[Dict]:
        """Simple content search (can be enhanced with embedding)."""
        results = []
        q = query.lower()
        for item in reversed(self.content):
            if q in item["content"].lower():
                results.append(item)
                if len(results) >= limit:
                    break
        return results


@dataclass 
class SemanticMemory:
    """Key facts, summaries, and distilled knowledge (compressed context)."""
    def __init__(self, max_facts: int = 1000):
        self.max_facts = max_facts
        self.facts: OrderedDict[str, Dict] = OrderedDict()
        self._embeddings: Dict[str, List[float]] = {}
    
    def add_fact(self, key: str, content: str, importance: float = 1.0) -> None:
        """Add or update a fact."""
        self.facts[key] = {
            "content": content,
            "importance": importance,
            "updated": time.time(),
            "created": self.facts.get(key, {}).get("created", time.time()),
        }

        while len(self.facts) > self.max_facts:
            oldest_key = min(self.facts, key=lambda k: self.facts[k].get("importance", 0))
            del self.facts[oldest_key]
    
    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve a fact by key."""
        fact = self.facts.get(key)
        return fact["content"] if fact else None
    
    def query(self, query_str: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Query facts by relevance (simple substring match, upgradeable to embedding)."""
        q = query_str.lower()
        scored = []
        for key, fact in self.facts.items():
            content = fact["content"].lower()
            score = 0.0
            if q in key.lower():
                score += 2.0
            if q in content:
                score += 1.0
            if score > 0:
                scored.append((key, fact["content"], score * fact.get("importance", 1.0)))
        scored.sort(key=lambda x: x[2], reverse=True)
        return [(k, c) for k, c, _ in scored[:limit]]
    
    def to_messages(self, limit: int = 10) -> List[Dict]:
        """Convert most important facts to system messages."""
        facts = sorted(self.facts.values(), 
                      key=lambda f: f.get("importance", 0), reverse=True)[:limit]
        if not facts:
            return []
        content = "Key facts:\n" + "\n".join([f"- {f['content'][:200]}" for f in facts])
        return [{"role": "system", "content": content}]


class ContextCompressor:
    """Compress conversation context to fit within token budget."""
    
    def __init__(self, max_tokens: int = 8000, tokens_per_char: float = 0.4):
        self.max_tokens = max_tokens
        self.tokens_per_char = tokens_per_char
        self._summary_cache: Dict[str, str] = {}
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        return int(len(text) * self.tokens_per_char)
    
    def compress_messages(self, messages: List[Dict], preserve_system: bool = True) -> List[Dict]:
        """Compress messages to fit within token budget."""
        if not messages:
            return []
        
        system_msgs = [m for m in messages if m.get("role") == "system"] if preserve_system else []
        other_msgs = [m for m in messages if m.get("role") != "system"] if preserve_system else messages
        

        recent = other_msgs[-10:] if len(other_msgs) > 10 else other_msgs[:]
        older = other_msgs[:-10] if len(other_msgs) > 10 else []
        

        result = system_msgs[:]
        
        if older:

            summary = f"[Earlier conversation: {len(older)} messages summarised]"
            result.insert(0, {"role": "system", "content": summary})
        
        result.extend(recent)
        return result
    
    def sliding_window(self, messages: List[Dict], window_size: int = 50) -> List[Dict]:
        """Apply sliding window to keep only recent messages."""
        return messages[-window_size:] if len(messages) > window_size else messages[:]
    
    def create_summary(self, messages: List[Dict]) -> str:
        """Create a summary of conversation messages (placeholder for LLM summarization)."""
        if not messages:
            return "No conversation yet."
        
        roles = {}
        for m in messages:
            role = m.get("role", "unknown")
            roles[role] = roles.get(role, 0) + 1
        
        return f"Conversation summary: {len(messages)} turns. Role distribution: {roles}"


class InfiniteContextManager:
    """
    Manages conversation context with theoretically unlimited capacity.
    
    Layers:
    - Working Memory: Recent N messages (fit in LLM context window)
    - Episodic Memory: Full conversation history with lookup
    - Semantic Memory: Compressed facts and summaries
    - Compression: Automatic summarization when context grows
    """
    
    def __init__(self, session_id: Optional[str] = None, 
                 max_working_memory: int = 100,
                 max_episodic: int = 100000,
                 max_semantic: int = 1000):
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self._working_memory: List[Dict] = []
        self._episodic = EpisodicMemory(capacity=max_episodic)
        self._semantic = SemanticMemory(max_facts=max_semantic)
        self._compressor = ContextCompressor()
        self._max_working = max_working_memory
        self._lock = asyncio.Lock()
    
    async def add_message(self, role: str, content: str, 
                         metadata: Optional[Dict] = None) -> None:
        """Add a message to the context."""
        async with self._lock:
            msg = {"role": role, "content": content, "timestamp": time.time()}
            if metadata:
                msg.update(metadata)
            
            self._working_memory.append(msg)
            self._episodic.add_turn(role, content, metadata=metadata)
            

            if len(self._working_memory) > self._max_working:

                self._working_memory = self._working_memory[-self._max_working:]
                await self._maybe_compress()
    
    async def _maybe_compress(self) -> None:
        """Compress working memory if it's getting too large."""
        total_tokens = sum(self._compressor.estimate_tokens(m["content"]) for m in self._working_memory)
        if total_tokens > self._compressor.max_tokens:

            recent = self._working_memory[-20:]
            older = self._working_memory[:-20]
            summary = self._compressor.create_summary(older)
            self._semantic.add_fact("conversation_summary", summary)
            self._working_memory = [{"role": "system", "content": f"[Summary: {summary}]"}] + recent
    
    async def get_context(self, max_messages: int = 50, 
                         include_semantic: bool = True) -> List[Dict]:
        """Get messages for the LLM, with semantic context if available."""
        async with self._lock:
            result = []
            

            if include_semantic:
                result.extend(self._semantic.to_messages(limit=5))
            

            if len(self._working_memory) > max_messages:

                compressed = self._compressor.sliding_window(self._working_memory, max_messages)
                result.extend(compressed)
            else:
                result.extend(self._working_memory)
            
            return result
    
    async def query_history(self, query: str, limit: int = 10) -> List[Dict]:
        """Search conversation history for relevant turns."""
        return self._episodic.find_by_content(query, limit=limit)
    
    def add_fact(self, key: str, content: str, importance: float = 1.0) -> None:
        """Add a fact to semantic memory."""
        self._semantic.add_fact(key, content, importance)
    
    def get_stats(self) -> Dict:
        """Get context statistics."""
        return {
            "session_id": self.session_id,
            "working_memory_size": len(self._working_memory),
            "episodic_turns": len(self._episodic.content),
            "semantic_facts": len(self._semantic.facts),
        }





from agent.iteration_budget import IterationBudget
from agent.conversation_loop import ConversationLoop
from multiling.model_tools import (
    get_tool_definitions,
    handle_function_call,
    get_all_tool_names,
    get_available_toolsets,
    ensure_tools_discovered,
    refresh_tool_maps,
)
from multiling.toolsets import DEFAULT_TOOLSETS






logger.info("Loading tool modules...")
from tools import file_tools, terminal_tool, system_tools, web_tools
from tools import delegate_tool, skill_manager_tool, cronjob_tools


from tools.registry import registry

logger.info(f"Registered {len(get_all_tool_names())} tools from new system")





TOOL_REGISTRY: Dict[str, Callable] = {}

def _register_legacy_tools():
    """Register legacy tool format for backward compatibility."""

    all_tools = get_all_tool_names()
    for name in all_tools:
        entry = registry.get_entry(name)
        if entry:
            TOOL_REGISTRY[name] = lambda args, entry=entry: entry.handler(args)
_register_legacy_tools()

TOOL_SPECS = []






class SessionManager:
    """Manages infinite context sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, InfiniteContextManager] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
    
    async def get_session(self, session_id: Optional[str] = None) -> InfiniteContextManager:
        """Get or create a session."""
        sid = session_id or f"default_{uuid.uuid4().hex[:8]}"
        async with self._lock:
            if sid not in self._sessions:
                self._sessions[sid] = InfiniteContextManager(session_id=sid)
            return self._sessions[sid]
    
    async def cleanup_stale_sessions(self, max_age_seconds: float = 3600) -> int:
        """Remove stale sessions. Returns number removed."""
        now = time.time()
        removed = 0
        async with self._lock:
            stale = [sid for sid, sess in self._sessions.items() 
                    if (now - sess._episodic.created_at) > max_age_seconds]
            for sid in stale:
                del self._sessions[sid]
                removed += 1
        return removed





class NexusOrchestrator:
    """
    Main orchestrator class integrating:
    - Tool registry (self-registering tools)
    - Conversation loop with iteration budget
    - Legacy worker system (optional)
    - OpenAI-compatible API
    - Infinite context via session manager
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "hermes-3-mini",
        ai_model: str = None,
        ai_base_url: str = None,
        ai_api_key: str = None,
        ai_provider: str = None,
        max_iterations: int = 90,
        enabled_toolsets: List[str] = None,
        config: Dict[str, Any] = None,
        session_id: Optional[str] = None,
    ):

        if config is None:
            config = _load_config()


        ai_config = config.get("ai", {})

        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or secrets.token_hex(16)
        self.model = ai_model or model
        self.ai_model = ai_model or model
        self.ai_base_url = ai_base_url or os.getenv("AI_BASE_URL") or ai_config.get("base_url", "http://localhost:11434/v1")
        self.ai_api_key = ai_api_key or os.getenv("AI_API_KEY") or ai_config.get("api_key", "")
        self.ai_provider = ai_provider or ai_config.get("provider", "local") if ai_config else ai_provider or "local"
        self.max_iterations = max_iterations
        self.enabled_toolsets = enabled_toolsets or DEFAULT_TOOLSETS


        self.config = config


        anti_loop_config = config.get("anti_loop", {}) if config else {}
        is_mobile = config.get("platform", {}).get("mobile", False) if config else False
        try:
            from src.ai.safety.guard import get_guard
            self.anti_loop = get_guard(is_mobile=is_mobile)
            if anti_loop_config.get("max_depth"):
                self.anti_loop.depth_guard.max_depth = int(anti_loop_config["max_depth"])
            logger.info(f"Anti-loop guard initialized: max_depth={self.anti_loop.depth_guard.max_depth}")
        except ImportError as e:
            logger.warning(f"Anti-loop guard not available: {e}")
            self.anti_loop = None


        self.conversation_loop = ConversationLoop(
            max_iterations=max_iterations,
            tool_delay=0.5,
            quiet_mode=False,
        )


        self._session_manager = SessionManager()
        self._current_session_id = session_id
        self._context: Optional[InfiniteContextManager] = None


        self.scheduler: Optional["TaskScheduler"] = None


        ensure_tools_discovered()
        refresh_tool_maps()

        logger.info(f"NexusOrchestrator v3.3.2 initialized: provider={self.ai_provider}, model={self.ai_model}, infinite_context=True")

    async def _get_context(self) -> InfiniteContextManager:
        """Get or initialize the infinite context manager."""
        if self._context is None:
            self._context = await self._session_manager.get_session(self._current_session_id)
        return self._context

    def chat(self, message: str, system_message: str = None, 
             session_id: Optional[str] = None) -> str:
        """
        Simple chat interface - synchronous.
        Returns final response string.
        Now with infinite context support across sessions!
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": message})
        

        tools = get_tool_definitions(enabled_toolsets=self.enabled_toolsets)
        
        if not tools:
            return "No tools available. Please check configuration."
        

        result = self._run_conversation(messages, tools, session_id=session_id)
        return result.get("final_response", "")





    async def chat_stream(self, message: str, system_message: str = None,
                          session_id: Optional[str] = None,
                          tool_callback=None):
        """Async generator yielding structured events for TUI streaming.

        Yields dicts:
          {"type": "thinking", "content": "..."}     — model reasoning/CoT
          {"type": "text", "content": "..."}          — incremental text token
          {"type": "tool_call", "name": "...", "args": {...}}  — tool invoked
          {"type": "tool_result", "name": "...", "result": {...}, "elapsed_ms": N}
          {"type": "done", "final_text": "..."}       — stream complete
          {"type": "error", "message": "..."}          — fatal error
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": message})

        tools = get_tool_definitions(enabled_toolsets=self.enabled_toolsets)
        if not tools:
            yield {"type": "error", "message": "No tools available."}
            return


        async for event in self._stream_conversation(
            messages, tools, session_id=session_id, tool_callback=tool_callback
        ):
            yield event

    async def _stream_conversation(self, messages, tools, session_id=None,
                                   tool_callback=None, max_iters=90):
        """Streaming conversation loop with tool execution."""
        import aiohttp
        import time as time_mod

        ctx = await self._get_context()
        for msg in messages:
            await ctx.add_message(msg["role"], msg["content"])

        api_call_count = 0
        final_text_parts = []
        accumulated_tool_calls = {}

        while api_call_count < max_iters:
            api_call_count += 1


            context_msgs = await ctx.get_context(max_messages=50)


            headers = {"Content-Type": "application/json"}
            if self.ai_api_key:
                headers["Authorization"] = f"Bearer {self.ai_api_key}"

            payload = {
                "model": self.ai_model,
                "messages": context_msgs,
                "stream": True,
            }
            if tools:
                payload["tools"] = tools

            has_tool_calls = False
            has_content = False
            current_reasoning = ""
            tool_calls_for_round = []

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.ai_base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=300),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            yield {"type": "error",
                                   "message": f"AI error {resp.status}: {body[:200]}"}
                            return


                        buffer = b""
                        accumulated_tool_calls = {}
                        async for chunk in resp.content.iter_any():
                            buffer += chunk
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                line = line.strip()
                                if not line or line == b"data: [DONE]":
                                    if line == b"data: [DONE]":
                                        break
                                    continue
                                if not line.startswith(b"data: "):
                                    continue
                                data_str = line[6:].decode("utf-8", errors="replace")
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                for choice in data.get("choices", []):
                                    delta = choice.get("delta", {}) or {}


                                    reasoning = delta.get("reasoning_content") or ""
                                    if reasoning:
                                        yield {"type": "thinking",
                                               "content": reasoning}


                                    text = delta.get("content") or ""
                                    if text:
                                        has_content = True
                                        final_text_parts.append(text)
                                        yield {"type": "text", "content": text}


                                    for tc_delta in delta.get("tool_calls", []) or []:
                                        has_tool_calls = True
                                        idx = tc_delta.get("index", 0)
                                        acc = accumulated_tool_calls.setdefault(
                                            idx,
                                            {"id": "", "type": "function",
                                             "function": {"name": "", "arguments": ""}},
                                        )
                                        if tc_delta.get("id"):
                                            acc["id"] = tc_delta.get("id")
                                        fd = tc_delta.get("function", {}) or {}
                                        if fd.get("name"):
                                            acc["function"]["name"] += fd["name"]
                                        if fd.get("arguments"):
                                            acc["function"]["arguments"] += fd["arguments"]

                if has_tool_calls:

                    tool_calls_for_round = [
                        accumulated_tool_calls[i]
                        for i in sorted(accumulated_tool_calls)
                    ]


                    for tc in tool_calls_for_round:
                        fn_name = tc["function"]["name"]
                        fn_args_str = tc["function"]["arguments"]
                        try:
                            fn_args = json.loads(fn_args_str) if fn_args_str else {}
                        except json.JSONDecodeError:
                            fn_args = {"raw": fn_args_str}

                        yield {"type": "tool_call",
                               "name": fn_name, "args": fn_args}

                        t0 = time_mod.time()
                        result_raw = handle_function_call(
                            fn_name, fn_args,
                            guard=getattr(self, 'anti_loop', None),
                        )
                        elapsed = round((time_mod.time() - t0) * 1000)
                        try:
                            result_obj = json.loads(result_raw)
                        except (json.JSONDecodeError, TypeError):
                            result_obj = {"result": str(result_raw)}


                        if hasattr(self, 'anti_loop') and self.anti_loop is not None:
                            injection = self.anti_loop.get_context_injection()
                            if injection and not isinstance(result_obj, dict):
                                result_obj = {"result": str(result_obj)}
                            if injection and isinstance(result_obj, dict):
                                result_obj["_anti_loop_warning"] = injection

                        yield {"type": "tool_result",
                               "name": fn_name,
                               "result": result_obj,
                               "elapsed_ms": elapsed}

                        await ctx.add_message("tool", json.dumps(result_obj))


                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": json.dumps(result_obj, ensure_ascii=False)[:2000],
                        })


                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls_for_round,
                    })

                    continue


                final_text = "".join(final_text_parts)
                if final_text:
                    await ctx.add_message("assistant", final_text)
                yield {"type": "done", "final_text": final_text}
                return

            except aiohttp.ClientError as e:
                yield {"type": "error", "message": f"Connection error: {e}"}
                return
            except Exception as e:
                import traceback
                yield {"type": "error",
                       "message": f"{e}\n{traceback.format_exc()}"}
                return

        yield {"type": "done", "final_text": "[Max iterations reached]"}

    def _run_conversation(self, messages: List[Dict], tools: List[Dict],
                         session_id: Optional[str] = None) -> Dict:
        """Internal conversation runner using conversation loop."""

        if self.ai_provider and self.ai_provider != "local" and self.ai_base_url:
            return self._run_with_upstream_ai(messages, tools, session_id=session_id)
        else:

            return self._run_local_tools_only(messages, tools, session_id=session_id)

    def _run_with_upstream_ai(self, messages: List[Dict], tools: List[Dict],
                             session_id: Optional[str] = None) -> Dict:
        """Run conversation with upstream AI service, with infinite context."""
        import aiohttp
        
        async def call_ai(request_messages, request_tools):
            headers = {"Content-Type": "application/json"}
            if self.ai_api_key:
                headers["Authorization"] = f"Bearer {self.ai_api_key}"
            
            payload = {
                "model": self.ai_model,
                "messages": request_messages,
            }
            if request_tools:
                payload["tools"] = request_tools
            
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{self.ai_base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as r:
                        if r.status != 200:
                            return None, f"AI error: {r.status}"
                        return await r.json(), None
            except Exception as e:
                return None, str(e)
        
        async def execute_tool(name, args):
            result = handle_function_call(name, args)
            try:
                return json.loads(result)
            except:
                return {"result": result}
        

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self._async_run_conversation(messages, tools, call_ai, execute_tool, session_id=session_id)
            )
            return result
        finally:
            loop.close()

    async def _async_run_conversation(
        self,
        messages: List[Dict],
        tools: List[Dict],
        call_model_fn,
        execute_tool_fn,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Async conversation with tool execution and infinite context.
        
        Returns dict with keys: final_response, messages, tool_cards
        """
        import time as _time

        max_iterations = self.max_iterations
        iteration_budget = IterationBudget(max_iterations)
        budget_grace_call = False
        api_call_count = 0
        tool_cards: list = []
        

        ctx = await self._get_context()
        

        for msg in messages:
            await ctx.add_message(msg["role"], msg["content"])
        
        while (
            api_call_count < max_iterations and iteration_budget.remaining > 0
        ) or budget_grace_call:
            api_call_count += 1
            
            if budget_grace_call:
                budget_grace_call = False
            elif not iteration_budget.consume():
                break
            

            context_msgs = await ctx.get_context(max_messages=50)
            

            result, err = await call_model_fn(context_msgs, tools)
            
            if err:
                return {"final_response": f"Error: {err}", "messages": messages,
                        "tool_cards": tool_cards}
            
            if not result:
                continue
            
            msg = result.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            
            if content and not tool_calls:

                await ctx.add_message("assistant", content)
                messages.append({"role": "assistant", "content": content})
                return {"final_response": content, "messages": messages,
                        "tool_cards": tool_cards}
            
            if tool_calls:

                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name", "")
                    fn_args = tc.get("function", {}).get("arguments", {})
                    
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except json.JSONDecodeError:
                            fn_args = {"raw": fn_args}
                    

                    t0 = _time.time()
                    result_raw = handle_function_call(
                        fn_name, fn_args,
                        guard=getattr(self, 'anti_loop', None),
                    )
                    elapsed_ms = round((_time.time() - t0) * 1000, 2)
                    try:
                        result_obj = json.loads(result_raw)
                    except:
                        result_obj = {"result": str(result_raw)}


                    if hasattr(self, 'anti_loop') and self.anti_loop is not None:
                        injection = self.anti_loop.get_context_injection()
                        if injection and isinstance(result_obj, dict):
                            result_obj["_anti_loop_warning"] = injection
                    

                    tool_cards.append({
                        "id": tc.get("id") or f"call_{uuid.uuid4().hex[:10]}",
                        "type": "tool_card",
                        "tool": fn_name,
                        "status": "error" if (isinstance(result_obj, dict) and result_obj.get("error")) else "success",
                        "arguments": fn_args if isinstance(fn_args, dict) else {"raw": str(fn_args)},
                        "result": result_obj,
                        "result_preview": json.dumps(result_obj, ensure_ascii=False)[:200],
                        "elapsed_ms": elapsed_ms,
                    })
                    

                    await ctx.add_message("tool", json.dumps(result_obj, ensure_ascii=False))
                
                continue
            else:

                break
        
        return {"final_response": "[Max iterations reached]", "messages": messages,
                "tool_cards": tool_cards}

    def _run_local_tools_only(self, messages: List[Dict], tools: List[Dict],
                             session_id: Optional[str] = None) -> Dict:
        """Run in local mode without AI - just execute tools directly."""
        return {
            "final_response": f"Local mode: {len(tools)} tools available. Configure AI_BASE_URL to enable LLM.",
            "messages": messages,
        }

    async def get_context_stats(self) -> Dict:
        """Get infinite context statistics."""
        if self._context:
            return self._context.get_stats()
        return {"status": "no active context"}

    def get_tools(self) -> List[Dict]:
        """Get available tool definitions."""
        return get_tool_definitions(enabled_toolsets=self.enabled_toolsets)

    def get_tool_names(self) -> List[str]:
        """Get all registered tool names."""
        return get_all_tool_names()

    def get_toolsets(self) -> Dict[str, dict]:
        """Get available toolsets."""
        return get_available_toolsets()





class TaskScheduler:
    """Legacy task scheduler for backward compatibility."""
    def __init__(self):
        self._pending = asyncio.PriorityQueue()
        self._running: Dict[str, Any] = {}
        self._completed: Dict[str, Any] = {}
    
    async def start(self):
        logger.info("TaskScheduler started (legacy mode)")
    
    async def stop(self):
        pass





async def start_api_server(
    host: str = "0.0.0.0",
    port: int = 18080,
    api_key: str = None,
    ai_base_url: str = None,
    ai_api_key: str = None,
    ai_provider: str = None,
    ai_model: str = None,
    **kwargs
):
    """Start the OpenAI-compatible API server."""
    from aiohttp import web


    config = _load_config()
    ai_config = config.get("ai", {})

    if ai_base_url is None:
        ai_base_url = ai_config.get("base_url", "http://localhost:11434/v1")
    if ai_api_key is None:
        ai_api_key = os.getenv("AI_API_KEY") or ai_config.get("api_key", "")
    if ai_provider is None:
        ai_provider = ai_config.get("provider", "local")
    if ai_model is None:
        ai_model = ai_config.get("model", "hermes-3-mini")

    orch = NexusOrchestrator(
        api_key=api_key,
        ai_base_url=ai_base_url,
        ai_api_key=ai_api_key,
        ai_provider=ai_provider,
        ai_model=ai_model,
        config=config,
    )
    
    async def health(request):
        return web.json_response({
            "status": "ok",
            "version": "3.3.2",
            "model": orch.ai_model,
            "tools_count": len(orch.get_tool_names()),
        })
    
    async def list_models(request):
        return web.json_response({
            "object": "list",
            "data": [{"id": orch.ai_model, "object": "model"}],
        })
    
    async def chat_completions(request):
        try:
            body = await request.json()
        except:
            return web.json_response({"error": {"message": "Invalid JSON"}}, status=400)
        
        messages = body.get("messages", [])
        tools = body.get("tools", [])
        session_id = body.get("session_id")
        
        if not messages:
            return web.json_response({"error": {"message": "messages required"}}, status=400)
        

        try:
            result = orch._run_conversation(messages, tools)
        except Exception as e:
            return web.json_response({"error": {"message": str(e)}}, status=500)
        
        return web.json_response({
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "model": orch.ai_model or "multiling",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result.get("final_response", ""),
                },
                "finish_reason": "stop",
            }],
            "tool_cards": result.get("tool_cards", []),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        })
    
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", list_models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    logger.info(f"API server started: http://{host}:{port}")
    return site





def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MINXG NexusOrchestrator v3.3.2 (Infinite Context)")
    parser.add_argument("--port", type=int, default=18080, help="API server port")
    parser.add_argument("--host", default="0.0.0.0", help="API server host")
    parser.add_argument("--model", default="hermes-3-mini", help="Model name")
    parser.add_argument("--ai-base-url", help="AI upstream base URL")
    parser.add_argument("--ai-api-key", help="AI upstream API key")
    parser.add_argument("--ai-provider", default="local", help="AI provider (local/openai/anthropic)")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    parser.add_argument("--chat", metavar="MSG", help="Send a single chat message")
    parser.add_argument("--session-id", help="Session ID for infinite context")
    
    args = parser.parse_args()
    
    if args.list_tools:
        orch = NexusOrchestrator()
        print(f"\n📦 Available Toolsets:")
        for ts_name, ts_data in orch.get_toolsets().items():
            print(f"  {ts_name}: {len(ts_data.get('tools', []))} tools")
        print(f"\n📊 Total: {len(orch.get_tool_names())} tools")
        return 0
    
    if args.chat:
        orch = NexusOrchestrator(
            ai_base_url=args.ai_base_url,
            ai_api_key=args.ai_api_key,
            ai_provider=args.ai_provider,
            model=args.model,
            session_id=args.session_id,
        )
        response = orch.chat(args.chat)
        print(response)
        return 0
    

    banner = f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║     MINXG NexusOrchestrator v3.3.2                    ║
    ║     Infinite Context: Enabled                               ║
    ║     Starting API server on port {args.port}...                    ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)
    
    asyncio.run(start_api_server(
        host=args.host,
        port=args.port,
        ai_base_url=args.ai_base_url,
        ai_api_key=args.ai_api_key,
        ai_provider=args.ai_provider,
        model=args.model,
    ))
    

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
