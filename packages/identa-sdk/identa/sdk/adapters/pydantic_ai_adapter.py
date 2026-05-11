# packages/identa-sdk/identa/sdk/adapters/pydantic_ai_adapter.py
from typing import Any
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure
from identa.core.domain.migration import MigrationEngine, MigrationPlan, ChangeType

class PydanticAIAdapter(BaseAdapter):
    framework_name = "pydantic_ai"

    def inspect(self, agent: Any) -> AgentStructure:
        from identa.core.domain.structure import AgentNode, AgentEdge
        import hashlib, json
        
        nodes = []
        edges = []
        
        # LLM Root
        model_name = getattr(getattr(agent, "model", None), "model_name", "unknown")
        root_node = AgentNode(
            id="pydantic_ai_root",
            type="llm",
            name=f"pydantic_ai_root ({model_name})",
            model=model_name,
            id_stability="stable",
        )
        nodes.append(root_node)
        
        # Tools
        try:
            # PydanticAI agents have ._function_tools or .tools depending on version
            tools = getattr(agent, "_function_tools", {})
            if not tools and hasattr(agent, "list_tools"):
                tools = {t.name: t for t in agent.list_tools()}
            
            for tool_name, tool in tools.items():
                tool_node = AgentNode(
                    id=f"tool:{tool_name}",
                    type="tool",
                    name=tool_name,
                    id_stability="stable"
                )
                nodes.append(tool_node)
                edges.append(AgentEdge(from_node="pydantic_ai_root", to_node=f"tool:{tool_name}"))
        except Exception:
            pass

        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": [(e.from_node, e.to_node) for e in sorted(edges, key=lambda x: (x.from_node, x.to_node))],
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=edges)

    def wrap(self, agent: Any) -> WrappedAgent:
        # Note: agent is never mutated.
        wrapped = WrappedAgent(callable=None, original=agent, framework_name=self.framework_name)
        
        def traced(input_value: Any) -> Any:
            if "pydantic_ai_root" in wrapped.interventions:
                return wrapped.interventions["pydantic_ai_root"]
                
            prompt = input_value if isinstance(input_value, str) else input_value.get("query") or str(input_value)
            model_name = getattr(getattr(agent, "model", None), "model_name", None)
            span_id = TracingService.start_span(
                name="pydantic_ai_run",
                kind="agent",
                metadata=SpanMetadata(model=model_name, node_id="pydantic_ai_root"),
            )
            try:
                # Use run_sync for sync evaluation engine
                if hasattr(agent, "run_sync"):
                    res = agent.run_sync(prompt)
                else:
                    res = agent.run(prompt)
                
                # PydanticAI >= 1.0 uses .output, older might use .data
                return getattr(res, "output", getattr(res, "data", res))
            finally:
                TracingService.end_span(span_id)
                
        wrapped.callable = traced
        return wrapped

def _mutate_pydantic_ai(agent, plan: MigrationPlan):
    for change in plan.changes:
        if change.change_type == ChangeType.REPLACE_MODEL:
            if hasattr(agent, "model"):
                agent.model = change.to_val
    return agent

# Register on import
MigrationEngine.register_mutator("pydantic_ai", _mutate_pydantic_ai)
