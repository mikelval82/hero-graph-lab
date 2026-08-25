from pathlib import Path
from unittest import TestCase

from hero_graph_lab.typescript_adapter import ScriptSource, TypeScriptGraphAdapter


FIXTURE = Path(__file__).parents[1] / "fixtures" / "typescript_app"
PROJECT_STATIC = Path(__file__).parents[1] / "src" / "hero_graph_lab" / "static"


def script_sources() -> list[ScriptSource]:
    return [
        ScriptSource(
            path=path,
            module_name=".".join((FIXTURE.name, *path.relative_to(FIXTURE).with_suffix("").parts)),
            module_parent=f"package:{FIXTURE.name}.src",
            source=path.relative_to(FIXTURE).as_posix(),
        )
        for path in sorted((FIXTURE / "src").iterdir())
    ]


class TypeScriptGraphAdapterTest(TestCase):
    def test_extracts_the_real_frontend_repeatably(self) -> None:
        sources = [
            ScriptSource(
                path=path,
                module_name=f"hero_graph_lab.static.{path.stem}",
                module_parent="package:hero_graph_lab.static",
                source=path.relative_to(PROJECT_STATIC.parents[2]).as_posix(),
            )
            for path in sorted(PROJECT_STATIC.glob("*.js"))
        ]

        first = TypeScriptGraphAdapter().extract(sources)
        second = TypeScriptGraphAdapter().extract(sources)

        self.assertEqual(first, second)
        nodes = {node["id"]: node for node in first["nodes"]}
        self.assertEqual(
            nodes["module:hero_graph_lab.static.app"]["source"],
            "src/hero_graph_lab/static/app.js",
        )
        self.assertEqual(
            nodes["function:hero_graph_lab.static.app.renderCodePanel"]["line"],
            1350,
        )

    def test_extracts_typescript_declarations_with_exact_containment(self) -> None:
        graph = TypeScriptGraphAdapter().extract(script_sources())
        nodes = {node["id"]: node for node in graph["nodes"]}

        self.assertEqual(nodes["module:typescript_app.src.gateway"]["source"], "src/gateway.ts")
        self.assertEqual(nodes["interface:typescript_app.src.gateway.MessagePort"]["kind"], "interface")
        self.assertEqual(
            nodes["method:typescript_app.src.gateway.MessagePort.send"]["parent"],
            "interface:typescript_app.src.gateway.MessagePort",
        )
        self.assertEqual(nodes["type:typescript_app.src.gateway.Command"]["kind"], "type")
        self.assertEqual(nodes["type:typescript_app.src.gateway.DeliveryState"]["label"], "DeliveryState")
        self.assertEqual(
            nodes["method:typescript_app.src.gateway.TelegramGateway.send"]["parent"],
            "class:typescript_app.src.gateway.TelegramGateway",
        )
        self.assertEqual(nodes["function:typescript_app.src.gateway.format"]["line"], 25)
        self.assertEqual(nodes["function:typescript_app.src.card.NotificationCard"]["kind"], "function")

    def test_resolves_relative_dependencies_and_only_evidenced_calls(self) -> None:
        graph = TypeScriptGraphAdapter().extract(script_sources())
        edges = {
            (edge["source"], edge["target"], edge["kind"])
            for edge in graph["edges"]
        }

        gateway_module = "module:typescript_app.src.gateway"
        service_module = "module:typescript_app.src.service"
        legacy_module = "module:typescript_app.src.legacy"
        self.assertIn((service_module, gateway_module, "depends_on"), edges)
        self.assertIn((legacy_module, gateway_module, "depends_on"), edges)
        self.assertIn(
            (
                "method:typescript_app.src.service.NotificationService.notify",
                "function:typescript_app.src.gateway.format",
                "calls",
            ),
            edges,
        )
        self.assertIn(
            (
                "method:typescript_app.src.service.NotificationService.notify",
                "method:typescript_app.src.service.NotificationService.deliver",
                "calls",
            ),
            edges,
        )
        self.assertIn(
            (
                "function:typescript_app.src.legacy.dispatch",
                "function:typescript_app.src.gateway.format",
                "calls",
            ),
            edges,
        )
        self.assertFalse(any("telegram" in edge["target"] for edge in graph["edges"]))
        self.assertFalse(
            any(
                edge["source"] == "method:typescript_app.src.service.NotificationService.deliver"
                and edge["kind"] == "calls"
                for edge in graph["edges"]
            )
        )

    def test_keeps_malformed_modules_and_is_input_order_independent(self) -> None:
        sources = script_sources()
        first = TypeScriptGraphAdapter().extract(sources)
        second = TypeScriptGraphAdapter().extract(list(reversed(sources)))

        self.assertEqual(first, second)
        node_ids = {node["id"] for node in first["nodes"]}
        self.assertIn("module:typescript_app.src.broken", node_ids)
        self.assertIn("function:typescript_app.src.broken.beforeError", node_ids)
        self.assertIn("function:typescript_app.src.broken.afterError", node_ids)


if __name__ == "__main__":
    import unittest

    unittest.main()
