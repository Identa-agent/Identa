from abc import ABC, abstractmethod
from typing import List, Optional
from identa.core.domain.models import Workspace, Run, Baseline, ReproducibilityBundle, RunStatus
from identa.core.domain.results import EvaluationResult


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

    @abstractmethod
    def save_evaluation_result(self, result: EvaluationResult) -> None:
        pass

    @abstractmethod
    def get_evaluation_result(self, result_id: str) -> Optional[EvaluationResult]:
        pass

    @abstractmethod
    def list_evaluation_results(self, run_id: str) -> List[EvaluationResult]:
        pass

    # ── ReproducibilityBundle ────────────────────────────────────────────────

    @abstractmethod
    def save_reproducibility_bundle(self, bundle: ReproducibilityBundle) -> None:
        pass

    @abstractmethod
    def get_reproducibility_bundle(self, bundle_id: str) -> Optional[ReproducibilityBundle]:
        pass

    @abstractmethod
    def update_run_status(self, run_id: str, new_status: RunStatus, reason: Optional[str] = None) -> bool:
        """Atomic update to prevent race conditions."""
        pass
