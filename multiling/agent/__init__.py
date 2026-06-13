"""
MINXG Agent Framework — 自主智能体系统
=======================================
提供多智能体协作、角色定义、记忆管理、工具使用、反思机制等完整能力。

核心概念:
  - Agent: 具备角色、记忆、工具使用能力的自主实体
  - MultiAgentSession: 多智能体协作会话
  - Role: 智能体角色模板（系统级定义）
  - Capability: 智能体能力声明与匹配
""""

from .agent import Agent, AgentConfig
from .session import MultiAgentSession, AgentMessage
from .role import Role, RoleRegistry
from .capability import Capability, CapabilityRegistry
from .reflection import ReflectionEngine

__all__ = [
    "Agent", "AgentConfig",
    "MultiAgentSession", "AgentMessage",
    "Role", "RoleRegistry",
    "Capability", "CapabilityRegistry",
    "ReflectionEngine",
]