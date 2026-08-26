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


@dataclass(frozen=True)
class _GlobalProvider:
    module: _ParsedModule
    members: dict[str, str]


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
    statements: tuple[SyntaxNode, ...] = ()
    global_roots: set[str] = field(default_factory=lambda: {"globalThis"})
    global_providers: dict[str, dict[str, str]] = field(default_factory=dict)
    global_aliases: dict[str, str] = field(default_factory=dict)
    global_references: set[str] = field(default_factory=set)

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
        provider_candidates: dict[str, list[_GlobalProvider]] = defaultdict(list)
        for module in parsed:
            for namespace, members in module.global_providers.items():
                provider_candidates[namespace].append(_GlobalProvider(module, members))
        global_apis = {
            namespace: providers[0]
            for namespace, providers in provider_candidates.items()
            if len(providers) == 1
        }
        edges: set[tuple[str, str, str]] = set()
        for module in parsed:
            edges.update(module.containment)
            self._resolve_module(module, by_path, global_apis, edges)
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
        module.statements = self._module_statements(module)
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
        for statement in module.statements:
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
        self._collect_script_bindings(module)
        self._collect_commonjs_imports(module)
        return module

    def _language(self, path: Path) -> Language:
        suffix = path.suffix.lower()
        if suffix in {".jsx", ".tsx"}:
            return self._tsx
        if suffix == ".ts":
            return self._typescript
        return self._javascript

    def _module_statements(self, module: _ParsedModule) -> tuple[SyntaxNode, ...]:
        statements: list[SyntaxNode] = []
        for statement in module.tree.root_node.named_children:
            wrapper = self._root_iife(statement)
            if wrapper is None:
                statements.append(statement)
                continue
            callable_node, call = wrapper
            body = callable_node.child_by_field_name("body")
            if body is None or body.type != "statement_block":
                statements.append(statement)
                continue
            statements.extend(body.named_children)
            parameters = callable_node.child_by_field_name("parameters")
            arguments = call.child_by_field_name("arguments")
            if parameters is None or arguments is None:
                continue
            parameter_nodes = [child for child in parameters.named_children if child.type == "identifier"]
            for parameter, argument in zip(parameter_nodes, arguments.named_children):
                if self._contains_global_object(module, argument):
                    module.global_roots.add(self._text(module, parameter))
        return tuple(statements)

    @staticmethod
    def _root_iife(statement: SyntaxNode) -> tuple[SyntaxNode, SyntaxNode] | None:
        if statement.type != "expression_statement" or len(statement.named_children) != 1:
            return None
        call = statement.named_children[0]
        if call.type != "call_expression":
            return None
        function = call.child_by_field_name("function")
        while function is not None and function.type == "parenthesized_expression":
            function = function.named_children[0] if len(function.named_children) == 1 else None
        if function is None or function.type not in {"arrow_function", "function_expression", "generator_function"}:
            return None
        return function, call

    def _contains_global_object(self, module: _ParsedModule, node: SyntaxNode) -> bool:
        if node.type == "this":
            return True
        if node.type == "identifier" and self._text(module, node) == "globalThis":
            return True
        return any(self._contains_global_object(module, child) for child in node.named_children)

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

    def _collect_script_bindings(self, module: _ParsedModule) -> None:
        object_bindings: dict[str, dict[str, str]] = {}
        for statement in module.statements:
            if statement.type not in {"lexical_declaration", "variable_declaration"}:
                continue
            for declarator in (child for child in statement.named_children if child.type == "variable_declarator"):
                name_node = declarator.child_by_field_name("name")
                value = declarator.child_by_field_name("value")
                if name_node is None or name_node.type != "identifier" or value is None:
                    continue
                members = self._object_member_names(module, value)
                if members is not None:
                    object_bindings[self._text(module, name_node)] = members

        for assignment in self._module_assignments(module.statements):
            left = assignment.child_by_field_name("left")
            right = assignment.child_by_field_name("right")
            if left is None or right is None:
                continue
            global_path = self._global_access_parts(module, left)
            members = self._resolved_object_members(module, right, object_bindings)
            if global_path is not None and len(global_path) == 1:
                module.global_providers[global_path[0]] = members
                continue
            if self._is_module_exports(module, left):
                module.exports.update(members)

        for statement in module.statements:
            for node in self._walk(statement):
                global_path = self._global_access_parts(module, node)
                if global_path:
                    module.global_references.add(global_path[0])
        module.global_aliases = self._global_alias_bindings(module, module.statements)

    def _object_member_names(self, module: _ParsedModule, value: SyntaxNode) -> dict[str, str] | None:
        object_node = value if value.type == "object" else None
        if value.type == "call_expression":
            function = value.child_by_field_name("function")
            arguments = value.child_by_field_name("arguments")
            if self._static_member(module, function) == ("Object", "freeze") and arguments is not None:
                object_node = next((child for child in arguments.named_children if child.type == "object"), None)
        if object_node is None:
            return None
        members: dict[str, str] = {}
        for child in object_node.named_children:
            if child.type in {"shorthand_property_identifier", "shorthand_property_identifier_pattern"}:
                name = self._text(module, child)
                members[name] = name
            elif child.type == "pair":
                key = child.child_by_field_name("key")
                member_value = child.child_by_field_name("value")
                if key is None or member_value is None or member_value.type != "identifier":
                    continue
                members[self._text(module, key).strip("\"'")] = self._text(module, member_value)
        return members

    def _resolved_object_members(
        self,
        module: _ParsedModule,
        value: SyntaxNode,
        object_bindings: dict[str, dict[str, str]],
    ) -> dict[str, str]:
        if value.type == "identifier":
            member_names = object_bindings.get(self._text(module, value), {})
        else:
            member_names = self._object_member_names(module, value) or {}
        resolved: dict[str, str] = {}
        for public_name, local_name in member_names.items():
            target = self._unique(module.declarations.get(local_name, set()))
            if target:
                resolved[public_name] = target
        return resolved

    @classmethod
    def _module_assignments(cls, statements: tuple[SyntaxNode, ...]) -> list[SyntaxNode]:
        assignments: list[SyntaxNode] = []

        def visit(node: SyntaxNode) -> None:
            if node.type in _FUNCTION_NODES or node.type in {
                "class",
                "class_declaration",
                "class_expression",
                "abstract_class_declaration",
            }:
                return
            if node.type == "assignment_expression":
                assignments.append(node)
                return
            for child in node.named_children:
                visit(child)

        for statement in statements:
            visit(statement)
        return assignments

    def _global_access_parts(self, module: _ParsedModule, node: SyntaxNode) -> tuple[str, ...] | None:
        if node.type != "member_expression":
            return None
        object_node = node.child_by_field_name("object")
        property_node = node.child_by_field_name("property")
        if object_node is None or property_node is None:
            return None
        property_name = self._text(module, property_node)
        if object_node.type == "identifier" and self._text(module, object_node) in module.global_roots:
            return (property_name,)
        prefix = self._global_access_parts(module, object_node)
        return (*prefix, property_name) if prefix is not None else None

    def _is_module_exports(self, module: _ParsedModule, node: SyntaxNode) -> bool:
        return self._static_member(module, node) == ("module", "exports")

    def _static_member(self, module: _ParsedModule, node: SyntaxNode | None) -> tuple[str, str] | None:
        if node is None or node.type != "member_expression":
            return None
        object_node = node.child_by_field_name("object")
        property_node = node.child_by_field_name("property")
        if object_node is None or object_node.type != "identifier" or property_node is None:
            return None
        return self._text(module, object_node), self._text(module, property_node)

    @staticmethod
    def _walk(node: SyntaxNode) -> Iterable[SyntaxNode]:
        yield node
        for child in node.named_children:
            yield from TypeScriptGraphAdapter._walk(child)

    def _global_alias_bindings(
        self,
        module: _ParsedModule,
        roots: Iterable[SyntaxNode],
    ) -> dict[str, str]:
        candidates: dict[str, set[str]] = defaultdict(set)

        def visit(node: SyntaxNode) -> None:
            if node.type in _FUNCTION_NODES:
                return
            if node.type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                value = node.child_by_field_name("value")
                if name_node is not None and name_node.type == "identifier" and value is not None:
                    alias_path = self._global_access_parts(module, value)
                    if alias_path is not None and len(alias_path) == 1:
                        candidates[self._text(module, name_node)].add(alias_path[0])
            for child in node.named_children:
                visit(child)

        for root in roots:
            visit(root)
        return {
            local: next(iter(namespaces))
            for local, namespaces in candidates.items()
            if len(namespaces) == 1
        }

    def _collect_commonjs_imports(self, module: _ParsedModule) -> None:
        for statement in module.statements:
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
        global_apis: dict[str, _GlobalProvider],
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

        module_global_aliases = {
            local: global_apis[namespace]
            for local, namespace in module.global_aliases.items()
            if namespace in global_apis
        }
        for namespace in module.global_references:
            provider = global_apis.get(namespace)
            if provider and provider.module.module_id != module.module_id:
                edges.add((module.module_id, provider.module.module_id, "depends_on"))

        for scope in module.call_scopes:
            scope_aliases = {
                local: global_apis[namespace]
                for local, namespace in self._global_alias_bindings(module, (scope.body,)).items()
                if namespace in global_apis
            }
            for call in self._call_expressions(scope.body):
                target = self._resolve_call(
                    module,
                    scope,
                    call,
                    named_bindings,
                    namespace_bindings,
                    {**module_global_aliases, **scope_aliases},
                    global_apis,
                )
                if target and target != scope.source_id:
                    edges.add((scope.source_id, target, "calls"))

    def _resolve_call(
        self,
        module: _ParsedModule,
        scope: _CallScope,
        call: SyntaxNode,
        named_bindings: dict[str, str],
        namespace_bindings: dict[str, _ParsedModule],
        global_aliases: dict[str, _GlobalProvider],
        global_apis: dict[str, _GlobalProvider],
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
        global_path = self._global_access_parts(module, function)
        if global_path is not None and len(global_path) == 2:
            provider = global_apis.get(global_path[0])
            target = provider.members.get(global_path[1]) if provider else None
            return target if target and self._callable(target) else None
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
            object_name = self._text(module, object_node)
            global_provider = global_aliases.get(object_name)
            if global_provider:
                target = global_provider.members.get(property_name)
                return target if target and self._callable(target) else None
            namespace = namespace_bindings.get(object_name)
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
