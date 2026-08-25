from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hero_graph_lab.extractor import (
    extract_project_graph,
    extract_python_graph,
    project_source_files,
    python_source_files,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_service.py"


class PythonGraphExtractorTest(TestCase):
    def test_exposes_supported_web_sources_as_file_nodes_without_invented_symbols(self) -> None:
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

        self.assertEqual(files, [python_file, javascript_file, page, stylesheet])
        nodes = {node["id"]: node for node in graph["nodes"]}
        javascript_node = next(
            node for node in nodes.values() if node["source"] == "src/web/static/app.js"
        )
        self.assertEqual(javascript_node["kind"], "file")
        self.assertEqual(javascript_node["label"], "app.js")
        self.assertEqual(javascript_node["parent"], "package:project.src.web.static")
        self.assertFalse(any(edge["source"] == javascript_node["id"] for edge in graph["edges"]))
        self.assertNotIn("README.md", {node["source"] for node in nodes.values()})

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
