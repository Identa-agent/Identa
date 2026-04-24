from typing import Any, Optional
from pydantic_ai import Agent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata

class PydanticAIAdapter:
    @staticmethod
    def wrap_for_tracing(agent: Agent):
        original_run = agent.run
        
        def wrapped_run(user_prompt: str, *args, **kwargs):
            span_id = TracingService.start_span(
                name=f"pydantic_ai_run",
                kind="agent",
                metadata=SpanMetadata(model=agent.model.model_name if hasattr(agent.model, 'model_name') else None)
            )
            try:
                result = original_run(user_prompt, *args, **kwargs)
                return result
            finally:
                TracingService.end_span(span_id)
                
        agent.run = wrapped_run
        return agent

    @staticmethod
    def inspect(agent: Agent):
        # PydanticAI agents are more linear, structure is simpler
        pass
