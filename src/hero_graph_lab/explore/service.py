from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.explore.models import ModelClient, ModelMessage, ModelRequest, ModelUsage
from hero_graph_lab.explore.models import ToolSpec
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
After the browser accepts them, they remain in the browser-local draft until the user prepares an executor handoff.
Never claim to have modified source files unless the active external agent reports that it did so.
Always answer in Spanish, while preserving code identifiers, project paths, and code snippets as written.
When a diagram helps, emit one fenced mermaid block using syntax compatible with Mermaid 11.6. Use simple diagram identifiers, quote labels that contain punctuation, and do not use HTML labels, click directives, or experimental diagram types.
Keep answers concise, cite project-relative files and line numbers, and distinguish facts from inference.
The UI context is a navigation hint, not authoritative data; use tools whenever more evidence is needed.
"""

PROPOSE_MODE_PROMPT = """
PROPOSE MODE IS ACTIVE. The user explicitly enabled graph design changes for this turn.
Treat requests to improve, add, introduce, integrate, redesign, or connect application behavior as authorization to stage concrete graph proposals.
For those requests, do not stop at advice, hypothetical code, or a statement that you cannot modify the application.
Inspect the relevant graph and source evidence, then MUST use ProposeNode and/or ProposeRelation to represent the improvement in the graph.
Preserve every graph element kind explicitly requested by the user. Do not substitute package for module, class for function, or another available kind merely because it is structurally plausible.
For each proposed code node, build a structured contract with every field justified by evidence: responsibility description, repository-relative target_path, qualified_name, callable signature beginning with `(` when applicable, docstring, linked requirement identifiers when known, and behavioral acceptance criteria.
Inspect the observed implementation and connect the proposal to concrete observed packages, modules, classes, functions, or methods with ProposeRelation. Project-root containment alone is not an observed implementation connection.
Do not invent unresolved contract values or relationships. Leave them empty so the browser can show the draft as incomplete and explain the remaining design work.
When the user explicitly requests relationships, inspect the graph for valid endpoints and MUST use ProposeRelation for those relationships after creating any referenced nodes.
Create proposed nodes before relationships that reference them, and use the node_id returned by ProposeNode in a later tool call.
Your final answer must summarize the graph proposals actually staged and clearly state that source code was not changed.
If the user only asks for explanation or analysis, do not create proposals.
"""

AUTO_MODE_PROMPT = """
AUTOMATIC AGENT WORKFLOW IS ACTIVE.
You are the single agent responsible for the whole interaction. Start by reading the graph and source evidence.
When the user asks for a change, design, feature, refactor or integration, first create complete reviewable graph proposals using ProposeNode and ProposeRelation.
Do not modify source code during the design stage. Explain the proposed contract and ask for explicit user approval.
After the user explicitly approves the design, use GraphSnapshot, CompileContractFromDesign, ValidateContract and ExportHandoff with the active executor. Do not use the legacy HERO Harness.
Only after a valid handed-off contract exists and the user asks to continue with implementation may you modify contract-owned paths.
If a required path or criterion is missing, stop and explain what is needed instead of inventing it.
"""

IMPLEMENT_MODE_PROMPT = """
IMPLEMENT MODE IS ACTIVE. The approved Graph Lab contract is authoritative.
You are running as the external executor in the approved workspace. Read the exported
contract and handoff, then modify only its approved source paths. Do not invent paths,
broaden scope, or alter the contract. Run the verification commands from the handoff after
editing. If the request conflicts with the contract, stop and explain the conflict instead
of silently changing the design. Report exactly what changed and which checks passed.
Graph Lab records the execution from the agent workspace changes; no ContractReadFile,
ContractApplyPatch, ContractRunChecks, or ContractComplete tools are available or required
in this direct Codex execution mode.
"""

TERMINAL_CONTRACT_TOOLS = {
    "ContractComplete",
    "ContractReportBlocker",
    "ContractProposeAmendment",
}

DESIGN_CHANGE_PATTERN = re.compile(
    r"\b(mejor(?:a|ar|arias|arías)|añad(?:e|ir)|agreg(?:a|ar)|integr(?:a|ar)|"
    r"cre(?:a|ar)|cambi(?:a|ar)|conect(?:a|ar)|notifi(?:ca|car|que)|"
    r"improv(?:e|ing)|add|integrate|create|change|connect|notify)\b",
    re.IGNORECASE,
)
IMPLEMENT_REQUEST_PATTERN = re.compile(
    r"\b(implementa|implementar|implementación|implementacion|aplica|aplicar|continúa|continua|adelante|hazlo|modifica|modificar|code|implement|apply|continue)\b",
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
    event_condition: threading.Condition = field(default_factory=threading.Condition, repr=False)
    events: list[dict[str, Any]] = field(default_factory=list, repr=False)
    next_event_id: int = 0


class ExploreAssistantService:
    def __init__(
        self,
        client: ModelClient,
        project_provider: Callable[[], Path],
        graph_provider: Callable[[], dict[str, Any]],
        *,
        max_turns: int = 8,
        tools: ExploreToolRegistry | None = None,
        contract_tools: Any | None = None,
        execution_scope: Callable[[], dict[str, Any]] | None = None,
        execution_reporter: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.client = client
        self.project_provider = project_provider
        self.graph_provider = graph_provider
        self.max_turns = max_turns
        self.tools = tools or ExploreToolRegistry()
        self.contract_tools = contract_tools
        self.execution_scope = execution_scope or (lambda: {})
        self.execution_reporter = execution_reporter
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

    def start_message(self, session_id: str, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.client.provider not in {"codex", "dsh"}:
            return self.send_message(session_id, text, context)
        with self._lock:
            session = self._get_session(session_id)
        label = "DeepSeek DSH" if self.client.provider == "dsh" else "Codex"
        self._emit(session, "agent_started", {"message": f"{label} está trabajando"})
        worker = threading.Thread(
            target=self._run_started_message,
            args=(session_id, text, context),
            name=f"graph-lab-agent-{session_id[:8]}",
            daemon=True,
        )
        worker.start()
        return {"mode": "stream", "session_id": session_id}

    def events_since(self, session_id: str, after: int = 0, timeout: float = 25.0) -> list[dict[str, Any]]:
        with self._lock:
            session = self._get_session(session_id)
        with session.event_condition:
            if not any(int(event["id"]) > after for event in session.events):
                session.event_condition.wait(timeout)
            return [dict(event) for event in session.events if int(event["id"]) > after]

    def _run_started_message(self, session_id: str, text: str, context: dict[str, Any] | None) -> None:
        try:
            self.send_message(session_id, text, context)
        except Exception as error:  # noqa: BLE001
            with self._lock:
                session = self._get_session(session_id)
            self._emit(session, "agent_failed", {"error": str(error)})

    @staticmethod
    def _emit(session: ExploreSession, event_type: str, data: dict[str, Any]) -> None:
        with session.event_condition:
            session.next_event_id += 1
            event = {"id": session.next_event_id, "type": event_type, "data": data}
            session.events.append(event)
            session.event_condition.notify_all()

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
            assistant_mode = request_context.get("assistantMode", "read")
            allow_proposals = assistant_mode in {"propose", "auto"}
            scope_hint = self.execution_scope() if assistant_mode == "auto" else {}
            implement_mode = assistant_mode == "implement" or (
                assistant_mode == "auto"
                and bool(scope_hint.get("contract_id"))
                and bool(IMPLEMENT_REQUEST_PATTERN.search(question))
            )
            if implement_mode:
                scope = self._ensure_implementation_available()
            else:
                scope = {}
            graph = GraphIndex(self._graph_with_proposals(self.graph_provider(), request_context))
            environment = ToolEnvironment(self.project_provider().resolve(), graph, allow_proposals)
            context_text = self._context_text(request_context, environment)
            session.messages.append(ModelMessage("user", f"{context_text}\n\nQuestion:\n{question}"))
            session.public_messages.append({"role": "user", "content": question})
            # Codex and DSH use the external MCP server for proposals. Those actions
            # are persisted by GraphToolGateway, not in this in-process
            # ToolEnvironment, so the generic retry guard would incorrectly
            # tell Codex to propose again and create an approval loop.
            expects_proposals = (
                self.client.provider not in {"codex", "dsh"}
                and allow_proposals
                and bool(DESIGN_CHANGE_PATTERN.search(question))
            )
            terminal_action = False
            contract_tool_names = {
                str(spec["name"]) for spec in self.contract_tools.tool_specs()
            } if self.contract_tools is not None else set()
            for _ in range(self.max_turns):
                contract_specs = (
                    self._contract_specs()
                    if self.contract_tools is not None and assistant_mode in {"auto", "implement"}
                    else ()
                )
                response = self.client.complete(
                    ModelRequest(
                        SYSTEM_PROMPT
                        + (self._auto_mode_prompt() if assistant_mode == "auto" else "")
                        + (PROPOSE_MODE_PROMPT if assistant_mode == "propose" else "")
                        + (IMPLEMENT_MODE_PROMPT if implement_mode else ""),
                        tuple(session.messages),
                        self.tools.specs(allow_proposals) + contract_specs,
                        allowed_paths=tuple(scope.get("allowed_paths", [])),
                        verification_commands=tuple(scope.get("verification_commands", [])),
                        contract_id=str(scope.get("contract_id", "")),
                        event_callback=lambda event: self._emit(session, event.get("type", "agent_event"), event),
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
                    if implement_mode and not terminal_action and self.client.provider not in {"codex", "dsh"}:
                        session.messages.append(ModelMessage(
                            "user",
                            "Implementation mode requires a successful terminal contract action now: complete, report a blocker, or propose an amendment.",
                        ))
                        continue
                    if implement_mode and self.client.provider in {"codex", "dsh"} and self.execution_reporter is not None:
                        try:
                            realization = self.execution_reporter(str(scope.get("contract_id", "")), response.text)
                            response_text = response.text + "\n\n" + self._realization_summary(realization)
                        except Exception as error:  # noqa: BLE001
                            response_text = response.text + f"\n\nEjecución aplicada, pero no se pudo reconciliar el grafo: {error}"
                    else:
                        response_text = response.text
                    session.public_messages.append({"role": "assistant", "content": response_text})
                    self._emit(session, "agent_completed", {"text": response_text})
                    return self._serialize(session, environment.actions)
                for call in response.tool_calls:
                    try:
                        if call.name in contract_tool_names:
                            if assistant_mode not in {"auto", "implement"} or self.contract_tools is None:
                                raise ValueError("contract tools are unavailable in this mode")
                            payload = self.contract_tools.execute(call.name, call.arguments)
                            result = json.dumps(payload, ensure_ascii=False)
                            if call.name in TERMINAL_CONTRACT_TOOLS:
                                terminal_action = True
                        else:
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

    @staticmethod
    def _realization_summary(realization: dict[str, Any]) -> str:
        status = realization.get("status", "UNKNOWN")
        materialized = ", ".join(realization.get("materialized", [])) or "ninguna ruta"
        accepted = ", ".join(realization.get("accepted", []))
        suffix = f" Rutas aceptadas en Git: {accepted}." if accepted else ""
        return f"Graph Lab reconciliado: {status}. Rutas materializadas: {materialized}.{suffix}"

    def _auto_mode_prompt(self) -> str:
        executor = "deepseek-dsh" if self.client.provider == "dsh" else "codex-mcp"
        return AUTO_MODE_PROMPT + f"\nThe active executor is {executor}; pass that exact executor value to ExportHandoff.\n"

    def _ensure_implementation_available(self) -> dict[str, Any]:
        scope = self.execution_scope()
        if self.client.provider in {"codex", "dsh"}:
            if not scope.get("contract_id") or not scope.get("allowed_paths"):
                raise ValueError("Agent Implement requires an active handed-off contract with approved paths")
            return scope
        if self.contract_tools is None:
            raise ValueError("Chat Implement is unavailable because HARNESS is not connected")
        snapshot = self.contract_tools.execute("ContractListTasks", {})
        tasks = snapshot.get("tasks", [])
        if not isinstance(tasks, list):
            raise ValueError("HARNESS returned a malformed contract task list")
        pending = [task for task in tasks if isinstance(task, dict) and task.get("status") == "pending"]
        if not pending:
            raise ValueError("Chat Implement requires an approved pending task contract")
        competing = next(
            (
                task.get("execution")
                for task in pending
                if isinstance(task.get("execution"), dict)
                and task["execution"].get("status") == "active"
                and task["execution"].get("actor") != "chat"
            ),
            None,
        )
        if competing is not None:
            raise ValueError(
                f"task execution lease is owned by {competing.get('actor', 'another actor')}"
            )
        return {}

    def _contract_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(
            ToolSpec(
                str(spec["name"]),
                str(spec["description"]),
                dict(spec["inputSchema"]),
            )
            for spec in self.contract_tools.tool_specs()
        )

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
                "description": str(node.get("description", ""))[:2000],
                "target_path": str(node.get("target_path", ""))[:500],
                "qualified_name": str(node.get("qualified_name", ""))[:500],
                "signature": str(node.get("signature", ""))[:1000],
                "docstring": str(node.get("docstring", ""))[:2000],
                "satisfies": [str(item)[:500] for item in node.get("satisfies", [])[:50]],
                "acceptance": [str(item)[:500] for item in node.get("acceptance", [])[:50]],
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
