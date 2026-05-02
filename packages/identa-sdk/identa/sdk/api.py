import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Union, Dict
from identa.core.domain.models import Workspace, Run, MetricSpec
from identa.core.domain.evaluation import EvaluationEngine
from identa.core.domain.metrics import ExactMatchMetric, LatencyMetric
from identa.core.domain.results import EvaluationResult
from identa.core.domain.comparison import ComparisonEngine, ComparisonResult
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.application.commands.workspace_commands import WorkspaceCommandHandler, CreateWorkspaceCommand
from identa.core.application.commands.run_commands import RunCommandHandler, StartRunCommand, FinishRunCommand
from identa.sdk.registry import AgentRegistry
from identa.sdk.adapters.base import WrappedAgent
import identa.sdk.adapters  # noqa: F401  triggers registration

class IdentaClient:
    def __init__(self, workspace_id: str, db_url: str = "sqlite:///identa.db"):
        self.storage = SQLiteStorageAdapter(db_url)
        self.workspace_id = workspace_id
        
        # Initialize registries
        self.metrics_registry = {
            "exact_match": ExactMatchMetric(),
            "latency": LatencyMetric()
        }
        self.engine = EvaluationEngine(self.metrics_registry)
        
        # Handlers
        self.workspace_handler = WorkspaceCommandHandler(self.storage)
        self.run_handler = RunCommandHandler(self.storage)

        # Ensure workspace exists
        self.workspace_handler.handle_create_workspace(CreateWorkspaceCommand(
            id=workspace_id,
            name=workspace_id,
            backend_uri=db_url
        ))

    def evaluate(self, agent: Any, suite: List[Dict[str, Any]], run_id: str, **kwargs):
        return self.engine.evaluate(agent, suite, run_id, **kwargs)

_client: Optional[IdentaClient] = None

def set_workspace(name: str, db_url: str = "sqlite:///identa.db"):
    global _client
    _client = IdentaClient(workspace_id=name, db_url=db_url)

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
