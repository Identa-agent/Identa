from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from identa.core.domain.exceptions import RunAlreadyCompletedError

class DriftEvaluationMode(str, Enum):
    STANDARD = "standard"
    VANGUARD = "vanguard"
    HYBRID = "hybrid"

class EvaluationConfig(BaseModel):
    drift_mode: DriftEvaluationMode = DriftEvaluationMode.STANDARD
    # ... other config options ...

class Workspace(BaseModel):
    id: str
    name: str
    backend_uri: str

class MetricSpec(BaseModel):
    name: str
    metric: str
    weight: float = 1.0
    threshold: Optional[float] = None
    minimize: bool = False

class MetricAggregate(BaseModel):
    metric_name: str
    value: float
    count: int
    distribution_stats: Optional[Dict[str, float]] = None

class CostModel(BaseModel):
    provider: str
    model: str
    input_cost_per_1k: float
    output_cost_per_1k: float

class CostEstimate(BaseModel):
    tokens_input: int
    tokens_output: int
    cost_estimate: Optional[float] = None
    confidence: Literal["high", "approximate"]

class TraceConfig(BaseModel):
    capture_prompts: bool = True
    capture_outputs: Literal["full", "truncated", "none"] = "truncated"
    max_tokens: int = 2000
    compress: bool = True
    sampling_rate: float = 1.0

class ReproducibilityBundle(BaseModel):
    id: str
    python_version: str
    identa_version: str
    framework_versions: Dict[str, str]
    provider_models: Dict[str, str]
    structure_hash: Optional[str] = None
    resolution: Literal["boundary", "node", "tool", "llm"]
    hashes: Dict[str, str] # { config, suite, metrics, plan? }
    seed: Optional[int] = None
    evaluation_mode: str

class Run(BaseModel):
    id: str
    workspace_id: str
    name: str
    parent_run_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, Any] = Field(default_factory=dict)
    status: RunStatus # "running" | "finished" | "failed"
    started_at: datetime
    ended_at: Optional[datetime] = None
    evaluation_mode: str
    reproducibility_bundle_id: Optional[str] = None
    artifact_ids: List[str] = Field(default_factory=list)

    def mark_completed(self):
        """Transitions the run to 'finished' state."""
        self._ensure_not_completed()
        self.status = RunStatus.FINISHED
        self.ended_at = datetime.now(timezone.utc)

    def fail(self, reason: str):
        """Transitions the run to 'failed' state and logs the reason."""
        self._ensure_not_completed()
        self.status = RunStatus.FAILED
        self.ended_at = datetime.now(timezone.utc)
        self.tags["failure_reason"] = reason

    def _ensure_not_completed(self):
        if self.status in (RunStatus.FINISHED, RunStatus.FAILED):
            raise RunAlreadyCompletedError(self.id)

class Baseline(BaseModel):
    name: str
    run_id: str
    registered_at: datetime
