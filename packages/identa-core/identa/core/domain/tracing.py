import gzip
import io
import json
from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field

class MediaContent(BaseModel):
    type: Literal["image", "audio", "video"]
    mime_type: str
    data: str  # base64 encoded
    metadata: Dict[str, Any] = Field(default_factory=dict)

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
    media: List[MediaContent] = Field(default_factory=list)
    metadata: SpanMetadata
    timing: SpanTiming

class TraceArtifact(BaseModel):
    id: str
    structure_hash: str
    spans: List[Span]

    def infer_causal_bottleneck(self) -> Optional[str]:
        """Simple causal inference: Identify node with highest average latency."""
        node_latencies: Dict[str, List[float]] = {}
        for span in self.spans:
            if span.metadata.node_id:
                nid = span.metadata.node_id
                if nid not in node_latencies:
                    node_latencies[nid] = []
                node_latencies[nid].append(span.timing.latency_ms)
        
        if not node_latencies:
            return None
            
        # Return node ID with the highest average latency
        avg_latencies = {nid: sum(latencies)/len(latencies) for nid, latencies in node_latencies.items()}
        return max(avg_latencies, key=avg_latencies.get)
