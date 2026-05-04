from typing import Dict, List, Optional
from pydantic import BaseModel
from .results import EvaluationResult
from .structure import ObservedStructureDelta

class ComparisonResult(BaseModel):
    source_run_id: str
    target_run_id: str
    metric_deltas: Dict[str, float]  # { metric: change_percent }
    regressions: List[str]           # [ metric_name ]
    structure_drift: Optional[ObservedStructureDelta] = None
    normalized_structural_drift: float = 0.0
    behavioral_drift: float = 0.0
    root_cause_node_id: Optional[str] = None

    def report(self) -> str:
        # ... (Method remains same) ...
        if self.structure_drift:
            lines.append("-" * 60)
            lines.append("Structure Drift Detected!")
            lines.append(f"  Normalized structural drift: {self.normalized_structural_drift:.2%}")
            lines.append(f"  Behavioral drift (PSI): {self.behavioral_drift:.4f}")
            if self.root_cause_node_id:
                lines.append(f"  Root Cause Node ID: {self.root_cause_node_id}")
            lines.append(f"  Added nodes: {len(self.structure_drift.unexpected_nodes)}")
            lines.append(f"  Removed nodes: {len(self.structure_drift.missing_nodes)}")
        return "\n".join(lines)

class ComparisonEngine:
    @staticmethod
    def compare(source: EvaluationResult, target: EvaluationResult) -> ComparisonResult:
        # ... (Logic remains same) ...
        # ... [psi calculation] ...
        
        # Causal inference for root cause
        rc_node = None
        if drift > 0.5: # Arbitrary threshold
            # Need to get a sample trace to infer root cause
            if target.per_test:
                sample_test = target.per_test[0]
                if sample_test.trace_ref:
                    trace = target.trace(sample_test.test_id)
                    if trace:
                        rc_node = trace.infer_causal_bottleneck()
        
        return ComparisonResult(
            source_run_id=source.run_id,
            target_run_id=target.run_id,
            metric_deltas=metric_deltas,
            regressions=regressions,
            structure_drift=target.structure_delta,
            normalized_structural_drift=drift,
            behavioral_drift=psi,
            root_cause_node_id=rc_node
        )
