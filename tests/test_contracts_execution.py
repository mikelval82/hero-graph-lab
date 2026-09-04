from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from hero_graph_lab.contracts import (
    ContractRepository,
    ContractStatus,
    ExecutionRequest,
    IntentContract,
    SourceSnapshot,
    VerificationPolicy,
    validate_contract,
)
from hero_graph_lab.contracts.validation import ContractValidationError
from hero_graph_lab.execution.adapters import DeepSeekHarnessAdapter, ManualHandoffAdapter
from hero_graph_lab.server import LabState, make_handler


def request(contract_id: str = "contract-1") -> ExecutionRequest:
    contract = IntentContract(contract_id, "Add feature", "Implement the feature", acceptance_criteria=["tests pass"])
    return ExecutionRequest(contract, SourceSnapshot("package:demo", {"nodes": [], "edges": []}), VerificationPolicy(["python3 -m unittest"]))


class ContractsExecutionTest(TestCase):
    def test_validation_and_repository_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            repository = ContractRepository(Path(directory))
            contract = validate_contract(request().contract)
            path = repository.save(contract)
            loaded = repository.get(contract.id)
            exists = path.is_file()

        self.assertTrue(exists)
        self.assertEqual(loaded, contract)

    def test_validation_requires_acceptance_criteria(self) -> None:
        with self.assertRaises(ContractValidationError):
            validate_contract(IntentContract("x", "Title", "Objective"))

    def test_manual_handoff_writes_files_without_project_changes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing.py").write_text("pass\n", encoding="utf-8")
            receipt = ManualHandoffAdapter(root).handoff(request())
            handoff = root / ".graph-lab" / "handoffs" / "contract-1"
            names = sorted(path.name for path in handoff.iterdir())
            existing = (root / "existing.py").read_text(encoding="utf-8")

        self.assertEqual(receipt.status, ContractStatus.HANDED_OFF)
        self.assertEqual(names, ["contract.json", "instructions.md", "source-snapshot.json", "verification-policy.json"])
        self.assertEqual(existing, "pass\n")

    def test_deepseek_adapter_is_explicitly_export_only(self) -> None:
        with TemporaryDirectory() as directory:
            adapter = DeepSeekHarnessAdapter(Path(directory))
            receipt = adapter.handoff(request("deepseek-1"))

        self.assertFalse(adapter.capabilities()["execution"])
        self.assertIn("pending", receipt.message)

    def test_reconcile_reports_materialized_and_divergent_contracts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("def run():\n    return True\n", encoding="utf-8")
            state = LabState(root, root / "observations.json")
            state.create_contract({"id": "materialized", "title": "M", "objective": "O", "acceptance_criteria": ["A"]})
            materialized_handoff = state.export_handoff("materialized", {"required_paths": ["main.py"]})
            materialized_id = materialized_handoff["execution_id"]
            state.record_evidence(materialized_id, {"revision": "abc"})
            materialized = state.reconcile("materialized", materialized_id)
            state.create_contract({"id": "divergent", "title": "D", "objective": "O", "acceptance_criteria": ["A"]})
            divergent_id = state.export_handoff("divergent", {"required_paths": ["missing.py"]})["execution_id"]
            divergent = state.reconcile("divergent", divergent_id)

        self.assertEqual(materialized["status"], "MATERIALIZED")
        self.assertEqual(divergent["status"], "DIVERGENT")
        self.assertEqual(divergent["missing"], ["missing.py"])

    def test_neutral_mcp_gateway_exposes_contract_lifecycle(self) -> None:
        with TemporaryDirectory() as directory:
            state = LabState(Path(directory), Path(directory) / "observations.json")
            names = {item["name"] for item in state.contract_tools.tool_specs()}
            created = state.contract_tools.execute("CreateIntentContract", {"id": "mcp-contract", "title": "MCP", "objective": "O", "acceptance_criteria": ["A"]})

        self.assertIn("ExportHandoff", names)
        self.assertIn("RecordExecutionEvidence", names)
        self.assertEqual(created["id"], "mcp-contract")

    def test_neutral_server_contract_flow_needs_no_harness(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = LabState(root, root / "observations.json")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def call(path: str, payload: dict | None = None) -> dict:
                request = Request(
                    base + path,
                    data=None if payload is None else json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"} if payload is not None else {},
                    method="POST" if payload is not None else "GET",
                )
                with urlopen(request) as response:
                    return json.load(response)

            try:
                capabilities = call("/api/capabilities")
                created = call("/api/contracts", {"id": "api-contract", "title": "API", "objective": "Test API", "acceptance_criteria": ["works"]})
                handoff = call("/api/contracts/api-contract/handoff", {"executor": "manual"})
                status = call(f"/api/executions/{handoff['execution_id']}")
            finally:
                server.shutdown()
                server.server_close()

        self.assertFalse(capabilities["executor_required"])
        self.assertEqual(created["id"], "api-contract")
        self.assertEqual(handoff["status"], "HANDED_OFF")
        self.assertEqual(status["executor"], "manual")

    def test_handoff_can_be_reloaded_after_graph_lab_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = LabState(root, root / "observations.json")
            first.create_contract({"id": "restartable", "title": "R", "objective": "O", "acceptance_criteria": ["A"]})
            receipt = first.export_handoff("restartable", {})
            second = LabState(root, root / "observations.json")
            evidence = second.record_evidence(receipt["execution_id"], {"revision": "external-1"})

        self.assertEqual(evidence["execution_id"], receipt["execution_id"])
