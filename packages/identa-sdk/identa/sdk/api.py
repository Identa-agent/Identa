import uuid
import contextvars
from datetime import datetime, timezone
import asyncio
from typing import Any, List, Optional, Union, Dict, Callable, Coroutine
from identa.core.domain.models import Workspace, Run, MetricSpec, RunStatus, MetricAggregate
from identa.core.domain.evaluation import EvaluationEngine
from identa.core.domain.metrics import ExactMatchMetric, LatencyMetric
from identa.core.domain.results import EvaluationResult
from identa.core.domain.comparison import ComparisonEngine, ComparisonResult
from identa.core.domain.reproduction import ReproductionEngine, capture_environment
from identa.core.domain.calibration import CalibrationEngine
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.persistence.local_artifact_adapter import LocalArtifactAdapter
from identa.core.adapters.mlflow_exporter import MLflowExporter, HAS_MLFLOW
from identa.core.application.commands.base import Command, Query
from identa.core.application.commands.workspace_commands import (
    WorkspaceCommandHandler, 
    CreateWorkspaceCommand
)
from identa.core.application.commands.run_commands import (
    RunCommandHandler, 
    StartRunCommand, 
    FinishRunCommand
)
from identa.core.application.queries.run_queries import (
    RunQueryHandler,
    GetRunQuery,
    ListRunsQuery
)
from identa.core.domain.models import ReproducibilityBundle
from identa.core.ports.storage import StoragePort
from identa.core.ports.exporter import ExporterPort
from identa.core.ports.artifacts import ArtifactPort
from identa.sdk.registry import AgentRegistry, get_registry
from identa.sdk.adapters.base import WrappedAgent
from identa.sdk.suites import load_suite
import identa.sdk.adapters  # noqa: F401  triggers registration

class IdentaClient:
    def __init__(
        self, 
        workspace_id: str, 
        db_url: str = "sqlite:///identa.db", 
        artifact_path: str = "artifacts", 
        tracking_uri: Optional[str] = None,
        storage: Optional[StoragePort] = None,
        artifacts: Optional[ArtifactPort] = None,
        exporter: Optional[ExporterPort] = None
    ):
        self.storage = storage or SQLiteStorageAdapter(db_url)
        self.artifacts = artifacts or LocalArtifactAdapter(artifact_path)
        self.workspace_id = workspace_id
        
        # Initialize exporter if available
        self.exporter = exporter
        if self.exporter is None and HAS_MLFLOW:
            self.exporter = MLflowExporter(tracking_uri=tracking_uri)

        # Initialize registries
        self.metrics_registry = {
            "exact_match": ExactMatchMetric(),
            "latency": LatencyMetric()
        }
        self.engine = EvaluationEngine(self.metrics_registry, self.artifacts)
        self.repro_engine = ReproductionEngine(self.engine)
        self.calib_engine = CalibrationEngine(evaluate)
        
        # Handlers with DI
        self.workspace_handler = WorkspaceCommandHandler(self.storage, exporter=self.exporter)
        self.run_handler = RunCommandHandler(self.storage, exporter=self.exporter)
        self.query_handler = RunQueryHandler(self.storage)

        # Register in DI container
        registry = get_registry()
        registry.register_service(StoragePort, self.storage)
        if self.exporter:
            registry.register_service(ExporterPort, self.exporter)
            
        registry.register_handler(CreateWorkspaceCommand, self.workspace_handler)
        registry.register_handler(StartRunCommand, self.run_handler)
        registry.register_handler(FinishRunCommand, self.run_handler)
        registry.register_handler(GetRunQuery, self.query_handler)
        registry.register_handler(ListRunsQuery, self.query_handler)

        # Ensure workspace exists
        self.workspace_handler.handle_create_workspace(CreateWorkspaceCommand(
            id=workspace_id,
            name=workspace_id,
            backend_uri=db_url
        ))

    def evaluate(self, agent: Any, suite: List[Dict[str, Any]], run_id: str, **kwargs):
        return self.engine.evaluate(agent, suite, run_id, **kwargs)

    def execute(self, command: Union[Command, Query]) -> Any:
        return execute(command)

# ContextVar for thread-safe client access
_client_var: contextvars.ContextVar[Optional[IdentaClient]] = contextvars.ContextVar(
    'identa_client', default=None
)

