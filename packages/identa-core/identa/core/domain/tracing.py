from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field

class SpanTiming(BaseModel):
    start_time: datetime
    end_time: datetime
    latency_ms: float

class SpanMetadata(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    prompt_template: Optional[str] = None
    rendered_prompt: Optional[str] = None
    tool_name: Optional[str] = None
    node_id: Optional[str] = None
    node_id_stability: Literal["stable", "ephemeral"] = "stable"
    structure_hash: Optional[str] = None

class Span(BaseModel):
    id: str
    parent_id: Optional[str] = None
    name: str
    kind: Literal["llm", "tool", "agent", "chain", "custom"]
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: SpanMetadata
    timing: SpanTiming

class TraceArtifact(BaseModel):
    id: str
    structure_hash: str
    spans: List[Span]
