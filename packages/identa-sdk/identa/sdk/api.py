import uuid
from typing import Any, List, Optional, Union, Dict
from identa.core.domain.models import Workspace, Run, MetricSpec
from identa.core.domain.evaluation import EvaluationEngine
from identa.core.domain.metrics import ExactMatchMetric, LatencyMetric
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.application.commands.workspace_commands import WorkspaceCommandHandler, CreateWorkspaceCommand
from identa.core.application.commands.run_commands import RunCommandHandler, StartRunCommand
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
    def __init__(self, run: Run):
        self.run = run

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Update run status to finished in storage if needed
        pass

def start_run(name: str) -> RunContext:
    if not _client:
        raise ValueError("Call set_workspace first")
    
    run_id = str(uuid.uuid4())
    run = _client.run_handler.handle_start_run(StartRunCommand(
        id=run_id,
        workspace_id=_client.workspace_id,
        name=name
    ))
    return RunContext(run)

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
    if not _client:
         # Minimal detection doesn't technically need _client but spec says evaluate does.
         # Actually inspect doesn't need _client based on the spec code.
         pass
    if isinstance(agent, WrappedAgent):
        agent = agent.original
    adapter = AgentRegistry.detect(agent)
    return adapter.inspect(agent)
