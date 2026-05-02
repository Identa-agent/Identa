# packages/identa-sdk/identa/sdk/adapters/langgraph_adapter.py
from typing import Any
import hashlib, json
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

try:
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError:
    BaseCallbackHandler = object

class IdentaLangGraphCallback(BaseCallbackHandler):
    def __init__(self):
        self.span_ids = {}

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:
        name = serialized.get("name", "node")
        # Avoid double-tracing the root agent call if it's already traced by LangGraphAdapter.wrap
        if name == "LangGraph":
            return
        
        run_id = str(kwargs.get("run_id", name))
        sid = TracingService.start_span(
            name=name,
            kind="node",
            metadata=SpanMetadata(node_id=name)
        )
        self.span_ids[run_id] = sid

    def on_chain_end(self, response: Any, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "node"))
        sid = self.span_ids.pop(run_id, None)
        if sid:
            TracingService.end_span(sid)

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "node"))
        sid = self.span_ids.pop(run_id, None)
        if sid:
            TracingService.end_span(sid)

class LangGraphAdapter(BaseAdapter):
    framework_name = "langgraph"

    def inspect(self, graph: Any) -> AgentStructure:
        # Use LangGraph's get_graph() if available to extract nodes and edges
        try:
            drawable = graph.get_graph()
            nodes = []
            for node in drawable.nodes.values():
                # Map LangGraph node types to Identa types if possible
                nodes.append(AgentNode(
                    id=node.id, 
                    type="custom", 
                    name=node.name, 
                    id_stability="stable"
                ))
            
            edges = []
            for edge in drawable.edges:
                edges.append(AgentEdge(from_node=edge.source, to_node=edge.target))
        except (AttributeError, Exception):
            # Fallback to minimal extraction from graph.nodes
            nodes = [
                AgentNode(id=name, type="custom", name=name, id_stability="stable")
                for name in graph.nodes.keys()
            ]
            edges = []

        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": sorted(f"{e.from_node}->{e.to_node}" for e in edges),
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=edges)

    def wrap(self, graph: Any) -> WrappedAgent:
        # No monkeypatch. We capture the bound method and call it through the proxy.
        original_invoke = graph.invoke
        
        def traced(input_value: Any, config: Any = None, **kwargs: Any) -> Any:
            span_id = TracingService.start_span(
                name="langgraph_invoke",
                kind="agent",
                metadata=SpanMetadata(),
            )
            
            # Prepare config with Identa callback
            if config is None:
                config = {}
            
            callbacks = config.get("callbacks", [])
            if not any(isinstance(c, IdentaLangGraphCallback) for c in callbacks):
                # Copy to avoid mutating user's config list
                callbacks = list(callbacks) + [IdentaLangGraphCallback()]
                config["callbacks"] = callbacks
                
            try:
                return original_invoke(input_value, config=config, **kwargs)
            finally:
                TracingService.end_span(span_id)
        return WrappedAgent(callable=traced, original=graph, framework_name=self.framework_name)
