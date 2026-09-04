"""Safe filesystem-only handoff for human or external executors."""

from __future__ import annotations

from pathlib import Path

from hero_graph_lab.contracts.models import ContractStatus, ExecutionReceipt, ExecutionRequest
from hero_graph_lab.contracts.serialization import dumps


class ManualHandoffAdapter:
    name = "manual"

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def capabilities(self) -> dict[str, object]:
        return {"label": "Manual / external runtime", "handoff": True, "execution": False, "modifies_project": False, "integration": "filesystem", "evidence": True}

    def handoff(self, request: ExecutionRequest) -> ExecutionReceipt:
        execution_id = request.execution_id or request.contract.id
        target = self.project_root / ".graph-lab" / "handoffs" / execution_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "contract.json").write_text(dumps(request.contract), encoding="utf-8")
        (target / "verification-policy.json").write_text(dumps(request.verification_policy), encoding="utf-8")
        (target / "source-snapshot.json").write_text(dumps(request.source_snapshot), encoding="utf-8")
        instructions = request.instructions.strip() or "Implement the contract in an external workspace and return execution evidence."
        (target / "instructions.md").write_text(f"# Execution handoff\n\n{instructions}\n", encoding="utf-8")
        return ExecutionReceipt(execution_id, self.name, ContractStatus.HANDED_OFF, str(target), message="Handoff exported; no project files modified")

    def status(self, execution_id: str) -> dict[str, object]:
        target = self.project_root / ".graph-lab" / "handoffs" / execution_id
        return {"execution_id": execution_id, "executor": self.name, "status": ContractStatus.HANDED_OFF if target.is_dir() else ContractStatus.BLOCKED, "handoff_path": str(target)}

    def cancel(self, execution_id: str) -> None:
        return None
