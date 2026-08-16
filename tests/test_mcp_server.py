from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from hero_graph_lab.mcp_bridge import GraphLabClient
from hero_graph_lab.server import LabState, make_handler


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_app"


class ProtocolHarnessHost:
    def request(self, method: str, path: str, body: bytes | None = None):  # noqa: ANN201
        if path == "/api/v1/contracts/tasks":
            payload = {"snapshot_id": "snap-protocol", "tasks": [{"id": "T-1"}]}
        elif path == "/api/v1/contracts/tasks/T-1":
            payload = {"contract": {"snapshot_id": "snap-protocol", "task": {"id": "T-1"}}}
        elif path == "/api/v1/contracts/executions":
            self.begin_body = json.loads(body or b"{}")
            payload = {"execution_id": "exec-protocol", "status": "active"}
        else:
            payload = {"status": "ok"}
        return 200, "application/json", json.dumps(payload).encode("utf-8")


class McpServerTest(TestCase):
    def test_rejects_non_loopback_graph_lab_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            GraphLabClient("https://example.com")

    def test_stdio_protocol_lists_and_calls_live_graph_tools(self) -> None:
        with TemporaryDirectory() as directory:
            harness = ProtocolHarnessHost()
            state = LabState(
                FIXTURE,
                Path(directory) / "observations.json",
                harness_host=harness,
            )
            graph_server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=graph_server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{graph_server.server_port}"
                parent = next(node for node in state.graph()["nodes"] if node["kind"] == "module")
                result = asyncio.run(self._exercise_protocol(base_url, parent["id"]))
            finally:
                graph_server.shutdown()
                graph_server.server_close()
                thread.join()

        self.assertEqual(result["server_name"], "hero-graph-lab")
        self.assertIn("GraphSearch", result["tool_names"])
        self.assertIn("ContractGetTask", result["tool_names"])
        self.assertIn("OrderService", result["content"])
        self.assertFalse(result["is_error"])
        self.assertEqual(result["proposal_op"], "add_node")
        self.assertEqual(result["contract_snapshot"], "snap-protocol")
        self.assertEqual(result["execution_id"], "exec-protocol")
        self.assertEqual(harness.begin_body, {"task_id": "T-1", "actor": "mcp"})
        self.assertEqual(state.graph_tools.pending_proposals()["items"][0]["action"]["label"], "McpProtocolProbe")

    @staticmethod
    async def _exercise_protocol(base_url: str, parent_id: str) -> dict[str, object]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hero_graph_lab.mcp_server", "--url", base_url],
            cwd=str(Path(__file__).parents[1]),
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool("GraphSearch", {"query": "OrderService"})
                proposed = await session.call_tool(
                    "ProposeNode",
                    {"label": "McpProtocolProbe", "kind": "class", "parent_id": parent_id},
                )
                contract = await session.call_tool("ContractGetTask", {"task_id": "T-1"})
                execution = await session.call_tool("ContractBeginExecution", {"task_id": "T-1"})
                return {
                    "server_name": initialized.serverInfo.name,
                    "tool_names": {tool.name for tool in listed.tools},
                    "content": "\n".join(
                        item.text for item in called.content if item.type == "text"
                    ),
                    "is_error": bool(called.isError),
                    "proposal_op": proposed.structuredContent["actions"][0]["op"],
                    "contract_snapshot": contract.structuredContent["contract"]["snapshot_id"],
                    "execution_id": execution.structuredContent["execution_id"],
                }

    def test_stdio_tool_error_is_actionable_when_graph_lab_is_down(self) -> None:
        result = asyncio.run(self._call_unavailable_server())

        self.assertTrue(result.isError)
        self.assertIn("Graph Lab is unavailable", result.content[0].text)

    @staticmethod
    async def _call_unavailable_server():  # noqa: ANN205
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hero_graph_lab.mcp_server", "--url", "http://127.0.0.1:1"],
            cwd=str(Path(__file__).parents[1]),
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.call_tool("GraphSearch", {"query": "anything"})
