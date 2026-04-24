import hashlib
import json
from typing import Dict, Any, List, Optional
from langgraph.graph import CompiledGraph
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata

class LangGraphAdapter:
    @staticmethod
    def inspect(graph: CompiledGraph) -> AgentStructure:
        nodes = []
        edges = []
        
        # LangGraph nodes
        for node_name, node_data in graph.nodes.items():
            nodes.append(AgentNode(
                id=node_name,
                type="custom", # LangGraph doesn't always expose node type easily
                name=node_name,
                id_stability="stable"
            ))
            
        # LangGraph edges
        # This is simplified; LangGraph edges are more complex
        # for start, end in graph.builder.edges:
        #    edges.append(AgentEdge(from_node=start, to_node=end))

        # Generate version_hash
        struct_data = {
            "nodes": sorted([n.id for n in nodes]),
            "edges": sorted([f"{e.from_node}->{e.to_node}" for e in edges])
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()

        return AgentStructure(
            id=str(hashlib.md5(version_hash.encode()).hexdigest()),
            version_hash=version_hash,
            nodes=nodes,
            edges=edges
        )

    @staticmethod
    def wrap_for_tracing(graph: CompiledGraph):
        # In a real implementation, we would use LangGraph's callback system
        # or monkeypatch the invoke/stream methods.
        original_invoke = graph.invoke
        
        def wrapped_invoke(input: Any, *args, **kwargs):
            span_id = TracingService.start_span(
                name="langgraph_invoke",
                kind="agent",
                metadata=SpanMetadata()
            )
            try:
                result = original_invoke(input, *args, **kwargs)
                return result
            finally:
                TracingService.end_span(span_id)
                
        graph.invoke = wrapped_invoke
        return graph
