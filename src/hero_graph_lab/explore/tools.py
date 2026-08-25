from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.explore.models import ToolSpec
from hero_graph_lab.extractor import EXCLUDED_DIRECTORY_NAMES


MAX_TOOL_OUTPUT = 40_000
PROPOSAL_NODE_KINDS = {"package", "module", "class", "function", "method"}
PROPOSAL_RELATION_KINDS = {"calls", "uses", "depends_on", "publishes", "contains", "custom"}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


class GraphIndex:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.nodes = {str(node["id"]): node for node in graph.get("nodes", [])}
        self.edges: list[dict[str, Any]] = []
        for index, edge in enumerate(graph.get("edges", [])):
            normalized = dict(edge)
            normalized.setdefault(
                "id",
                f"observed:{index}:{edge.get('source')}:{edge.get('kind')}:{edge.get('target')}",
            )
            self.edges.append(normalized)

    def node(self, node_id: str) -> dict[str, Any]:
        if node_id not in self.nodes:
            raise ValueError(f"unknown graph node: {node_id}")
        return self.nodes[node_id]

    def edge(self, edge_id: str) -> dict[str, Any] | None:
        return next((edge for edge in self.edges if edge["id"] == edge_id), None)


@dataclass(frozen=True)
class ToolEnvironment:
    project_root: Path
    graph: GraphIndex
    allow_proposals: bool = False
    actions: list[dict[str, Any]] = field(default_factory=list)

    def resolve(self, value: str) -> Path:
        root = self.project_root.resolve()
        candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("path is outside the selected project")
        return candidate

    def has_node(self, node_id: str) -> bool:
        return node_id in self.graph.nodes or any(
            action.get("op") == "add_node" and action.get("node_id") == node_id
            for action in self.actions
        )


@dataclass(frozen=True)
class ExploreTool:
    spec: ToolSpec
    handler: Callable[[dict[str, Any], ToolEnvironment], Any]


class ExploreToolRegistry:
    def __init__(self) -> None:
        self._tools = {tool.spec.name: tool for tool in _default_tools()}

    def specs(self, allow_proposals: bool = False) -> tuple[ToolSpec, ...]:
        return tuple(
            tool.spec
            for tool in self._tools.values()
            if allow_proposals or not tool.spec.name.startswith("Propose")
        )

    def execute(self, name: str, arguments: dict[str, Any], environment: ToolEnvironment) -> str:
        if name not in self._tools:
            raise ValueError(f"unknown tool: {name}")
        result = self._tools[name].handler(arguments, environment)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return text[:MAX_TOOL_OUTPUT] + ("\n...[truncated]" if len(text) > MAX_TOOL_OUTPUT else "")


def _visible_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, names in os.walk(root):
        directories[:] = sorted(
            name
            for name in directories
            if name not in EXCLUDED_DIRECTORY_NAMES and not name.startswith(".venv")
        )
        files.extend(Path(current) / name for name in sorted(names))
    return files


def _read(arguments: dict[str, Any], environment: ToolEnvironment) -> str:
    path = environment.resolve(str(arguments["path"]))
    if not path.is_file():
        raise ValueError("file does not exist")
    start = max(1, int(arguments.get("start_line", 1)))
    limit = min(400, max(1, int(arguments.get("limit", 200))))
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[start - 1 : start - 1 + limit]
    return "\n".join(f"{start + index}: {line}" for index, line in enumerate(lines))


def _glob(arguments: dict[str, Any], environment: ToolEnvironment) -> list[str]:
    pattern = str(arguments["pattern"])
    return [
        path.relative_to(environment.project_root).as_posix()
        for path in _visible_files(environment.project_root)
        if fnmatch.fnmatch(path.relative_to(environment.project_root).as_posix(), pattern)
    ][:500]


def _grep(arguments: dict[str, Any], environment: ToolEnvironment) -> list[dict[str, Any]]:
    pattern = re.compile(str(arguments["pattern"]), re.IGNORECASE if arguments.get("ignore_case") else 0)
    glob_pattern = str(arguments.get("glob", "**/*"))
    limit = min(200, max(1, int(arguments.get("limit", 50))))
    matches: list[dict[str, Any]] = []
    for path in _visible_files(environment.project_root):
        relative = path.relative_to(environment.project_root).as_posix()
        if not fnmatch.fnmatch(relative, glob_pattern):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append({"path": relative, "line": line_number, "text": line[:500]})
                if len(matches) >= limit:
                    return matches
    return matches


