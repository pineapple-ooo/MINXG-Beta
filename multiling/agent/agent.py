"""
agent.py — 自主智能体核心

Agent 是具备角色感知、记忆管理、工具调用、反思能力的自主实体。
每个 Agent 拥有独立的上下文、记忆层和工具集。
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("minxg.agent")


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    role: str = "assistant"
    system_prompt: str = ""
    model: str = "hermes-3-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    max_iterations: int = 50
    auto_tool_call: bool = True
    reflection_enabled: bool = True
    memory_capacity: int = 5000
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "role": self.role,
            "model": self.model, "temperature": self.temperature,
            "max_tokens": self.max_tokens, "top_p": self.top_p,
            "max_iterations": self.max_iterations,
            "auto_tool_call": self.auto_tool_call,
            "reflection_enabled": self.reflection_enabled,
            "memory_capacity": self.memory_capacity,
            "metadata": self.metadata,
        }


class AgentMemory:
    """Agent 专用记忆管理（事件记忆 + 语义记忆 + 工作记忆）"""

    def __init__(self, capacity: int = 5000):
        self.capacity = capacity
        self._episodic: List[Dict] = []       # 原始对话记录
        self._semantic: Dict[str, Dict] = {}  # 提炼的知识/事实
        self._working: List[Dict] = []        # 当前会话工作记忆
        self._stats = {"adds": 0, "compressions": 0, "queries": 0}

    def add_event(self, role: str, content: str,
                  timestamp: float = None, meta: Dict = None) -> str:
        """添加事件到事件记忆"""
        eid = f"evt_{uuid.uuid4().hex[:10]}"
        event = {
            "id": eid, "role": role, "content": content,
            "timestamp": timestamp or time.time(),
            "meta": meta or {},
        }
        self._episodic.append(event)
        self._working.append(event)
        self._stats["adds"] += 1
        # 容量管理
        if len(self._episodic) > self.capacity:
            self._compress_old()
        if len(self._working) > 100:
            self._working = self._working[-80:]
        return eid

    def add_fact(self, key: str, content: str, importance: float = 1.0):
        """添加语义事实"""
        self._semantic[key] = {
            "content": content, "importance": importance,
            "created": time.time(), "accessed": time.time(),
        }

    def query(self, text: str, limit: int = 10) -> List[Dict]:
        """跨所有记忆层搜索相关内容"""
        self._stats["queries"] += 1
        results = []
        q = text.lower()
        # 搜索语义记忆
        for key, fact in self._semantic.items():
            score = 0.0
            if q in key.lower():
                score += 3.0
            if q in fact["content"].lower():
                score += 2.0
            if score > 0:
                results.append({
                    "source": "semantic", "key": key,
                    "content": fact["content"],
                    "score": score * fact["importance"],
                })
        # 搜索事件记忆（最近优先）
        for evt in reversed(self._episodic):
            if q in evt["content"].lower():
                results.append({
                    "source": "episodic", "id": evt["id"],
                    "content": evt["content"][:200],
                    "score": 1.0,
                })
                if len(results) >= limit:
                    break
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _compress_old(self):
        """压缩旧事件 → 语义事实"""
        to_compress = self._episodic[: len(self._episodic) // 2]
        if not to_compress:
            return
        # 简单的抽取式压缩：保留关键信息
        key = f"summary_{int(time.time())}"
        content_parts = [e["content"] for e in to_compress if len(e["content"]) > 20]
        if content_parts:
            summary = f"压缩摘要({len(content_parts)}条): " + "; ".join(
                c[:80] for c in content_parts[-10:]
            )
            self._semantic[key] = {
                "content": summary, "importance": 0.5,
                "created": time.time(), "accessed": time.time(),
            }
        self._episodic = self._episodic[len(self._episodic) // 2:]
        self._stats["compressions"] += 1

    def get_working_context(self, max_items: int = 20) -> List[Dict]:
        """获取工作记忆上下文"""
        return self._working[-max_items:]

    def get_stats(self) -> Dict:
        return {
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "working_count": len(self._working),
            **self._stats,
        }


class ToolRegistry:
    """Agent 级别的工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Dict] = {}

    def register(self, name: str, description: str,
                 parameters: Dict, handler: Callable):
        """注册一个工具"""
        self._tools[name] = {
            "name": name, "description": description,
            "parameters": parameters, "handler": handler,
        }

    def get_schema(self, name: str) -> Optional[Dict]:
        t = self._tools.get(name)
        if t:
            return {k: v for k, v in t.items() if k != "handler"}
        return None

    def get_all_schemas(self) -> List[Dict]:
        return [{k: v for k, v in t.items() if k != "handler"}
                for t in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, args: Dict) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]["handler"](**args)


