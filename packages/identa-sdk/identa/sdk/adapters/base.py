# packages/identa-sdk/identa/sdk/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from identa.core.domain.structure import AgentStructure

@dataclass
class WrappedAgent:
    """A traced callable. Original agent is preserved unmutated."""
    callable: Callable[[Any], Any]   # signature: (input) -> output, used by EvaluationEngine
    original: Any                     # untouched user agent
    framework_name: str

    def __call__(self, input: Any) -> Any:
        return self.callable(input)

class BaseAdapter(ABC):
    framework_name: str = "unknown"

    @abstractmethod
    def inspect(self, agent: Any) -> AgentStructure: ...

    @abstractmethod
    def wrap(self, agent: Any) -> WrappedAgent:
        """Return a traced callable. MUST NOT mutate `agent`."""