def _graph_get_node(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    return environment.graph.node(str(arguments["node_id"]))


def _graph_search(arguments: dict[str, Any], environment: ToolEnvironment) -> list[dict[str, Any]]:
    query = str(arguments["query"]).casefold()
    kinds = {str(kind) for kind in arguments.get("kinds", [])}
    limit = min(100, max(1, int(arguments.get("limit", 20))))
    matches = [
        node
        for node in environment.graph.nodes.values()
        if query in f"{node.get('label', '')} {node.get('id', '')} {node.get('source', '')}".casefold()
        and (not kinds or node.get("kind") in kinds)
    ]
    return matches[:limit]


def _graph_neighbors(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    node_id = str(arguments["node_id"])
    environment.graph.node(node_id)
    direction = str(arguments.get("direction", "both"))
    relation = arguments.get("relation")
    edges = [
        edge
        for edge in environment.graph.edges
        if (not relation or edge.get("kind") == relation)
        and (
            (direction in {"outgoing", "both"} and edge.get("source") == node_id)
            or (direction in {"incoming", "both"} and edge.get("target") == node_id)
        )
    ]
    node_ids = {
        str(edge["target"] if edge.get("source") == node_id else edge["source"])
        for edge in edges
    }
    return {"node": environment.graph.node(node_id), "neighbors": [environment.graph.nodes[node] for node in node_ids if node in environment.graph.nodes], "edges": edges}


def _graph_path(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    source = str(arguments["source_id"])
    target = str(arguments["target_id"])
    environment.graph.node(source)
    environment.graph.node(target)
    relation = arguments.get("relation")
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {node_id: [] for node_id in environment.graph.nodes}
    for edge in environment.graph.edges:
        if relation and edge.get("kind") != relation:
            continue
        if edge.get("source") in adjacency and edge.get("target") in adjacency:
            adjacency[str(edge["source"])].append((str(edge["target"]), edge))
            adjacency[str(edge["target"])].append((str(edge["source"]), edge))
    queue = deque([(source, [source], [])])
    visited = {source}
    while queue:
        current, nodes, edges = queue.popleft()
        if current == target:
            return {"nodes": [environment.graph.nodes[node_id] for node_id in nodes], "edges": edges}
        for neighbor, edge in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, [*nodes, neighbor], [*edges, edge]))
    return {"nodes": [], "edges": []}


def _graph_scope(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    root = str(arguments["node_id"])
    environment.graph.node(root)
    depth = min(6, max(0, int(arguments.get("depth", 2))))
    selected = {root}
    frontier = {root}
    for _ in range(depth):
        next_frontier = {
            str(edge["target"])
            for edge in environment.graph.edges
            if edge.get("kind") == "contains" and edge.get("source") in frontier
        }
        selected.update(next_frontier)
        frontier = next_frontier
    return {
        "nodes": [environment.graph.nodes[node_id] for node_id in selected if node_id in environment.graph.nodes],
        "edges": [edge for edge in environment.graph.edges if edge.get("source") in selected and edge.get("target") in selected],
    }


def _required_text(arguments: dict[str, Any], name: str, maximum: int = 120) -> str:
    value = str(arguments.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{name} is too long")
    return value


def _optional_text(arguments: dict[str, Any], name: str, maximum: int) -> str:
    return str(arguments.get(name, "")).strip()[:maximum]


def _text_list(arguments: dict[str, Any], name: str) -> list[str]:
    value = arguments.get(name, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    normalized: list[str] = []
    for item in value[:50]:
        entry = str(item).strip()[:500]
        if entry and entry not in normalized:
            normalized.append(entry)
    return normalized


def _target_path(arguments: dict[str, Any]) -> str:
    value = _optional_text(arguments, "target_path", 500).replace("\\", "/")
    if not value:
        return ""
    parts = value.split("/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value) or any(
        part in {"", ".", ".."} for part in parts
    ):
        raise ValueError("target_path must be repository-relative without empty, dot, or parent segments")
    return value


def _propose_node(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    if not environment.allow_proposals:
        raise ValueError("graph proposal mode is disabled")
    kind = str(arguments["kind"])
    if kind not in PROPOSAL_NODE_KINDS:
        raise ValueError(f"unsupported node kind: {kind}")
    parent_id = arguments.get("parent_id")
    if parent_id is not None:
        parent_id = str(parent_id)
        if not environment.has_node(parent_id):
            raise ValueError(f"unknown parent node: {parent_id}")
    action = {
        "op": "add_node",
        "node_id": f"agent-proposal:{uuid4()}",
        "label": _required_text(arguments, "label", 80),
        "kind": kind,
        "parent_id": parent_id,
        "description": _optional_text(arguments, "description", 2000),
        "target_path": _target_path(arguments),
        "qualified_name": _optional_text(arguments, "qualified_name", 500),
        "signature": _optional_text(arguments, "signature", 1000),
        "docstring": _optional_text(arguments, "docstring", 2000),
        "satisfies": _text_list(arguments, "satisfies"),
        "acceptance": _text_list(arguments, "acceptance"),
    }
    environment.actions.append(action)
    return action


def _propose_relation(arguments: dict[str, Any], environment: ToolEnvironment) -> dict[str, Any]:
    if not environment.allow_proposals:
        raise ValueError("graph proposal mode is disabled")
    source_id = str(arguments["source_id"])
    target_id = str(arguments["target_id"])
    if source_id == target_id:
        raise ValueError("a relationship requires two different nodes")
    for node_id in (source_id, target_id):
        if not environment.has_node(node_id):
            raise ValueError(f"unknown graph node: {node_id}")
    kind = str(arguments["kind"])
    if kind not in PROPOSAL_RELATION_KINDS:
        raise ValueError(f"unsupported relationship kind: {kind}")
    properties = arguments.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("properties must be an object")
    action = {
        "op": "add_relation",
        "relation_id": f"agent-relation:{uuid4()}",
        "source_id": source_id,
        "target_id": target_id,
        "kind": kind,
        "label": str(arguments.get("label", "")).strip()[:80],
        "properties": {str(key)[:80]: str(value)[:200] for key, value in list(properties.items())[:20]},
    }
    environment.actions.append(action)
    return action


def _default_tools() -> list[ExploreTool]:
    return [
        ExploreTool(ToolSpec("Read", "Read a UTF-8 project file with line numbers.", _schema({"path": {"type": "string"}, "start_line": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"])), _read),
        ExploreTool(ToolSpec("Glob", "List project files matching a glob.", _schema({"pattern": {"type": "string"}}, ["pattern"])), _glob),
        ExploreTool(ToolSpec("Grep", "Search project files with a regular expression.", _schema({"pattern": {"type": "string"}, "glob": {"type": "string"}, "ignore_case": {"type": "boolean"}, "limit": {"type": "integer"}}, ["pattern"])), _grep),
        ExploreTool(ToolSpec("GraphGetNode", "Get one code graph node by exact id.", _schema({"node_id": {"type": "string"}}, ["node_id"])), _graph_get_node),
        ExploreTool(ToolSpec("GraphSearch", "Search graph nodes by label, id, or source.", _schema({"query": {"type": "string"}, "kinds": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}}, ["query"])), _graph_search),
        ExploreTool(ToolSpec("GraphNeighbors", "Get incoming/outgoing neighboring nodes and relationships.", _schema({"node_id": {"type": "string"}, "direction": {"type": "string", "enum": ["incoming", "outgoing", "both"]}, "relation": {"type": "string"}}, ["node_id"])), _graph_neighbors),
        ExploreTool(ToolSpec("GraphPath", "Find the shortest undirected path between two graph nodes.", _schema({"source_id": {"type": "string"}, "target_id": {"type": "string"}, "relation": {"type": "string"}}, ["source_id", "target_id"])), _graph_path),
        ExploreTool(ToolSpec("GraphScope", "Return a containment subtree from a graph node.", _schema({"node_id": {"type": "string"}, "depth": {"type": "integer"}}, ["node_id"])), _graph_scope),
        ExploreTool(ToolSpec("ProposeNode", "Emit a reviewable structured node contract for the browser-local design draft. Include justified interface, behavior, and target metadata; this tool does not edit source files or synchronize the map to HARNESS.", _schema({"label": {"type": "string"}, "kind": {"type": "string", "enum": sorted(PROPOSAL_NODE_KINDS)}, "parent_id": {"type": "string"}, "description": {"type": "string"}, "target_path": {"type": "string"}, "qualified_name": {"type": "string"}, "signature": {"type": "string"}, "docstring": {"type": "string"}, "satisfies": {"type": "array", "items": {"type": "string"}}, "acceptance": {"type": "array", "items": {"type": "string"}}}, ["label", "kind"])), _propose_node),
        ExploreTool(ToolSpec("ProposeRelation", "Emit a reviewable relationship proposal for the browser-local design draft. This tool does not edit source files or synchronize the map to HARNESS.", _schema({"source_id": {"type": "string"}, "target_id": {"type": "string"}, "kind": {"type": "string", "enum": sorted(PROPOSAL_RELATION_KINDS)}, "label": {"type": "string"}, "properties": {"type": "object"}}, ["source_id", "target_id", "kind"])), _propose_relation),
    ]
