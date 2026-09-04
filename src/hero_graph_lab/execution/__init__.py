"""Executor-neutral handoff ports and adapters."""

from .ports import ExecutionAdapter
from .registry import ExecutionRegistry

__all__ = ["ExecutionAdapter", "ExecutionRegistry"]
