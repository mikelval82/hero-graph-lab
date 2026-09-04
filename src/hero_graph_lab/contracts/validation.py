"""Deterministic validation for the public contract envelope."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .models import IntentContract


class ContractValidationError(ValueError):
    """Raised when a contract cannot be handed off safely."""


def validate_contract(contract: IntentContract) -> IntentContract:
    errors: list[str] = []
    if not contract.id.strip():
        errors.append("id must not be empty")
    if not contract.title.strip():
        errors.append("title must not be empty")
    if not contract.objective.strip():
        errors.append("objective must not be empty")
    if not isinstance(contract.requirements, list):
        errors.append("requirements must be an array")
    if not isinstance(contract.acceptance_criteria, list):
        errors.append("acceptance_criteria must be an array")
    if not contract.acceptance_criteria:
        errors.append("at least one acceptance criterion is required")
    for index, criterion in enumerate(contract.acceptance_criteria):
        if not isinstance(criterion, str) or not criterion.strip():
            errors.append(f"acceptance_criteria[{index}] must be a non-empty string")
    if errors:
        raise ContractValidationError("; ".join(errors))
    return replace(contract, requirements=[item.strip() for item in contract.requirements], acceptance_criteria=[item.strip() for item in contract.acceptance_criteria])


def validate_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("contract payload must be an object")
    for key in ("id", "title", "objective", "acceptance_criteria"):
        if key not in payload:
            raise ContractValidationError(f"missing contract field: {key}")
    for key in ("id", "title", "objective"):
        if not isinstance(payload[key], str):
            raise ContractValidationError(f"{key} must be a string")
    for key in ("requirements", "acceptance_criteria"):
        if key in payload and not isinstance(payload[key], list):
            raise ContractValidationError(f"{key} must be an array")
