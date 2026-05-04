from typing import Protocol, Any, Dict, List, Optional

class LLMJudgePort(Protocol):
    def judge(self, trace_data: Dict[str, Any], prompt: str) -> float:
        """Evaluates a trace and returns a qualitative drift score [0.0, 1.0]."""
        ...
