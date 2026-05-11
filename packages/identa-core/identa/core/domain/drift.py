from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field

class DriftLayer(str, Enum):
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    BEHAVIORAL = "behavioral"
    CAUSAL = "causal"
    TEMPORAL = "temporal"

class DriftSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DriftTestResult(BaseModel):
    layer: DriftLayer
    metric_name: str
    score: float  # normalized [0, 1]
    raw_statistic: float
    p_value: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    is_drift: bool
    severity: DriftSeverity
    affected_nodes: List[str] = Field(default_factory=list)
    affected_paths: List[List[str]] = Field(default_factory=list)
    effect_size: Optional[float] = None  # Cohen's d or similar
    recommendation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UnifiedDriftReport(BaseModel):
    run_id: str
    baseline_run_id: Optional[str] = None
    overall_drift: bool
    max_severity: DriftSeverity
    layer_results: List[DriftTestResult]
    composite_score: float  # weighted ensemble
    root_cause_nodes: List[str] = Field(default_factory=list)
    root_cause_paths: List[List[str]] = Field(default_factory=list)
    
    def summary(self) -> str:
        lines = [
            f"Unified Drift Report: {self.run_id}",
            f"Overall Drift: {'YES' if self.overall_drift else 'NO'}",
            f"Max Severity: {self.max_severity.value.upper()}",
            f"Composite Score: {self.composite_score:.4f}",
            "-" * 50,
        ]
        for r in self.layer_results:
            sig = "✗" if r.is_drift else "✓"
            lines.append(f"{sig} {r.layer.value:12} | {r.metric_name:20} | score={r.score:.4f} | p={r.p_value:.4f if r.p_value else 'N/A'} | {r.severity.value}")
        if self.root_cause_nodes:
            lines.append("-" * 50)
            lines.append(f"Root Cause Nodes: {', '.join(self.root_cause_nodes)}")
        return "\n".join(lines)
