"""



"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional, Any
import hashlib


class WorkspaceSlot:
    def __init__(self, name: str, max_chars: int = 4000, compress_after: int = 3):
        self.name = name
        self.max_chars = max_chars
        self.compress_after = compress_after
        self._content: str = ""
        self._update_count: int = 0

    def update(self, content: str, source: str = "ai") -> None:
        self._history.append({
            "content": self._content,
            "source": source,
            "timestamp": time.time(),
        })
        self._content = content
        self._update_count += 1
        if len(self._history) > self.compress_after:
            self._compress()

    def _compress(self) -> None:
        if len(self._history) <= 2:
            return
        old_versions = self._history[:-2]
        summary = f"[History: {len(old_versions)} prior updates from {old_versions[0].get('source','?')} to {old_versions[-1].get('source','?')}]"
        self._history = [{"content": summary, "source": "compressor", "timestamp": time.time()}] + self._history[-2:]

    def get(self) -> str:
        return self._content

    def get_full(self) -> str:
        parts = [f"=== {self.name} (current) ===", self._content]
        if self._history:
            parts.append(f"\n--- history ({len(self._history)} versions) ---")
            for h in self._history[-2:]:
                parts.append(f"[{h['source']}] {h['content'][:200]}...")
        return "\n".join(parts)


class StructuredWorkspace:
    """
    """
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"ws_{int(time.time())}_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:6]}"
        self.created_at = time.time()
        self.turn_count: int = 0
        self.tool_calls_count: int = 0

        self.slots: Dict[str, WorkspaceSlot] = {
            "objective": WorkspaceSlot("objective", max_chars=2000),
            "findings": WorkspaceSlot("findings", max_chars=6000),
            "plan": WorkspaceSlot("plan", max_chars=3000),
            "progress": WorkspaceSlot("progress", max_chars=2000),
            "scratchpad": WorkspaceSlot("scratchpad", max_chars=4000),
            "constraints": WorkspaceSlot("constraints", max_chars=1500),
        }

        self._recent_messages: List[Dict] = []
        self._max_recent: int = 6

    def set_objective(self, text: str) -> None:
        self.slots["objective"].update(text, source="user")

    def update_findings(self, text: str) -> None:
        current = self.slots["findings"].get()
        if current:
            if text in current:
                return
            new_content = current + "\n---\n" + text
        else:
            new_content = text
        self.slots["findings"].update(new_content, source="tool")

    def update_slot(self, name: str, content: str, source: str = "ai") -> None:
        if name in self.slots:
            self.slots[name].update(content, source=source)

    def add_tool_result(self, tool_name: str, result: Dict) -> None:
        self.tool_calls_count += 1
        preview = json.dumps(result, ensure_ascii=False)[:800]
        entry = f"[Tool: {tool_name}] {preview}"
        current = self.slots["findings"].get()
        if current:
            self.slots["findings"].update(current + "\n" + entry, source="tool")
        else:
            self.slots["findings"].update(entry, source="tool")

    def add_message(self, role: str, content: str) -> None:
        self._recent_messages.append({"role": role, "content": content, "timestamp": time.time()})
        if len(self._recent_messages) > self._max_recent:
            self._recent_messages = self._recent_messages[-self._max_recent:]

    def build_context(self, include_workspace: bool = True, include_recent: bool = True) -> List[Dict]:
        """
        """
        messages: List[Dict] = []

        if include_workspace:
            workspace_text = self._render_workspace()
            messages.append({
                "role": "system",
                "content": (
                    "You are an AI Agent with a structured workspace. "
                    "Use the workspace below to track progress. After each tool call, "
                    "output a brief workspace update in your response if state changed.\n\n"
                    f"{workspace_text}"
                ),
            })

        if include_recent:
            for m in self._recent_messages:
                messages.append({"role": m["role"], "content": m["content"]})

        return messages

    def _render_workspace(self) -> str:
        parts = [f"# Workspace (Session: {self.session_id}, Turns: {self.turn_count}, Tools: {self.tool_calls_count})"]
        for name in ["objective", "plan", "progress", "findings", "constraints", "scratchpad"]:
            slot = self.slots[name]
            content = slot.get().strip()
            if content:
                parts.append(f"\n## {name.upper()}\n{content}")
        return "\n".join(parts)

    def advance_turn(self) -> None:
        self.turn_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "tool_calls_count": self.tool_calls_count,
            "slots": {k: v.get() for k, v in self.slots.items()},
            "recent_messages": self._recent_messages,
        }

    def estimate_tokens(self) -> int:
        total_chars = len(self._render_workspace()) + sum(len(m["content"]) for m in self._recent_messages)
