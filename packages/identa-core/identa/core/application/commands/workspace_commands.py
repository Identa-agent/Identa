from typing import Any, Optional
from identa.core.domain.models import Workspace
from identa.core.ports.storage import StoragePort
from identa.core.ports.exporter import ExporterPort
from identa.core.application.commands.base import Command

class CreateWorkspaceCommand(Command):
    id: str
    name: str
    backend_uri: str

class WorkspaceCommandHandler:
    def __init__(self, storage: StoragePort, exporter: Optional[ExporterPort] = None):
        self.storage = storage
        self.exporter = exporter

    def handle(self, cmd: Command) -> Any:
        if isinstance(cmd, CreateWorkspaceCommand):
            return self.handle_create_workspace(cmd)
        raise ValueError(f"Unsupported command: {type(cmd)}")

    def handle_create_workspace(self, cmd: CreateWorkspaceCommand) -> Workspace:
        workspace = Workspace(id=cmd.id, name=cmd.name, backend_uri=cmd.backend_uri)
        self.storage.save_workspace(workspace)
        return workspace
