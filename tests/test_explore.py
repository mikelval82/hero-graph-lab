from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from hero_graph_lab.explore.clients import FakeModelClient, GeminiModelClient
from hero_graph_lab.explore.models import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
    ToolSpec,
)
from hero_graph_lab.explore.service import ExploreAssistantService
from hero_graph_lab.explore.tools import ExploreToolRegistry, GraphIndex, ToolEnvironment
from hero_graph_lab.extractor import extract_python_graph


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_app"


class FakeGeminiPart:
    @staticmethod
    def from_text(*, text: str) -> SimpleNamespace:
        return SimpleNamespace(text=text, function_call=None, thought=False)

    @staticmethod
    def from_function_response(*, name: str, response: dict) -> SimpleNamespace:
        return SimpleNamespace(function_response=SimpleNamespace(name=name, response=response))


class ExploreAssistantTest(TestCase):
    def test_when_gemini_request_fails_expect_runtime_error(self) -> None:
        def generate_content(**kwargs):  # noqa: ANN003, ANN202
            del kwargs
            raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")

        fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        fake_types = SimpleNamespace(
            FunctionDeclaration=lambda **kwargs: kwargs,
            Tool=lambda **kwargs: kwargs,
            GenerateContentConfig=lambda **kwargs: kwargs,
            AutomaticFunctionCallingConfig=lambda **kwargs: kwargs,
            Content=lambda **kwargs: SimpleNamespace(**kwargs),
            Part=FakeGeminiPart,
        )
        client = GeminiModelClient("gemini-2.5-flash", client=fake_client, types_module=fake_types)

        with self.assertRaisesRegex(RuntimeError, "429 RESOURCE_EXHAUSTED: quota exceeded"):
            client.complete(ModelRequest("Explore safely.", (), ()))

    def test_gemini_translates_tools_and_preserves_function_call_content(self) -> None:
        original_content = SimpleNamespace(
            parts=[
                SimpleNamespace(text="Inspecting the graph.", function_call=None, thought=False),
                SimpleNamespace(
                    text=None,
                    thought=False,
                    function_call=SimpleNamespace(
                        id="call-1",
                        name="GraphSearch",
                        args={"query": "OrderService"},
                    ),
                ),
            ]
        )
        response = SimpleNamespace(
            candidates=[SimpleNamespace(content=original_content, finish_reason="STOP")],
            usage_metadata=SimpleNamespace(prompt_token_count=31, candidates_token_count=7),
        )
        generated: dict = {}

        def generate_content(**kwargs):  # noqa: ANN003, ANN202
            generated.update(kwargs)
            return response

        fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        fake_types = SimpleNamespace(
            FunctionDeclaration=lambda **kwargs: kwargs,
            Tool=lambda **kwargs: kwargs,
            GenerateContentConfig=lambda **kwargs: kwargs,
            AutomaticFunctionCallingConfig=lambda **kwargs: kwargs,
            Content=lambda **kwargs: SimpleNamespace(**kwargs),
            Part=FakeGeminiPart,
        )
        client = GeminiModelClient("gemini-2.5-flash", client=fake_client, types_module=fake_types)

        result = client.complete(
            ModelRequest(
                "Explore safely.",
                (ModelMessage("user", "Find the service"),),
                (ToolSpec("GraphSearch", "Search nodes", {"type": "object"}),),
            )
        )

        self.assertEqual(result.text, "Inspecting the graph.")
        self.assertEqual(result.usage, ModelUsage(31, 7))
        self.assertEqual(result.tool_calls[0].arguments, {"query": "OrderService"})
        self.assertIs(result.tool_calls[0].provider_payload, original_content)
        self.assertEqual(generated["config"]["tools"][0]["function_declarations"][0]["name"], "GraphSearch")

        translated = client._messages(
            (
                ModelMessage("assistant", result.text, result.tool_calls),
                ModelMessage("tool", "[]", tool_call_id="call-1", tool_name="GraphSearch"),
            )
        )
        self.assertIs(translated[0], original_content)
        self.assertEqual(translated[1].role, "tool")
        self.assertEqual(translated[1].parts[0].function_response.response["result"], "[]")

    def test_runs_provider_neutral_tool_loop_without_exposing_injected_context(self) -> None:
        graph = extract_python_graph(FIXTURE)
        selected = next(node for node in graph["nodes"] if node["kind"] == "module")
        client = FakeModelClient(
            [
                ModelResponse(tool_calls=(ToolCall("call-1", "GraphGetNode", {"node_id": selected["id"]}),)),
                ModelResponse("This module is grounded in the graph.", usage=ModelUsage(12, 8)),
            ]
        )
        service = ExploreAssistantService(client, lambda: FIXTURE, lambda: graph)
        session_id = service.create_session()["id"]

        result = service.send_message(
            session_id,
            "What is this module?",
            {"selectedNodeId": selected["id"], "visibleNodeIds": [selected["id"]]},
        )

        self.assertEqual([message["content"] for message in result["messages"]], [
            "What is this module?",
            "This module is grounded in the graph.",
        ])
        self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 8})
        self.assertEqual(len(client.requests), 2)
        self.assertIn("Always answer in Spanish", client.requests[0].system_prompt)
        self.assertIn("Current Graph Lab context", client.requests[0].messages[0].content)
        self.assertEqual(client.requests[1].messages[-1].tool_name, "GraphGetNode")

    def test_read_only_tools_confine_paths_and_find_graph_paths(self) -> None:
        graph = GraphIndex(extract_python_graph(FIXTURE))
        environment = ToolEnvironment(FIXTURE.resolve(), graph)
        registry = ExploreToolRegistry()
        module = next(node for node in graph.nodes.values() if node["kind"] == "module")
        parent = graph.node(module["parent"])

        path = registry.execute(
            "GraphPath",
            {"source_id": parent["id"], "target_id": module["id"], "relation": "contains"},
            environment,
        )
        self.assertIn(module["id"], path)
        self.assertIn("order_service.py", registry.execute("Glob", {"pattern": "**/*.py"}, environment))
        self.assertIn("class OrderService", registry.execute("Grep", {"pattern": "class OrderService"}, environment))

        with TemporaryDirectory() as directory:
            outside = Path(directory) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside"):
                registry.execute("Read", {"path": str(outside)}, environment)

    def test_graph_tools_search_neighbors_and_containment_scope(self) -> None:
        graph = GraphIndex(extract_python_graph(FIXTURE))
        environment = ToolEnvironment(FIXTURE.resolve(), graph)
        registry = ExploreToolRegistry()
        contains = next(edge for edge in graph.edges if edge["kind"] == "contains")

        search = json.loads(registry.execute("GraphSearch", {"query": "OrderService"}, environment))
        neighbors = json.loads(
            registry.execute(
                "GraphNeighbors",
                {"node_id": contains["source"], "direction": "outgoing", "relation": "contains"},
                environment,
            )
        )
        scope = json.loads(
            registry.execute("GraphScope", {"node_id": contains["source"], "depth": 1}, environment)
        )

        self.assertTrue(any(node["label"] == "OrderService" for node in search))
        self.assertIn(contains["target"], {node["id"] for node in neighbors["neighbors"]})
        self.assertIn(contains["target"], {node["id"] for node in scope["nodes"]})

    def test_rejects_unknown_sessions_empty_messages_and_excessive_tool_turns(self) -> None:
        graph = extract_python_graph(FIXTURE)
        client = FakeModelClient(
            [ModelResponse(tool_calls=(ToolCall("call-1", "GraphSearch", {"query": "order"}),))]
        )
        service = ExploreAssistantService(client, lambda: FIXTURE, lambda: graph, max_turns=1)
        session_id = service.create_session()["id"]

        with self.assertRaisesRegex(KeyError, "unknown explore session"):
            service.session("missing")
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            service.send_message(session_id, "  ")
        with self.assertRaisesRegex(RuntimeError, "tool turn limit"):
            service.send_message(session_id, "Keep searching")