class Agent:
    """
    自主智能体核心类

    能力:
    - 角色化对话（system prompt + persona）
    - 多层记忆（事件/语义/工作）
    - 工具自主调用
    - 自我反思与纠错
    - 多轮上下文管理
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.id = f"agent_{uuid.uuid4().hex[:12]}"
        self.memory = AgentMemory(config.memory_capacity)
        self.tool_registry = ToolRegistry()
        self._conversation_history: List[Dict] = []
        self._total_calls = 0
        self._total_errors = 0
        self._created_at = time.time()
        self._last_active = time.time()

    def register_tool(self, name: str, description: str,
                      parameters: Dict, handler: Callable):
        """注册工具到 Agent"""
        self.tool_registry.register(name, description, parameters, handler)

    def register_tools_from_dict(self, tools: List[Dict]):
        """从字典列表批量注册工具"""
        for t in tools:
            self.tool_registry.register(
                t["name"], t.get("description", ""),
                t.get("parameters", {}), t["handler"]
            )

    def add_message(self, role: str, content: str, meta: Dict = None):
        """添加消息到对话历史"""
        msg = {"role": role, "content": content,
               "timestamp": time.time(), "meta": meta or {}}
        self._conversation_history.append(msg)
        self.memory.add_event(role, content, meta=meta)
        self._last_active = time.time()

    def get_messages(self, limit: int = 20) -> List[Dict]:
        """获取最近的消息"""
        return self._conversation_history[-limit:]

    def build_system_prompt(self) -> str:
        """构建完整的系统提示词"""
        prompt = self.config.system_prompt or f"You are {self.config.role}."
        # 注入记忆中的关键事实
        recent_facts = self.memory.query("recent context", limit=5)
        if recent_facts:
            fact_text = "\n".join(f"- {f['content']}" for f in recent_facts)
            prompt += f"\n\n记住以下关键信息:\n{fact_text}"
        return prompt

    def build_messages_for_llm(self, limit: int = 30) -> List[Dict]:
        """构建发送给 LLM 的消息列表"""
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        for msg in self._conversation_history[-limit:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        return messages

    def reflect(self, last_action: str, last_result: str) -> Optional[str]:
        """
        反思机制：分析上一次行动的结果，决定是否需要修正
        返回修正建议或 None
        """
        if not self.config.reflection_enabled:
            return None
        # 简单的规则引擎反思
        if "error" in last_result.lower():
            return f"上次操作失败: {last_result[:200]}，考虑替代方案。"
        if len(last_result) < 10:
            return f"结果可能不完整（仅{len(last_result)}字符），请确认或重试。"
        return None

    def get_status(self) -> Dict:
        """获取 Agent 状态"""
        return {
            "id": self.id, "name": self.config.name,
            "role": self.config.role,
            "uptime_sec": round(time.time() - self._created_at, 2),
            "messages_count": len(self._conversation_history),
            "tools_count": len(self.tool_registry._tools),
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "memory": self.memory.get_stats(),
            "last_active": self._last_active,
        }

    def reset(self):
        """重置 Agent 状态（保留配置和工具）"""
        self._conversation_history.clear()
        self.memory = AgentMemory(self.config.memory_capacity)
        self._total_calls = 0
        self._total_errors = 0
        self._created_at = time.time()

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "status": self.get_status(),
            "tools": [t for t in self.tool_registry.get_all_schemas()],
        }