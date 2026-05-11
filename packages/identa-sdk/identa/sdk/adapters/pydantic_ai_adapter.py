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
        # Phase 1: minimal stub — PydanticAI agents are linear.
        # Returns a single-node structure so resolution="node" works.
        from identa.core.domain.structure import AgentNode
        import hashlib, json
        model_name = getattr(getattr(agent, "model", None), "model_name", "unknown")
        node = AgentNode(
            id="pydantic_ai_root",
            type="llm",
            name="pydantic_ai_root",
            model=model_name,
            id_stability="stable",
        )
        version_hash = hashlib.sha256(json.dumps({"nodes": ["pydantic_ai_root"]}).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=[node], edges=[])

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
