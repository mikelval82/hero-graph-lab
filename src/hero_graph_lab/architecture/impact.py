from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any


CONTRACT_FIELDS = (
    "label",
    "kind",
    "parent",
    "status",
    "description",
    "target_path",
    "qualified_name",
    "signature",
    "docstring",
    "satisfies",
    "acceptance",
)
DEPENDENCY_KINDS = frozenset({"calls", "depends_on", "uses", "publishes"})
CODE_ANCHOR_KINDS = frozenset({"file", "module"})


class ContractImpactAnalyzer:
    """Explain contract drift through bounded, observed dependency evidence."""

    def __init__(self, *, max_depth: int = 3, max_dependents: int = 100) -> None:
        if not isinstance(max_depth, int) or max_depth < 1:
            raise ValueError("max_depth must be a positive integer")
        if not isinstance(max_dependents, int) or max_dependents < 1:
            raise ValueError("max_dependents must be a positive integer")
        self.max_depth = max_depth
        self.max_dependents = max_dependents

    def analyze(
        self,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
        graph: dict[str, Any],
    ) -> dict[str, Any]:
        drift = contract_snapshot_delta(baseline, candidate)
        graph_nodes, graph_edges = _graph_items(graph)
        node_by_id = {node["id"]: node for node in graph_nodes}
        changed_ids = _changed_contract_ids(drift, baseline, candidate)
        anchor_evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
        unresolved: list[dict[str, str]] = []

        for contract_node_id in sorted(changed_ids):
            anchors, stale = _resolve_contract_anchors(
                contract_node_id,
                baseline,
                candidate,
                node_by_id,
            )
            if not anchors:
                unresolved.append(
                    {
                        "contract_node_id": contract_node_id,
                        "reason": "stale_observed_anchor" if stale else "no_observed_anchor",
                    }
                )
                continue
            for anchor_id, evidence in anchors:
                if evidence not in anchor_evidence[anchor_id]:
                    anchor_evidence[anchor_id].append(evidence)

        anchors = []
        for anchor_id in sorted(anchor_evidence):
            item = _node_view(node_by_id[anchor_id])
            evidence = sorted(anchor_evidence[anchor_id], key=_evidence_key)
            item["contract_node_ids"] = sorted(
                {entry["contract_node_id"] for entry in evidence}
            )
            item["evidence"] = evidence
            anchors.append(item)

        dependents, truncated = self._dependents(
            [item["id"] for item in anchors],
            node_by_id,
            graph_edges,
        )
        return {
            "summary": {
                "changed_contract_nodes": (
                    drift["summary"]["added_nodes"]
                    + drift["summary"]["removed_nodes"]
                    + drift["summary"]["changed_nodes"]
                ),
                "changed_contract_relations": (
                    drift["summary"]["added_relations"]
                    + drift["summary"]["removed_relations"]
                    + drift["summary"]["changed_relations"]
                ),
                "code_anchors": len(anchors),
                "dependent_code": len(dependents),
                "unresolved_contract_nodes": len(unresolved),
                "truncated": truncated,
            },
            "anchors": anchors,
            "dependents": dependents,
            "unresolved": unresolved,
        }

    def _dependents(
        self,
        anchor_ids: list[str],
        node_by_id: dict[str, dict[str, Any]],
        graph_edges: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in graph_edges:
            if (
                edge.get("kind") not in DEPENDENCY_KINDS
                or edge.get("status") in {"proposed", "removed"}
                or edge.get("source") not in node_by_id
                or edge.get("target") not in node_by_id
                or edge.get("source") == edge.get("target")
            ):
                continue
            incoming[edge["target"]].append(edge)
        for edges in incoming.values():
            edges.sort(key=_edge_key)

        visited = set(anchor_ids)
        queue = deque((anchor_id, anchor_id, 0, []) for anchor_id in sorted(anchor_ids))
        dependents: list[dict[str, Any]] = []
        truncated = False
        while queue:
            current_id, anchor_id, distance, path = queue.popleft()
            candidates = [
                edge for edge in incoming.get(current_id, []) if edge["source"] not in visited
            ]
            if distance >= self.max_depth:
                truncated = truncated or bool(candidates)
                continue
            for edge in candidates:
                dependent_id = edge["source"]
                if dependent_id in visited:
                    continue
                if len(dependents) >= self.max_dependents:
                    truncated = True
                    continue
                visited.add(dependent_id)
                next_path = [*path, _path_edge(edge, node_by_id)]
                item = _node_view(node_by_id[dependent_id])
                item.update(
                    {
                        "distance": distance + 1,
                        "anchor_id": anchor_id,
                        "path": next_path,
                    }
                )
                dependents.append(item)
                queue.append((dependent_id, anchor_id, distance + 1, next_path))

        dependents.sort(key=lambda item: (item["distance"], item["id"]))
        return dependents, truncated


def contract_snapshot_delta(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Return the exact, deterministic delta between normalized snapshots."""

    baseline_nodes, baseline_edges, _ = _snapshot_items(baseline)
    candidate_nodes, candidate_edges, _ = _snapshot_items(candidate)
    left_nodes = {item["id"]: item for item in baseline_nodes}
    right_nodes = {item["id"]: item for item in candidate_nodes}
    added_node_ids = sorted(right_nodes.keys() - left_nodes.keys())
    removed_node_ids = sorted(left_nodes.keys() - right_nodes.keys())
    changed_nodes = []
    for node_id in sorted(left_nodes.keys() & right_nodes.keys()):
        changes = {
            field: {
                "before": deepcopy(left_nodes[node_id][field]),
                "after": deepcopy(right_nodes[node_id][field]),
            }
            for field in CONTRACT_FIELDS
            if left_nodes[node_id][field] != right_nodes[node_id][field]
        }
        if changes:
            changed_nodes.append(
                {"id": node_id, "label": right_nodes[node_id]["label"], "changes": changes}
            )

    left_edges = {_edge_key(item): item for item in baseline_edges}
    right_edges = {_edge_key(item): item for item in candidate_edges}
    added_edge_keys = sorted(right_edges.keys() - left_edges.keys())
    removed_edge_keys = sorted(left_edges.keys() - right_edges.keys())
    changed_relations = []
    for key in sorted(left_edges.keys() & right_edges.keys()):
        changes = {
            field: {
                "before": deepcopy(left_edges[key][field]),
                "after": deepcopy(right_edges[key][field]),
            }
            for field in ("status", "properties")
            if left_edges[key][field] != right_edges[key][field]
        }
        if changes:
            changed_relations.append({"key": list(key), "changes": changes})

    left_acceptance = _acceptance_set(left_nodes)
    right_acceptance = _acceptance_set(right_nodes)
    acceptance_added = [
        {"node_id": node_id, "criterion": criterion}
        for node_id, criterion in sorted(right_acceptance - left_acceptance)
    ]
    acceptance_removed = [
        {"node_id": node_id, "criterion": criterion}
        for node_id, criterion in sorted(left_acceptance - right_acceptance)
    ]
    result = {
        "added_nodes": [deepcopy(right_nodes[node_id]) for node_id in added_node_ids],
        "removed_nodes": [deepcopy(left_nodes[node_id]) for node_id in removed_node_ids],
        "changed_nodes": changed_nodes,
        "added_relations": [deepcopy(right_edges[key]) for key in added_edge_keys],
        "removed_relations": [deepcopy(left_edges[key]) for key in removed_edge_keys],
        "changed_relations": changed_relations,
        "acceptance_added": acceptance_added,
        "acceptance_removed": acceptance_removed,
    }
    result["summary"] = {
        "added_nodes": len(result["added_nodes"]),
        "removed_nodes": len(result["removed_nodes"]),
        "changed_nodes": len(result["changed_nodes"]),
        "added_relations": len(result["added_relations"]),
        "removed_relations": len(result["removed_relations"]),
        "changed_relations": len(result["changed_relations"]),
        "acceptance_added": len(acceptance_added),
        "acceptance_removed": len(acceptance_removed),
    }
    return result


def _resolve_contract_anchors(
    contract_node_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    graph_nodes: dict[str, dict[str, Any]],
) -> tuple[list[tuple[str, dict[str, str]]], bool]:
    baseline_nodes, baseline_edges, baseline_endpoints = _snapshot_items(baseline)
    candidate_nodes, candidate_edges, candidate_endpoints = _snapshot_items(candidate)
    contract_nodes = {
        item["id"]: item for item in [*baseline_nodes, *candidate_nodes]
    }
    endpoint_ids = {
        item["id"] for item in [*baseline_endpoints, *candidate_endpoints]
    }
    scope_ids = _module_scope(contract_node_id, contract_nodes)
    anchors: list[tuple[str, dict[str, str]]] = []
    stale = False

    if contract_node_id in graph_nodes:
        anchors.append(
            (
                contract_node_id,
                {"kind": "exact_node_id", "contract_node_id": contract_node_id},
            )
        )

    contract_node = contract_nodes.get(contract_node_id)
    target_path = str(contract_node.get("target_path", "")) if contract_node else ""
    if target_path:
        matches = sorted(
            (
                node_id
                for node_id, node in graph_nodes.items()
                if node.get("kind") in CODE_ANCHOR_KINDS
                and node.get("source") == target_path
            )
        )
        for node_id in matches:
            anchors.append(
                (
                    node_id,
                    {
                        "kind": "exact_target_path",
                        "contract_node_id": contract_node_id,
                        "target_path": target_path,
                    },
                )
            )

    relation_by_key = {
        _edge_key(edge): edge for edge in [*baseline_edges, *candidate_edges]
    }
    for edge in (relation_by_key[key] for key in sorted(relation_by_key)):
        source_in = edge["source"] in scope_ids
        target_in = edge["target"] in scope_ids
        if source_in == target_in:
            continue
        observed_id = edge["target"] if source_in else edge["source"]
        if observed_id not in endpoint_ids:
            continue
        if observed_id not in graph_nodes:
            stale = True
            continue
        scope_node_id = edge["source"] if source_in else edge["target"]
        anchors.append(
            (
                observed_id,
                {
                    "kind": "design_relation",
                    "contract_node_id": contract_node_id,
                    "scope_node_id": scope_node_id,
                    "relation_kind": edge["kind"],
                    "relation_label": edge["label"],
                },
            )
        )
    return anchors, stale


def _module_scope(
    node_id: str, nodes: dict[str, dict[str, Any]]
) -> set[str]:
    scope = {node_id}
    current = nodes.get(node_id)
    seen = {node_id}
    while current and current.get("kind") != "module":
        parent_id = current.get("parent")
        if not parent_id or parent_id in seen or parent_id not in nodes:
            break
        scope.add(parent_id)
        seen.add(parent_id)
        current = nodes[parent_id]
    return scope


def _changed_contract_ids(
    drift: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]
) -> set[str]:
    baseline_nodes, _, _ = _snapshot_items(baseline)
    candidate_nodes, _, _ = _snapshot_items(candidate)
    design_ids = {item["id"] for item in [*baseline_nodes, *candidate_nodes]}
    changed = {
        item["id"]
        for group in ("added_nodes", "removed_nodes", "changed_nodes")
        for item in drift[group]
    }
    for group in ("added_relations", "removed_relations"):
        for edge in drift[group]:
            changed.update({edge["source"], edge["target"]} & design_ids)
    for relation in drift["changed_relations"]:
        changed.update(set(relation["key"][:2]) & design_ids)
    return changed


def _snapshot_items(
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(snapshot, dict):
        raise ValueError("contract snapshot must be a JSON object")
    nodes = snapshot.get("nodes")
    edges = snapshot.get("edges")
    endpoints = snapshot.get("observed_endpoints")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(endpoints, list):
        raise ValueError("contract snapshot must contain node, edge and endpoint arrays")
    return nodes, edges, endpoints


def _graph_items(graph: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(graph, dict):
        raise ValueError("observed graph must be a JSON object")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("observed graph must contain node and edge arrays")
    valid_nodes = [
        node for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str)
    ]
    if len(valid_nodes) != len(nodes):
        raise ValueError("observed graph contains invalid nodes")
    valid_edges = [
        edge
        for edge in edges
        if isinstance(edge, dict)
        and isinstance(edge.get("source"), str)
        and isinstance(edge.get("target"), str)
        and isinstance(edge.get("kind"), str)
    ]
    if len(valid_edges) != len(edges):
        raise ValueError("observed graph contains invalid relationships")
    canonical_nodes: dict[str, dict[str, Any]] = {}
    for node in sorted(nodes, key=_node_key):
        canonical_nodes.setdefault(node["id"], node)
    return list(canonical_nodes.values()), sorted(edges, key=_edge_key)


def _node_view(node: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": node["id"],
        "label": str(node.get("label", node["id"])),
        "kind": str(node.get("kind", "unknown")),
        "source": str(node.get("source", "")),
    }
    for field in ("line", "end_line"):
        if isinstance(node.get(field), int):
            result[field] = node[field]
    return result


def _path_edge(
    edge: dict[str, Any], nodes: dict[str, dict[str, Any]]
) -> dict[str, str]:
    return {
        "source": edge["source"],
        "source_label": str(nodes[edge["source"]].get("label", edge["source"])),
        "target": edge["target"],
        "target_label": str(nodes[edge["target"]].get("label", edge["target"])),
        "kind": edge["kind"],
    }


def _node_key(node: dict[str, Any]) -> tuple[str, str, int, str, str, str]:
    return (
        str(node.get("id", "")),
        str(node.get("source", "")),
        node.get("line") if isinstance(node.get("line"), int) else 0,
        str(node.get("parent", "")),
        str(node.get("kind", "")),
        str(node.get("label", "")),
    )


def _acceptance_set(nodes: dict[str, dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (node_id, criterion)
        for node_id, node in nodes.items()
        for criterion in node["acceptance"]
    }


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(edge.get("source", "")),
        str(edge.get("target", "")),
        str(edge.get("kind", "")),
        str(edge.get("label", "")),
    )


def _evidence_key(evidence: dict[str, str]) -> tuple[str, ...]:
    return tuple(f"{key}={value}" for key, value in sorted(evidence.items()))
