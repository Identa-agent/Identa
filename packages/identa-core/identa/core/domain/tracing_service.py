import contextvars
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from identa.core.domain.tracing import Span, SpanMetadata, SpanTiming, TraceArtifact, MediaContent

# No default=[] — using a sentinel avoids sharing a single list across all contexts.
_active_spans: contextvars.ContextVar[List[Span]] = contextvars.ContextVar("_active_spans")
_current_trace: contextvars.ContextVar[Optional[TraceArtifact]] = contextvars.ContextVar("_current_trace", default=None)

class TracingService:
    @staticmethod
    def start_trace(structure_hash: Optional[str] = None) -> str:
        trace_id = str(uuid.uuid4())
        _current_trace.set(TraceArtifact(id=trace_id, structure_hash=structure_hash or "none", spans=[]))
        _active_spans.set([])  # Always create a fresh list per trace — never share across contexts.
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
        active = _active_spans.get([])
        parent_id = active[-1].id if active else None
        now = datetime.now(timezone.utc)
        span = Span(
            id=span_id,
            parent_id=parent_id,
            name=name,
            kind=kind,
            metadata=metadata or SpanMetadata(),
            timing=SpanTiming(start_time=now, end_time=now, latency_ms=0.0)
        )
        active.append(span)
        # Ensure the updated list is always written back to the context.
        _active_spans.set(active)
        return span_id

    @staticmethod
    def end_span(span_id: str, outputs: Optional[Dict[str, Any]] = None):
        active = _active_spans.get([])
        if not active or active[-1].id != span_id:
            return  # Out-of-order close — ignore gracefully.

        span = active.pop()
        _active_spans.set(active)

        end_time = datetime.now(timezone.utc)
        latency_ms = (end_time - span.timing.start_time).total_seconds() * 1000
        # Pydantic v2 models are immutable by default — use model_copy to update.
        updated_span = span.model_copy(update={
            "timing": span.timing.model_copy(update={"end_time": end_time, "latency_ms": latency_ms}),
            "outputs": outputs or span.outputs,
        })
        trace = _current_trace.get()
        if trace:
            trace.spans.append(updated_span)

    @staticmethod
    def log_media(media_item: MediaContent):
        """Attaches media content to the currently active span."""
        active = _active_spans.get([])
        if not active:
            return
        
        # Update the top span in the active stack
        span = active[-1]
        # Pydantic v2 model_copy
        updated_media = list(span.media) + [media_item]
        updated_span = span.model_copy(update={"media": updated_media})
        active[-1] = updated_span
        _active_spans.set(active)
