# packages/identa-sdk/identa/sdk/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from contextlib import contextmanager
from typing import Any, Callable, Dict
from identa.core.domain.structure import AgentStructure

@dataclass
class WrappedAgent:
    """A traced callable. Original agent is preserved unmutated."""
    callable: Callable[[Any], Any]   # signature: (input) -> output, used by EvaluationEngine
    original: Any                     # untouched user agent
    framework_name: str
    interventions: Dict[str, Any] = field(default_factory=dict)

    def __call__(self, input: Any, **kwargs) -> Any:
        return self.callable(input, **kwargs)

    @contextmanager
    def intervene_node(self, node_id: str, mock_output: Any):
        self.interventions[node_id] = mock_output
        try:
            yield
        finally:
            self.interventions.pop(node_id, None)

class BaseAdapter(ABC):
    framework_name: str = "unknown"

    @abstractmethod
    def inspect(self, agent: Any) -> AgentStructure: ...

    @abstractmethod
    def wrap(self, agent: Any) -> WrappedAgent:
        """Return a traced callable. MUST NOT mutate `agent`."""
