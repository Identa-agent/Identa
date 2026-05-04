import logging
from typing import Any, Dict, Optional, Literal
from pydantic import Field
from datetime import datetime, timezone
from functools import singledispatchmethod

from identa.core.domain.models import Run, RunStatus
from identa.core.ports.storage import StoragePort
from identa.core.ports.exporter import ExporterPort
from identa.core.application.commands.base import Command

logger = logging.getLogger(__name__)

class StartRunCommand(Command):
    id: str
    workspace_id: str
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, Any] = Field(default_factory=dict)
    evaluation_mode: str = "controlled"

class FinishRunCommand(Command):
    run_id: str
    status: Literal["finished", "failed"] = "finished"

class RunCommandHandler:
    def __init__(self, storage: StoragePort, exporter: Optional[ExporterPort] = None):
        self.storage = storage
        # TODO: Remove exporter if it continues to be unused, or implement its logic
        self.exporter = exporter

    @singledispatchmethod
    def handle(self, cmd: Command) -> Any:
        raise ValueError(f"Unsupported command: {type(cmd)}")

    @handle.register
    def _(self, cmd: StartRunCommand) -> Run:
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
        try:
            self.storage.save_run(run)
        except Exception as e:
            logger.error(f"Storage failure while saving StartRunCommand for run {run.id}: {e}", exc_info=True)
            raise
        return run

    @handle.register
    def _(self, cmd: FinishRunCommand) -> None:
        new_status = RunStatus.FAILED if cmd.status == "failed" else RunStatus.FINISHED
        reason = "Run manually marked as failed via command." if cmd.status == "failed" else None
        
        try:
            self.storage.update_run_status(cmd.run_id, new_status, reason=reason)
        except Exception as e:
            logger.error(f"Storage failure while updating FinishRunCommand for run {cmd.run_id}: {e}", exc_info=True)
            raise