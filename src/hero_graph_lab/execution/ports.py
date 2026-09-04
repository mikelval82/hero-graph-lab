"""Ports implemented by local or external execution runtimes."""

from __future__ import annotations

from typing import Protocol

from hero_graph_lab.contracts.models import ExecutionReceipt, ExecutionRequest


class ExecutionAdapter(Protocol):
    name: str

    def capabilities(self) -> dict[str, object]: ...

    def handoff(self, request: ExecutionRequest) -> ExecutionReceipt: ...

    def status(self, execution_id: str) -> dict[str, object]: ...

    def cancel(self, execution_id: str) -> None: ...
