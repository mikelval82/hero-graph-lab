"""Build deterministic project graphs from Python, script, document, and file sources."""

from __future__ import annotations

import ast
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from hero_graph_lab.markdown_adapter import (
    MarkdownGraphAdapter,
    MarkdownSource,
)
from hero_graph_lab.typescript_adapter import (
    SCRIPT_SOURCE_SUFFIXES,
    ScriptSource,
    TypeScriptGraphAdapter,
)


EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".e2e-temp",
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".uv-cache",
        "__pycache__",
        "build",
        "dist",
        "env",
        "htmlcov",
        "node_modules",
        "outputs",
        "venv",
    }
)
PROJECT_SOURCE_SUFFIXES = frozenset(
    {".cjs", ".css", ".htm", ".html", ".js", ".jsx", ".md", ".mjs", ".py", ".ts", ".tsx"}
)


def python_source_files(path: Path) -> list[Path]:
    return _source_files(path, frozenset({".py"}))


def project_source_files(path: Path) -> list[Path]:
    """Return supported project files in stable traversal order."""
    return _source_files(path, PROJECT_SOURCE_SUFFIXES)


def _source_files(path: Path, suffixes: frozenset[str]) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in suffixes else []
    files: list[Path] = []
    for root, directories, names in os.walk(path):
        directories[:] = sorted(
            name for name in directories if not _excluded_directory(name)
        )
        files.extend(
            Path(root) / name
            for name in sorted(names)
            if Path(name).suffix.lower() in suffixes
        )
    return files


def _excluded_directory(name: str) -> bool:
    return name in EXCLUDED_DIRECTORY_NAMES or name.startswith(".venv")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str
    parent: str | None
    line: int
    end_line: int
    source: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str


def merge_markdown_containment_edges(
    document_edges: Iterable[dict[str, str]], edges: list[Edge]
) -> None:
    """Merge Markdown ``contains`` edges without changing existing graph edges."""
    existing = {(edge.source, edge.target, edge.kind) for edge in edges}
    for edge in document_edges:
        if edge.get("kind") != "contains":
            continue
        key = (edge["source"], edge["target"], edge["kind"])
        if key not in existing:
            edges.append(Edge(*key))
            existing.add(key)


