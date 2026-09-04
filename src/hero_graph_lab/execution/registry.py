"""In-process registry for explicitly selected external executors."""

from __future__ import annotations

from pathlib import Path

from .adapters import CodexMcpAdapter, DeepSeekHarnessAdapter, ManualHandoffAdapter


class ExecutionRegistry:
    def __init__(self, project_root: Path) -> None:
        self.adapters = {
            "codex-mcp": CodexMcpAdapter(project_root),
            "deepseek-dsh": DeepSeekHarnessAdapter(project_root),
            "manual": ManualHandoffAdapter(project_root),
        }

    def capabilities(self) -> dict[str, dict[str, object]]:
        return {name: adapter.capabilities() for name, adapter in self.adapters.items()}

    def get(self, name: str):  # noqa: ANN001
        try:
            return self.adapters[name]
        except KeyError as error:
            raise ValueError(f"unknown execution adapter: {name}") from error
