from abc import ABC, abstractmethod
from typing import List

class LLMJudgePort(ABC):
    @abstractmethod
    def judge_drift(self, baseline_output: str, current_output: str, 
                    context: str = "") -> float:
        """Return qualitative drift score between 0.0 (identical) and 1.0 (completely different)."""
        pass
