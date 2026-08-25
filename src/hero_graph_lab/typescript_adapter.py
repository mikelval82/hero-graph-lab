from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node as SyntaxNode, Parser, Tree


SCRIPT_SOURCE_SUFFIXES = frozenset({".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"})
_RESOLUTION_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_FUNCTION_NODES = frozenset(
    {
        "arrow_function",
        "function_declaration",
        "function_expression",
        "generator_function_declaration",
        "generator_function",
        "method_definition",
    }
)


@dataclass(frozen=True)
class ScriptSource:
    path: Path
    module_name: str
    module_parent: str | None
    source: str


@dataclass(frozen=True)
class _ImportBinding:
    specifier: str
    default: str | None = None
    namespace: str | None = None
    named: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class _CallScope:
    source_id: str
    body: SyntaxNode
    class_id: str | None = None


@dataclass
class _ParsedModule:
    source: ScriptSource
    content: bytes
    tree: Tree
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    containment: set[tuple[str, str, str]] = field(default_factory=set)
    declarations: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    exports: dict[str, str] = field(default_factory=dict)
    default_export: str | None = None
    methods: dict[tuple[str, str], str] = field(default_factory=dict)
    imports: list[_ImportBinding] = field(default_factory=list)
    call_scopes: list[_CallScope] = field(default_factory=list)

    @property
    def module_id(self) -> str:
        return f"module:{self.source.module_name}"


