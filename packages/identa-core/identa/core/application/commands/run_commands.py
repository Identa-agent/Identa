from pydantic import Field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from identa.core.domain.models import Run, RunStatus
from identa.core.ports.storage import StoragePort
from identa.core.ports.exporter import ExporterPort
from identa.core.application.commands.base import Command

class StartRunCommand(Command):
    id: str
    workspace_id: str
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, Any] = Field(default_factory=dict)
    evaluation_mode: str = "controlled"


class FinishRunCommand(Command):
    run_id: str
    status: str = "finished"  # "finished" | "failed"

class RunCommandHandler:
    def __init__(self, storage: StoragePort, exporter: Optional[ExporterPort] = None):
        self.storage = storage
        self.exporter = exporter

    def handle(self, cmd: Command) -> Any:
        if isinstance(cmd, StartRunCommand):
            return self.handle_start_run(cmd)
        elif isinstance(cmd, FinishRunCommand):
            return self.handle_finish_run(cmd)
        raise ValueError(f"Unsupported command: {type(cmd)}")

    def handle_start_run(self, cmd: StartRunCommand) -> Run:
        run = Run(
            id=cmd.id,
            workspace_id=cmd.workspace_id,
            name=cmd.name,
            params=cmd.params,
            tags=cmd.tags,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            evaluation_mode=cmd.evaluation_mode
        )
        self.storage.save_run(run)
        return run

    def handle_finish_run(self, cmd: FinishRunCommand) -> None:
        new_status = RunStatus.FAILED if cmd.status == "failed" else RunStatus.FINISHED
        reason = "Run manually marked as failed via command." if cmd.status == "failed" else None
        
        self.storage.update_run_status(cmd.run_id, new_status, reason=reason)
