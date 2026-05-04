import hashlib
import json
import logging
import threading
from typing import Any, Dict, Optional

from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

logger = logging.getLogger(__name__)

try:
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError:
    BaseCallbackHandler = object

class IdentaLangGraphCallback(BaseCallbackHandler):
    def __init__(self):
        if BaseCallbackHandler is not object:
            super().__init__()
        self.span_ids: Dict[str, str] = {}
        self._lock = threading.Lock()  # FIX: Thread safety for shared state
        
        self.raise_error = False
        self.ignore_chain = False
        self.ignore_llm = False
        self.ignore_tool = False
        self.ignore_retriever = False

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:
        name = serialized.get("name", "node") if serialized else "node"
            
        if name == "LangGraph":
            return
        
        run_id = str(kwargs.get("run_id", name))
        sid = TracingService.start_span(
            name=name,
            kind="chain",
            metadata=SpanMetadata(node_id=name)
        )
        with self._lock:
            self.span_ids[run_id] = sid

    def on_chain_end(self, response: Any, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "node"))
        with self._lock:
            sid = self.span_ids.pop(run_id, None)
        if sid:
            TracingService.end_span(sid)

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "node"))
        with self._lock:
            sid = self.span_ids.pop(run_id, None)
        if sid:
            TracingService.end_span(sid)

class LangGraphAdapter(BaseAdapter):
    framework_name = "langgraph"

    def inspect(self, graph: Any) -> AgentStructure:
        nodes, edges = [], []
        try:
            drawable = graph.get_graph()
            for node in drawable.nodes.values():
                nodes.append(AgentNode(
                    id=node.id, type="custom", name=node.name, id_stability="stable"
                ))
            for edge in drawable.edges:
                edges.append(AgentEdge(from_node=edge.source, to_node=edge.target))
        except AttributeError as e:
            logger.debug("Failed to extract graph via get_graph, falling back to basic extraction: %s", e)
            if hasattr(graph, "nodes") and isinstance(graph.nodes, dict):
                nodes = [
                    AgentNode(id=name, type="custom", name=name, id_stability="stable")
                    for name in graph.nodes.keys()
                ]
        except Exception as e:
            logger.error("Unexpected error during graph inspection: %s", e, exc_info=True)

        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": sorted(f"{e.from_node}->{e.to_node}" for e in edges),
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=edges)

    def wrap(self, graph: Any) -> WrappedAgent:
        original_invoke = graph.invoke
        
        def traced(input_value: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
            span_id = TracingService.start_span(
                name="langgraph_invoke",
                kind="agent",
                metadata=SpanMetadata(),
            )
            
            # FIX: Deep-ish copy to prevent mutating the caller's config
            safe_config = dict(config) if config else {}
            callbacks = safe_config.get("callbacks", [])
            
            if not any(isinstance(c, IdentaLangGraphCallback) for c in callbacks):
                safe_config["callbacks"] = list(callbacks) + [IdentaLangGraphCallback()]
                
            try:
                return original_invoke(input_value, config=safe_config, **kwargs)
            finally:
                TracingService.end_span(span_id)
                
        return WrappedAgent(callable=traced, original=graph, framework_name=self.framework_name)