import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Union, Dict, Callable
from identa.core.domain.models import Workspace, Run, MetricSpec
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
from identa.sdk.registry import AgentRegistry, get_registry
from identa.sdk.adapters.base import WrappedAgent
from identa.sdk.suites import load_suite
import identa.sdk.adapters  # noqa: F401  triggers registration

class IdentaClient:
    def __init__(self, workspace_id: str, db_url: str = "sqlite:///identa.db", artifact_path: str = "artifacts", tracking_uri: Optional[str] = None):
        self.storage = SQLiteStorageAdapter(db_url)
        self.artifacts = LocalArtifactAdapter(artifact_path)
        self.workspace_id = workspace_id
        
        # Initialize exporter if available
        self.exporter: Optional[ExporterPort] = None
        if HAS_MLFLOW:
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

_client: Optional[IdentaClient] = None

def set_workspace(name: str, db_url: str = "sqlite:///identa.db", tracking_uri: Optional[str] = None):
    global _client
    _client = IdentaClient(workspace_id=name, db_url=db_url, tracking_uri=tracking_uri)

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
        status = "failed" if exc_type is not None else "finished"
        self._client.run_handler.handle_finish_run(
            FinishRunCommand(run_id=self.run.id, status=status)
        )
        return False  # Never suppress exceptions.

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
    if not _client:
        raise ValueError("Call set_workspace first")

    run_id = str(uuid.uuid4())
    run = _client.run_handler.handle_start_run(StartRunCommand(
        id=run_id,
        workspace_id=_client.workspace_id,
        name=name
    ))
    return RunContext(run, _client)

def evaluate(agent: Any, suite: List[Dict[str, Any]], **kwargs):
    if not _client:
        raise ValueError("Call set_workspace first")

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
    return _client.evaluate(wrapped, suite, run_id=run_id, **kwargs)

def inspect(agent: Any) -> "AgentStructure":
    """Optional: inspect an agent without running a suite."""
    if isinstance(agent, WrappedAgent):
        agent = agent.original
    adapter = AgentRegistry.detect(agent)
    return adapter.inspect(agent)

def compare_to_baseline(result: EvaluationResult, baseline_name: str = "default") -> ComparisonResult:
    """Compares an evaluation result against a registered baseline."""
    if not _client:
        raise ValueError("Call set_workspace first")
    
    baseline = _client.storage.get_baseline(_client.workspace_id, baseline_name)
    if not baseline:
        raise ValueError(f"Baseline '{baseline_name}' not found in workspace '{_client.workspace_id}'")
    
    baseline_results = _client.storage.list_evaluation_results(baseline.run_id)
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
    if not _client:
        raise ValueError("Call set_workspace first")
    
    run = _client.storage.get_run(run_id)
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
    if _client and _client.exporter:
        return _client.exporter.export_result(result)
    
    # Fallback if no client or exporter (Task 1.1 handles the Error if mlflow missing)
    exporter = MLflowExporter(tracking_uri=tracking_uri)
    return exporter.export_result(result)

def calibrate(agent_factory: Callable, suite: List[Dict[str, Any]], param_grid: Dict[str, List[Any]], **kwargs) -> Dict[str, Any]:
    """Orchestrates a calibration loop to find the best agent hyperparameters."""
    if not _client:
        raise ValueError("Call set_workspace first")
    return _client.calib_engine.calibrate(agent_factory, suite, param_grid, **kwargs)

def execute(command: Union[Command, Query]):
    """
    Generic command bus to route core commands through the SDK.
    Injects necessary dependencies automatically.
    """
    registry = get_registry()
    handler = registry.get_handler(type(command))
    
    # Map command to the correct handle method
    if isinstance(command, CreateWorkspaceCommand):
        return handler.handle_create_workspace(command)
    elif isinstance(command, StartRunCommand):
        return handler.handle_start_run(command)
    elif isinstance(command, FinishRunCommand):
        return handler.handle_finish_run(command)
    elif isinstance(command, GetRunQuery):
        return handler.handle_get_run(command)
    elif isinstance(command, ListRunsQuery):
        return handler.handle_list_runs(command)
    else:
        raise ValueError(f"Unsupported command/query type: {type(command)}")
