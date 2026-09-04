"""Export-only DeepSeek Harness adapter; it never pretends to execute."""

from __future__ import annotations

from pathlib import Path

from .manual import ManualHandoffAdapter
from hero_graph_lab.contracts.models import ExecutionReceipt, ExecutionRequest


class DeepSeekHarnessAdapter(ManualHandoffAdapter):
    name = "deepseek-harness"

    def capabilities(self) -> dict[str, object]:
        return {"handoff": True, "execution": False, "modifies_project": False, "integration": "pending"}

    def handoff(self, request: ExecutionRequest) -> ExecutionReceipt:
        receipt = super().handoff(request)
        return ExecutionReceipt(receipt.execution_id, self.name, receipt.status, receipt.handoff_path, message="Exported for DeepSeek Harness; CLI/API integration is pending")
