"""Extract Markdown documents and evidence-bounded references into Graph Lab's observed graph."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class MarkdownSource:
    """Input descriptor for one Markdown document."""

    path: Path
    module_name: str
    module_parent: str | None
    source: str


class MarkdownGraphAdapter:
    """Detect Markdown references and resolve them to observed graph nodes without inventing targets."""

    def extract(
        self,
        sources: Iterable[MarkdownSource],
        observed_nodes: Iterable[dict[str, Any]] = (),
    ) -> dict[str, list[dict[str, Any]]]:
        """Return document nodes and evidence-bounded references for the given Markdown sources."""
        ordered = sorted(sources, key=lambda item: item.source)
        index = _alias_index(observed_nodes)
        nodes: dict[str, dict[str, Any]] = {}
        edges: set[tuple[str, str, str]] = set()
        for source in ordered:
            document_id = f"document:{source.module_name}"
            text = source.path.read_text(encoding="utf-8")
            if document_id not in nodes:
                nodes[document_id] = {
                    "id": document_id,
                    "kind": "document",
                    "label": source.path.name,
                    "parent": source.module_parent,
                    "line": 1,
                    "end_line": max(1, len(text.splitlines())),
                    "source": source.source,
                }
            if source.module_parent is not None:
                edges.add((source.module_parent, document_id, "contains"))
            for candidate in _reference_candidates(text):
                targets = index.get(candidate)
                if targets is not None and len(targets) == 1:
                    target_id = next(iter(targets))
                    edges.add((document_id, target_id, "references"))
        return {
            "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
            "edges": [
                {"source": source, "target": target, "kind": kind}
                for source, target, kind in sorted(edges)
            ],
        }


def _alias_index(
    observed_nodes: Iterable[dict[str, Any]],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for node in observed_nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        aliases: set[str] = set()
        source_path = node.get("source")
        if source_path:
            aliases.add(source_path)
            aliases.add(_basename(source_path))
        label = node.get("label")
        if label:
            aliases.add(label)
        aliases.update(_qualified_aliases(node_id))
        for alias in aliases:
            index[alias].add(node_id)
    return index


def _basename(source_path: str) -> str:
    return source_path.rsplit("/", 1)[-1]


def _qualified_aliases(node_id: str) -> list[str]:
    remainder = node_id.split(":", 1)[1] if ":" in node_id else node_id
    if not remainder:
        return []
    if any(ch in "/:" or ch.isspace() for ch in remainder):
        return []
    parts = remainder.split(".")
    return [".".join(parts[offset:]) for offset in range(len(parts))]


def _reference_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    fence_marker: str | None = None
    fence_length = 0
    for line in text.splitlines():
        marker, length = _fence_run(line.lstrip())
        if fence_marker is not None:
            if marker == fence_marker and length >= fence_length:
                fence_marker = None
            continue
        if marker is not None:
            fence_marker = marker
            fence_length = length
            continue
        if _indented_code_line(line):
            continue
        candidates.extend(_inline_code_candidates(line))
        candidates.extend(_link_destination_candidates(line))
    return candidates


def _fence_run(text: str) -> tuple[str | None, int]:
    if not text or text[0] not in ("`", "~"):
        return None, 0
    marker = text[0]
    length = 0
    for char in text:
        if char != marker:
            break
        length += 1
    if length < 3:
        return None, 0
    return marker, length


def _indented_code_line(line: str) -> bool:
    if line.startswith("\t"):
        return True
    spaces = 0
    for char in line:
        if char != " ":
            break
        spaces += 1
    return spaces >= 4


def _inline_code_candidates(line: str) -> list[str]:
    candidates: list[str] = []
    size = len(line)
    offset = 0
    while offset < size:
        if line[offset] != "`":
            offset += 1
            continue
        run_end = offset
        while run_end < size and line[run_end] == "`":
            run_end += 1
        length = run_end - offset
        closer = _closing_run(line, run_end, length)
        if closer is None:
            offset = run_end
            continue
        inner = line[run_end:closer].strip()
        if inner:
            candidates.append(inner)
        offset = closer + length
    return candidates


def _closing_run(line: str, start: int, length: int) -> int | None:
    size = len(line)
    offset = start
    while offset < size:
        if line[offset] != "`":
            offset += 1
            continue
        run_end = offset
        while run_end < size and line[run_end] == "`":
            run_end += 1
        if run_end - offset == length:
            return offset
        offset = run_end
    return None


def _link_destination_candidates(line: str) -> list[str]:
    candidates: list[str] = []
    size = len(line)
    offset = 0
    while offset < size:
        if line[offset] != "[":
            offset += 1
            continue
        if offset > 0 and line[offset - 1] == "!":
            offset += 1
            continue
        close = offset + 1
        while close < size and line[close] != "]":
            close += 1
        if close >= size:
            break
        if close + 1 >= size or line[close + 1] != "(":
            offset = close + 1
            continue
        depth = 0
        cursor = close + 2
        while cursor < size:
            char = line[cursor]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            cursor += 1
        if cursor >= size:
            offset = close + 1
            continue
        destination = _normalize_destination(line[close + 2 : cursor])
        if destination:
            candidates.append(destination)
        offset = cursor + 1
    return candidates


def _normalize_destination(raw: str) -> str | None:
    destination = raw.strip()
    if len(destination) >= 2 and destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1].strip()
    if destination.startswith("./"):
        destination = destination[2:]
    destination = destination.split("#", 1)[0].strip()
    return destination or None
