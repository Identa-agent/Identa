import hashlib
import json
import uuid
import io
from datetime import timezone
from typing import Any, List, Optional, Protocol, Union, Dict
from identa.core.domain.models import MetricSpec, MetricAggregate
from identa.core.domain.results import EvaluationResult, PerTestResult
from identa.core.domain.structure import AgentStructure, ObservedStructureDelta
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.metrics import Metric
from identa.core.domain.drift_engine import EnterpriseDriftEngine
from identa.core.ports.artifacts import ArtifactPort
from identa.core.ports.llm_judge import LLMJudgePort


class EmbeddingProvider(Protocol):
    def get_embedding(self, text: str) -> list:
        ...


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
    def __init__(self, metrics_registry: Dict[str, Metric], artifact_port: Optional[ArtifactPort] = None, 
                 embedding_provider: Optional[EmbeddingProvider] = None, llm_judge: Optional[LLMJudgePort] = None):
        self.metrics_registry = metrics_registry
        self.artifact_port = artifact_port
        self.embedding_provider = embedding_provider
        self.llm_judge = llm_judge
        self.drift_engine = EnterpriseDriftEngine(embedding_provider, llm_judge)

    def evaluate(
        self,
        agent: AgentProtocol,
        suite: List[Dict[str, Any]],
        run_id: str,
        resolution: str = "boundary",
        structure: Optional[AgentStructure] = None,
        metrics: Optional[List[Union[str, MetricSpec]]] = None,
        mode: str = "controlled",
        baseline_texts: Optional[List[str]] = None,
        baseline_structure: Optional[AgentStructure] = None,
        baseline_traces: Optional[List[List[str]]] = None,
        baseline_node_outputs: Optional[Dict[str, List[Any]]] = None,
        drift_mode: str = "standard",
        max_concurrency: int = 1
    ) -> EvaluationResult:
        # [Inside evaluate]
        # ... logic ...
        per_test_results = []
        aggregates = {}
        trace_refs = []
        observed_nodes_across_suite = {} # { node_id: count }
        current_texts = []
        current_traces = []
        current_node_outputs = {}

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

        def run_one(test):
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
            node_scores = {} # { node_id: { metric: score } }
    
            for m_spec in resolved_metrics:
                metric_impl = self.metrics_registry.get(m_spec.metric)
                if metric_impl:
                    # Overall score
                    score = metric_impl.compute(test_input, output, expected, trace)
                    scores[m_spec.name] = score
                    
                    # Per-node scores if trace is available
                    if trace and trace.spans:
                        # Group spans by node
                        nodes_in_trace = {}
                        for span in trace.spans:
                            if span.node_id:
                                if span.node_id not in nodes_in_trace:
                                    nodes_in_trace[span.node_id] = []
                                nodes_in_trace[span.node_id].append(span)
                        
                        for node_id, node_spans in nodes_in_trace.items():
                            # Create a sub-trace for this node
                            node_trace = trace.__class__(
                                id=f"{trace.id}_{node_id}",
                                structure_hash=trace.structure_hash,
                                spans=node_spans
                            )
                            n_score = metric_impl.compute(test_input, output, expected, node_trace)
                            if node_id not in node_scores:
                                node_scores[node_id] = {}
                            node_scores[node_id][m_spec.name] = n_score

            trace_id = None
            if trace and self.artifact_port:
                content = trace.to_gzip_jsonl()
                trace_id = self.artifact_port.save_artifact(run_id, f"trace_{test_id}.jsonl.gz", io.BytesIO(content))

            return {
                "test_id": test_id,
                "input": test_input,
                "expected": expected,
                "output": output,
                "scores": scores,
                "node_scores": node_scores,
                "trace": trace,
                "trace_id": trace_id
            }

        if max_concurrency > 1:
            from concurrent.futures import ThreadPoolExecutor
            from contextvars import copy_context
            with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
                futures = [executor.submit(copy_context().run, run_one, test) for test in suite]
                loop_results = [f.result() for f in futures]
        else:
            loop_results = [run_one(test) for test in suite]

        # 4. Process loop results
        for res in loop_results:
            test_id = res["test_id"]
            test_input = res["input"]
            expected = res["expected"]
            output = res["output"]
            scores = res["scores"]
            node_scores = res["node_scores"]
            trace = res["trace"]
            trace_id = res["trace_id"]

            current_texts.append(str(output))
            if trace:
                current_traces.append(trace.node_sequence)
                for span in trace.spans:
                    if span.metadata.node_id:
                        nid = span.metadata.node_id
                        observed_nodes_across_suite[nid] = observed_nodes_across_suite.get(nid, 0) + 1
                        current_node_outputs.setdefault(nid, []).append(span.outputs)
            
            if trace_id:
                trace_refs.append(trace_id)
            
            per_test_results.append(PerTestResult(
                test_id=test_id,
                input=test_input,
                expected=expected,
                output=output,
                scores=scores,
                node_scores=node_scores,
                trace_ref=trace_id
            ))
            
            # Update aggregates
            for m_name, score in scores.items():
                if m_name not in aggregates:
                    aggregates[m_name] = {"sum": 0.0, "count": 0}
                aggregates[m_name]["sum"] += score
                aggregates[m_name]["count"] += 1

        # 4. Final Aggregates
        final_aggregates = [
            MetricAggregate(
                metric_name=name,
                value=data["sum"] / data["count"],
                count=data["count"]
            )
            for name, data in aggregates.items()
        ]

        # Calculate drift
        semantic_drift = 0.0
        drift_report = None
        
        drift_report = self.drift_engine.detect(
            run_id=run_id,
            baseline_structure=baseline_structure,
            current_structure=structure,
            baseline_texts=baseline_texts or [],
            current_texts=current_texts,
            baseline_traces=baseline_traces or [],
            current_traces=current_traces,
            baseline_node_outputs=baseline_node_outputs,
            current_node_outputs=current_node_outputs,
            drift_mode=drift_mode,
        )
        semantic_drift = drift_report.composite_score        
        # 5. Compute Structure Delta
        structure_delta = None
        if resolution != "boundary":
            intended_ids = {n.id for n in structure.nodes} if structure else set()
            observed_ids = set(observed_nodes_across_suite.keys())
            
            missing_nodes = {nid: 0 for nid in intended_ids - observed_ids}
            unexpected_nodes = {nid: observed_nodes_across_suite[nid] for nid in observed_ids - intended_ids}
            
            total_unique_nodes = len(intended_ids.union(observed_ids))
            
            total = len(per_test_results)
            observed_frequency = {nid: count/total for nid, count in observed_nodes_across_suite.items()}
            
            structure_delta = ObservedStructureDelta.compute(
                intended=structure,
                unexpected_nodes=unexpected_nodes,
                missing_nodes=missing_nodes,
                total_unique_nodes=total_unique_nodes,
                observed_frequency=observed_frequency,
                traced_test_count=len([r for r in per_test_results if r.trace_ref]),
                total_test_count=total
            )

        return EvaluationResult(
            id=str(uuid.uuid4()),
            run_id=run_id,
            suite_hash=suite_hash,
            suite_version=suite_version,
            structure_hash=structure_hash,
            resolution=resolution,
            evaluation_mode=mode,
            metric_specs=resolved_metrics,
            aggregates=final_aggregates,
            per_test=per_test_results,
            trace_refs=trace_refs,
            structure_delta=structure_delta,
            artifact_port=self.artifact_port,
            semantic_drift=semantic_drift,
            drift_report=drift_report
        )
