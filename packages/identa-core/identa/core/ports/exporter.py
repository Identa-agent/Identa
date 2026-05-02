from abc import ABC, abstractmethod
from identa.core.domain.results import EvaluationResult

class ExporterPort(ABC):
    @abstractmethod
    def export_result(self, result: EvaluationResult) -> str:
        """Exports the evaluation result to an external system and returns the external URL/ID."""
        pass
