# packages/identa-sdk/identa/sdk/adapters/__init__.py
from identa.sdk.registry import AgentRegistry
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

def _is_langgraph(agent): return type(agent).__module__.startswith("langgraph.")
def _is_pydantic_ai(agent): return type(agent).__module__.startswith("pydantic_ai.")

AgentRegistry.register(_is_langgraph, LangGraphAdapter, name="langgraph")
AgentRegistry.register(_is_pydantic_ai, PydanticAIAdapter, name="pydantic_ai")
