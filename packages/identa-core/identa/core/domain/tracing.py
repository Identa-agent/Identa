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
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

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

    def infer_causal_bottleneck(self, baseline_trace: Optional['TraceArtifact'] = None) -> Optional[str]:
        """Identify node whose output change most correlates with metric drift."""
        if not baseline_trace:
            # Fallback to latency-based bottleneck if no baseline
            node_latencies: Dict[str, List[float]] = {}
            for span in self.spans:
                if span.metadata.node_id:
                    nid = span.metadata.node_id
                    if nid not in node_latencies:
                        node_latencies[nid] = []
                    node_latencies[nid].append(span.timing.latency_ms)
            
            if not node_latencies:
                return None
                
            avg_latencies = {nid: sum(latencies)/len(latencies) for nid, latencies in node_latencies.items()}
            return max(avg_latencies, key=avg_latencies.get)
        
        # Map node_id -> output in baseline
        baseline_outputs = {}
        for span in baseline_trace.spans:
            if span.metadata.node_id:
                baseline_outputs[span.metadata.node_id] = span.outputs
        
        # Find node with maximum output divergence
        max_divergence = 0.0
        bottleneck_node = None
        
        for span in self.spans:
            nid = span.metadata.node_id
            if nid and nid in baseline_outputs:
                # Simple string divergence
                b_out = str(baseline_outputs[nid])
                c_out = str(span.outputs)
                # Avoid division by zero
                b_words = b_out.split()
                c_words = c_out.split()
                if not b_words and not c_words:
                    divergence = 0.0
                else:
                    divergence = len(set(b_words) ^ set(c_words)) / max(len(b_words), 1)
                
                if divergence > max_divergence:
                    max_divergence = divergence
                    bottleneck_node = nid
        
        return bottleneck_node

    def to_gzip_jsonl(self) -> bytes:
        """Serializes the trace spans to a gzipped JSON Lines format."""
        out = io.BytesIO()
        with gzip.GzipFile(fileobj=out, mode='wb') as f:
            for span in self.spans:
                # We use model_dump_json() to ensure pydantic serialization
                f.write((span.model_dump_json() + "\n").encode('utf-8'))
        return out.getvalue()
