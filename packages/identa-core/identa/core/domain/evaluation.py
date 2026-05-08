import hashlib
import json
import uuid
import numpy as np
from scipy.stats import wasserstein_distance
from scipy.spatial.distance import cdist
import ot
from datetime import timezone
from typing import Any, List, Optional, Protocol, Union, Dict
from identa.core.domain.models import MetricSpec, MetricAggregate
from identa.core.domain.results import EvaluationResult, PerTestResult
from identa.core.domain.structure import AgentStructure, ObservedStructureDelta
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.metrics import Metric
from identa.core.ports.artifacts import ArtifactPort
from identa.core.ports.llm_judge import LLMJudgePort
import io

# ... [rest of the methods: _compute_suite_hash, _extract_suite_version] ...

class EmbeddingProvider(Protocol):
    def get_embedding(self, text: str) -> np.ndarray:
        ...

# ... [EvaluationEngine class] ...


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

    def calculate_semantic_drift(self, baseline_texts: List[str], current_texts: List[str]) -> float:
        if not self.embedding_provider or not baseline_texts or not current_texts:
            return 0.0

        baseline_embeddings = np.array([self.embedding_provider.get_embedding(t) for t in baseline_texts])
        current_embeddings = np.array([self.embedding_provider.get_embedding(t) for t in current_texts])

        # 2-Wasserstein via optimal transport on cosine distance matrix
        M = cdist(baseline_embeddings, current_embeddings, metric='cosine')
        a = np.ones(len(baseline_embeddings)) / len(baseline_embeddings)
        b = np.ones(len(current_embeddings)) / len(current_embeddings)
        return float(ot.emd2(a, b, M))

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
        drift_mode: str = "standard"
    ) -> EvaluationResult:
        # [Inside evaluate]
        # Branching logic for drift_mode
        qualitative_drift = 0.0
        if drift_mode == "vanguard":
            # Initialize/Run advanced models (scaffold for now)
            pass
        elif drift_mode == "standard":
            # Standard stats
            pass
        # ... logic ...
        per_test_results = []
        aggregates = {}
        trace_refs = []
        observed_nodes_across_suite = {} # { node_id: count }
        current_texts = []

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
            current_texts.append(str(output))
            
            # End Trace
            trace = TracingService.end_trace()
            
            # ... [rest of the evaluate method logic] ...
            if trace:
                for span in trace.spans:
                    if span.metadata.node_id:
                        nid = span.metadata.node_id
                        observed_nodes_across_suite[nid] = observed_nodes_across_suite.get(nid, 0) + 1
            
            trace_id = None
            if trace and self.artifact_port:
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

            per_test_results.append(PerTestResult(
                test_id=test_id,
                input=test_input,
                expected=expected,
                output=output,
                scores=scores,
                node_scores={},
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

        # Calculate semantic drift if baseline is provided
        semantic_drift = 0.0
        if baseline_texts:
            semantic_drift = self.calculate_semantic_drift(baseline_texts, current_texts)
            
            if drift_mode == "vanguard" and self.llm_judge:
                # Pairwise judge between baseline and current outputs
                total_q_drift = 0.0
                for b_text, c_text in zip(baseline_texts, current_texts):
                    total_q_drift += self.llm_judge.judge_drift(b_text, c_text)
                qualitative_drift = total_q_drift / len(baseline_texts)
                
                # Combine with semantic drift (0.6 semantic, 0.4 qualitative)
                semantic_drift = 0.6 * semantic_drift + 0.4 * qualitative_drift
        
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
            metric_specs=resolved_metrics,
            aggregates=final_aggregates,
            per_test=per_test_results,
            trace_refs=trace_refs,
            structure_delta=structure_delta,
            artifact_port=self.artifact_port,
            semantic_drift=semantic_drift
        )
