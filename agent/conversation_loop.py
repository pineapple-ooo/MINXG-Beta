"""
Conversation Loop - Core agent conversation orchestration.

This module implements the main agent loop that handles:
- Tool-calling iterations with budget management
- Interrupt handling for user feedback
- Grace call mechanism for final responses
- Error recovery and retry logic
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from agent.iteration_budget import IterationBudget

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single conversation turn."""
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class ConversationLoop:
    """Manages the agent conversation loop with iteration budget and interrupt handling."""

    def __init__(
        self,
        max_iterations: int = 90,
        tool_delay: float = 1.0,
        quiet_mode: bool = False,
    ):
        self.max_iterations = max_iterations
        self.tool_delay = tool_delay
        self.quiet_mode = quiet_mode
        

        self.iteration_budget = IterationBudget(max_iterations)
        self._budget_grace_call = False
        

        self._interrupt_requested = False
        self._pending_steer: Optional[str] = None
        

        self.step_callback: Optional[Callable] = None
        self.thinking_callback: Optional[Callable] = None
        

        self._api_call_count = 0
        self._current_tool: Optional[str] = None
        self._last_activity_ts = time.time()
        self._last_activity_desc = ""

    @property
    def api_call_count(self) -> int:
        return self._api_call_count

    def request_interrupt(self) -> None:
        """Request interrupt at next opportunity."""
        self._interrupt_requested = True
        logger.debug("Interrupt requested")

    def drain_pending_steer(self) -> Optional[str]:
        """Get and clear pending steer text."""
        steer = self._pending_steer
        self._pending_steer = None
        return steer

    def touch_activity(self, desc: str) -> None:
        """Update last activity timestamp."""
        self._last_activity_ts = time.time()
        self._last_activity_desc = desc

    def get_activity_summary(self) -> dict:
        """Get current activity summary for diagnostics."""
        return {
            "last_activity_ts": self._last_activity_ts,
            "last_activity_desc": self._last_activity_desc,
            "seconds_since_activity": round(time.time() - self._last_activity_ts, 1),
            "api_call_count": self._api_call_count,
            "max_iterations": self.max_iterations,
            "budget_used": self.iteration_budget.used,
            "budget_max": self.iteration_budget.max_total,
        }

    def run_turn(
        self,
        messages: List[Dict],
        tools: List[Dict],
        call_model_fn: Callable,
        execute_tool_fn: Callable,
        anti_loop_guard=None,
    ) -> Dict[str, Any]:
        """
        Run a conversation turn with tool calling loop.

        Args:
            messages: Conversation messages
            tools: Available tool schemas
            call_model_fn: Function to call the LLM
            execute_tool_fn: Function to execute a tool
            anti_loop_guard: Optional AntiLoopGuard instance for loop detection

        Returns:
            Dict with final_response, messages, and turn metadata
        """
        api_call_count = 0
        turn_exit_reason = "unknown"
        interrupt_during_loop = False


        if not messages:
            messages = []

        self.iteration_budget = IterationBudget(self.max_iterations)

        while (
            api_call_count < self.max_iterations
            and self.iteration_budget.remaining > 0
        ) or self._budget_grace_call:

            if self._interrupt_requested:
                interrupt_during_loop = True
                turn_exit_reason = "interrupted_by_user"
                if not self.quiet_mode:
                    print("\n⚡ Breaking out of tool loop due to interrupt...")
                break

            api_call_count += 1
            self._api_call_count = api_call_count
            self.touch_activity(f"starting API call #{api_call_count}")


            if self._budget_grace_call:
                self._budget_grace_call = False
            elif not self.iteration_budget.consume():
                turn_exit_reason = "budget_exhausted"
                if not self.quiet_mode:
                    print(f"\n⚠️  Iteration budget exhausted ({self.iteration_budget.used}/{self.iteration_budget.max_total} iterations used)")
                break


            if self.step_callback is not None:
                try:
                    self.step_callback(api_call_count, [])
                except Exception as e:
                    logger.debug("step_callback error (iteration %s): %s", api_call_count, e)


            steer = self.drain_pending_steer()


            request_messages = list(messages)
            if steer:

                for i in range(len(request_messages) - 1, -1, -1):
                    if request_messages[i].get("role") == "tool":
                        request_messages[i]["content"] = (
                            request_messages[i].get("content", "") + f"\n\nUser guidance: {steer}"
                        )
                        break

            try:

                response = call_model_fn(request_messages, tools)


                if response.get("tool_calls"):
                    assistant_message = {
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": response["tool_calls"],
                    }
                    messages.append(assistant_message)


                    for tool_call in response["tool_calls"]:
                        fn_name = tool_call.get("function", {}).get("name", "")
                        fn_args = tool_call.get("function", {}).get("arguments", {})


                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except json.JSONDecodeError:
                                fn_args = {"raw": fn_args}

                        self._current_tool = fn_name
                        self.touch_activity(f"executing {fn_name}")


                        if self.tool_delay > 0 and api_call_count > 1:
                            time.sleep(self.tool_delay)


                        if anti_loop_guard is not None:
                            allowed, reason = anti_loop_guard.pre_check(
                                fn_name, fn_args
                            )
                            if not allowed and reason != "cached":
                                result = json.dumps({
                                    "error": f"Tool call blocked by anti-loop: {reason}",
                                    "blocked_at_iteration": api_call_count,
                                })
                                tool_message = {
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id"),
                                    "content": result,
                                }
                                messages.append(tool_message)
                                continue


                        result = execute_tool_fn(fn_name, fn_args)


                        if anti_loop_guard is not None:
                            success = not (isinstance(result, str) and '"error"' in result[:50])
                            anti_loop_guard.record(
                                fn_name, fn_args, result,
                                success=success,
                            )


                        if isinstance(result, str):
                            try:
                                result = json.loads(result)
                            except json.JSONDecodeError:
                                pass

                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "content": json.dumps(result) if isinstance(result, dict) else str(result),
                        }
                        messages.append(tool_message)

                    continue

                elif response.get("content"):

                    assistant_message = {
                        "role": "assistant",
                        "content": response["content"],
                    }
                    messages.append(assistant_message)
                    turn_exit_reason = "completed"
                    break

                else:

                    turn_exit_reason = "empty_response"
                    break

            except Exception as e:
                logger.exception("Error in API call #%d", api_call_count)
                error_msg = f"Error during API call #{api_call_count}: {str(e)}"


                if self.iteration_budget.remaining <= 5:
                    turn_exit_reason = "error_near_max_iterations"
                else:
                    turn_exit_reason = f"error: {e}"


                messages.append({
                    "role": "tool",
                    "content": json.dumps({"error": error_msg}),
                })
                break


        if turn_exit_reason == "unknown":
            turn_exit_reason = "max_iterations_reached"

        if turn_exit_reason in ("budget_exhausted", "max_iterations_reached", "error_near_max_iterations"):

            if api_call_count > 0 and not interrupt_during_loop:
                self._budget_grace_call = True


        final_response = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_response = msg["content"]
                break

        return {
            "final_response": final_response,
            "messages": messages,
            "turn_exit_reason": turn_exit_reason,
            "api_call_count": api_call_count,
            "iteration_budget_used": self.iteration_budget.used,
            "interrupted": interrupt_during_loop,
        }

    def refund_iteration(self) -> None:
        """Refund an iteration (e.g., for execute_code turns)."""
        self.iteration_budget.refund()

    def get_turn_exit_message(self, reason: str) -> str:
        """Get user-facing message for turn exit reason."""
        prefix = "\n⚠️  "
        
        if reason == "interrupted_by_user":
            return (
                prefix
                + "the request was interrupted. Send `continue` to retry."
            )
        if reason == "budget_exhausted":
            return (
                prefix
                + "the per-turn iteration/cost budget was exhausted before a "
                "final answer. Send `continue` to keep going."
            )
        if reason == "max_iterations_reached" or reason.startswith("max_iterations"):
            return (
                prefix
                + "the maximum tool-iteration limit was reached before a "
                "final answer. Send `continue` to keep going, or raise "
                "`max_iterations`."
            )
        if reason.startswith("error"):
            return (
                prefix
                + "an error occurred. Check the tool output above, then send `continue`."
            )
        if reason == "empty_response":
            return (
                prefix
                + "received an empty response. Send `continue` to retry."
            )
        return ""


__all__ = ["ConversationLoop", "ConversationTurn"]
