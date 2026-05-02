# packages/identa-sdk/identa/sdk/adapters/__init__.py
#
# Framework adapters are optional — only registered when the matching
# framework package is installed.  Install the extras you need:
#
#   pip install identa-sdk[langgraph]
#   pip install identa-sdk[pydantic-ai]
#   pip install identa-sdk[all]

from identa.sdk.registry import AgentRegistry

try:
    from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter

    def _is_langgraph(agent: object) -> bool:
        return type(agent).__module__.startswith("langgraph.")

    AgentRegistry.register(_is_langgraph, LangGraphAdapter, name="langgraph")
except ImportError:
    pass  # langgraph not installed — adapter silently skipped.

try:
    from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

    def _is_pydantic_ai(agent: object) -> bool:
        return type(agent).__module__.startswith("pydantic_ai.")

    AgentRegistry.register(_is_pydantic_ai, PydanticAIAdapter, name="pydantic_ai")
except ImportError:
    pass  # pydantic-ai not installed — adapter silently skipped.