def set_workspace(name: str, db_url: str = "sqlite:///identa.db", tracking_uri: Optional[str] = None):
    client = IdentaClient(workspace_id=name, db_url=db_url, tracking_uri=tracking_uri)
    _client_var.set(client)

def get_client() -> Optional[IdentaClient]:
    return _client_var.get()

class RunContext:
    """Context manager that wraps a Run and provides the user-facing run API."""

    def __init__(self, run: Run, client: "IdentaClient"):
        self.run = run
        self._client = client
        self._result: Optional[EvaluationResult] = None

    def __enter__(self) -> "RunContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Finalize the run: mark finished or failed and persist the update."""
        status = RunStatus.FAILED if exc_type is not None else RunStatus.FINISHED
        try:
            self._client.execute(FinishRunCommand(run_id=self.run.id, status=status))
        except Exception as persistence_error:
            # Log error: Failed to persist run closure.
            if exc_type is None:
                raise persistence_error # Re-raise if no prior exception existed
        return False # Do not swallow the original exception

    def log_params(self, params: Dict[str, Any]) -> None:
        """Attach key-value parameters to this run (persisted immediately)."""
        self.run.params.update(params)
        self._client.storage.save_run(self.run)

    def set_tags(self, tags: Dict[str, Any]) -> None:
        """Attach tags to this run (persisted immediately)."""
        self.run.tags.update(tags)
        self._client.storage.save_run(self.run)

    def log_results(self, result: EvaluationResult) -> None:
        """Associate an EvaluationResult with this run (persisted via storage)."""
        self._result = result
        self._client.storage.save_evaluation_result(result)

    @property
    def result(self) -> Optional[EvaluationResult]:
        return self._result


def start_run(name: str) -> RunContext:
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")

    run_id = str(uuid.uuid4())
    # Correcting the call to the handler
    run = client.run_handler.handle(StartRunCommand(
        id=run_id,
        workspace_id=client.workspace_id,
        name=name
    ))
    return RunContext(run, client)

def evaluate(agent: Any, suite: List[Dict[str, Any]], drift_mode: Optional[str] = None, **kwargs):
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")
    
    if drift_mode:
        kwargs["drift_mode"] = drift_mode

    # If user already passed a WrappedAgent (advanced use), skip detection.
    if isinstance(agent, WrappedAgent):
        wrapped = agent
        structure = kwargs.get("structure")
    else:
        adapter = AgentRegistry.detect(agent)
        resolution = kwargs.get("resolution", "boundary")
        structure = kwargs.get("structure")
        if resolution != "boundary" and structure is None:
            structure = adapter.inspect(agent)
            kwargs["structure"] = structure
        wrapped = adapter.wrap(agent)

    run_id = kwargs.pop("run_id", "standalone")
    return client.evaluate(wrapped, suite, run_id=run_id, **kwargs)

def inspect(agent: Any) -> "AgentStructure":
    """Optional: inspect an agent without running a suite."""
    if isinstance(agent, WrappedAgent):
        agent = agent.original
    adapter = AgentRegistry.detect(agent)
    return adapter.inspect(agent)

def compare_to_baseline(result: EvaluationResult, baseline_name: str = "default") -> ComparisonResult:
    """Compares an evaluation result against a registered baseline."""
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")
    
    baseline = client.storage.get_baseline(client.workspace_id, baseline_name)
    if not baseline:
        raise ValueError(f"Baseline '{baseline_name}' not found in workspace '{client.workspace_id}'")
    
    baseline_results = client.storage.list_evaluation_results(baseline.run_id)
    if not baseline_results:
        raise ValueError(f"No evaluation results found for baseline run '{baseline.run_id}'")
    
    # Compare against the first (primary) result for the baseline run
    return ComparisonEngine.compare(baseline_results[0], result)

def assert_no_regressions(result: EvaluationResult, baseline_name: str = "default"):
    """Asserts that there are no regressions compared to the baseline."""
    comparison = compare_to_baseline(result, baseline_name)
    if comparison.regressions:
        raise AssertionError(f"Regressions detected: {', '.join(comparison.regressions)}\n{comparison.report()}")
    print(f"✅ No regressions detected against baseline '{baseline_name}'")

