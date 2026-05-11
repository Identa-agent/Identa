import hashlib
import json
from typing import Any
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure, AgentNode
from identa.core.domain.migration import MigrationEngine, MigrationPlan, ChangeType

class LangChainAdapter(BaseAdapter):
    framework_name = "langchain"

    def inspect(self, agent: Any) -> AgentStructure:
        # Minimal structural inspection for LangChain chains/runnables
        nodes = []
        try:
            # Try to get the name of the runnable
            name = getattr(agent, "name", None) or type(agent).__name__
            nodes.append(AgentNode(
                id=name, type="chain", name=name, id_stability="stable"
            ))
        except Exception:
            pass

        if not nodes:
            nodes.append(AgentNode(
                id="langchain_root", type="chain", name="langchain_root", id_stability="stable"
            ))

        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": [],
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=[])

    def wrap(self, agent: Any) -> WrappedAgent:
        wrapped = WrappedAgent(callable=None, original=agent, framework_name=self.framework_name)
        
        def traced(input_value: Any, **kwargs: Any) -> Any:
            # Interventions
            if wrapped.interventions and list(wrapped.interventions.keys())[0] in [n.id for n in self.inspect(agent).nodes]:
                return list(wrapped.interventions.values())[0]

            span_id = TracingService.start_span(
                name=getattr(agent, "name", "langchain_invoke"),
                kind="agent",
                metadata=SpanMetadata(),
            )
            try:
                if hasattr(agent, "invoke"):
                    return agent.invoke(input_value, **kwargs)
                return agent(input_value, **kwargs)
            finally:
                TracingService.end_span(span_id)
                
        wrapped.callable = traced
        return wrapped

def _mutate_langchain(agent, plan: MigrationPlan):
    for change in plan.changes:
        if change.change_type == ChangeType.REPLACE_MODEL:
            # Simple bind for LangChain runnables
            if hasattr(agent, "bind"):
                agent = agent.bind(model=change.to_val)
    return agent

# Register on import
MigrationEngine.register_mutator("langchain", _mutate_langchain)
