from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from hero_graph_lab.execution.dsh_client import DshClient

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


class CodexModelClient:
    """Use the installed Codex CLI as the single Graph Lab chat agent."""

    provider = "codex"

    def __init__(self, model: str = "codex", *, project_root: Path | None = None, command: str | None = None) -> None:
        self.model = model
        self.project_root = (project_root or Path.cwd()).resolve()
        self.command = command or shutil.which("codex") or "codex"

    def complete(self, request: ModelRequest) -> ModelResponse:
        prompt = self._prompt(request)
        before = self._git_status()
        try:
            process = subprocess.Popen(
                [self.command, "exec", "--json", "--sandbox", "workspace-write", "--cd", str(self.project_root), "--skip-git-repo-check", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # Merge stderr so a verbose CLI/MCP diagnostic cannot fill a
                # second pipe while we are consuming the JSON event stream.
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root,
            )
            assert process.stdin is not None
            process.stdin.write(prompt)
            process.stdin.close()
            lines: list[str] = []
            assert process.stdout is not None
            for line in process.stdout:
                lines.append(line)
                self._emit_codex_event(request, line)
            returncode = process.wait(timeout=600)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"Codex execution failed: {error}") from error
        output = "".join(lines)
        if returncode != 0:
            detail = output.strip()
            raise RuntimeError(f"Codex execution failed ({returncode}): {detail[-2_000:]}")
        # Graph Lab writes its own contract/handoff/evidence artifacts while
        # preparing an execution. Those files are orchestration output, not
        # source changes performed by Codex, so they must not trip the
        # contract-owned-path guard.
        violations = sorted(
            path
            for path in self._git_status() - before - set(request.allowed_paths)
            if not path.startswith(".graph-lab/")
        )
        if violations:
            raise RuntimeError(
                "Codex modified paths outside the approved contract: "
                + ", ".join(violations)
                + ". Request a contract amendment before continuing."
            )
        text = self._extract_text(output)
        if not text:
            raise RuntimeError("Codex returned no assistant response")
        return ModelResponse(text=text)

    @staticmethod
    def _emit_codex_event(request: ModelRequest, line: str) -> None:
        if request.event_callback is None:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        event_type = str(event.get("type", "codex_event"))
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        normalized: dict[str, Any] = {"source": "codex", "type": event_type}
        if item.get("type") in {"agent_message", "assistant_message"}:
            normalized["type"] = "agent_message_delta"
            normalized["text"] = item.get("text") or item.get("content") or ""
        elif item.get("type") in {
            "tool_call",
            "tool_use",
            "command_execution",
            "mcp_tool_call",
            "mcp_tool_use",
        }:
            normalized["type"] = "tool_activity"
            normalized["tool"] = (
                item.get("name")
                or item.get("tool_name")
                or item.get("command")
                or item.get("server_tool")
                or "tool"
            )
        elif event_type in {"thread.started", "turn.started", "item.started"}:
            normalized["type"] = "agent_progress"
            normalized["message"] = {
                "thread.started": "Codex ha iniciado la sesión",
                "turn.started": "Codex está razonando",
                "item.started": "Codex está preparando la respuesta",
            }.get(event_type, "Codex está trabajando")
        normalized["raw"] = event
        request.event_callback(normalized)

    def _prompt(self, request: ModelRequest) -> str:
        history = []
        for message in request.messages:
            if message.role == "tool":
                continue
            history.append(f"{message.role.upper()}:\n{message.content}")
        return (
            f"{request.system_prompt}\n\n"
            "You are the active Codex agent for HERO Graph Lab. Use the configured "
            "hero_graph_lab MCP server when graph evidence or proposals are needed. "
            "Respect the requested read, propose or implement mode.\n\n"
            + (f"ACTIVE CONTRACT: {request.contract_id}\n" if request.contract_id else "")
            + ("APPROVED WRITE PATHS:\n" + "\n".join(f"- {path}" for path in request.allowed_paths) + "\n" if request.allowed_paths else "")
            + ("VERIFICATION COMMANDS:\n" + "\n".join(f"- {command}" for command in request.verification_commands) + "\n" if request.verification_commands else "")
            + "\n\n".join(history)
        )

    def _git_status(self) -> set[str]:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return set()
        paths = set()
        for line in result.stdout.splitlines():
            if len(line) > 3:
                paths.add(line[3:].strip().split(" -> ")[-1])
        return paths

    @staticmethod
    def _extract_text(output: str) -> str:
        texts: list[str] = []
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") if isinstance(event, dict) else None
            if isinstance(item, dict) and item.get("type") in {"agent_message", "assistant_message"}:
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    texts.append(value)
            elif isinstance(event, dict) and event.get("type") in {"message", "assistant_message"}:
                value = event.get("text") or event.get("content")
                if isinstance(value, str):
                    texts.append(value)
        return "\n\n".join(texts).strip()


