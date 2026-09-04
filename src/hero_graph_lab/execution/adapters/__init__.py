"""Built-in execution adapters."""

from .deepseek_harness import DeepSeekHarnessAdapter
from .codex import CodexMcpAdapter
from .manual import ManualHandoffAdapter

__all__ = ["CodexMcpAdapter", "DeepSeekHarnessAdapter", "ManualHandoffAdapter"]
