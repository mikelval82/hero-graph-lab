from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Iterable

from hero_graph_lab.explore.tools import ExploreToolRegistry, GraphIndex, ToolEnvironment


MAX_PROPOSAL_ACTIONS = 500
MCP_INSTRUCTIONS = (
    "Inspect the active Graph Lab project with graph and source tools. "
    "ProposeNode and ProposeRelation only stage reviewable browser-local design actions; "
    "they never edit source files or synchronize HARNESS. Save map remains explicit. "
    "Contract tools read and advance the active HARNESS mission contract; acquire an execution "
    "lease before editing with native workspace tools and complete only through verification."
)


def _graph_with_actions(graph: dict[str, Any], actions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    merged = {
        **graph,
        "nodes": [dict(node) for node in graph.get("nodes", [])],
        "edges": [dict(edge) for edge in graph.get("edges", [])],
    }
    known_nodes = {str(node.get("id")) for node in merged["nodes"]}
    known_edges = {str(edge.get("id")) for edge in merged["edges"]}
    for action in actions:
        if action.get("op") == "add_node":
            node_id = str(action["node_id"])
            if node_id in known_nodes:
                continue
            parent_id = action.get("parent_id")
            merged["nodes"].append(
                {
                    "id": node_id,
                    "label": action["label"],
                    "kind": action["kind"],
                    "parent": parent_id,
                    "description": action.get("description", ""),
                    "source": "",
                    "line": 0,
                    "end_line": 0,
                    "status": "proposed",
                    "designProvenance": "CODEX_MCP",
                }
            )
            known_nodes.add(node_id)
            if parent_id:
                edge_id = f"mcp-containment:{node_id}"
                if edge_id not in known_edges:
                    merged["edges"].append(
                        {
                            "id": edge_id,
                            "source": str(parent_id),
                            "target": node_id,
                            "kind": "contains",
                            "status": "proposed",
                            "generated": True,
                            "designProvenance": "CODEX_MCP",
                        }
                    )
                    known_edges.add(edge_id)
        elif action.get("op") == "add_relation":
            relation_id = str(action["relation_id"])
            if relation_id in known_edges:
                continue
            merged["edges"].append(
                {
                    "id": relation_id,
                    "source": action["source_id"],
                    "target": action["target_id"],
                    "kind": action["kind"],
                    "label": action.get("label", ""),
                    "properties": action.get("properties", {}),
                    "status": "proposed",
                    "designProvenance": "CODEX_MCP",
                }
            )
            known_edges.add(relation_id)
    return merged


class GraphToolGateway:
    """Transport-neutral access to the active project's graph tool registry."""

    def __init__(
        self,
        project_provider: Callable[[], Path],
        graph_provider: Callable[[], dict[str, Any]],
        registry: ExploreToolRegistry | None = None,
    ) -> None:
        self.project_provider = project_provider
        self.graph_provider = graph_provider
        self.registry = registry or ExploreToolRegistry()
        self._history: list[dict[str, Any]] = []
        self._pending: list[dict[str, Any]] = []
        self._revision = 0
        self._lock = threading.RLock()

    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema,
                "annotations": {
                    "readOnlyHint": not spec.name.startswith("Propose"),
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            }
            for spec in self.registry.specs(allow_proposals=True)
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
        with self._lock:
            if len(self._history) >= MAX_PROPOSAL_ACTIONS and name.startswith("Propose"):
                raise ValueError("the MCP proposal limit has been reached; restart Graph Lab or select a project")
            graph = GraphIndex(_graph_with_actions(self.graph_provider(), self._history))
            existing_actions = list(self._history)
            environment = ToolEnvironment(
                self.project_provider().resolve(),
                graph,
                allow_proposals=name.startswith("Propose"),
                actions=existing_actions,
            )
            content = self.registry.execute(name, arguments, environment)
            actions = environment.actions[len(self._history) :]
            for action in actions:
                self._revision += 1
                stored = dict(action)
                self._history.append(stored)
                self._pending.append({"revision": self._revision, "action": stored})
            return {"content": content, "actions": [dict(action) for action in actions]}

    def pending_proposals(self) -> dict[str, Any]:
        with self._lock:
            return {
                "revision": self._revision,
                "items": [
                    {"revision": item["revision"], "action": dict(item["action"])}
                    for item in self._pending
                ],
            }

    def acknowledge_proposals(self, revisions: list[int]) -> dict[str, Any]:
        if not isinstance(revisions, list) or any(not isinstance(item, int) for item in revisions):
            raise ValueError("revisions must be an array of integers")
        accepted = set(revisions)
        with self._lock:
            self._pending = [item for item in self._pending if item["revision"] not in accepted]
            return self.pending_proposals()

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._pending.clear()
            self._revision = 0
