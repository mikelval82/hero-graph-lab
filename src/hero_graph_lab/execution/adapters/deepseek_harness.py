"""DSH handoff adapter used by the official DeepSeek chat provider."""

from __future__ import annotations

from pathlib import Path

from .manual import ManualHandoffAdapter
from hero_graph_lab.contracts.models import ExecutionReceipt, ExecutionRequest


class DeepSeekHarnessAdapter(ManualHandoffAdapter):
    """Export a contract for the active official DeepSeek DSH chat session."""

    name = "deepseek-dsh"

    def capabilities(self) -> dict[str, object]:
        return {
            "label": "DeepSeek DSH",
            "handoff": True,
            "execution": False,
            "modifies_project": False,
            "integration": "official-dsh-chat",
            "evidence": True,
        }

    def handoff(self, request: ExecutionRequest) -> ExecutionReceipt:
        receipt = super().handoff(request)
        return ExecutionReceipt(
            receipt.execution_id,
            self.name,
            receipt.status,
            receipt.handoff_path,
            message="Exported for the active DeepSeek DSH chat session",
        )
