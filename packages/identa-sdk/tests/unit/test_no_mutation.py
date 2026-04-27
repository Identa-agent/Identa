"""The user's agent object must be returned to them unmodified."""
from unittest.mock import MagicMock
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

def test_langgraph_adapter_does_not_mutate_graph():
    graph = MagicMock()
    graph.nodes = {"a": object(), "b": object()}
    original_invoke = graph.invoke

    LangGraphAdapter().wrap(graph)

    assert graph.invoke is original_invoke, "graph.invoke was monkeypatched"

def test_pydantic_ai_adapter_does_not_mutate_agent():
    agent = MagicMock()
    original_run = agent.run
    original_run_sync = agent.run_sync

    PydanticAIAdapter().wrap(agent)

    assert agent.run is original_run, "agent.run was monkeypatched"
    assert agent.run_sync is original_run_sync, "agent.run_sync was monkeypatched"