class PythonGraphExtractor(ast.NodeVisitor):
    def __init__(
        self,
        path: Path,
        *,
        module_name: str | None = None,
        module_parent: str | None = None,
        source: str | None = None,
        symbols: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.module_name = module_name
        self.module_id = f"module:{module_name or path.stem}"
        self.source = source or path.name
        self.nodes: list[Node] = [
            Node(self.module_id, "module", path.name, module_parent, 1, 1, self.source)
        ]
        self.edges: list[Edge] = [Edge(module_parent, self.module_id, "contains")] if module_parent else []
        self.scope: list[str] = [self.module_id]
        self.symbols = symbols if symbols is not None else {}

    def extract(self, tree: ast.AST | None = None, *, index_symbols: bool = True) -> dict[str, Any]:
        tree = tree or ast.parse(self.path.read_text(encoding="utf-8"), filename=str(self.path))
        self.nodes[0] = Node(
            self.module_id,
            "module",
            self.path.name,
            self.nodes[0].parent,
            1,
            max((getattr(node, "end_lineno", 1) or 1 for node in ast.walk(tree)), default=1),
            self.source,
        )
        if index_symbols:
            self._index_symbols(tree)
        self.visit(tree)
        return {
            "source": self.path.name,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
        }

    def _index_symbols(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.symbols[node.name] = self._class_id(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent = self._lexical_parent(tree, node)
                symbol_id = self._symbol_id(node.name, parent)
                self.symbols[node.name] = symbol_id
                if parent is not None:
                    self.symbols[f"{parent.name}.{node.name}"] = symbol_id

    @staticmethod
    def _lexical_parent(tree: ast.AST, target: ast.AST) -> ast.ClassDef | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and target in node.body:
                return node
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        node_id = self._class_id(node.name)
        self._add_node(node_id, "class", node.name, node)
        self.scope.append(node_id)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent_class = self.scope[-1].removeprefix("class:") if self.scope[-1].startswith("class:") else None
        if parent_class and self.module_name:
            parent_class = parent_class.removeprefix(f"{self.module_name}.")
        node_id = self._symbol_id(node.name, parent_class)
        self._add_node(node_id, "method" if parent_class else "function", node.name, node)
        self.scope.append(node_id)
        self.generic_visit(node)
        self.scope.pop()

    def _class_id(self, name: str) -> str:
        qualifier = f"{self.module_name}." if self.module_name else ""
        return f"class:{qualifier}{name}"

    def _symbol_id(self, name: str, parent: str | ast.ClassDef | None) -> str:
        parent_name = parent.name if isinstance(parent, ast.ClassDef) else parent
        qualifier = f"{self.module_name}." if self.module_name else ""
        return f"method:{qualifier}{parent_name}.{name}" if parent_name else f"function:{qualifier}{name}"

    def _add_node(self, node_id: str, kind: str, label: str, node: ast.AST) -> None:
        self.nodes.append(
            Node(
                node_id,
                kind,
                label,
                self.scope[-1],
                getattr(node, "lineno", 1),
                getattr(node, "end_lineno", getattr(node, "lineno", 1)) or 1,
                self.source,
            )
        )
        self.edges.append(Edge(self.scope[-1], node_id, "contains"))

    def visit_Call(self, node: ast.Call) -> None:
        called_name = self._call_name(node.func)
        target = self.symbols.get(called_name) or self.symbols.get(called_name.rsplit(".", 1)[-1])
        if target is not None and self.scope[-1] != target:
            edge = Edge(self.scope[-1], target, "calls")
            if edge not in self.edges:
                self.edges.append(edge)
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = PythonGraphExtractor._call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""


def extract_python_graph(path: Path) -> dict[str, Any]:
    if path.is_file():
        return PythonGraphExtractor(path).extract()
    return _extract_python_package(path)


def extract_project_graph(path: Path) -> dict[str, Any]:
    """Extract a graph whose payload always contains source, root, nodes, and edges."""
    if path.is_file():
        if path.suffix.lower() == ".py":
            graph = PythonGraphExtractor(path).extract()
            graph["root"] = f"module:{path.stem}"
            return graph
        if path.suffix.lower() in SCRIPT_SOURCE_SUFFIXES:
            module_name = path.name[: -len(path.suffix)]
            graph = TypeScriptGraphAdapter().extract(
                [ScriptSource(path, module_name, None, path.name)]
            )
            graph.update({"source": path.name, "root": f"module:{module_name}"})
            return graph
        if path.suffix.lower() == ".md":
            module_name = path.name[: -len(path.suffix)]
            graph = MarkdownGraphAdapter().extract(
                [MarkdownSource(path, module_name, None, path.name)]
            )
            graph.update({"source": path.name, "root": f"document:{module_name}"})
            return graph
        return _extract_single_file(path)
    return _extract_python_package(path, include_project_files=True)


def _extract_single_file(path: Path) -> dict[str, Any]:
    source = path.name
    node_id = f"file:{source}"
    content = path.read_text(encoding="utf-8")
    node = Node(node_id, "file", path.name, None, 1, max(1, len(content.splitlines())), source)
    return {
        "source": source,
        "root": node_id,
        "nodes": [asdict(node)],
        "edges": [],
    }


def _extract_python_package(path: Path, *, include_project_files: bool = False) -> dict[str, Any]:
    """Extract Python package structure and optionally all supported project files."""
    root_name = path.name
    root_id = f"package:{root_name}"
    source_files = project_source_files(path) if include_project_files else python_source_files(path)
    python_files = [file for file in source_files if file.suffix.lower() == ".py"]
    files = [file for file in python_files if file.name != "__init__.py"]
    parsed: list[tuple[Path, str, str, ast.AST]] = []
    symbol_candidates: dict[str, set[str]] = defaultdict(set)

    for file in files:
        relative = file.relative_to(path)
        module_name = ".".join((root_name, *relative.with_suffix("").parts))
        source = relative.as_posix()
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        parsed.append((file, module_name, source, tree))
        _index_package_symbols(tree, module_name, symbol_candidates)

    symbols = {name: next(iter(targets)) for name, targets in symbol_candidates.items() if len(targets) == 1}
    nodes = [Node(root_id, "package", root_name, None, 0, 0, "")]
    edges: list[Edge] = []
    package_ids = {root_id}

    def add_package_path(relative_parent: Path) -> str:
        parent_id = root_id
        for depth in range(1, len(relative_parent.parts) + 1):
            parts = relative_parent.parts[:depth]
            package_name = ".".join((root_name, *parts))
            package_id = f"package:{package_name}"
            if package_id not in package_ids:
                nodes.append(Node(package_id, "package", parts[-1], parent_id, 0, 0, ""))
                edges.append(Edge(parent_id, package_id, "contains"))
                package_ids.add(package_id)
            parent_id = package_id
        return parent_id

    init_files = (file for file in python_files if file.name == "__init__.py")
    for file in init_files:
        add_package_path(file.relative_to(path).parent)

    for file, module_name, source, tree in parsed:
        parent_id = add_package_path(file.relative_to(path).parent)
        extractor = PythonGraphExtractor(
            file,
            module_name=module_name,
            module_parent=parent_id,
            source=source,
            symbols=symbols,
        )
        graph = extractor.extract(tree, index_symbols=False)
        nodes.extend(Node(**node) for node in graph["nodes"])
        edges.extend(Edge(**edge) for edge in graph["edges"])

    if include_project_files:
        script_sources: list[ScriptSource] = []
        for file in source_files:
            if file.suffix.lower() not in SCRIPT_SOURCE_SUFFIXES:
                continue
            relative = file.relative_to(path)
            parent_id = add_package_path(relative.parent)
            module_name = ".".join((root_name, *relative.with_suffix("").parts))
            script_sources.append(
                ScriptSource(file, module_name, parent_id, relative.as_posix())
            )
        script_graph = TypeScriptGraphAdapter().extract(script_sources)
        nodes.extend(Node(**node) for node in script_graph["nodes"])
        edges.extend(Edge(**edge) for edge in script_graph["edges"])

        for file in source_files:
            if (
                file.suffix.lower() == ".py"
                or file.suffix.lower() in SCRIPT_SOURCE_SUFFIXES
                or file.suffix.lower() == ".md"
            ):
                continue
            relative = file.relative_to(path)
            parent_id = add_package_path(relative.parent)
            source = relative.as_posix()
            content = file.read_text(encoding="utf-8")
            node_id = f"file:{root_name}:{source}"
            nodes.append(
                Node(
                    node_id,
                    "file",
                    file.name,
                    parent_id,
                    1,
                    max(1, len(content.splitlines())),
                    source,
                )
            )
            edges.append(Edge(parent_id, node_id, "contains"))

        markdown_sources: list[MarkdownSource] = []
        for file in source_files:
            if file.suffix.lower() != ".md":
                continue
            relative = file.relative_to(path)
            module_name = ".".join((root_name, *relative.with_suffix("").parts))
            markdown_sources.append(
                MarkdownSource(
                    file,
                    module_name,
                    add_package_path(relative.parent),
                    relative.as_posix(),
                )
            )

        phase_a_nodes = [asdict(node) for node in nodes]
        document_graph = MarkdownGraphAdapter().extract(markdown_sources)
        nodes.extend(Node(**node) for node in document_graph["nodes"])
        merge_markdown_containment_edges(document_graph["edges"], edges)

        reference_graph = MarkdownGraphAdapter().extract(
            markdown_sources, observed_nodes=phase_a_nodes
        )
        edges.extend(
            Edge(**edge)
            for edge in reference_graph["edges"]
            if edge["kind"] == "references"
        )

    return {
        "source": root_name,
        "root": root_id,
        "nodes": [asdict(node) for node in nodes],
        "edges": [asdict(edge) for edge in edges],
    }


def _index_package_symbols(
    tree: ast.AST,
    module_name: str,
    candidates: dict[str, set[str]],
) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbol_id = f"class:{module_name}.{node.name}"
            for name in (node.name, f"{module_name}.{node.name}"):
                candidates[name].add(symbol_id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = PythonGraphExtractor._lexical_parent(tree, node)
            if parent is None:
                symbol_id = f"function:{module_name}.{node.name}"
                names = (node.name, f"{module_name}.{node.name}")
            else:
                symbol_id = f"method:{module_name}.{parent.name}.{node.name}"
                names = (
                    node.name,
                    f"{parent.name}.{node.name}",
                    f"{module_name}.{parent.name}.{node.name}",
                )
            for name in names:
                candidates[name].add(symbol_id)
