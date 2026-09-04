"""Deterministic JSON conversion for contract models."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import StrEnum
from typing import Any, TypeVar


T = TypeVar("T")


def to_dict(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {key: to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_dict(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    return value


def dumps(value: Any) -> str:
    return json.dumps(to_dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def loads(text: str) -> Any:
    return json.loads(text)
