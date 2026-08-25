from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase

from hero_graph_lab.explore.gateway import GraphToolGateway
from hero_graph_lab.extractor import extract_python_graph


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_app"


class GraphToolGatewayTest(TestCase):
    def setUp(self) -> None:
        self.graph = extract_python_graph(FIXTURE)
        self.gateway = GraphToolGateway(lambda: FIXTURE, lambda: self.graph)

    def test_exposes_the_authoritative_registry_contract(self) -> None:
        tools = self.gateway.tool_specs()

        self.assertEqual(
            {tool["name"] for tool in tools},
            {
                "Read",
                "Glob",
                "Grep",
                "GraphGetNode",
                "GraphSearch",
                "GraphNeighbors",
                "GraphPath",
                "GraphScope",
                "ProposeNode",
                "ProposeRelation",
            },
        )
        proposal = next(tool for tool in tools if tool["name"] == "ProposeNode")
        search = next(tool for tool in tools if tool["name"] == "GraphSearch")
        self.assertFalse(proposal["annotations"]["readOnlyHint"])
        self.assertTrue(search["annotations"]["readOnlyHint"])
        self.assertEqual(proposal["inputSchema"]["additionalProperties"], False)
        self.assertTrue(
            {
                "target_path",
                "qualified_name",
                "signature",
                "docstring",
                "satisfies",
                "acceptance",
            }.issubset(proposal["inputSchema"]["properties"])
        )

    def test_executes_queries_against_the_active_graph(self) -> None:
        result = self.gateway.execute("GraphSearch", {"query": "OrderService"})

        matches = json.loads(result["content"])
        self.assertTrue(any(node["label"] == "OrderService" for node in matches))
        self.assertEqual(result["actions"], [])

    def test_stages_ordered_proposals_and_keeps_them_queryable_after_ack(self) -> None:
        parent = next(node for node in self.graph["nodes"] if node["kind"] == "module")
        proposed = self.gateway.execute(
            "ProposeNode",
            {
                "label": "TelegramNotifier",
                "kind": "class",
                "parent_id": parent["id"],
                "description": "Sends Telegram notifications",
                "target_path": "src/application/telegram.py",
                "qualified_name": "TelegramNotifier",
                "docstring": "Send application notifications through Telegram.",
                "satisfies": ["BR-002"],
                "acceptance": ["Provider failures do not escape the adapter."],
            },
        )
        proposed_node = proposed["actions"][0]
        self.assertEqual(proposed_node["target_path"], "src/application/telegram.py")
        self.assertEqual(proposed_node["qualified_name"], "TelegramNotifier")
        self.assertEqual(
            proposed_node["docstring"],
            "Send application notifications through Telegram.",
        )
        self.assertEqual(proposed_node["satisfies"], ["BR-002"])
        self.assertEqual(
            proposed_node["acceptance"],
            ["Provider failures do not escape the adapter."],
        )
        related = self.gateway.execute(
            "ProposeRelation",
            {
                "source_id": proposed_node["node_id"],
                "target_id": parent["id"],
                "kind": "depends_on",
                "label": "uses application services",
            },
        )

        pending = self.gateway.pending_proposals()
        self.assertEqual([item["revision"] for item in pending["items"]], [1, 2])
        self.assertEqual([item["action"]["op"] for item in pending["items"]], ["add_node", "add_relation"])

        self.gateway.acknowledge_proposals([1, 2])
        self.assertEqual(self.gateway.pending_proposals()["items"], [])
        found = json.loads(
            self.gateway.execute("GraphSearch", {"query": "TelegramNotifier"})["content"]
        )
        self.assertEqual(found[0]["id"], proposed_node["node_id"])
        self.assertEqual(found[0]["target_path"], "src/application/telegram.py")
        self.assertEqual(related["actions"][0]["source_id"], proposed_node["node_id"])

    def test_rejects_invalid_calls_without_advancing_the_inbox(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown tool"):
            self.gateway.execute("MissingTool", {})
        with self.assertRaisesRegex(ValueError, "unknown parent"):
            self.gateway.execute(
                "ProposeNode",
                {"label": "Orphan", "kind": "class", "parent_id": "missing"},
            )
        with self.assertRaisesRegex(ValueError, "target_path must be repository-relative"):
            self.gateway.execute(
                "ProposeNode",
                {"label": "Escape", "kind": "module", "target_path": "../escape.py"},
            )

        self.assertEqual(self.gateway.pending_proposals(), {"revision": 0, "items": []})

    def test_reset_discards_project_scoped_proposal_state(self) -> None:
        self.gateway.execute("ProposeNode", {"label": "Draft", "kind": "module"})

        self.gateway.reset()

        self.assertEqual(self.gateway.pending_proposals(), {"revision": 0, "items": []})
        self.assertEqual(
            json.loads(self.gateway.execute("GraphSearch", {"query": "Draft"})["content"]),
            [],
        )
