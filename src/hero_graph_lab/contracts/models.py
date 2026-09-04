"""Serializable contract models; no executor-specific dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    HANDED_OFF = "HANDED_OFF"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    MATERIALIZED = "MATERIALIZED"
    DIVERGENT = "DIVERGENT"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class IntentContract:
    id: str
    title: str
    objective: str
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    status: ContractStatus = ContractStatus.DRAFT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceSnapshot:
    root: str
    graph: dict[str, Any]
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    captured_at: str = ""


@dataclass(frozen=True)
class VerificationPolicy:
    commands: list[str] = field(default_factory=list)
    required_paths: list[str] = field(default_factory=list)
    required_relationships: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionRequest:
    contract: IntentContract
    source_snapshot: SourceSnapshot
    verification_policy: VerificationPolicy
    instructions: str = ""
    execution_id: str = ""


@dataclass(frozen=True)
class ExecutionEvidence:
    execution_id: str
    revision: str
    changed_files: list[str] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionReceipt:
    execution_id: str
    executor: str
    status: ContractStatus
    handoff_path: str
    changed_files: list[str] = field(default_factory=list)
    message: str = ""


@dataclass(frozen=True)
class ReconciliationResult:
    contract_id: str
    status: ContractStatus
    materialized: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    divergent: list[str] = field(default_factory=list)
    details: str = ""
