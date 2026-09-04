"""Codex MCP handoff adapter.

Graph Lab prepares the contract and Codex executes it in its own workspace.
Execution status and evidence are returned through the neutral contract API.
"""

from __future__ import annotations

from pathlib import Path

from hero_graph_lab.contracts.models import ExecutionReceipt, ExecutionRequest

from .manual import ManualHandoffAdapter


class CodexMcpAdapter(ManualHandoffAdapter):
    """Export a contract for Codex configured through the Graph Lab MCP server."""

    name = "codex-mcp"

    def capabilities(self) -> dict[str, object]:
        return {
            "label": "Codex (MCP)",
            "handoff": True,
            "execution": False,
            "modifies_project": False,
            "integration": "mcp",
            "evidence": True,
        }

    def handoff(self, request: ExecutionRequest) -> ExecutionReceipt:
        receipt = super().handoff(request)
        return ExecutionReceipt(
            receipt.execution_id,
            self.name,
            receipt.status,
            receipt.handoff_path,
            message="Exported for Codex MCP; Codex executes in its own workspace",
        )
