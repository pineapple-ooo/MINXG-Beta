"""
MINXG Agent Framework — Autonomous AI agents with planning, memory, and tool use.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import json


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentThought:
    """A single thought in the agent's reasoning chain."""
    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentMemory:
    """Agent's working memory."""
    goal: str
    thoughts: List[AgentThought] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    results: List[Any] = field(default_factory=list)


class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent implementation.

    Combines reasoning traces with action execution for autonomous task completion.
    Supports tool use, self-correction, and multi-step planning.
    """

    def __init__(
        self,
        name: str = "minxg-agent",
        max_steps: int = 50,
        tools: Optional[Dict[str, Callable]] = None,
    ):
        self.name = name
        self.max_steps = max_steps
        self.tools = tools or {}
        self.state = AgentState.IDLE
        self.memory: Optional[AgentMemory] = None

    def run(self, goal: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run the agent on a goal.

        Args:
            goal: The task to accomplish.
            context: Optional initial context.

        Returns:
            Dictionary with result and execution trace.
        """
        self.state = AgentState.THINKING
        self.memory = AgentMemory(goal=goal, context=context or {})

        for step in range(self.max_steps):
            # Generate thought
            thought = self._think(step)
            self.memory.thoughts.append(thought)

            if thought.action:
                self.state = AgentState.ACTING
                observation = self._act(thought.action)
                self.memory.thoughts[-1].observation = observation

                if observation.startswith("DONE:"):
                    self.state = AgentState.DONE
                    self.memory.results.append(observation[5:].strip())
                    break
            else:
                # Final answer
                self.state = AgentState.DONE
                self.memory.results.append(thought.thought)
                break

        return {
            "goal": goal,
            "result": self.memory.results[-1] if self.memory.results else None,
            "steps": len(self.memory.thoughts),
            "trace": [t.thought for t in self.memory.thoughts],
            "state": self.state.value,
        }

    def _think(self, step: int) -> AgentThought:
        """Generate next thought based on current state."""
        # Simplified ReAct - in production, this would call an LLM
        if step == 0:
            return AgentThought(
                thought=f"I need to accomplish: {self.memory.goal}",
                action=f"search({self.memory.goal})",
            )
        return AgentThought(
            thought=f"Step {step}: Continuing based on previous observations",
            action=None,
        )

    def _act(self, action: str) -> str:
        """Execute an action using available tools."""
        # Parse action string
        if action.startswith("search("):
            query = action[7:-1]
            return f"Search results for: {query}"
        elif action in self.tools:
            return str(self.tools[action]())
        return f"Action executed: {action}"

    def add_tool(self, name: str, func: Callable) -> None:
        """Register a tool with the agent."""
        self.tools[name] = func

    def get_trace(self) -> List[Dict]:
        """Get the full execution trace."""
        if not self.memory:
            return []
        return [
            {
                "thought": t.thought,
                "action": t.action,
                "observation": t.observation,
            }
            for t in self.memory.thoughts
        ]


class PlanningAgent:
    """
    Task decomposition and planning agent.

    Breaks complex goals into subtasks and executes them in order.
    """

    def __init__(self, max_parallel: int = 3):
        self.max_parallel = max_parallel
        self.plan: List[Dict] = []
        self.results: List[Any] = []

    def plan_task(self, goal: str) -> List[Dict]:
        """Decompose a goal into subtasks."""
        # Simplified planning - in production, use LLM for decomposition
        self.plan = [
            {"id": 1, "task": f"Understand: {goal}", "status": "pending", "depends_on": []},
            {"id": 2, "task": f"Research: {goal}", "status": "pending", "depends_on": [1]},
            {"id": 3, "task": f"Execute: {goal}", "status": "pending", "depends_on": [2]},
            {"id": 4, "task": f"Verify: {goal}", "status": "pending", "depends_on": [3]},
        ]
        return self.plan

    def execute_plan(self) -> List[Any]:
        """Execute the plan in dependency order."""
        completed = set()
        results = []

        while len(completed) < len(self.plan):
            for task in self.plan:
                if task["id"] in completed:
                    continue
                if all(d in completed for d in task["depends_on"]):
                    # Execute task
                    task["status"] = "completed"
                    completed.add(task["id"])
                    results.append({"task_id": task["id"], "result": f"Completed: {task['task']}"})

        self.results = results
        return results


class MultiAgentSystem:
    """
    Multi-agent orchestration system.

    Coordinates multiple specialized agents for complex tasks.
    """

    def __init__(self):
        self.agents: Dict[str, ReActAgent] = {}
        self.coordinator = None

    def add_agent(self, name: str, specialization: str) -> ReActAgent:
        """Add a specialized agent."""
        agent = ReActAgent(name=name)
        agent.memory = AgentMemory(goal=f"Specialized in: {specialization}")
        self.agents[name] = agent
        return agent

    def delegate(self, task: str, agent_name: str) -> Dict[str, Any]:
        """Delegate a task to a specific agent."""
        if agent_name not in self.agents:
            return {"error": f"Agent {agent_name} not found"}
        return self.agents[agent_name].run(task)

    def broadcast(self, task: str) -> Dict[str, Dict]:
        """Broadcast a task to all agents."""
        results = {}
        for name, agent in self.agents.items():
            results[name] = agent.run(f"{name}: {task}")
        return results

    def get_team_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            name: {
                "state": agent.state.value,
                "memory_size": len(agent.memory.thoughts) if agent.memory else 0,
            }
            for name, agent in self.agents.items()
        }


class SelfReflectiveAgent(ReActAgent):
    """
    Agent with self-reflection capabilities.

    Reviews its own reasoning and corrects mistakes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reflection_history: List[Dict] = []

    def reflect(self) -> Dict[str, Any]:
        """Review past actions and identify improvements."""
        if not self.memory:
            return {"reflections": []}

        reflections = []
        for i, thought in enumerate(self.memory.thoughts):
            if thought.observation and "error" in thought.observation.lower():
                reflections.append({
                    "step": i,
                    "issue": thought.observation,
                    "suggestion": f"Consider alternative approach at step {i}",
                })

        self.reflection_history.append({
            "goal": self.memory.goal,
            "reflections": reflections,
            "timestamp": time.time(),
        })

        return {"reflections": reflections, "total": len(reflections)}

    def run_with_reflection(self, goal: str) -> Dict[str, Any]:
        """Run agent and reflect on performance."""
        result = self.run(goal)
        reflection = self.reflect()
        return {
            **result,
            "reflection": reflection,
        }
