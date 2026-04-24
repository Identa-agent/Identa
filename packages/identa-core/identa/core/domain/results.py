from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from .models import MetricSpec, MetricAggregate
from .structure import ObservedStructureDelta

class PerTestResult(BaseModel):
    test_id: str
    output: Any
    scores: Dict[str, float]
    trace_ref: Optional[str] = None

class FailureRecord(BaseModel):
    test_id: str
    input: Any
    expected_output: Any
    actual_output: Any
    scores: Dict[str, float]
    trace_ref: Optional[str] = None

class EvaluationResult(BaseModel):
    id: str
    run_id: str
    suite_hash: str
    suite_version: str
    structure_hash: Optional[str] = None
    resolution: Literal["boundary", "node", "tool", "llm"]
    metric_specs: List[MetricSpec]
    aggregates: List[MetricAggregate]
    per_test: List[PerTestResult]
    trace_refs: List[str] = Field(default_factory=list)
    structure_delta: Optional[ObservedStructureDelta] = None
