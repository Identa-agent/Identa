import uuid
from typing import Any, List, Optional, Union, Dict
from identa.core.domain.models import Workspace, Run, MetricSpec
from identa.core.domain.evaluation import EvaluationEngine
from identa.core.domain.metrics import ExactMatchMetric, LatencyMetric
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.application.commands.workspace_commands import WorkspaceCommandHandler, CreateWorkspaceCommand
from identa.core.application.commands.run_commands import RunCommandHandler, StartRunCommand

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
    # In a real SDK, we'd detect the current run from a context var
    # For now, we'll assume a run is managed by the user or passed in
    return _client.evaluate(agent, suite, run_id="standalone", **kwargs)
