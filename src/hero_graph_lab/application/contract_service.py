"""Lifecycle operations for executor-neutral intent contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.contracts import ContractRepository, IntentContract, compile_design_contract, validate_contract
from hero_graph_lab.contracts.serialization import dumps as contract_dumps


class ContractService:
    """Own contract persistence, compilation and deterministic validation."""

    def __init__(self, project_root: Path, graph_provider: Callable[[], dict[str, Any]]) -> None:
        self._graph_provider = graph_provider
        self.repository = ContractRepository(project_root)

    def set_project(self, project_root: Path) -> None:
        self.repository = ContractRepository(project_root)

    def list(self) -> list[dict[str, object]]:
        return [json.loads(contract_dumps(item)) for item in self.repository.list()]

    def create(self, payload: dict[str, Any]) -> dict[str, object]:
        contract = IntentContract(
            id=str(payload.get("id") or uuid4()),
            title=str(payload.get("title", "")),
            objective=str(payload.get("objective", "")),
            requirements=list(payload.get("requirements", [])),
            acceptance_criteria=list(payload.get("acceptance_criteria", [])),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), dict) else {},
        )
        contract = validate_contract(contract)
        path = self.repository.save(contract)
        return json.loads(contract_dumps(contract)) | {"path": str(path)}

    def compile_from_design(self, payload: dict[str, Any]) -> dict[str, object]:
        graph = payload.get("graph") if isinstance(payload.get("graph"), dict) else self._graph_provider()
        contract = compile_design_contract(
            graph,
            title=str(payload.get("title", "Graph Lab design")),
            objective=str(payload.get("objective", "Implement the accepted Graph Lab design")),
            contract_id=str(payload.get("id")) if payload.get("id") else None,
            acceptance_criteria=[str(item) for item in payload.get("acceptance_criteria", [])],
        )
        path = self.repository.save(contract)
        return json.loads(contract_dumps(contract)) | {"path": str(path), "compiled_from_design": True}

    def get(self, contract_id: str) -> dict[str, object]:
        return json.loads(contract_dumps(self.repository.get(contract_id)))

    def validate(self, contract_id: str) -> dict[str, object]:
        contract = validate_contract(self.repository.get(contract_id))
        self.repository.save(contract)
        return {"valid": True, "contract": json.loads(contract_dumps(contract))}
