from abc import ABC, abstractmethod
from typing import Any, Optional
from identa.core.domain.tracing import TraceArtifact

class Metric(ABC):
    @abstractmethod
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        pass

class ExactMatchMetric(Metric):
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        return 1.0 if str(output).strip() == str(expected).strip() else 0.0

class LatencyMetric(Metric):
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        if not trace or not trace.spans:
            return 0.0
        # Sum of all top-level spans or just the duration of the whole trace
        return sum(s.timing.latency_ms for s in trace.spans if s.parent_id is None)
