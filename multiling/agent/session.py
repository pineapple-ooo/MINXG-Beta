"""
session.py — 多智能体协作会话

MultiAgentSession 管理多个 Agent 之间的协作对话，
支持角色分配、消息路由、冲突检测和共识达成。
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .agent import Agent


@dataclass
class AgentMessage:
    """智能体间通信消息"""
    sender: str           
    receiver: str         
    content: str          
    msg_type: str = "text"  
    tool_name: str = ""   
    tool_args: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    msg_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:10]}")

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id, "sender": self.sender,
            "receiver": self.receiver, "type": self.msg_type,
            "content": self.content, "tool_name": self.tool_name,
            "tool_args": self.tool_args, "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class MultiAgentSession:
    """
    多智能体协作会话管理器

    功能:
    - 管理多个 Agent 的生命周期
    - 消息路由（定向/广播）
    - 协作策略（顺序/并行/投票）
    - 冲突检测与解决
    - 会话状态持久化
    """

    def __init__(self, session_id: str = None, max_rounds: int = 100):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.max_rounds = max_rounds
        self._agents: Dict[str, Agent] = {}
        self._messages: List[AgentMessage] = []
        self._round = 0
        self._created_at = time.time()
        self._status = "initialized"  
        self._collaboration_log: List[Dict] = []

    def register_agent(self, agent: Agent, role: str = None) -> str:
        """注册 Agent 到会话，可选指定角色"""
        if role:
            agent.config.role = role
        self._agents[agent.id] = agent
        agent.add_message("system", f"你已加入协作会话 {self.session_id}，角色: {agent.config.role}")
        return agent.id

    def remove_agent(self, agent_id: str):
        """从会话中移除 Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, Agent]:
        return self._agents.copy()

    def send_message(self, sender_id: str, receiver_id: str,
                     content: str, msg_type: str = "text",
                     tool_name: str = "", tool_args: Dict = None) -> AgentMessage:
        """发送消息（定向或广播）"""
        msg = AgentMessage(
            sender=sender_id,
            receiver=receiver_id if receiver_id else "",
            content=content,
            msg_type=msg_type,
            tool_name=tool_name,
            tool_args=tool_args or {},
        )
        self._messages.append(msg)

        
        if receiver_id and receiver_id in self._agents:
            self._agents[receiver_id].add_message("user",
                f"[来自 {sender_id}]: {content}",
                meta={"msg_id": msg.msg_id, "sender": sender_id}
            )
        elif not receiver_id:
            
            for aid, agent in self._agents.items():
                if aid != sender_id:
                    agent.add_message("user",
                        f"[来自 {sender_id}]: {content}",
                        meta={"msg_id": msg.msg_id, "sender": sender_id, "broadcast": True}
                    )
        return msg

    async def run_round(self, strategy: str = "sequential") -> Dict:
        """
        执行一轮协作

        策略:
          - sequential: 按注册顺序依次执行
          - parallel: 所有 Agent 并行思考
          - voting: 收集所有意见后投票
        """
        self._round += 1
        if self._round > self.max_rounds:
            self._status = "completed"
            return {"status": "max_rounds_reached", "round": self._round}

        round_log = {"round": self._round, "strategy": strategy, "actions": []}

        if strategy == "sequential":
            for agent_id, agent in self._agents.items():
                action = await self._execute_agent_turn(agent)
                round_log["actions"].append(action)

        elif strategy == "parallel":
            tasks = [self._execute_agent_turn(a) for a in self._agents.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    round_log["actions"].append({"error": str(r)})
                else:
                    round_log["actions"].append(r)

        elif strategy == "voting":
            proposals = []
            for agent_id, agent in self._agents.items():
                action = await self._execute_agent_turn(agent)
                proposals.append({"agent_id": agent_id, **action})
            
            consensus = self._resolve_by_voting(proposals)
            round_log["actions"] = proposals
            round_log["consensus"] = consensus

        self._collaboration_log.append(round_log)
        return round_log

    async def _execute_agent_turn(self, agent: Agent) -> Dict:
        """执行单个 Agent 的回合"""
        status = agent.get_status()
        
        messages = agent.build_messages_for_llm(limit=20)
        
        
        return {
            "agent_id": agent.id,
            "agent_name": agent.config.name,
            "role": agent.config.role,
            "message_count": len(agent.get_messages()),
            "memory_stats": status["memory"],
        }

    def _resolve_by_voting(self, proposals: List[Dict]) -> Optional[Dict]:
        """通过投票达成共识（简化版）"""
        if not proposals:
            return None
        
        return {
            "method": "majority_vote",
            "participants": len(proposals),
            "selected": proposals[0],  
        }

    def get_collaboration_log(self) -> List[Dict]:
        """获取完整协作日志"""
        return self._collaboration_log.copy()

    def get_message_history(self, limit: int = 50) -> List[Dict]:
        """获取消息历史"""
        return [m.to_dict() for m in self._messages[-limit:]]

    def get_summary(self) -> Dict:
        """获取会话摘要"""
        return {
            "session_id": self.session_id,
            "status": self._status,
            "round": self._round,
            "agent_count": len(self._agents),
            "message_count": len(self._messages),
            "agents": {aid: a.config.name for aid, a in self._agents.items()},
            "uptime_sec": round(time.time() - self._created_at, 2),
        }

    def reset(self):
        """重置会话"""
        self._messages.clear()
        self._round = 0
        self._collaboration_log.clear()
        self._status = "initialized"
        for agent in self._agents.values():
            agent.reset()