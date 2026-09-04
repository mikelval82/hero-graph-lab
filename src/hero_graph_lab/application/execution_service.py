"""Executor-neutral handoff, evidence and reconciliation operations."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from hero_graph_lab.contracts import (
    ContractStatus,
    ExecutionEvidence,
    ExecutionRequest,
    IntentContract,
    ReconciliationResult,
    SourceSnapshot,
    VerificationPolicy,
    validate_contract,
)
from hero_graph_lab.contracts.serialization import dumps as contract_dumps, loads as contract_loads
from hero_graph_lab.execution import ExecutionRegistry
from hero_graph_lab.extractor import project_source_files

from .contract_service import ContractService


class ExecutionService:
    """Coordinate external executors without embedding a specific agent runtime."""

    def __init__(
        self,
        project_root: Path,
        contracts: ContractService,
        graph_provider: Callable[[], dict[str, Any]],
    ) -> None:
        self._project_root = project_root
        self._contracts = contracts
        self._graph_provider = graph_provider
        self.registry = ExecutionRegistry(project_root)
        self.requests: dict[str, ExecutionRequest] = {}
        self.executors: dict[str, str] = {}
        self.evidence: dict[str, list[ExecutionEvidence]] = {}

    def set_project(self, project_root: Path) -> None:
        self._project_root = project_root
        self.registry = ExecutionRegistry(project_root)
        self.requests = {}
        self.executors = {}
        self.evidence = {}

    def active_scope(self) -> dict[str, object]:
        active = [
            contract for contract in self._contracts.repository.list()
            if contract.status in {ContractStatus.HANDED_OFF, ContractStatus.EXECUTING, ContractStatus.VERIFYING}
        ]
        if not active:
            return {}
        contract = active[-1]
        targets = contract.metadata.get("targets", []) if isinstance(contract.metadata, dict) else []
        return {
            "contract_id": contract.id,
            "allowed_paths": sorted(
                str(item.get("target_path")) for item in targets
                if isinstance(item, dict) and item.get("target_path")
            ),
            "verification_commands": [],
        }

    def export_handoff(self, contract_id: str, payload: dict[str, Any]) -> dict[str, object]:
        contract = validate_contract(self._contracts.repository.get(contract_id))
        policy = VerificationPolicy(
            commands=[str(item) for item in payload.get("commands", [])],
            required_paths=[str(item) for item in payload.get("required_paths", [])],
            required_relationships=list(payload.get("required_relationships", [])),
        )
        handed_off = replace(contract, status=ContractStatus.HANDED_OFF)
        execution_id = str(payload.get("execution_id") or uuid4())
        request = ExecutionRequest(handed_off, self._source_snapshot(), policy, str(payload.get("instructions", "")), execution_id)
        executor = self.registry.get(str(payload.get("executor", "manual")))
        receipt = executor.handoff(request)
        self._contracts.repository.save(replace(handed_off, status=receipt.status))
        self.requests[receipt.execution_id] = request
        self.executors[receipt.execution_id] = receipt.executor
        return json.loads(contract_dumps(receipt))

    def status(self, execution_id: str) -> dict[str, object]:
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        executor_name = self.executors.get(execution_id, "codex-mcp")
        status = self.registry.get(executor_name).status(execution_id)
        if executor_name == "deepseek-dsh" and status.get("status") == ContractStatus.VERIFYING:
            if not self.evidence.get(execution_id):
                self.record_evidence(
                    execution_id,
                    {
                        "revision": self._git_revision(),
                        "changed_files": self._changed_since_snapshot(request),
                        "notes": str(status.get("output", "")),
                        "artifacts": {"dsh_return_code": status.get("return_code")},
                    },
                )
                status["reconciliation"] = self.reconcile(request.contract.id, execution_id)
        return status | {"evidence": [json.loads(contract_dumps(item)) for item in self.evidence.get(execution_id, [])]}

    def cancel(self, execution_id: str) -> dict[str, object]:
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        self.registry.get(self.executors.get(execution_id, "manual")).cancel(execution_id)
        self._contracts.repository.save(replace(request.contract, status=ContractStatus.BLOCKED))
        return self.status(execution_id)

    def record_evidence(self, execution_id: str, payload: dict[str, Any]) -> dict[str, object]:
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        evidence = ExecutionEvidence(
            execution_id, str(payload.get("revision", "")), [str(item) for item in payload.get("changed_files", [])],
            list(payload.get("commands", [])), str(payload.get("notes", "")),
            payload.get("artifacts", {}) if isinstance(payload.get("artifacts", {}), dict) else {},
        )
        self.evidence.setdefault(execution_id, []).append(evidence)
        self._contracts.repository.save(replace(request.contract, status=ContractStatus.VERIFYING))
        target = self._project_root / ".graph-lab" / "evidence" / f"{execution_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contract_dumps(self.evidence[execution_id]), encoding="utf-8")
        return json.loads(contract_dumps(evidence))

    def reconcile(self, contract_id: str, execution_id: str) -> dict[str, object]:
        contract = self._contracts.repository.get(contract_id)
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        graph = self._graph_provider()
        actual_paths = {str(node.get("source")) for node in graph.get("nodes", []) if node.get("source")}
        targets = contract.metadata.get("targets", []) if isinstance(contract.metadata, dict) else []
        required_paths = set(request.verification_policy.required_paths) | {
            str(item.get("target_path")) for item in targets if isinstance(item, dict) and item.get("target_path")
        }
        materialized = sorted(path for path in required_paths if self._path_is_present(path, actual_paths))
        missing = sorted(path for path in required_paths if path not in materialized)
        relationships = {(item.get("source"), item.get("target"), item.get("kind")) for item in graph.get("edges", [])}
        divergent = [str(item) for item in request.verification_policy.required_relationships if isinstance(item, dict) and (item.get("source"), item.get("target"), item.get("kind")) not in relationships]
        changed = self._changed_since_snapshot(request)
        unexpected = [path for path in changed if not path.startswith(".graph-lab/") and not any(path == allowed or path.startswith(allowed.rstrip("/") + "/") for allowed in required_paths)]
        divergent.extend(f"changed outside contract authority: {path}" for path in unexpected)
        status = ContractStatus.MATERIALIZED if not missing and not divergent else ContractStatus.DIVERGENT
        accepted = self._committed_paths(request, materialized)
        metadata = dict(contract.metadata) | {"realized_paths": materialized, "accepted_paths": accepted}
        result = ReconciliationResult(contract.id, status, materialized, missing, divergent)
        self._contracts.repository.save(replace(contract, status=status, metadata=metadata))
        return json.loads(contract_dumps(result)) | {"accepted": accepted}

    def complete_agent_execution(self, contract_id: str, notes: str) -> dict[str, Any]:
        candidates = [request for request in self.requests.values() if request.contract.id == contract_id]
        if not candidates:
            raise KeyError(f"no execution handoff for contract: {contract_id}")
        request = candidates[-1]
        self.record_evidence(request.execution_id, {"revision": self._git_revision(), "changed_files": self._changed_since_snapshot(request), "notes": notes})
        return self.reconcile(contract_id, request.execution_id)

    @staticmethod
    def _path_is_present(required: str, actual_paths: set[str]) -> bool:
        normalized = required.strip().rstrip("/")
        return normalized in actual_paths or any(path.startswith(normalized + "/") for path in actual_paths)

    def _source_snapshot(self) -> SourceSnapshot:
        files: dict[str, dict[str, object]] = {}
        for path in project_source_files(self._project_root):
            relative = path.name if self._project_root.is_file() else path.relative_to(self._project_root).as_posix()
            content = path.read_bytes()
            files[relative] = {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        graph = self._graph_provider()
        return SourceSnapshot(graph.get("root", ""), graph, files, datetime.now(UTC).isoformat())

    def _changed_since_snapshot(self, request: ExecutionRequest) -> list[str]:
        current = self._source_snapshot().files
        before = request.source_snapshot.files
        return sorted(path for path in set(current) | set(before) if current.get(path) != before.get(path))

    def _committed_paths(self, request: ExecutionRequest, materialized: list[str]) -> list[str]:
        dirty = self._git_dirty_paths()
        changed = set(self._changed_since_snapshot(request))
        return sorted(path for path in materialized if path in changed and path not in dirty)

    def _git_revision(self) -> str:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self._project_root, text=True, capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    def _git_dirty_paths(self) -> set[str]:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=self._project_root, text=True, capture_output=True, check=False)
        return {line[3:].strip().split(" -> ")[-1] for line in result.stdout.splitlines() if len(line) > 3} if result.returncode == 0 else set()

    def _request_for_execution(self, execution_id: str) -> ExecutionRequest | None:
        request = self.requests.get(execution_id)
        if request is not None:
            return request
        handoff = self._project_root / ".graph-lab" / "handoffs" / execution_id
        try:
            contract_payload = contract_loads((handoff / "contract.json").read_text(encoding="utf-8"))
            snapshot_payload = contract_loads((handoff / "source-snapshot.json").read_text(encoding="utf-8"))
            policy_payload = contract_loads((handoff / "verification-policy.json").read_text(encoding="utf-8"))
            values = dict(contract_payload) | {"status": ContractStatus(contract_payload.get("status", "DRAFT"))}
            request = ExecutionRequest(IntentContract(**values), SourceSnapshot(**snapshot_payload), VerificationPolicy(**policy_payload), execution_id=execution_id)
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        self.requests[execution_id] = request
        return request
