from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel
from identa.core.domain.models import Run
from identa.core.ports.storage import StoragePort

class StartRunCommand(BaseModel):
    id: str
    workspace_id: str
    name: str
    params: Dict[str, Any] = {}
    tags: Dict[str, Any] = {}
    evaluation_mode: str = "controlled"

class RunCommandHandler:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    def handle_start_run(self, cmd: StartRunCommand) -> Run:
        run = Run(
            id=cmd.id,
            workspace_id=cmd.workspace_id,
            name=cmd.name,
            params=cmd.params,
            tags=cmd.tags,
            status="running",
            started_at=datetime.now(),
            evaluation_mode=cmd.evaluation_mode
        )
        self.storage.save_run(run)
        return run
