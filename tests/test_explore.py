from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from hero_graph_lab.explore.clients import DeepSeekModelClient, FakeModelClient, GeminiModelClient
from hero_graph_lab.explore.models import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
    ToolSpec,
)
from hero_graph_lab.explore.service import ExploreAssistantService
from hero_graph_lab.explore.service import SYSTEM_PROMPT
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


class FakeContractTools:
    def __init__(self, *, owner: str | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.owner = owner

    def tool_specs(self) -> list[dict]:
        from hero_graph_lab.contract_gateway import HarnessContractGateway

        return HarnessContractGateway(
            SimpleNamespace(),
            actor="chat",
            include_chat_tools=True,
        ).tool_specs()

    def execute(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "ContractListTasks":
            execution = (
                {"status": "active", "actor": self.owner}
                if self.owner is not None
                else None
            )
            return {"tasks": [{"id": "T-1", "status": "pending", "execution": execution}]}
        if name == "ContractReadFile":
            return {"path": "src/notifier.py", "sha256": "hash-1", "content": "old"}
        if name == "ContractBeginExecution":
            return {"execution_id": "lease-1", "status": "active"}
        return {"status": "ok", "passed": True}


class ExploreAssistantTest(TestCase):
    def test_system_prompt_bounds_mermaid_to_supported_safe_syntax(self) -> None:
        self.assertIn("syntax compatible with Mermaid 11.6", SYSTEM_PROMPT)
        self.assertIn("do not use HTML labels, click directives, or experimental diagram types", SYSTEM_PROMPT)

    def test_deepseek_translates_chat_tools_and_usage(self) -> None:
        captured: dict = {}

        def create(**kwargs):  # noqa: ANN003, ANN202
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Inspecting the graph.",
                            tool_calls=[
                                SimpleNamespace(
                                    id="call-1",
                                    function=SimpleNamespace(
                                        name="GraphSearch",
                                        arguments=json.dumps({"query": "OrderService"}),
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=17, completion_tokens=5),
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        client = DeepSeekModelClient("deepseek-v4-flash", client=fake_client)

        result = client.complete(
            ModelRequest(
                "Explore safely.",
                (ModelMessage("user", "Find the service"),),
                (ToolSpec("GraphSearch", "Search nodes", {"type": "object"}),),
                max_tokens=321,
            )
        )

        self.assertEqual(result.text, "Inspecting the graph.")
        self.assertEqual(result.usage, ModelUsage(17, 5))
        self.assertEqual(result.tool_calls[0].arguments, {"query": "OrderService"})
        self.assertEqual(captured["model"], "deepseek-v4-flash")
        self.assertEqual(captured["max_tokens"], 321)
        self.assertNotIn("max_completion_tokens", captured)
        self.assertEqual(captured["tools"][0]["function"]["name"], "GraphSearch")

    def test_when_deepseek_request_fails_expect_runtime_error(self) -> None:
        def create(**kwargs):  # noqa: ANN003, ANN202
            del kwargs
            raise Exception("TLS handshake failed")

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        client = DeepSeekModelClient("deepseek-v4-flash", client=fake_client)

        with self.assertRaisesRegex(RuntimeError, "DeepSeek request failed: TLS handshake failed"):
            client.complete(ModelRequest("Explore safely.", (), ()))

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

    def test_when_agent_proposes_graph_changes_expect_reviewable_actions(self) -> None:
        graph = extract_python_graph(FIXTURE)
        nodes = graph["nodes"][:2]
        client = FakeModelClient(
            [
                ModelResponse(
                    tool_calls=(
                        ToolCall("call-1", "ProposeNode", {
                            "label": "PaymentPolicy",
                            "kind": "class",
                            "parent_id": nodes[0]["id"],
                            "description": "Own payment rules",
                            "target_path": "application/payment_policy.py",
                            "qualified_name": "PaymentPolicy",
                            "docstring": "Decide whether a payment may proceed.",
                            "satisfies": ["BR-001"],
                            "acceptance": ["Rejected payments expose a stable reason."],
                        }),
                        ToolCall("call-2", "ProposeRelation", {"source_id": nodes[0]["id"], "target_id": nodes[1]["id"], "kind": "depends_on", "label": "uses policy"}),
                    )
                ),
                ModelResponse("He añadido dos cambios en modo propuesta."),
            ]
        )
        service = ExploreAssistantService(client, lambda: FIXTURE, lambda: graph)
        session_id = service.create_session()["id"]

        result = service.send_message(
            session_id,
            "Propón un nodo y una relación",
            {"assistantMode": "propose"},
        )

        self.assertEqual([action["op"] for action in result["actions"]], ["add_node", "add_relation"])
        self.assertEqual(result["actions"][0]["label"], "PaymentPolicy")
        self.assertEqual(result["actions"][0]["target_path"], "application/payment_policy.py")
        self.assertEqual(result["actions"][0]["satisfies"], ["BR-001"])
        self.assertEqual(result["actions"][1]["kind"], "depends_on")
        self.assertIn("PROPOSE MODE IS ACTIVE", client.requests[0].system_prompt)
        self.assertIn("MUST use ProposeNode", client.requests[0].system_prompt)
        self.assertIn("browser-local draft", client.requests[0].system_prompt)
        self.assertIn("Save map", client.requests[0].system_prompt)
        self.assertIn("Preserve every graph element kind explicitly requested", client.requests[0].system_prompt)
        self.assertIn("Do not substitute package for module", client.requests[0].system_prompt)
        self.assertIn("structured contract", client.requests[0].system_prompt)
        self.assertIn("observed implementation", client.requests[0].system_prompt)
        self.assertNotIn("not persisted until the user saves", client.requests[0].system_prompt)
        self.assertNotIn("actions", service.session(session_id))

    def test_when_propose_mode_returns_only_advice_expect_corrective_retry(self) -> None:
        graph = extract_python_graph(FIXTURE)
        parent = graph["nodes"][0]
        client = FakeModelClient(
            [
                ModelResponse("No puedo modificar la aplicación, pero te sugiero un enfoque."),
                ModelResponse(tool_calls=(ToolCall("call-1", "ProposeNode", {"label": "TelegramNotifier", "kind": "class", "parent_id": parent["id"]}),)),
                ModelResponse("He añadido TelegramNotifier al grafo como propuesta."),
            ]
        )
        service = ExploreAssistantService(client, lambda: FIXTURE, lambda: graph)
        session_id = service.create_session()["id"]

        result = service.send_message(
            session_id,
            "¿Cómo mejorarías la aplicación para notificar una venta?",
            {"assistantMode": "propose"},
        )

        self.assertEqual(result["actions"][0]["label"], "TelegramNotifier")
        self.assertEqual(result["messages"][-1]["content"], "He añadido TelegramNotifier al grafo como propuesta.")
        self.assertIn("staged no graph changes", client.requests[1].messages[-1].content)

    def test_when_proposal_references_unknown_node_expect_tool_error(self) -> None:
        graph = GraphIndex(extract_python_graph(FIXTURE))
        environment = ToolEnvironment(FIXTURE.resolve(), graph, allow_proposals=True)
        registry = ExploreToolRegistry()

        with self.assertRaisesRegex(ValueError, "unknown parent node"):
            registry.execute(
                "ProposeNode",
                {"label": "Orphan", "kind": "class", "parent_id": "missing"},
                environment,
            )

    def test_when_read_mode_expect_proposal_tools_hidden_and_draft_visible(self) -> None:
        graph = extract_python_graph(FIXTURE)
        draft_id = "agent-proposal:existing"
        client = FakeModelClient([ModelResponse("Puedo ver el borrador.")])
        service = ExploreAssistantService(client, lambda: FIXTURE, lambda: graph)
        session_id = service.create_session()["id"]

        service.send_message(
            session_id,
            "Describe el borrador",
            {"proposalNodes": [{"id": draft_id, "label": "DraftPolicy", "kind": "class", "parent": graph["nodes"][0]["id"]}]},
        )

        self.assertNotIn("ProposeNode", {tool.name for tool in client.requests[0].tools})
        self.assertNotIn("PROPOSE MODE IS ACTIVE", client.requests[0].system_prompt)
        self.assertIn(draft_id, client.requests[0].messages[0].content)

    def test_implement_mode_refuses_unavailable_or_competing_harness_before_model(self) -> None:
        graph = extract_python_graph(FIXTURE)
        unavailable_client = FakeModelClient([ModelResponse("should not run")])
        unavailable = ExploreAssistantService(
            unavailable_client,
            lambda: FIXTURE,
            lambda: graph,
        )

        with self.assertRaisesRegex(ValueError, "HARNESS is not connected"):
            unavailable.send_message(
                unavailable.create_session()["id"],
                "Implementa el contrato",
                {"assistantMode": "implement"},
            )
        self.assertEqual(unavailable_client.requests, [])

        competing_client = FakeModelClient([ModelResponse("should not run")])
        competing = ExploreAssistantService(
            competing_client,
            lambda: FIXTURE,
            lambda: graph,
            contract_tools=FakeContractTools(owner="mcp"),
        )
        with self.assertRaisesRegex(ValueError, "owned by mcp"):
            competing.send_message(
                competing.create_session()["id"],
                "Implementa el contrato",
                {"assistantMode": "implement"},
            )
        self.assertEqual(competing_client.requests, [])

    def test_implement_mode_uses_contract_toolchain_and_terminal_action(self) -> None:
        graph = extract_python_graph(FIXTURE)
        calls = (
            ToolCall("c1", "ContractGetTask", {"task_id": "T-1"}),
            ToolCall("c2", "ContractBeginExecution", {"task_id": "T-1"}),
            ToolCall("c3", "ContractReadFile", {"execution_id": "lease-1", "path": "src/notifier.py"}),
            ToolCall(
                "c4",
                "ContractApplyPatch",
                {
                    "execution_id": "lease-1",
                    "path": "src/notifier.py",
                    "expected_sha256": "hash-1",
                    "old_text": "old",
                    "new_text": "new",
                },
            ),
            ToolCall("c5", "ContractRunChecks", {"execution_id": "lease-1"}),
            ToolCall("c6", "ContractValidate", {"execution_id": "lease-1"}),
            ToolCall("c7", "ContractComplete", {"execution_id": "lease-1"}),
        )
        client = FakeModelClient(
            [ModelResponse(tool_calls=calls), ModelResponse("Contrato implementado y validado.")]
        )
        contract_tools = FakeContractTools()
        service = ExploreAssistantService(
            client,
            lambda: FIXTURE,
            lambda: graph,
            contract_tools=contract_tools,
        )

        result = service.send_message(
            service.create_session()["id"],
            "Implementa la tarea aprobada",
            {"assistantMode": "implement"},
        )

        self.assertEqual(result["messages"][-1]["content"], "Contrato implementado y validado.")
        self.assertEqual(contract_tools.calls[0], ("ContractListTasks", {}))
        self.assertEqual(
            [name for name, _ in contract_tools.calls[1:]],
            [call.name for call in calls],
        )
        exposed = {tool.name for tool in client.requests[0].tools}
        self.assertIn("ContractApplyPatch", exposed)
        self.assertNotIn("ProposeNode", exposed)
        self.assertIn("IMPLEMENT MODE IS ACTIVE", client.requests[0].system_prompt)

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
