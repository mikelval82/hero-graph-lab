"""Filesystem repository for versioned Graph Lab contracts and execution records."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from .models import ContractStatus, IntentContract
from .serialization import dumps, loads
from .validation import validate_payload


T = TypeVar("T")


class ContractRepository:
    def __init__(self, project_root: Path) -> None:
        self.root = project_root.resolve() / ".graph-lab" / "contracts"

    def save(self, contract: IntentContract) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(contract.id)
        path.write_text(dumps(contract), encoding="utf-8")
        return path

    def get(self, contract_id: str) -> IntentContract:
        payload = loads(self._path(contract_id).read_text(encoding="utf-8"))
        validate_payload(payload)
        fields_by_name = {item.name for item in fields(IntentContract)}
        values = {key: value for key, value in payload.items() if key in fields_by_name}
        values["status"] = ContractStatus(payload.get("status", "DRAFT"))
        return IntentContract(**values)

    def list(self) -> list[IntentContract]:
        if not self.root.is_dir():
            return []
        return [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]

    def _path(self, contract_id: str) -> Path:
        if not contract_id or Path(contract_id).name != contract_id or contract_id in {".", ".."}:
            raise ValueError("invalid contract id")
        return self.root / f"{contract_id}.json"
