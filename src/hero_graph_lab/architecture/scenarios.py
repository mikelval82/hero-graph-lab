from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.architecture.impact import contract_snapshot_delta


SCENARIO_LIMIT = 50
NODE_LIMIT = 500
RELATION_LIMIT = 1_000
ENDPOINT_LIMIT = 500
LIST_LIMIT = 50
DESIGN_STATUSES = {"proposed", "modified", "removed"}


class ArchitectureScenarioService:
    """Persist and compare immutable, project-scoped architecture alternatives."""

    def __init__(self, state_path: Path, project_provider: Callable[[], Path]) -> None:
        self.state_path = state_path
        self._project_provider = project_provider
        self._lock = threading.RLock()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            scenarios = self._project_scenarios(self._read_document())
            return [self._summary(item) for item in deepcopy(scenarios)]

    def capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("scenario body must be a JSON object")
        name = _text(payload.get("name"), "name", 120, required=True)
        description = _text(payload.get("description", ""), "description", 1_000)
        snapshot = _normalize_snapshot(payload.get("snapshot"))
        scenario = {
            "id": str(uuid4()),
            "name": name,
            "description": description,
            "created_at": datetime.now(UTC).isoformat(),
            "project": self._project_path(),
            "snapshot": snapshot,
        }
        with self._lock:
            document = self._read_document()
            scenarios = self._project_scenarios(document, create=True)
            if len(scenarios) >= SCENARIO_LIMIT:
                raise ValueError(f"a project may store at most {SCENARIO_LIMIT} scenarios")
            scenarios.append(scenario)
            self._write_document(document)
        return deepcopy(scenario)

    def get(self, scenario_id: str) -> dict[str, Any]:
        normalized_id = _text(scenario_id, "scenario id", 100, required=True)
        with self._lock:
            scenario = self._find(self._project_scenarios(self._read_document()), normalized_id)
            return deepcopy(scenario)

    def compare(self, left_id: str, right_id: str) -> dict[str, Any]:
        with self._lock:
            scenarios = self._project_scenarios(self._read_document())
            left = deepcopy(self._find(scenarios, left_id))
            right = deepcopy(self._find(scenarios, right_id))
        return _compare_scenarios(left, right)

    def _project_path(self) -> str:
        return str(Path(self._project_provider()).resolve())

    def _project_key(self) -> str:
        return os.path.normcase(self._project_path())

    def _project_scenarios(
        self,
        document: dict[str, Any],
        *,
        create: bool = False,
    ) -> list[dict[str, Any]]:
        projects = document["projects"]
        key = self._project_key()
        if create:
            return projects.setdefault(key, [])
        return projects.get(key, [])

    @staticmethod
    def _find(scenarios: list[dict[str, Any]], scenario_id: str) -> dict[str, Any]:
        for scenario in scenarios:
            if scenario.get("id") == scenario_id:
                return scenario
        raise KeyError(f"unknown scenario: {scenario_id}")

    @staticmethod
    def _summary(scenario: dict[str, Any]) -> dict[str, Any]:
        snapshot = scenario["snapshot"]
        return {
            "id": scenario["id"],
            "name": scenario["name"],
            "description": scenario["description"],
            "created_at": scenario["created_at"],
            "project": scenario["project"],
            "node_count": len(snapshot["nodes"]),
            "relation_count": len(snapshot["edges"]),
            "observed_endpoint_count": len(snapshot["observed_endpoints"]),
        }

    def _read_document(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": 1, "projects": {}}
        try:
            document = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("scenario state is malformed") from error
        if (
            not isinstance(document, dict)
            or document.get("version") != 1
            or not isinstance(document.get("projects"), dict)
            or any(not isinstance(items, list) for items in document["projects"].values())
        ):
            raise ValueError("scenario state is malformed")
        return document

    def _write_document(self, document: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(f"{self.state_path.name}.tmp")
        temporary.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)


def _normalize_snapshot(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        raise ValueError("snapshot must be a JSON object")
    nodes_value = _bounded_array(value.get("nodes"), "snapshot nodes", NODE_LIMIT)
    edges_value = _bounded_array(value.get("edges"), "snapshot edges", RELATION_LIMIT)
    endpoints_value = _bounded_array(
        value.get("observed_endpoints"), "observed endpoints", ENDPOINT_LIMIT
    )

    nodes = [_normalize_node(item) for item in nodes_value]
    endpoints = [_normalize_endpoint(item) for item in endpoints_value]
    node_ids = [item["id"] for item in nodes]
    endpoint_ids = [item["id"] for item in endpoints]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("snapshot contains duplicate node ids")
    if len(set(endpoint_ids)) != len(endpoint_ids):
        raise ValueError("snapshot contains duplicate observed endpoint ids")
    if set(node_ids) & set(endpoint_ids):
        raise ValueError("design nodes and observed endpoints must have distinct ids")

    valid_ids = set(node_ids) | set(endpoint_ids)
    edges = [_normalize_edge(item) for item in edges_value]
    edge_keys = [_edge_key(item) for item in edges]
    if len(set(edge_keys)) != len(edge_keys):
        raise ValueError("snapshot contains duplicate relationships")
    for edge in edges:
        if edge["source"] not in valid_ids or edge["target"] not in valid_ids:
            raise ValueError("relationship references an unknown endpoint")

    return {
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": sorted(edges, key=_edge_key),
        "observed_endpoints": sorted(endpoints, key=lambda item: item["id"]),
    }


def _normalize_node(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each snapshot node must be a JSON object")
    status = _text(value.get("status"), "node status", 20, required=True)
    if status not in DESIGN_STATUSES:
        raise ValueError("node status must be proposed, modified, or removed")
    parent = value.get("parent")
    if parent is not None:
        parent = _text(parent, "node parent", 500, required=True)
    return {
        "id": _text(value.get("id"), "node id", 500, required=True),
        "label": _text(value.get("label"), "node label", 120, required=True),
        "kind": _text(value.get("kind"), "node kind", 64, required=True),
        "parent": parent,
        "status": status,
        "description": _text(value.get("description", ""), "node description", 2_000),
        "target_path": _text(value.get("target_path", ""), "target path", 500),
        "qualified_name": _text(
            value.get("qualified_name", ""), "qualified name", 500
        ),
        "signature": _text(value.get("signature", ""), "signature", 1_000),
        "docstring": _text(value.get("docstring", ""), "docstring", 2_000),
        "satisfies": _text_list(value.get("satisfies", []), "satisfies"),
        "acceptance": _text_list(value.get("acceptance", []), "acceptance"),
    }


def _normalize_endpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each observed endpoint must be a JSON object")
    return {
        "id": _text(value.get("id"), "observed endpoint id", 500, required=True),
        "label": _text(value.get("label"), "observed endpoint label", 120, required=True),
        "kind": _text(value.get("kind"), "observed endpoint kind", 64, required=True),
        "source": _text(value.get("source", ""), "observed endpoint source", 500),
    }


def _normalize_edge(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each snapshot relationship must be a JSON object")
    status = _text(value.get("status"), "relationship status", 20, required=True)
    if status not in DESIGN_STATUSES:
        raise ValueError("relationship status must be proposed, modified, or removed")
    source = _text(value.get("source"), "relationship source", 500, required=True)
    target = _text(value.get("target"), "relationship target", 500, required=True)
    if source == target:
        raise ValueError("relationship endpoints must be different")
    properties = value.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("relationship properties must be a JSON object")
    return {
        "source": source,
        "target": target,
        "kind": _text(value.get("kind"), "relationship kind", 64, required=True),
        "label": _text(value.get("label", ""), "relationship label", 200),
        "status": status,
        "properties": _normalize_json(properties),
    }


def _compare_scenarios(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "left": _scenario_identity(left),
        "right": _scenario_identity(right),
        **contract_snapshot_delta(left["snapshot"], right["snapshot"]),
    }


def _scenario_identity(scenario: dict[str, Any]) -> dict[str, str]:
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "created_at": scenario["created_at"],
    }


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str, str]:
    return edge["source"], edge["target"], edge["kind"], edge["label"]


def _text(value: Any, field: str, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    normalized = value.strip()
    if required and not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return normalized


def _text_list(value: Any, field: str) -> list[str]:
    values = _bounded_array(value, field, LIST_LIMIT)
    normalized = {
        _text(item, f"{field} item", 500, required=True)
        for item in values
    }
    return sorted(normalized)


def _bounded_array(value: Any, field: str, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValueError(f"{field} may contain at most {maximum} items")
    return value


def _normalize_json(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        raise ValueError("relationship properties are too deeply nested")
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _text(value, "relationship property", 500)
    if isinstance(value, list):
        if len(value) > LIST_LIMIT:
            raise ValueError(f"relationship property arrays may contain at most {LIST_LIMIT} items")
        return [_normalize_json(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > LIST_LIMIT:
            raise ValueError(f"relationship properties may contain at most {LIST_LIMIT} keys")
        if any(not isinstance(key, str) for key in value):
            raise ValueError("relationship property names must be text")
        return {
            _text(key, "relationship property name", 100, required=True): _normalize_json(
                item, depth=depth + 1
            )
            for key, item in sorted(value.items())
        }
    raise ValueError("relationship properties must contain JSON values")
