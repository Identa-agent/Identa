import hashlib
import json
import uuid
from datetime import timezone
from typing import Any, List, Optional, Protocol, Union, Dict
from identa.core.domain.models import MetricSpec, MetricAggregate
from identa.core.domain.results import EvaluationResult, PerTestResult
from identa.core.domain.structure import AgentStructure, ObservedStructureDelta
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.metrics import Metric
from identa.core.ports.artifacts import ArtifactPort
import io


def _compute_suite_hash(suite: List[Dict[str, Any]]) -> str:
    """Stable SHA-256 of the test suite content, key-sorted for reproducibility."""
    canonical = json.dumps(
        [dict(sorted(t.items())) for t in suite],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _extract_suite_version(suite: List[Dict[str, Any]], suite_hash: str) -> str:
    """Return explicit version if present in the suite metadata, else derive from hash prefix."""
    if suite and isinstance(suite[0], dict):
        # Allow suites passed as [{"version": "v1.2", ...}, ...] or just a bare list.
        if "version" in suite[0] and isinstance(suite[0]["version"], str):
            return suite[0]["version"]
    return f"auto:{suite_hash[:8]}"

class AgentProtocol(Protocol):
    def __call__(self, input: Any) -> Any:
        ...

class EvaluationEngine:
    def __init__(self, metrics_registry: Dict[str, Metric], artifact_port: Optional[ArtifactPort] = None):
        self.metrics_registry = metrics_registry
        self.artifact_port = artifact_port

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
        trace_refs = []
        observed_nodes_across_suite = {} # { node_id: count }

        # 1. Compute stable suite identity (replaces hardcoded "TODO").
        suite_hash = _compute_suite_hash(suite)
        suite_version = _extract_suite_version(suite, suite_hash)

        # 2. Resolve structure_hash from the snapshot, if provided.
        structure_hash = structure.version_hash if structure else None

        # 3. Prepare metrics
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
            
            if trace:
                for span in trace.spans:
                    if span.metadata.node_id:
                        nid = span.metadata.node_id
                        observed_nodes_across_suite[nid] = observed_nodes_across_suite.get(nid, 0) + 1
            
            trace_id = None
            
            trace_id = None
            if trace and self.artifact_port:
                # Save trace as gzip JSONL
                content = trace.to_gzip_jsonl()
                trace_id = self.artifact_port.save_artifact(run_id, f"trace_{test_id}.jsonl.gz", io.BytesIO(content))
                trace_refs.append(trace_id)
            
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

            # Compute Node Metrics (if resolution != boundary)
            node_scores = {}
            if resolution != "boundary" and trace:
                for span in trace.spans:
                    if span.metadata.node_id:
                        nid = span.metadata.node_id
                        if nid not in node_scores:
                            node_scores[nid] = {}
                        # For now, latency is the primary node-level metric we can auto-extract
                        node_scores[nid]["latency"] = span.timing.latency_ms

            per_test_results.append(PerTestResult(
                test_id=test_id,
                input=test_input,
                expected=expected,
                output=output,
                scores=scores,
                node_scores=node_scores,
                trace_ref=trace_id
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

        # 5. Compute Structure Delta
        structure_delta = None
        if resolution != "boundary":
            # In a real impl, we'd pass the actual counts to ObservedStructureDelta.compute
            # For now, we'll use the tracked counts.
            structure_delta = ObservedStructureDelta.compute(structure, per_test_results)
            # Patching the frequencies for the wow factor
            total = len(per_test_results)
            structure_delta.observed_frequency = {nid: count/total for nid, count in observed_nodes_across_suite.items()}
            
            if structure:
                intended_ids = {n.id for n in structure.nodes}
                observed_ids = set(observed_nodes_across_suite.keys())
                for nid in intended_ids - observed_ids:
                    structure_delta.missing_nodes[nid] = 0
                for nid in observed_ids - intended_ids:
                    structure_delta.unexpected_nodes[nid] = observed_nodes_across_suite[nid]

        return EvaluationResult(
            id=str(uuid.uuid4()),
            run_id=run_id,
            suite_hash=suite_hash,
            suite_version=suite_version,
            structure_hash=structure_hash,
            resolution=resolution,
            metric_specs=resolved_metrics,
            aggregates=final_aggregates,
            per_test=per_test_results,
            trace_refs=trace_refs,
            structure_delta=structure_delta,
            artifact_port=self.artifact_port
        )
