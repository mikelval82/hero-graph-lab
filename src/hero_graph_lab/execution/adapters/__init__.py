"""Built-in execution adapters."""

from .deepseek_harness import DeepSeekHarnessAdapter
from .manual import ManualHandoffAdapter

__all__ = ["DeepSeekHarnessAdapter", "ManualHandoffAdapter"]
