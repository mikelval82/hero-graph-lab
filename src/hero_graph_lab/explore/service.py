from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.explore.models import ModelClient, ModelMessage, ModelRequest, ModelUsage
from hero_graph_lab.explore.tools import (
    PROPOSAL_NODE_KINDS,
    PROPOSAL_RELATION_KINDS,
    ExploreToolRegistry,
    GraphIndex,
    ToolEnvironment,
)


SYSTEM_PROMPT = """You are Explore Assistant inside HERO Graph Lab.
Help the user understand the selected codebase using evidence from the graph and source tools.
Use graph tools for structural and relationship questions and Read/Grep/Glob for source evidence.
Use ProposeNode and ProposeRelation only when the user explicitly asks to change the graph design.
Graph proposals are reviewable design changes: they never modify source files.
After the browser accepts them, it automatically persists them in its browser-local draft; Save map is the separate explicit synchronization step to HARNESS.
Never claim to have modified source files or synchronized a proposal to HARNESS unless the user saved the map.
Always answer in Spanish, while preserving code identifiers, project paths, and code snippets as written.
Keep answers concise, cite project-relative files and line numbers, and distinguish facts from inference.
The UI context is a navigation hint, not authoritative data; use tools whenever more evidence is needed.
"""

PROPOSE_MODE_PROMPT = """
PROPOSE MODE IS ACTIVE. The user explicitly enabled graph design changes for this turn.
Treat requests to improve, add, introduce, integrate, redesign, or connect application behavior as authorization to stage concrete graph proposals.
For those requests, do not stop at advice, hypothetical code, or a statement that you cannot modify the application.
Inspect the relevant graph and source evidence, then MUST use ProposeNode and/or ProposeRelation to represent the improvement in the graph.
Preserve every graph element kind explicitly requested by the user. Do not substitute package for module, class for function, or another available kind merely because it is structurally plausible.
When the user explicitly requests relationships, inspect the graph for valid endpoints and MUST use ProposeRelation for those relationships after creating any referenced nodes.
Create proposed nodes before relationships that reference them, and use the node_id returned by ProposeNode in a later tool call.
Your final answer must summarize the graph proposals actually staged and clearly state that source code was not changed.
If the user only asks for explanation or analysis, do not create proposals.
"""

DESIGN_CHANGE_PATTERN = re.compile(
    r"\b(mejor(?:a|ar|arias|arías)|añad(?:e|ir)|agreg(?:a|ar)|integr(?:a|ar)|"
    r"cre(?:a|ar)|cambi(?:a|ar)|conect(?:a|ar)|notifi(?:ca|car|que)|"
    r"improv(?:e|ing)|add|integrate|create|change|connect|notify)\b",
    re.IGNORECASE,
)


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
        tools: ExploreToolRegistry | None = None,
    ) -> None:
        self.client = client
        self.project_provider = project_provider
        self.graph_provider = graph_provider
        self.max_turns = max_turns
        self.tools = tools or ExploreToolRegistry()
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
            request_context = context or {}
            allow_proposals = request_context.get("assistantMode") == "propose"
            graph = GraphIndex(self._graph_with_proposals(self.graph_provider(), request_context))
            environment = ToolEnvironment(self.project_provider().resolve(), graph, allow_proposals)
            context_text = self._context_text(request_context, environment)
            session.messages.append(ModelMessage("user", f"{context_text}\n\nQuestion:\n{question}"))
            session.public_messages.append({"role": "user", "content": question})
            expects_proposals = allow_proposals and bool(DESIGN_CHANGE_PATTERN.search(question))
            for _ in range(self.max_turns):
                response = self.client.complete(
                    ModelRequest(
                        SYSTEM_PROMPT + (PROPOSE_MODE_PROMPT if allow_proposals else ""),
                        tuple(session.messages),
                        self.tools.specs(allow_proposals),
                    )
                )
                self._add_usage(session, response.usage)
                session.messages.append(ModelMessage("assistant", response.text, response.tool_calls))
                if not response.tool_calls:
                    if expects_proposals and not environment.actions:
                        session.messages.append(ModelMessage(
                            "user",
                            "Your response staged no graph changes. Propose mode requires you to inspect the graph and call ProposeNode and/or ProposeRelation now. Do not return implementation advice without tool calls.",
                        ))
                        continue
                    session.public_messages.append({"role": "assistant", "content": response.text})
                    return self._serialize(session, environment.actions)
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
            "proposal_nodes": [],
            "proposal_edges": [],
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
        payload["proposal_nodes"] = [
            node for node in environment.graph.nodes.values() if node.get("status") == "proposed"
        ][:100]
        payload["proposal_edges"] = [
            edge for edge in environment.graph.edges if edge.get("status") == "proposed"
        ][:200]
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

    @staticmethod
    def _graph_with_proposals(graph: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        merged = {
            **graph,
            "nodes": [dict(node) for node in graph.get("nodes", [])],
            "edges": [dict(edge) for edge in graph.get("edges", [])],
        }
        known_ids = {str(node.get("id")) for node in merged["nodes"]}
        candidates: list[dict[str, Any]] = []
        for node in context.get("proposalNodes", [])[:100]:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id", ""))
            label = str(node.get("label", "")).strip()
            kind = str(node.get("kind", ""))
            if not node_id or node_id in known_ids or not label or kind not in PROPOSAL_NODE_KINDS:
                continue
            candidates.append({
                "id": node_id,
                "label": label[:80],
                "kind": kind,
                "parent": node.get("parent"),
                "status": "proposed",
                "source": "",
                "line": 0,
                "end_line": 0,
            })
            known_ids.add(node_id)
        merged["nodes"].extend(
            node for node in candidates if node["parent"] is None or str(node["parent"]) in known_ids
        )
        for edge in context.get("proposalEdges", [])[:200]:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            kind = str(edge.get("kind", ""))
            if source in known_ids and target in known_ids and source != target and kind in PROPOSAL_RELATION_KINDS:
                merged["edges"].append({
                    "id": str(edge.get("id", f"draft:{source}:{kind}:{target}")),
                    "source": source,
                    "target": target,
                    "kind": kind,
                    "label": str(edge.get("label", ""))[:80],
                    "status": "proposed",
                    "properties": {},
                })
        return merged

    def _get_session(self, session_id: str) -> ExploreSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise KeyError(f"unknown explore session: {session_id}") from error

    @staticmethod
    def _add_usage(session: ExploreSession, usage: ModelUsage) -> None:
        session.input_tokens += usage.input_tokens
        session.output_tokens += usage.output_tokens

    def _serialize(
        self, session: ExploreSession, actions: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        payload = {
            "id": session.id,
            "provider": self.client.provider,
            "model": self.client.model,
            "messages": list(session.public_messages),
            "usage": {"input_tokens": session.input_tokens, "output_tokens": session.output_tokens},
        }
        if actions:
            payload["actions"] = list(actions)
        return payload
