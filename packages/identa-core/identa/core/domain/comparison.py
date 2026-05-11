from typing import Dict, List, Optional
from pydantic import BaseModel
from .results import EvaluationResult
from .structure import ObservedStructureDelta
from .metrics import PopulationStabilityIndex

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
        lines = [
            "=" * 60,
            f"Comparison: {self.source_run_id} → {self.target_run_id}",
            "=" * 60,
        ]
        if self.metric_deltas:
            lines.append("Metric Deltas:")
            for metric, delta in self.metric_deltas.items():
                sign = "+" if delta > 0 else ""
                lines.append(f"  {metric}: {sign}{delta:.2%}")
        if self.regressions:
            lines.append("-" * 60)
            lines.append(f"⚠️  Regressions: {', '.join(self.regressions)}")
        if self.structure_drift:
            lines.append("-" * 60)
            lines.append("Structure Drift Detected!")
            lines.append(f"  Normalized structural drift: {self.normalized_structural_drift:.2%}")
            lines.append(f"  Behavioral drift (PSI): {self.behavioral_drift:.4f}")
            if self.root_cause_node_id:
                lines.append(f"  Root Cause Node ID: {self.root_cause_node_id}")
            lines.append(f"  Added nodes: {len(self.structure_drift.unexpected_nodes)}")
            lines.append(f"  Removed nodes: {len(self.structure_drift.missing_nodes)}")
        if not self.regressions and not self.structure_drift:
            lines.append("✅ No regressions or structural drift detected.")
        return "\n".join(lines)

class ComparisonEngine:
    @staticmethod
    def compare(source: EvaluationResult, target: EvaluationResult) -> ComparisonResult:
        # 1. Compute metric deltas
        source_aggs = {agg.metric_name: agg.value for agg in source.aggregates}
        target_aggs = {agg.metric_name: agg.value for agg in target.aggregates}

        all_metrics = set(source_aggs.keys()) | set(target_aggs.keys())
        metric_deltas: Dict[str, float] = {}
        regressions: List[str] = []

        for metric in all_metrics:
            s_val = source_aggs.get(metric)
            t_val = target_aggs.get(metric)

            if s_val is not None and t_val is not None:
                if s_val == 0:
                    delta = 0.0 if t_val == 0 else float('inf')
                else:
                    delta = (t_val - s_val) / abs(s_val)
                metric_deltas[metric] = delta

                # Detect regressions: lower is worse for most metrics (exact_match, etc.)
                # except latency/cost where lower is better
                is_lower_better = metric in ("latency", "cost")
                if is_lower_better:
                    if t_val > s_val * 1.1:  # 10% tolerance
                        regressions.append(metric)
                else:
                    if t_val < s_val * 0.9:  # 10% tolerance
                        regressions.append(metric)

        # 2. Compute structural drift via PSI on observed node frequencies
        drift = 0.0
        psi = 0.0

        if target.structure_delta:
            drift = target.structure_delta.normalized_structural_drift

            # Compute PSI on observed_frequency distributions if both have structure deltas
            if source.structure_delta and source.structure_delta.observed_frequency and target.structure_delta.observed_frequency:
                psi = PopulationStabilityIndex.calculate_psi(
                    source.structure_delta.observed_frequency,
                    target.structure_delta.observed_frequency
                )

        # 3. Causal inference for root cause
        rc_node = None
        if drift > 0.5:
            if target.per_test:
                sample_test = target.per_test[0]
                if sample_test.trace_ref:
                    try:
                        trace = target.trace(sample_test.test_id)
                        if trace:
                            rc_node = trace.infer_causal_bottleneck()
                    except (ValueError, Exception):
                        pass  # artifact_port may not be available

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
