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

    def to_gzip_jsonl(self) -> bytes:
        """Serializes spans to JSONL and returns a gzip-compressed byte stream."""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb') as f:
            for span in self.spans:
                line = span.model_dump_json() + "\n"
                f.write(line.encode('utf-8'))
        return buf.getvalue()