class DshModelClient:
    """Use the official DeepSeek Harness CLI as the Graph Lab chat agent."""

    provider = "dsh"

    def __init__(
        self,
        model: str = "deepseek-v4-flash",
        *,
        project_root: Path | None = None,
        graph_lab_url: str = "http://127.0.0.1:8765",
        client: DshClient | None = None,
    ) -> None:
        self.model = model
        self.project_root = (project_root or Path.cwd()).resolve()
        self.graph_lab_url = graph_lab_url
        self.client = client or DshClient(self.project_root)

    def complete(self, request: ModelRequest) -> ModelResponse:
        if not self.client.available():
            raise RuntimeError(self.client.configuration_error() or "DeepSeek DSH is unavailable")
        profile = self.client.prepare_graph_lab_profile(
            python_executable=sys.executable,
            graph_lab_url=self.graph_lab_url,
        )
        before = CodexModelClient._git_status(self)
        execution_id = f"chat-{uuid4()}"
        prompt = self._prompt(request)
        if request.event_callback is not None:
            request.event_callback({"source": "dsh", "type": "agent_progress", "message": "DeepSeek DSH está trabajando"})
        try:
            self.client.start(
                execution_id,
                prompt,
                profile=profile,
                environment_overrides={
                    "DSH_MODEL": self.model,
                    "HERO_GRAPH_LAB_PYTHON": sys.executable,
                    "HERO_GRAPH_LAB_URL": self.graph_lab_url,
                },
            )
            status = self.client.wait(execution_id)
        except (OSError, TimeoutError) as error:
            raise RuntimeError(f"DeepSeek DSH execution failed: {error}") from error
        self._emit_events(request, status)
        if status.get("status") != "VERIFYING":
            detail = "\n".join(
                value
                for value in (str(status.get("detail", "")), str(status.get("output", "")))
                if value.strip()
            )
            raise RuntimeError(f"DeepSeek DSH execution failed: {detail[-2_000:]}")
        violations = sorted(
            path
            for path in CodexModelClient._git_status(self) - before - set(request.allowed_paths)
            if not path.startswith(".graph-lab/")
        )
        if violations:
            raise RuntimeError(
                "DeepSeek DSH modified paths outside the approved contract: "
                + ", ".join(violations)
                + ". Request a contract amendment before continuing."
            )
        text = "\n".join(
            str(event.get("text", ""))
            for event in status.get("events", [])
            if isinstance(event, dict) and event.get("type") == "agent_message_delta"
        ).strip()
        if not text:
            raise RuntimeError("DeepSeek DSH returned no assistant response")
        return ModelResponse(text=text)

    @staticmethod
    def _emit_events(request: ModelRequest, status: dict[str, object]) -> None:
        if request.event_callback is None:
            return
        for event in status.get("events", []):
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type", "agent_progress"))
            text = str(event.get("text", ""))
            request.event_callback(
                {
                    "source": "dsh",
                    "type": event_type,
                    "text": text if event_type == "agent_message_delta" else "",
                    "message": text if event_type != "agent_message_delta" else "",
                }
            )

    def _prompt(self, request: ModelRequest) -> str:
        history = []
        for message in request.messages:
            if message.role != "tool":
                history.append(f"{message.role.upper()}:\n{message.content}")
        return (
            f"{request.system_prompt}\n\n"
            "You are the active DeepSeek Harness agent for HERO Graph Lab. The official "
            "DSH profile exposes Graph Lab tools through MCP under the mcp__graph_lab__ "
            "namespace. Use those MCP tools for graph evidence, proposals, contract compilation, "
            "validation and handoff. Respect the requested read, propose or implement mode.\n\n"
            + (f"ACTIVE CONTRACT: {request.contract_id}\n" if request.contract_id else "")
            + ("APPROVED WRITE PATHS:\n" + "\n".join(f"- {path}" for path in request.allowed_paths) + "\n" if request.allowed_paths else "")
            + ("VERIFICATION COMMANDS:\n" + "\n".join(f"- {command}" for command in request.verification_commands) + "\n" if request.verification_commands else "")
            + "\n".join(history)
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


def create_model_client(provider: str, model: str | None = None, *, project_root: Path | None = None) -> ModelClient:
    load_project_env()
    normalized = provider.strip().lower()
    if normalized == "fake":
        return FakeModelClient()
    if normalized == "codex":
        return CodexModelClient(model or "codex", project_root=project_root)
    if normalized == "dsh":
        return DshModelClient(model or os.environ.get("HERO_GRAPH_LAB_DSH_MODEL", "deepseek-v4-flash"), project_root=project_root)
    if normalized == "anthropic":
        return AnthropicModelClient(model or "claude-sonnet-4-5")
    if normalized == "openai":
        return OpenAIModelClient(model or "gpt-5")
    if normalized == "deepseek":
        return DeepSeekModelClient(model or "deepseek-v4-flash")
    if normalized == "gemini":
        return GeminiModelClient(model or "gemini-2.5-flash")
    raise ValueError(f"unsupported explore provider: {provider}")
