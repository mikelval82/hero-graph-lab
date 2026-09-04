"""Compile an accepted graph design into a deterministic intent contract."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from .models import IntentContract
from .validation import ContractValidationError, validate_contract


DESIGN_STATUSES = {"proposed", "modified", "accepted"}
CODE_KINDS = {"file", "module", "class", "function", "method", "document"}


class DesignCompileError(ContractValidationError):
    """Raised when the graph design cannot become an executable contract."""


def compile_design_contract(
    graph: dict[str, Any],
    *,
    title: str,
    objective: str,
    contract_id: str | None = None,
    acceptance_criteria: list[str] | None = None,
) -> IntentContract:
    nodes = [dict(node) for node in graph.get("nodes", []) if _is_design_node(node)]
    edges = [dict(edge) for edge in graph.get("edges", []) if _is_design_edge(edge)]
    if not nodes:
        raise DesignCompileError("design contains no proposed or accepted nodes")
    issues: list[str] = []
    requirements: list[str] = []
    criteria: list[str] = _strings(acceptance_criteria)
    targets: list[dict[str, str]] = []
    node_ids = {str(node.get("id", "")) for node in nodes}
    for node in sorted(nodes, key=lambda item: str(item.get("id", ""))):
        node_id = str(node.get("id", ""))
        path = str(node.get("target_path", "")).strip().replace("\\", "/")
        kind = str(node.get("kind", ""))
        if kind in CODE_KINDS and not path:
            issues.append(f"{node_id}: missing target_path")
        if path:
            targets.append({"id": node_id, "target_path": path, "operation": _operation(node)})
        description = str(node.get("designDescription") or node.get("description") or "").strip()
        if description:
            requirements.append(f"{node.get('label', node_id)}: {description}")
        criteria.extend(_strings(node.get("acceptance")))
    relationships: list[dict[str, str]] = []
    for edge in sorted(edges, key=lambda item: (str(item.get("source")), str(item.get("target")), str(item.get("kind")))):
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        kind = str(edge.get("kind", ""))
        if not source or not target or not kind:
            issues.append("relationship has missing source, target, or kind")
            continue
        if target not in node_ids and not _observed_endpoint(graph, target):
            issues.append(f"relationship target is not observed or designed: {target}")
        relationships.append({"source": source, "target": target, "kind": kind})
    if issues:
        raise DesignCompileError("; ".join(issues))
    if not criteria:
        raise DesignCompileError("design contains no acceptance criteria")
    design_payload = {"nodes": nodes, "edges": edges}
    design_hash = hashlib.sha256(json.dumps(design_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    metadata = {"design_hash": design_hash, "design_revision": str(graph.get("design_revision", "")), "targets": targets, "relationships": relationships}
    return validate_contract(IntentContract(contract_id or f"design-{uuid4().hex[:12]}", title, objective, requirements, sorted(set(criteria)), metadata=metadata))


def _is_design_node(node: dict[str, Any]) -> bool:
    return str(node.get("status", "")) in DESIGN_STATUSES or (not node.get("source") and bool(node.get("target_path")))


def _is_design_edge(edge: dict[str, Any]) -> bool:
    return str(edge.get("status", "")) in DESIGN_STATUSES


def _operation(node: dict[str, Any]) -> str:
    status = str(node.get("status", "proposed"))
    return "CHANGE" if status == "modified" else "CREATE"


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in value or [] if str(item).strip()]


def _observed_endpoint(graph: dict[str, Any], node_id: str) -> bool:
    return any(str(node.get("id")) == node_id for node in graph.get("nodes", []) if str(node.get("status", "observed")) not in DESIGN_STATUSES)
