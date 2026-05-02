from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from .models import MetricSpec, MetricAggregate
from .structure import ObservedStructureDelta

class PerTestResult(BaseModel):
    test_id: str
    input: Any = None
    expected: Any = None
    output: Any
    scores: Dict[str, float]
    node_scores: Dict[str, Dict[str, float]] = Field(default_factory=dict) # { node_id: { metric: score } }
    trace_ref: Optional[str] = None

class FailureRecord(BaseModel):
    test_id: str
    input: Any
    expected_output: Any
    actual_output: Any
    scores: Dict[str, float]
    trace_ref: Optional[str] = None

class EvaluationResult(BaseModel):
    id: str
    run_id: str
    suite_hash: str
    suite_version: str
    structure_hash: Optional[str] = None
    resolution: Literal["boundary", "node", "tool", "llm"]
    metric_specs: List[MetricSpec]
    aggregates: List[MetricAggregate]
    per_test: List[PerTestResult]
    trace_refs: List[str] = Field(default_factory=list)
    structure_delta: Optional[ObservedStructureDelta] = None

    def summary(self) -> str:
        """Returns a human-readable summary of the evaluation results."""
        lines = [
            f"Evaluation Result {self.id}",
            f"Run ID: {self.run_id}",
            f"Suite Hash: {self.suite_hash} ({self.suite_version})",
            f"Resolution: {self.resolution}",
            "-" * 40,
            "Aggregates:"
        ]
        for agg in self.aggregates:
            lines.append(f"  {agg.metric_name}: {agg.value:.4f} (n={agg.count})")
        
        fail_count = len(self.failures())
        lines.append("-" * 40)
        lines.append(f"Total Tests: {len(self.per_test)}")
        lines.append(f"Failures: {fail_count}")
        
        return "\n".join(lines)

    def failures(self, threshold: float = 1.0) -> List[FailureRecord]:
        """Returns a list of FailureRecord for tests where any metric score was below threshold."""
        fails = []
        for res in self.per_test:
            is_fail = any(score < threshold for score in res.scores.values())
            if is_fail:
                fails.append(FailureRecord(
                    test_id=res.test_id,
                    input=res.input,
                    expected_output=res.expected,
                    actual_output=res.output,
                    scores=res.scores,
                    trace_ref=res.trace_ref
                ))
        return fails

    def to_df(self) -> Any:
        """Converts the per-test results to a pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_df(). Install it with 'pip install pandas'.")
        
        data = []
        for res in self.per_test:
            row = {
                "test_id": res.test_id,
                "output": str(res.output),
                "trace_ref": res.trace_ref
            }
            # Flatten scores
            for name, score in res.scores.items():
                row[f"score:{name}"] = score
            # Flatten node scores
            for node_id, n_scores in res.node_scores.items():
                for name, score in n_scores.items():
                    row[f"node:{node_id}:{name}"] = score
            data.append(row)
        
        return pd.DataFrame(data)

    def by_node(self) -> Dict[str, List[MetricAggregate]]:
        """Returns aggregates grouped by node_id."""
        node_aggs: Dict[str, Dict[str, List[float]]] = {} # { node_id: { metric: [scores] } }
        
        for res in self.per_test:
            for node_id, n_scores in res.node_scores.items():
                if node_id not in node_aggs:
                    node_aggs[node_id] = {}
                for m_name, score in n_scores.items():
                    if m_name not in node_aggs[node_id]:
                        node_aggs[node_id][m_name] = []
                    node_aggs[node_id][m_name].append(score)
        
        result = {}
        for node_id, m_data in node_aggs.items():
            aggs = []
            for m_name, scores in m_data.items():
                aggs.append(MetricAggregate(
                    metric_name=m_name,
                    value=sum(scores) / len(scores),
                    count=len(scores)
                ))
            result[node_id] = aggs
        return result
