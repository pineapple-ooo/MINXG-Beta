"""
MINXG Function Calling — Structured output and tool calling framework.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable, Type, get_type_hints
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, create_model
import json
import inspect


@dataclass
class FunctionSchema:
    """Schema for a function definition."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable] = None


class FunctionRegistry:
    """Registry for callable functions."""

    def __init__(self):
        self.functions: Dict[str, FunctionSchema] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable:
        """Decorator to register a function."""
        def decorator(func: Callable) -> Callable:
            func_name = name or func.__name__
            func_desc = description or (func.__doc__ or "").strip()

            # Extract parameters from type hints
            hints = get_type_hints(func)
            sig = inspect.signature(func)
            parameters = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            for param_name, param in sig.parameters.items():
                if param_name == "return":
                    continue
                param_type = hints.get(param_name, str)
                json_type = self._python_type_to_json(param_type)
                parameters["properties"][param_name] = {
                    "type": json_type,
                    "description": f"Parameter {param_name}",
                }
                if param.default is inspect.Parameter.empty:
                    parameters["required"].append(param_name)

            self.functions[func_name] = FunctionSchema(
                name=func_name,
                description=func_desc,
                parameters=parameters,
                handler=func,
            )
            return func
        return decorator

    def get(self, name: str) -> Optional[FunctionSchema]:
        """Get a function by name."""
        return self.functions.get(name)

    def list_all(self) -> List[Dict[str, str]]:
        """List all registered functions."""
        return [
            {"name": fs.name, "description": fs.description}
            for fs in self.functions.values()
        ]

    def to_openai_format(self) -> List[Dict[str, Any]]:
        """Convert to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": fs.name,
                    "description": fs.description,
                    "parameters": fs.parameters,
                },
            }
            for fs in self.functions.values()
        ]

    def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a function by name with arguments."""
        func = self.functions.get(name)
        if func is None:
            return {"error": f"Function {name} not found"}
        if func.handler is None:
            return {"error": f"Function {name} has no handler"}
        try:
            result = func.handler(**arguments)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _python_type_to_json(python_type: type) -> str:
        """Convert Python type to JSON schema type."""
        if python_type == int:
            return "integer"
        elif python_type == float:
            return "number"
        elif python_type == bool:
            return "boolean"
        elif python_type == list:
            return "array"
        elif python_type == dict:
            return "object"
        return "string"


class StructuredOutput:
    """
    Generate structured output from LLM responses.

    Uses Pydantic models to enforce output schemas.
    """

    @staticmethod
    def from_json(json_str: str, model_class: Type[BaseModel]) -> BaseModel:
        """Parse JSON string into a Pydantic model."""
        data = json.loads(json_str)
        return model_class(**data)

    @staticmethod
    def from_text(text: str, model_class: Type[BaseModel]) -> BaseModel:
        """Extract structured data from text."""
        # Try to find JSON in text
        import re
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            return StructuredOutput.from_json(json_match.group(), model_class)
        raise ValueError("No JSON found in text")

    @staticmethod
    def create_model(
        name: str,
        fields: Dict[str, tuple],
    ) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model.

        Args:
            name: Model name.
            fields: Dict of {field_name: (type, default_value)}.

        Returns:
            Pydantic model class.
        """
        return create_model(name, **fields)

    @staticmethod
    def to_json_schema(model_class: Type[BaseModel]) -> Dict[str, Any]:
        """Get JSON schema from a Pydantic model."""
        return model_class.model_json_schema()


class ToolCallingAgent:
    """
    Agent that can call tools/functions.

    Integrates with LLM providers for function calling.
    """

    def __init__(self, registry: Optional[FunctionRegistry] = None):
        self.registry = registry or FunctionRegistry()
        self.call_history: List[Dict] = []

    def add_tool(self, func: Callable, name: Optional[str] = None) -> None:
        """Add a tool function."""
        @self.registry.register(name=name)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper(*args, **kwargs)  # Register it

    def process_llm_response(
        self,
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process an LLM response that may contain tool calls.

        Args:
            response: LLM response dict.

        Returns:
            Result of tool execution or text response.
        """
        message = response.get("choices", [{}])[0].get("message", {})

        if "tool_calls" in message:
            results = []
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = json.loads(tool_call["function"]["arguments"])

                result = self.registry.call(func_name, func_args)
                results.append({
                    "tool": func_name,
                    "arguments": func_args,
                    "result": result,
                })
                self.call_history.append(results[-1])

            return {"tool_calls": results}

        return {"text": message.get("content", "")}

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        max_turns: int = 10,
    ) -> Dict[str, Any]:
        """
        Chat loop with automatic tool calling.

        Args:
            messages: Conversation history.
            max_turns: Maximum conversation turns.

        Returns:
            Final response.
        """
        for turn in range(max_turns):
            # In production, this would call an LLM with tools
            # For now, simulate the loop
            pass

        return {
            "messages": messages,
            "turns": max_turns,
            "tool_calls": self.call_history,
        }


# Common function schemas for popular use cases
COMMON_SCHEMAS = {
    "calculator": {
        "name": "calculator",
        "description": "Perform mathematical calculations",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate"},
            },
            "required": ["expression"],
        },
    },
    "search": {
        "name": "search",
        "description": "Search for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        },
    },
    "send_email": {
        "name": "send_email",
        "description": "Send an email",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    "get_weather": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
            },
            "required": ["location"],
        },
    },
    "create_calendar_event": {
        "name": "create_calendar_event",
        "description": "Create a calendar event",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "Start time"},
                "end": {"type": "string", "description": "End time"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start", "end"],
        },
    },
}