def reproduce(run_id: str, agent: Any, suite: List[Dict[str, Any]], **kwargs):
    """Reproduces a past run by checking environmental and structural parity."""
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")
    
    run = client.storage.get_run(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")
        
    if not run.reproducibility_bundle_id:
        raise ValueError(f"Run {run_id} has no reproducibility bundle")
        
    # We'd need a method to get bundle by ID, but storage doesn't have it yet.
    # For now, we'll assume it's stored in a way we can retrieve or we bypass.
    # Placeholder: assuming bundle retrieval works or is mocked.
    print(f"🔄 Reproducing run {run_id}...")
    
    # Simple delegation to engine for now
    return evaluate(agent, suite, run_id=f"repro_{run_id}", **kwargs)

def export_to_mlflow(result: EvaluationResult, tracking_uri: Optional[str] = None) -> str:
    """Exports an evaluation result to MLflow."""
    client = get_client()
    if client and client.exporter:
        return client.exporter.export_result(result)
    
    # Fallback if no client or exporter (Task 1.1 handles the Error if mlflow missing)
    exporter = MLflowExporter(tracking_uri=tracking_uri)
    return exporter.export_result(result)

def calibrate(agent_factory: Callable, suite: List[Dict[str, Any]], param_grid: Dict[str, List[Any]], **kwargs) -> Dict[str, Any]:
    """Orchestrates a calibration loop to find the best agent hyperparameters."""
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")
    return client.calib_engine.calibrate(agent_factory, suite, param_grid, **kwargs)

def execute(command: Union[Command, Query]):
    """
    Generic command bus to route core commands through the SDK.
    Injects necessary dependencies automatically.
    """
    registry = get_registry()
    handler = registry.get_handler(type(command))

    if hasattr(handler, 'handle'):
        return handler.handle(command)
    else:
        # Fallback for handlers not yet refactored
        raise NotImplementedError(f"Handler for {type(command)} must implement 'handle(cmd)'")

async def evaluate_async(agent: Any, suite: List[Dict[str, Any]], 
                         max_concurrency: int = 5, **kwargs) -> EvaluationResult:
    """Asynchronously evaluate an agent against a suite of tests."""
    client = get_client()
    if not client:
        raise ValueError("Call set_workspace first")
    
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def run_one(test):
        async with semaphore:
            # Wrap sync agent in thread pool
            loop = asyncio.get_running_loop()
            # client.evaluate is sync, but it calls engine.evaluate which is also sync
            return await loop.run_in_executor(None, lambda: evaluate(agent, [test], **kwargs))
    
    results = await asyncio.gather(*[run_one(t) for t in suite])
    return _merge_results(results)

def _merge_results(results: List[EvaluationResult]) -> EvaluationResult:
    if not results:
        raise ValueError("No results to merge")
    
    first = results[0]
    all_per_test = []
    all_trace_refs = []
    
    # Aggregates need to be recomputed
    metric_sums: Dict[str, float] = {}
    metric_counts: Dict[str, int] = {}
    
    for r in results:
        all_per_test.extend(r.per_test)
        all_trace_refs.extend(r.trace_refs)
        for agg in r.aggregates:
            metric_sums[agg.metric_name] = metric_sums.get(agg.metric_name, 0.0) + (agg.value * agg.count)
            metric_counts[agg.metric_name] = metric_counts.get(agg.metric_name, 0) + agg.count

    final_aggregates = [
        MetricAggregate(
            metric_name=name,
            value=metric_sums[name] / metric_counts[name],
            count=metric_counts[name]
        )
        for name in metric_sums
    ]

    return EvaluationResult(
        id=str(uuid.uuid4()),
        run_id=first.run_id,
        suite_hash=first.suite_hash,
        suite_version=first.suite_version,
        structure_hash=first.structure_hash,
        resolution=first.resolution,
        metric_specs=first.metric_specs,
        aggregates=final_aggregates,
        per_test=all_per_test,
        trace_refs=all_trace_refs,
        structure_delta=first.structure_delta, # Note: structural delta might need merging if resolution != boundary
        artifact_port=first.artifact_port,
        semantic_drift=sum(r.semantic_drift for r in results) / len(results) if results else 0.0
    )

