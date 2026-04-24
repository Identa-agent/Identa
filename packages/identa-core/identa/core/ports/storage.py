from abc import ABC, abstractmethod
from typing import List, Optional
from identa.core.domain.models import Workspace, Run, Baseline

class StoragePort(ABC):
    @abstractmethod
    def save_workspace(self, workspace: Workspace) -> None:
        pass

    @abstractmethod
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        pass

    @abstractmethod
    def list_workspaces(self) -> List[Workspace]:
        pass

    @abstractmethod
    def save_run(self, run: Run) -> None:
        pass

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[Run]:
        pass

    @abstractmethod
    def list_runs(self, workspace_id: str) -> List[Run]:
        pass

    @abstractmethod
    def save_baseline(self, baseline: Baseline) -> None:
        pass

    @abstractmethod
    def get_baseline(self, workspace_id: str, name: str) -> Optional[Baseline]:
        pass
