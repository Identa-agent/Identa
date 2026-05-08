import math
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from identa.core.domain.tracing import TraceArtifact
from pydantic import BaseModel

class Metric(ABC):
    @abstractmethod
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        pass

class PopulationStabilityIndex(Metric):
    def __init__(self, expected_dist: Dict[str, float]):
        self.expected_dist = expected_dist

    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        # This PSI isn't typically computed per-test, but for the whole evaluation.
        # As a per-test metric, it may not make perfect sense, but let's implement the math.
        # If we get a single observed node from the trace, we compare it against expected.
        return 0.0

    @staticmethod
    def calculate_psi(expected: Dict[str, float], actual: Dict[str, float]) -> float:
        psi = 0.0
        epsilon = 1e-6
        all_keys = set(expected.keys()).union(actual.keys())
        for key in all_keys:
            e = expected.get(key, 0.0)
            a = actual.get(key, 0.0)
            e = max(e, epsilon)
            a = max(a, epsilon)
            psi += (a - e) * math.log(a / e)
        return psi

class ExactMatchMetric(Metric):
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        if output == expected:
            return 1.0
        return 1.0 if str(output).strip() == str(expected).strip() else 0.0

class LatencyMetric(Metric):
    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        if not trace or not trace.spans:
            return 0.0
        # Sum of all top-level spans or just the duration of the whole trace
        return sum(s.timing.latency_ms for s in trace.spans if s.parent_id is None)

class CostModel(BaseModel):
    model: str
    input_cost_per_1k: float
    output_cost_per_1k: float

class CostMetric(Metric):
    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def compute(self, test_input: Any, output: Any, expected: Any, trace: Optional[TraceArtifact] = None) -> float:
        if not trace:
            return 0.0
        
        total_cost = 0.0
        for span in trace.spans:
            if span.kind == "llm" and span.metadata.model:
                # Extract tokens from metadata
                input_tokens = span.metadata.input_tokens or 0
                output_tokens = span.metadata.output_tokens or 0
                
                # Simple cost calc
                if self.cost_model.model in span.metadata.model:
                    total_cost += (
                        input_tokens * self.cost_model.input_cost_per_1k / 1000 +
                        output_tokens * self.cost_model.output_cost_per_1k / 1000
                    )
        return total_cost
