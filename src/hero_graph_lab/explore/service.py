from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.explore.models import ModelClient, ModelMessage, ModelRequest, ModelUsage
from hero_graph_lab.explore.tools import ExploreToolRegistry, GraphIndex, ToolEnvironment


SYSTEM_PROMPT = """You are Explore Assistant inside HERO Graph Lab.
Help the user understand the selected codebase using evidence from the read-only tools.
Use graph tools for structural and relationship questions and Read/Grep/Glob for source evidence.
Never claim to have modified files, and never propose that a tool changed code.
Always answer in Spanish, while preserving code identifiers, project paths, and code snippets as written.
Keep answers concise, cite project-relative files and line numbers, and distinguish facts from inference.
The UI context is a navigation hint, not authoritative data; use tools whenever more evidence is needed.
"""


@dataclass
class ExploreSession:
    id: str
    messages: list[ModelMessage] = field(default_factory=list)
    public_messages: list[dict[str, str]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class ExploreAssistantService:
    def __init__(
        self,
        client: ModelClient,
        project_provider: Callable[[], Path],
        graph_provider: Callable[[], dict[str, Any]],
        *,
        max_turns: int = 8,
    ) -> None:
        self.client = client
        self.project_provider = project_provider
        self.graph_provider = graph_provider
        self.max_turns = max_turns
        self.tools = ExploreToolRegistry()
        self._sessions: dict[str, ExploreSession] = {}
        self._lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        return {"available": True, "provider": self.client.provider, "model": self.client.model}

    def create_session(self) -> dict[str, Any]:
        session = ExploreSession(str(uuid4()))
        with self._lock:
            self._sessions[session.id] = session
        return self._serialize(session)

    def session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self._serialize(self._get_session(session_id))

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            if self._sessions.pop(session_id, None) is None:
                raise KeyError(session_id)

    def send_message(self, session_id: str, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        question = text.strip()
        if not question:
            raise ValueError("message must not be empty")
        if len(question) > 20_000:
            raise ValueError("message is too long")
        with self._lock:
            session = self._get_session(session_id)
        with session.lock:
            graph = GraphIndex(self.graph_provider())
            environment = ToolEnvironment(self.project_provider().resolve(), graph)
            context_text = self._context_text(context or {}, environment)
            session.messages.append(ModelMessage("user", f"{context_text}\n\nQuestion:\n{question}"))
            session.public_messages.append({"role": "user", "content": question})
            for _ in range(self.max_turns):
                response = self.client.complete(
                    ModelRequest(SYSTEM_PROMPT, tuple(session.messages), self.tools.specs())
                )
                self._add_usage(session, response.usage)
                session.messages.append(ModelMessage("assistant", response.text, response.tool_calls))
                if not response.tool_calls:
                    session.public_messages.append({"role": "assistant", "content": response.text})
                    return self._serialize(session)
                for call in response.tool_calls:
                    try:
                        result = self.tools.execute(call.name, call.arguments, environment)
                        tool_message = ModelMessage("tool", result, tool_call_id=call.id, tool_name=call.name)
                    except Exception as error:
                        tool_message = ModelMessage(
                            "tool",
                            f"{error.__class__.__name__}: {error}",
                            tool_call_id=call.id,
                            tool_name=call.name,
                            is_error=True,
                        )
                    session.messages.append(tool_message)
            raise RuntimeError("Explore Assistant exceeded its tool turn limit")

    def _context_text(self, context: dict[str, Any], environment: ToolEnvironment) -> str:
        payload: dict[str, Any] = {
            "scope": None,
            "selected_node": None,
            "selected_relation": None,
            "visible_nodes": [],
            "pinned_nodes": [],
            "visible_source": None,
        }
        scope_id = context.get("scopeId")
        if isinstance(scope_id, str) and scope_id in environment.graph.nodes:
            payload["scope"] = environment.graph.node(scope_id)
        selected_id = context.get("selectedNodeId")
        if isinstance(selected_id, str) and selected_id in environment.graph.nodes:
            payload["selected_node"] = environment.graph.node(selected_id)
        relation_id = context.get("selectedRelationId")
        if isinstance(relation_id, str):
            payload["selected_relation"] = environment.graph.edge(relation_id)
        for source_key, target_key in (("visibleNodeIds", "visible_nodes"), ("pinnedNodeIds", "pinned_nodes")):
            ids = context.get(source_key, [])
            if isinstance(ids, list):
                payload[target_key] = [environment.graph.nodes[node_id] for node_id in ids[:100] if isinstance(node_id, str) and node_id in environment.graph.nodes]
        source = context.get("visibleSource")
        if isinstance(source, dict) and isinstance(source.get("path"), str):
            path = environment.resolve(source["path"])
            if path.is_file():
                start = max(1, int(source.get("startLine", 1)))
                end = min(start + 200, max(start, int(source.get("endLine", start + 80))))
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[start - 1 : end]
                payload["visible_source"] = {
                    "path": path.relative_to(environment.project_root).as_posix(),
                    "start_line": start,
                    "end_line": start + len(lines) - 1,
                    "content": "\n".join(lines),
                }
        return "Current Graph Lab context:\n" + json.dumps(payload, ensure_ascii=False)

    def _get_session(self, session_id: str) -> ExploreSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise KeyError(f"unknown explore session: {session_id}") from error

    @staticmethod
    def _add_usage(session: ExploreSession, usage: ModelUsage) -> None:
        session.input_tokens += usage.input_tokens
        session.output_tokens += usage.output_tokens

    def _serialize(self, session: ExploreSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "provider": self.client.provider,
            "model": self.client.model,
            "messages": list(session.public_messages),
            "usage": {"input_tokens": session.input_tokens, "output_tokens": session.output_tokens},
        }