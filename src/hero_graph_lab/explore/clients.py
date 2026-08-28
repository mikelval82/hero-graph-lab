from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from hero_graph_lab.explore.models import (
    ModelClient,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
)


class FakeModelClient:
    provider = "fake"
    model = "deterministic-explorer"

    def __init__(self, responses: Iterable[ModelResponse] = ()) -> None:
        self._responses = deque(responses)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self._responses:
            return self._responses.popleft()
        return ModelResponse(
            text=(
                "Explore Assistant funciona con el proveedor determinista. "
                "Configura --explore-provider anthropic, openai, deepseek o gemini "
                "para obtener respuestas del modelo."
            )
        )


class AnthropicModelClient:
    provider = "anthropic"

    def __init__(self, model: str) -> None:
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as error:
            raise RuntimeError("Install hero-graph-lab[anthropic] to use the Anthropic provider.") from error
        self.model = model
        self._client = Anthropic()

    def complete(self, request: ModelRequest) -> ModelResponse:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=self._messages(request.messages),
            tools=[
                {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
                for tool in request.tools
            ],
        )
        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        usage = getattr(response, "usage", None)
        return ModelResponse(
            text="\n".join(texts).strip(),
            tool_calls=tuple(calls),
            usage=ModelUsage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            ),
            finish_reason=str(getattr(response, "stop_reason", "stop") or "stop"),
        )

    @staticmethod
    def _messages(messages: tuple[ModelMessage, ...]) -> list[dict]:
        output: list[dict] = []
        for message in messages:
            if message.role == "assistant" and message.tool_calls:
                content: list[dict] = []
                if message.content:
                    content.append({"type": "text", "text": message.content})
                content.extend(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                    for call in message.tool_calls
                )
                output.append({"role": "assistant", "content": content})
            elif message.role == "tool":
                block: dict = {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
                if message.is_error:
                    block["is_error"] = True
                output.append({"role": "user", "content": [block]})
            else:
                output.append({"role": message.role, "content": message.content})
        return output


class OpenAIModelClient:
    provider = "openai"
    max_tokens_parameter = "max_completion_tokens"

    def __init__(self, model: str, *, client: Any | None = None) -> None:
        if client is None:
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as error:
                raise RuntimeError("Install hero-graph-lab[openai] to use the OpenAI provider.") from error
            client = OpenAI()
        self.model = model
        self._client = client

    def complete(self, request: ModelRequest) -> ModelResponse:
        parameters: dict[str, Any] = {
            "model": self.model,
            self.max_tokens_parameter: request.max_tokens,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *self._messages(request.messages),
            ],
        }
        if request.tools:
            parameters["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
        response = self._client.chat.completions.create(**parameters)
        choice = response.choices[0]
        message = choice.message
        calls = tuple(
            ToolCall(call.id, call.function.name, json.loads(call.function.arguments or "{}"))
            for call in (message.tool_calls or [])
        )
        usage = response.usage
        return ModelResponse(
            text=message.content or "",
            tool_calls=calls,
            usage=ModelUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            ),
            finish_reason=choice.finish_reason or "stop",
        )

    @staticmethod
    def _messages(messages: tuple[ModelMessage, ...]) -> list[dict]:
        output: list[dict] = []
        for message in messages:
            if message.role == "assistant":
                entry: dict = {"role": "assistant", "content": message.content or None}
                if message.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                        }
                        for call in message.tool_calls
                    ]
                output.append(entry)
            elif message.role == "tool":
                output.append(
                    {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
                )
            else:
                output.append({"role": "user", "content": message.content})
        return output


class DeepSeekModelClient(OpenAIModelClient):
    provider = "deepseek"
    max_tokens_parameter = "max_tokens"

    def __init__(self, model: str, *, client: Any | None = None) -> None:
        load_project_env()
        if client is None:
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as error:
                raise RuntimeError("Install hero-graph-lab[deepseek] to use DeepSeek.") from error
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is required to use the DeepSeek provider.")
            client = OpenAI(
                api_key=api_key,
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
        self.model = model
        self._client = client

    def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            return super().complete(request)
        except Exception as error:
            raise RuntimeError(f"DeepSeek request failed: {error}") from error


def load_project_env(project_root: str | Path | None = None) -> None:
    if project_root is not None:
        candidates = [Path(project_root)]
    else:
        current = Path(__file__).resolve()
        candidates = [current.parent, *current.parents]

    for base in candidates:
        env_path = base / ".env"
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


class GeminiModelClient:
    provider = "gemini"

    def __init__(self, model: str, *, client: Any | None = None, types_module: Any | None = None) -> None:
        load_project_env()
        if client is None or types_module is None:
            try:
                from google import genai  # type: ignore
                from google.genai import types  # type: ignore
            except ImportError as error:
                raise RuntimeError("Install hero-graph-lab[gemini] to use the Gemini provider.") from error
            client = client or genai.Client()
            types_module = types_module or types
        self.model = model
        self._client = client
        self._types = types_module

    def complete(self, request: ModelRequest) -> ModelResponse:
        declarations = [
            self._types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.input_schema,
            )
            for tool in request.tools
        ]
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=self._messages(request.messages),
                config=self._types.GenerateContentConfig(
                    system_instruction=request.system_prompt,
                    max_output_tokens=request.max_tokens,
                    tools=[self._types.Tool(function_declarations=declarations)],
                    automatic_function_calling=self._types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except Exception as error:
            raise RuntimeError(f"Gemini request failed: {error}") from error
        candidate = response.candidates[0]
        parts = candidate.content.parts or []
        calls = tuple(
            ToolCall(
                str(getattr(part.function_call, "id", None) or f"gemini-{index}"),
                part.function_call.name,
                dict(part.function_call.args or {}),
                provider_payload=candidate.content,
            )
            for index, part in enumerate(parts)
            if getattr(part, "function_call", None) is not None
        )
        usage = getattr(response, "usage_metadata", None)
        finish_reason = getattr(candidate, "finish_reason", "stop")
        return ModelResponse(
            text="\n".join(
                part.text
                for part in parts
                if getattr(part, "text", None) and not getattr(part, "thought", False)
            ).strip(),
            tool_calls=calls,
            usage=ModelUsage(
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            ),
            finish_reason=str(getattr(finish_reason, "value", finish_reason) or "stop").lower(),
        )

    def _messages(self, messages: tuple[ModelMessage, ...]) -> list[Any]:
        output: list[Any] = []
        for message in messages:
            if message.role == "assistant":
                payload = next(
                    (call.provider_payload for call in message.tool_calls if call.provider_payload is not None),
                    None,
                )
                if payload is not None:
                    output.append(payload)
                elif message.content:
                    output.append(
                        self._types.Content(
                            role="model",
                            parts=[self._types.Part.from_text(text=message.content)],
                        )
                    )
            elif message.role == "tool":
                output.append(
                    self._types.Content(
                        role="tool",
                        parts=[
                            self._types.Part.from_function_response(
                                name=message.tool_name,
                                response={"result": message.content, "is_error": message.is_error},
                            )
                        ],
                    )
                )
            else:
                output.append(
                    self._types.Content(
                        role="user",
                        parts=[self._types.Part.from_text(text=message.content)],
                    )
                )
        return output


def create_model_client(provider: str, model: str | None = None) -> ModelClient:
    load_project_env()
    normalized = provider.strip().lower()
    if normalized == "fake":
        return FakeModelClient()
    if normalized == "anthropic":
        return AnthropicModelClient(model or "claude-sonnet-4-5")
    if normalized == "openai":
        return OpenAIModelClient(model or "gpt-5")
    if normalized == "deepseek":
        return DeepSeekModelClient(model or "deepseek-v4-flash")
    if normalized == "gemini":
        return GeminiModelClient(model or "gemini-2.5-flash")
    raise ValueError(f"unsupported explore provider: {provider}")