class TypeScriptGraphAdapter:
    """Extract bounded JavaScript/TypeScript structure into Graph Lab's graph."""

    def __init__(self) -> None:
        self._javascript = Language(tree_sitter_javascript.language())
        self._typescript = Language(tree_sitter_typescript.language_typescript())
        self._tsx = Language(tree_sitter_typescript.language_tsx())

    def extract(self, sources: Iterable[ScriptSource]) -> dict[str, list[dict[str, Any]]]:
        parsed = [self._parse(source) for source in sorted(sources, key=lambda item: item.source)]
        by_path = {module.source.path.resolve(): module for module in parsed}
        edges: set[tuple[str, str, str]] = set()
        for module in parsed:
            edges.update(module.containment)
            self._resolve_module(module, by_path, edges)
        nodes = [node for module in parsed for node in module.nodes.values()]
        return {
            "nodes": sorted(nodes, key=lambda node: node["id"]),
            "edges": [
                {"source": source, "target": target, "kind": kind}
                for source, target, kind in sorted(edges)
            ],
        }

    def _parse(self, source: ScriptSource) -> _ParsedModule:
        content = source.path.read_bytes()
        parser = Parser(self._language(source.path))
        tree = parser.parse(content)
        module = _ParsedModule(source=source, content=content, tree=tree)
        line_count = max(1, len(content.decode("utf-8", errors="replace").splitlines()))
        self._add_node(
            module,
            module.module_id,
            "module",
            source.path.name,
            source.module_parent,
            1,
            line_count,
        )
        if source.module_parent:
            module.containment.add((source.module_parent, module.module_id, "contains"))

        pending_exports: list[tuple[str, str]] = []
        for statement in tree.root_node.named_children:
            if statement.type == "import_statement":
                module.imports.append(self._import_statement(module, statement))
                continue
            if statement.type == "export_statement":
                specifier = self._source_specifier(module, statement)
                if specifier:
                    module.imports.append(self._export_dependency(statement, specifier, module))
                declaration = statement.child_by_field_name("declaration") or statement.child_by_field_name("value")
                if declaration is not None:
                    self._collect_declaration(
                        module,
                        declaration,
                        module.module_id,
                        exported=True,
                        default_export=any(child.type == "default" for child in statement.children),
                    )
                else:
                    pending_exports.extend(self._export_aliases(module, statement))
                continue
            self._collect_declaration(module, statement, module.module_id)

        for local_name, exported_name in pending_exports:
            target = self._unique(module.declarations.get(local_name, set()))
            if target:
                module.exports[exported_name] = target
        self._collect_commonjs_imports(module)
        return module

    def _language(self, path: Path) -> Language:
        suffix = path.suffix.lower()
        if suffix in {".jsx", ".tsx"}:
            return self._tsx
        if suffix == ".ts":
            return self._typescript
        return self._javascript

    def _collect_declaration(
        self,
        module: _ParsedModule,
        node: SyntaxNode,
        parent_id: str,
        *,
        exported: bool = False,
        default_export: bool = False,
    ) -> None:
        if node.type in {"lexical_declaration", "variable_declaration"}:
            for declarator in (child for child in node.named_children if child.type == "variable_declarator"):
                name_node = declarator.child_by_field_name("name")
                value = declarator.child_by_field_name("value")
                if name_node is None or name_node.type != "identifier" or value is None:
                    continue
                name = self._text(module, name_node)
                if value.type in {"arrow_function", "function_expression", "generator_function"}:
                    self._add_callable(module, value, name, "function", parent_id, exported=exported)
                elif value.type in {"class", "class_expression"}:
                    self._add_container(module, value, name, "class", parent_id, exported=exported)
            return

        if node.type in {"function_declaration", "generator_function_declaration", "function_expression"}:
            name_node = node.child_by_field_name("name")
            name = self._text(module, name_node) if name_node else "default"
            node_id = self._add_callable(module, node, name, "function", parent_id, exported=exported)
            if default_export:
                module.default_export = node_id
            return

        if node.type in {"class_declaration", "abstract_class_declaration", "class", "class_expression"}:
            name_node = node.child_by_field_name("name")
            name = self._text(module, name_node) if name_node else "default"
            node_id = self._add_container(module, node, name, "class", parent_id, exported=exported)
            if default_export:
                module.default_export = node_id
            return

        if node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self._add_container(
                    module,
                    node,
                    self._text(module, name_node),
                    "interface",
                    parent_id,
                    exported=exported,
                )
            return

        if node.type in {"type_alias_declaration", "enum_declaration"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self._add_symbol(
                    module,
                    node,
                    self._text(module, name_node),
                    "type",
                    parent_id,
                    exported=exported,
                )

    def _add_container(
        self,
        module: _ParsedModule,
        node: SyntaxNode,
        name: str,
        kind: str,
        parent_id: str,
        *,
        exported: bool,
    ) -> str:
        node_id = self._add_symbol(module, node, name, kind, parent_id, exported=exported)
        body = node.child_by_field_name("body")
        if body is None:
            return node_id
        accepted = {"method_definition"} if kind == "class" else {"method_signature"}
        for member in body.named_children:
            if member.type not in accepted:
                continue
            name_node = member.child_by_field_name("name")
            if name_node is None:
                continue
            method_name = self._text(module, name_node)
            method_id = f"method:{module.source.module_name}.{name}.{method_name}"
            self._add_node(
                module,
                method_id,
                "method",
                method_name,
                node_id,
                member.start_point.row + 1,
                member.end_point.row + 1,
            )
            module.containment.add((node_id, method_id, "contains"))
            module.methods[(node_id, method_name)] = method_id
            method_body = member.child_by_field_name("body")
            if method_body is not None:
                module.call_scopes.append(_CallScope(method_id, method_body, node_id))
        return node_id

    def _add_callable(
        self,
        module: _ParsedModule,
        node: SyntaxNode,
        name: str,
        kind: str,
        parent_id: str,
        *,
        exported: bool,
    ) -> str:
        node_id = self._add_symbol(module, node, name, kind, parent_id, exported=exported)
        body = node.child_by_field_name("body")
        if body is not None:
            module.call_scopes.append(_CallScope(node_id, body))
        return node_id

    def _add_symbol(
        self,
        module: _ParsedModule,
        node: SyntaxNode,
        name: str,
        kind: str,
        parent_id: str,
        *,
        exported: bool,
    ) -> str:
        node_id = f"{kind}:{module.source.module_name}.{name}"
        self._add_node(
            module,
            node_id,
            kind,
            name,
            parent_id,
            node.start_point.row + 1,
            node.end_point.row + 1,
        )
        module.containment.add((parent_id, node_id, "contains"))
        module.declarations[name].add(node_id)
        if exported:
            module.exports[name] = node_id
        return node_id

    @staticmethod
    def _add_node(
        module: _ParsedModule,
        node_id: str,
        kind: str,
        label: str,
        parent: str | None,
        line: int,
        end_line: int,
    ) -> None:
        existing = module.nodes.get(node_id)
        if existing:
            existing["line"] = min(existing["line"], line)
            existing["end_line"] = max(existing["end_line"], end_line)
            return
        module.nodes[node_id] = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "parent": parent,
            "line": line,
            "end_line": end_line,
            "source": module.source.source,
        }

    def _import_statement(self, module: _ParsedModule, node: SyntaxNode) -> _ImportBinding:
        specifier = self._source_specifier(module, node) or ""
        clause = next((child for child in node.named_children if child.type == "import_clause"), None)
        default = None
        namespace = None
        named: list[tuple[str, str]] = []
        if clause is not None:
            for child in clause.named_children:
                if child.type == "identifier":
                    default = self._text(module, child)
                elif child.type == "namespace_import":
                    identifier = next((item for item in child.named_children if item.type == "identifier"), None)
                    namespace = self._text(module, identifier) if identifier else None
                elif child.type == "named_imports":
                    for item in child.named_children:
                        if item.type != "import_specifier":
                            continue
                        imported_node = item.child_by_field_name("name")
                        alias_node = item.child_by_field_name("alias")
                        if imported_node is None:
                            continue
                        imported = self._text(module, imported_node)
                        named.append((self._text(module, alias_node) if alias_node else imported, imported))
        return _ImportBinding(specifier, default, namespace, tuple(named))

    def _export_dependency(
        self,
        node: SyntaxNode,
        specifier: str,
        module: _ParsedModule,
    ) -> _ImportBinding:
        named: list[tuple[str, str]] = []
        clause = next((child for child in node.named_children if child.type == "export_clause"), None)
        if clause is not None:
            for item in clause.named_children:
                name_node = item.child_by_field_name("name")
                alias_node = item.child_by_field_name("alias")
                if name_node is None:
                    continue
                imported = self._text(module, name_node)
                named.append((self._text(module, alias_node) if alias_node else imported, imported))
        return _ImportBinding(specifier, named=tuple(named))

    def _export_aliases(self, module: _ParsedModule, node: SyntaxNode) -> list[tuple[str, str]]:
        if node.child_by_field_name("source") is not None:
            return []
        aliases = []
        clause = next((child for child in node.named_children if child.type == "export_clause"), None)
        if clause is None:
            return aliases
        for item in clause.named_children:
            name_node = item.child_by_field_name("name")
            alias_node = item.child_by_field_name("alias")
            if name_node is None:
                continue
            local = self._text(module, name_node)
            aliases.append((local, self._text(module, alias_node) if alias_node else local))
        return aliases

    def _collect_commonjs_imports(self, module: _ParsedModule) -> None:
        for statement in module.tree.root_node.named_children:
            if statement.type not in {"lexical_declaration", "variable_declaration"}:
                continue
            for declarator in (child for child in statement.named_children if child.type == "variable_declarator"):
                value = declarator.child_by_field_name("value")
                specifier = self._require_specifier(module, value)
                if not specifier:
                    continue
                name_node = declarator.child_by_field_name("name")
                if name_node is None:
                    module.imports.append(_ImportBinding(specifier))
                elif name_node.type == "identifier":
                    module.imports.append(_ImportBinding(specifier, namespace=self._text(module, name_node)))
                elif name_node.type == "object_pattern":
                    named = []
                    for child in name_node.named_children:
                        if child.type in {"shorthand_property_identifier_pattern", "identifier"}:
                            name = self._text(module, child)
                            named.append((name, name))
                        elif child.type == "pair_pattern":
                            key = child.child_by_field_name("key")
                            value_node = child.child_by_field_name("value")
                            if key is not None and value_node is not None:
                                named.append((self._text(module, value_node), self._text(module, key)))
                    module.imports.append(_ImportBinding(specifier, named=tuple(named)))

    def _resolve_module(
        self,
        module: _ParsedModule,
        by_path: dict[Path, _ParsedModule],
        edges: set[tuple[str, str, str]],
    ) -> None:
        named_bindings: dict[str, str] = {}
        namespace_bindings: dict[str, _ParsedModule] = {}
        for binding in module.imports:
            target = self._resolve_import(module.source.path, binding.specifier, by_path)
            if target is None:
                continue
            edges.add((module.module_id, target.module_id, "depends_on"))
            if binding.default and target.default_export:
                named_bindings[binding.default] = target.default_export
            if binding.namespace:
                namespace_bindings[binding.namespace] = target
            for local, imported in binding.named:
                target_id = target.exports.get(imported)
                if target_id:
                    named_bindings[local] = target_id

        for scope in module.call_scopes:
            for call in self._call_expressions(scope.body):
                target = self._resolve_call(module, scope, call, named_bindings, namespace_bindings)
                if target and target != scope.source_id:
                    edges.add((scope.source_id, target, "calls"))

    def _resolve_call(
        self,
        module: _ParsedModule,
        scope: _CallScope,
        call: SyntaxNode,
        named_bindings: dict[str, str],
        namespace_bindings: dict[str, _ParsedModule],
    ) -> str | None:
        function = call.child_by_field_name("function")
        if function is None:
            return None
        if function.type == "identifier":
            name = self._text(module, function)
            imported = named_bindings.get(name)
            if imported and self._callable(imported):
                return imported
            local = self._unique(module.declarations.get(name, set()))
            return local if local and self._callable(local) else None
        if function.type not in {"member_expression", "subscript_expression"}:
            return None
        object_node = function.child_by_field_name("object")
        property_node = function.child_by_field_name("property") or function.child_by_field_name("index")
        if object_node is None or property_node is None:
            return None
        property_name = self._text(module, property_node).strip("\"'")
        if object_node.type == "this" and scope.class_id:
            return module.methods.get((scope.class_id, property_name))
        if object_node.type == "identifier":
            namespace = namespace_bindings.get(self._text(module, object_node))
            if namespace:
                target = namespace.exports.get(property_name)
                return target if target and self._callable(target) else None
        return None

    @staticmethod
    def _call_expressions(body: SyntaxNode) -> list[SyntaxNode]:
        calls: list[SyntaxNode] = []

        def visit(node: SyntaxNode, *, root: bool = False) -> None:
            if not root and node.type in _FUNCTION_NODES:
                return
            if node.type == "call_expression":
                calls.append(node)
            for child in node.named_children:
                visit(child)

        visit(body, root=True)
        return calls

    @staticmethod
    def _resolve_import(
        source_path: Path,
        specifier: str,
        by_path: dict[Path, _ParsedModule],
    ) -> _ParsedModule | None:
        if not specifier.startswith("."):
            return None
        base = source_path.parent / specifier
        candidates = [base] if base.suffix.lower() in SCRIPT_SOURCE_SUFFIXES else []
        suffixes = dict.fromkeys((source_path.suffix.lower(), *_RESOLUTION_SUFFIXES))
        if not candidates:
            candidates.extend(base.with_suffix(suffix) for suffix in suffixes)
            candidates.extend(base / f"index{suffix}" for suffix in suffixes)
        for candidate in candidates:
            target = by_path.get(candidate.resolve())
            if target:
                return target
        return None

    def _source_specifier(self, module: _ParsedModule, node: SyntaxNode) -> str | None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return None
        fragment = next((child for child in source_node.named_children if child.type == "string_fragment"), None)
        return self._text(module, fragment) if fragment else self._text(module, source_node).strip("\"'")

    def _require_specifier(self, module: _ParsedModule, node: SyntaxNode | None) -> str | None:
        if node is None or node.type != "call_expression":
            return None
        function = node.child_by_field_name("function")
        if function is None or function.type != "identifier" or self._text(module, function) != "require":
            return None
        arguments = node.child_by_field_name("arguments")
        if arguments is None:
            return None
        strings = [child for child in arguments.named_children if child.type == "string"]
        if len(strings) != 1:
            return None
        fragment = next((child for child in strings[0].named_children if child.type == "string_fragment"), None)
        return self._text(module, fragment) if fragment else None

    @staticmethod
    def _unique(values: set[str]) -> str | None:
        return next(iter(values)) if len(values) == 1 else None

    @staticmethod
    def _callable(node_id: str) -> bool:
        return node_id.startswith(("function:", "method:"))

    @staticmethod
    def _text(module: _ParsedModule, node: SyntaxNode | None) -> str:
        if node is None:
            return ""
        return module.content[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
