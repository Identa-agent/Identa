import uuid
from typing import Any, List, Optional, Protocol, Union, Dict
from identa.core.domain.models import MetricSpec, MetricAggregate
from identa.core.domain.results import EvaluationResult, PerTestResult
from identa.core.domain.structure import AgentStructure
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.metrics import Metric

class AgentProtocol(Protocol):
    def __call__(self, input: Any) -> Any:
        ...

class EvaluationEngine:
    def __init__(self, metrics_registry: Dict[str, Metric]):
        self.metrics_registry = metrics_registry

    def evaluate(
        self,
        agent: AgentProtocol,
        suite: List[Dict[str, Any]],
        run_id: str,
        resolution: str = "boundary",
        structure: Optional[AgentStructure] = None,
        metrics: Optional[List[Union[str, MetricSpec]]] = None,
        mode: str = "controlled"
    ) -> EvaluationResult:
        per_test_results = []
        aggregates = {}
        
        # 1. Inspect if needed (framework specific, handled by SDK usually)
        structure_hash = structure.version_hash if structure else None
        
        # 2. Prepare metrics
        resolved_metrics = []
        if metrics:
            for m in metrics:
                if isinstance(m, str):
                    resolved_metrics.append(MetricSpec(name=m, metric=m))
                else:
                    resolved_metrics.append(m)

        # 3. Evaluation Loop
        for test in suite:
            test_id = test.get("id", str(uuid.uuid4()))
            test_input = test.get("input")
            expected = test.get("expected")
            
            # Start Trace
            TracingService.start_trace(structure_hash=structure_hash)
            
            # Execute Agent
            output = agent(test_input)
            
            # End Trace
            trace = TracingService.end_trace()
            
            # Compute Metrics
            scores = {}
            for m_spec in resolved_metrics:
                metric_impl = self.metrics_registry.get(m_spec.metric)
                if metric_impl:
                    score = metric_impl.compute(test_input, output, expected, trace)
                    scores[m_spec.name] = score
                    
                    # Update aggregates (simple mean for now)
                    if m_spec.name not in aggregates:
                        aggregates[m_spec.name] = {"sum": 0.0, "count": 0}
                    aggregates[m_spec.name]["sum"] += score
                    aggregates[m_spec.name]["count"] += 1

            per_test_results.append(PerTestResult(
                test_id=test_id,
                output=output,
                scores=scores,
                trace_ref=trace.id if trace else None
            ))

        # 4. Final Aggregates
        final_aggregates = [
            MetricAggregate(
                metric_name=name,
                value=data["sum"] / data["count"],
                count=data["count"]
            )
            for name, data in aggregates.items()
        ]

        return EvaluationResult(
            id=str(uuid.uuid4()),
            run_id=run_id,
            suite_hash="TODO",
            suite_version="TODO",
            structure_hash=structure_hash,
            resolution=resolution,
            metric_specs=resolved_metrics,
            aggregates=final_aggregates,
            per_test=per_test_results
        )
