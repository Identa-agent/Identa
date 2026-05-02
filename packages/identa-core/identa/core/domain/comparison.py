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

    def report(self) -> str:
        """Returns a human-readable report of the comparison."""
        lines = [
            f"Comparison Report: {self.source_run_id} vs {self.target_run_id}",
            "-" * 60,
            "Metric Deltas:"
        ]
        for metric, delta in self.metric_deltas.items():
            lines.append(f"  {metric}: {delta:+.2%}")
        
        if self.regressions:
            lines.append("-" * 60)
            lines.append("Regressions Detected:")
            for reg in self.regressions:
                lines.append(f"  [!] {reg}")
        
        if self.structure_drift:
            lines.append("-" * 60)
            lines.append("Structure Drift Detected!")
            # Basic summary of drift
            lines.append(f"  Added nodes: {len(self.structure_drift.added_nodes)}")
            lines.append(f"  Removed nodes: {len(self.structure_drift.removed_nodes)}")
            lines.append(f"  Modified nodes: {len(self.structure_drift.modified_nodes)}")
            
        return "\n".join(lines)

class ComparisonEngine:
    @staticmethod
    def compare(source: EvaluationResult, target: EvaluationResult) -> ComparisonResult:
        """Compares two evaluation results and identifies regressions."""
        metric_deltas = {}
        regressions = []
        
        # Source aggregates by name for lookup
        source_aggs = {agg.metric_name: agg.value for agg in source.aggregates}
        
        for target_agg in target.aggregates:
            m_name = target_agg.metric_name
            if m_name in source_aggs:
                s_val = source_aggs[m_name]
                t_val = target_agg.value
                
                if s_val == 0:
                    delta = 0.0 if t_val == 0 else 1.0 # Avoid div by zero
                else:
                    delta = (t_val - s_val) / s_val
                
                metric_deltas[m_name] = delta
                
                # Simple regression detection: if target < source (assuming higher is better for all metrics for now)
                # In a real impl, we'd check MetricSpec.minimize
                # Since we don't have MetricSpec here, we'll assume higher is better.
                if t_val < s_val:
                    regressions.append(m_name)
        
        return ComparisonResult(
            source_run_id=source.run_id,
            target_run_id=target.run_id,
            metric_deltas=metric_deltas,
            regressions=regressions,
            structure_drift=target.structure_delta
        )
