import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hero_graph_lab.explore.tools import ExploreToolRegistry, GraphIndex, ToolEnvironment

from hero_graph_lab.extractor import (
    Edge,
    extract_project_graph,
    extract_python_graph,
    merge_markdown_containment_edges,
    project_source_files,
    python_source_files,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_service.py"


class PythonGraphExtractorTest(TestCase):
    def test_markdown_containment_integration(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            (project / "service.py").write_text(
                "class Service:\n    pass\n",
                encoding="utf-8",
            )
            (project / "README.md").write_text(
                "# Project\n\nSee `Service` for details.\n",
                encoding="utf-8",
            )

            graph = extract_project_graph(project)

        nodes = {node["id"]: node for node in graph["nodes"]}
        document_id = "document:project.README"
        service_id = "class:project.service.Service"
        self.assertIn(document_id, nodes)
        self.assertIn(service_id, nodes)
        self.assertIn(
            {"source": "package:project", "target": document_id, "kind": "contains"},
            graph["edges"],
        )
        self.assertIn(
            {"source": document_id, "target": service_id, "kind": "references"},
            graph["edges"],
        )

        environment = ToolEnvironment(project.resolve(), GraphIndex(graph))
        registry = ExploreToolRegistry()
        neighbors = json.loads(
            registry.execute(
                "GraphNeighbors",
                {"node_id": "package:project", "direction": "outgoing", "relation": "contains"},
                environment,
            )
        )
        scope = json.loads(
            registry.execute("GraphScope", {"node_id": "package:project", "depth": 1}, environment)
        )

        self.assertIn(document_id, {node["id"] for node in neighbors["neighbors"]})
        self.assertIn(document_id, {node["id"] for node in scope["nodes"]})

    def test_merge_markdown_containment_edges_deduplicates_preserves_order_and_excludes_references(self) -> None:
        existing = [
            Edge("package:project", "document:existing", "contains"),
            Edge("document:existing", "function:run", "references"),
        ]
        document_edges = [
            {"source": "package:project", "target": "document:existing", "kind": "contains"},
            {"source": "package:project", "target": "document:first", "kind": "contains"},
            {"source": "document:first", "target": "function:run", "kind": "references"},
            {"source": "package:project", "target": "document:second", "kind": "contains"},
            {"source": "package:project", "target": "document:first", "kind": "contains"},
        ]

        result = existing
        merge_markdown_containment_edges(document_edges, result)

        self.assertIs(result, existing)
        self.assertEqual(
            result,
            [
                Edge("package:project", "document:existing", "contains"),
                Edge("document:existing", "function:run", "references"),
                Edge("package:project", "document:first", "contains"),
                Edge("package:project", "document:second", "contains"),
            ],
        )

    def test_single_python_project_graph_always_exposes_module_root(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "service.py"
            path.write_text("class Service:\n    pass\n", encoding="utf-8")

            graph = extract_project_graph(path)

        self.assertEqual(set(graph), {"source", "root", "nodes", "edges"})
        self.assertEqual(graph["root"], "module:service")

    def test_exposes_script_symbols_while_css_and_html_remain_file_nodes(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            static = project / "src" / "web" / "static"
            static.mkdir(parents=True)
            python_file = project / "src" / "service.py"
            javascript_file = static / "app.js"
            stylesheet = static / "styles.css"
            page = static / "index.html"
            python_file.write_text("def run():\n    return True\n", encoding="utf-8")
            javascript_file.write_text("export function render() {}\n", encoding="utf-8")
            stylesheet.write_text("body { color: black; }\n", encoding="utf-8")
            page.write_text("<main>Graph Lab</main>\n", encoding="utf-8")
            (project / "README.md").write_text("not a code anchor\n", encoding="utf-8")

            files = project_source_files(project)
            graph = extract_project_graph(project)

        self.assertEqual(files, [project / "README.md", python_file, javascript_file, page, stylesheet])
        nodes = {node["id"]: node for node in graph["nodes"]}
        javascript_node = next(
            node
            for node in nodes.values()
            if node["source"] == "src/web/static/app.js" and node["kind"] == "module"
        )
        self.assertEqual(javascript_node["kind"], "module")
        self.assertEqual(javascript_node["label"], "app.js")
        self.assertEqual(javascript_node["parent"], "package:project.src.web.static")
        render_node = next(
            node for node in nodes.values() if node["source"] == "src/web/static/app.js" and node["label"] == "render"
        )
        self.assertEqual(render_node["kind"], "function")
        self.assertEqual(render_node["parent"], javascript_node["id"])
        self.assertEqual(
            {node["kind"] for node in nodes.values() if node["source"] in {"src/web/static/styles.css", "src/web/static/index.html"}},
            {"file"},
        )
        readme_nodes = [node for node in nodes.values() if node["source"] == "README.md"]
        self.assertEqual(len(readme_nodes), 1)
        self.assertEqual(readme_nodes[0]["kind"], "document")

    def test_ignores_generated_and_virtual_environment_directories(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            (project / "src").mkdir(parents=True)
            (project / ".venv" / "Lib" / "site-packages").mkdir(parents=True)
            (project / "build").mkdir()
            included = project / "src" / "service.py"
            included.write_text("def run():\n    return True\n", encoding="utf-8")
            (project / ".venv" / "Lib" / "site-packages" / "dependency.py").write_text(
                "def external():\n    return False\n",
                encoding="utf-8",
            )
            (project / "build" / "generated.py").write_text(
                "def generated():\n    return False\n",
                encoding="utf-8",
            )

            files = python_source_files(project)
            graph = extract_python_graph(project)

        self.assertEqual(files, [included])
        sources = {node["source"] for node in graph["nodes"] if node["source"]}
        self.assertEqual(sources, {"src/service.py"})

    def test_extracts_stable_structure_and_calls(self) -> None:
        first = extract_python_graph(FIXTURE)
        second = extract_python_graph(FIXTURE)

        self.assertEqual(first, second)
        self.assertEqual(first["source"], "order_service.py")
        self.assertIn(
            {
                "source": "method:OrderService.place",
                "target": "method:PricingPolicy.discounted_total",
                "kind": "calls",
            },
            first["edges"],
        )
        self.assertIn(
            {
                "source": "method:OrderService.place",
                "target": "function:format_confirmation",
                "kind": "calls",
            },
            first["edges"],
        )

    def test_extracts_package_depth_and_cross_module_calls(self) -> None:
        with TemporaryDirectory() as directory:
            package = Path(directory) / "shop"
            (package / "domain").mkdir(parents=True)
            (package / "application").mkdir()
            (package / "domain" / "models.py").write_text(
                "class Order:\n    def total(self) -> float:\n        return 10.0\n",
                encoding="utf-8",
            )
            (package / "application" / "order_service.py").write_text(
                "class OrderService:\n    def place(self, order) -> float:\n        return order.total()\n",
                encoding="utf-8",
            )

            graph = extract_python_graph(package)

        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(graph["source"], "shop")
        self.assertEqual(nodes["package:shop.application"]["parent"], "package:shop")
        self.assertEqual(
            nodes["module:shop.application.order_service"]["parent"],
            "package:shop.application",
        )
        self.assertEqual(
            nodes["class:shop.application.order_service.OrderService"]["parent"],
            "module:shop.application.order_service",
        )
        self.assertEqual(
            nodes["method:shop.application.order_service.OrderService.place"]["source"],
            "application/order_service.py",
        )
        self.assertIn(
            {
                "source": "method:shop.application.order_service.OrderService.place",
                "target": "method:shop.domain.models.Order.total",
                "kind": "calls",
            },
            graph["edges"],
        )

    def test_extracts_package_containing_only_init_file(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            package = project / "src" / "policies" / "datagravity"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")

            graph = extract_python_graph(project)

        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(
            nodes["package:project.src.policies.datagravity"]["parent"],
            "package:project.src.policies",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
