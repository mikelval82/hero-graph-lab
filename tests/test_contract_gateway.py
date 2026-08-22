from __future__ import annotations

import json
from unittest import TestCase

from hero_graph_lab.contract_gateway import HarnessContractGateway


class FakeHarnessHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes | None]] = []

    def request(self, method: str, path: str, body: bytes | None = None):  # noqa: ANN201
        self.calls.append((method, path, body))
        if path == "/api/v1/contracts/tasks":
            return 200, "application/json", json.dumps({"tasks": [{"id": "T-1"}]}).encode()
        return 200, "application/json", json.dumps({"status": "ok"}).encode()


class HarnessContractGatewayTest(TestCase):
    def test_specs_expose_bounded_read_and_lifecycle_tools(self) -> None:
        specs = {item["name"]: item for item in HarnessContractGateway(None).tool_specs()}

        self.assertEqual(
            set(specs),
            {
                "ContractListTasks",
                "ContractGetTask",
                "ContractBeginExecution",
                "ContractValidate",
                "ContractComplete",
                "ContractReportBlocker",
                "ContractProposeAmendment",
            },
        )
        self.assertTrue(specs["ContractListTasks"]["annotations"]["readOnlyHint"])
        self.assertFalse(specs["ContractBeginExecution"]["annotations"]["readOnlyHint"])
        self.assertNotIn("command", json.dumps(specs))

    def test_dispatches_to_harness_authority_and_pins_mcp_actor(self) -> None:
        host = FakeHarnessHost()
        gateway = HarnessContractGateway(host)

        listed = gateway.execute("ContractListTasks", {})
        begun = gateway.execute("ContractBeginExecution", {"task_id": "T-1"})

        self.assertEqual(listed["tasks"][0]["id"], "T-1")
        self.assertEqual(begun["status"], "ok")
        method, path, body = host.calls[1]
        self.assertEqual((method, path), ("POST", "/api/v1/contracts/executions"))
        self.assertEqual(json.loads(body), {"task_id": "T-1", "actor": "mcp"})

    def test_chat_gateway_adds_bounded_file_tools_and_pins_chat_actor(self) -> None:
        host = FakeHarnessHost()
        gateway = HarnessContractGateway(host, actor="chat", include_chat_tools=True)
        names = {item["name"] for item in gateway.tool_specs()}

        gateway.execute("ContractBeginExecution", {"task_id": "T-1"})
        gateway.execute(
            "ContractApplyPatch",
            {
                "execution_id": "lease-1",
                "path": "src/notifier.py",
                "expected_sha256": "abc",
                "old_text": "old",
                "new_text": "new",
            },
        )

        self.assertIn("ContractReadFile", names)
        self.assertIn("ContractApplyPatch", names)
        self.assertIn("ContractRunChecks", names)
        self.assertEqual(json.loads(host.calls[0][2]), {"task_id": "T-1", "actor": "chat"})
        self.assertEqual(
            host.calls[1][1],
            "/api/v1/contracts/executions/lease-1/apply-patch",
        )
        self.assertNotIn("execution_id", json.loads(host.calls[1][2]))

    def test_rejects_unknown_arguments_and_unavailable_worker(self) -> None:
        gateway = HarnessContractGateway(None)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            gateway.execute("ContractListTasks", {})
        with self.assertRaisesRegex(ValueError, "required"):
            HarnessContractGateway(FakeHarnessHost()).execute("ContractGetTask", {})
        with self.assertRaisesRegex(ValueError, "unknown contract tool"):
            HarnessContractGateway(FakeHarnessHost()).execute("ContractShell", {})


if __name__ == "__main__":
    import unittest

    unittest.main()
