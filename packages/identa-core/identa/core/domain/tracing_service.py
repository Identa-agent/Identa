import contextvars
import time
import uuid
from datetime import datetime
from typing import List, Optional, Any, Dict
from identa.core.domain.tracing import Span, SpanMetadata, SpanTiming, TraceArtifact

_active_spans = contextvars.ContextVar("_active_spans", default=[])
_current_trace = contextvars.ContextVar("_current_trace", default=None)

class TracingService:
    @staticmethod
    def start_trace(structure_hash: Optional[str] = None):
        trace_id = str(uuid.uuid4())
        _current_trace.set(TraceArtifact(id=trace_id, structure_hash=structure_hash or "none", spans=[]))
        _active_spans.set([])
        return trace_id

    @staticmethod
    def end_trace() -> Optional[TraceArtifact]:
        trace = _current_trace.get()
        _current_trace.set(None)
        _active_spans.set([])
        return trace

    @staticmethod
    def start_span(name: str, kind: str, metadata: Optional[SpanMetadata] = None) -> str:
        span_id = str(uuid.uuid4())
        parent_id = _active_spans.get()[-1].id if _active_spans.get() else None
        
        span = Span(
            id=span_id,
            parent_id=parent_id,
            name=name,
            kind=kind,
            metadata=metadata or SpanMetadata(),
            timing=SpanTiming(start_time=datetime.now(), end_time=datetime.now(), latency_ms=0.0)
        )
        
        _active_spans.get().append(span)
        return span_id

    @staticmethod
    def end_span(span_id: str, outputs: Optional[Dict[str, Any]] = None):
        active = _active_spans.get()
        if not active or active[-1].id != span_id:
            return # Should handle out of order better in real implementation
            
        span = active.pop()
        span.timing.end_time = datetime.now()
        span.timing.latency_ms = (span.timing.end_time - span.timing.start_time).total_seconds() * 1000
        if outputs:
            span.outputs = outputs
            
        trace = _current_trace.get()
        if trace:
            trace.spans.append(span)
