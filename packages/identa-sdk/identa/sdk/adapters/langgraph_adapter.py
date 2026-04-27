# packages/identa-sdk/identa/sdk/adapters/langgraph_adapter.py
from typing import Any
import hashlib, json
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

class LangGraphAdapter(BaseAdapter):
    framework_name = "langgraph"

    def inspect(self, graph: Any) -> AgentStructure:
        nodes = [
            AgentNode(id=name, type="custom", name=name, id_stability="stable")
            for name in graph.nodes.keys()
        ]
        edges: list[AgentEdge] = []  # TODO Phase 2: extract real edges
        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": sorted(f"{e.from_node}->{e.to_node}" for e in edges),
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=edges)

    def wrap(self, graph: Any) -> WrappedAgent:
        # No monkeypatch. We capture the bound method and call it through the proxy.
        original_invoke = graph.invoke
        def traced(input_value: Any) -> Any:
            span_id = TracingService.start_span(
                name="langgraph_invoke",
                kind="agent",
                metadata=SpanMetadata(),
            )
            try:
                return original_invoke(input_value)
            finally:
                TracingService.end_span(span_id)
        return WrappedAgent(callable=traced, original=graph, framework_name=self.framework_name)
