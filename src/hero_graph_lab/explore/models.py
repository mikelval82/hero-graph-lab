from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    provider_payload: Any | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class ModelMessage:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    is_error: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[ToolSpec, ...]
    max_tokens: int = 4_096


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: ModelUsage = field(default_factory=ModelUsage)
    finish_reason: str = "stop"


class ModelClient(Protocol):
    provider: str
    model: str

    def complete(self, request: ModelRequest) -> ModelResponse: ...