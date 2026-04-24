from typing import TypedDict
import pytest
from langgraph.graph import StateGraph, START, END
from identa.sdk import api
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter

# 1. Setup a simple LangGraph agent
class State(TypedDict):
    input: str
    data: str

def node_a(state: State):
    return {"data": state.get("input", "") + " -> A"}

def node_b(state: State):
    return {"data": state.get("data", "") + " -> B"}

builder = StateGraph(State)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)
graph = builder.compile()

def test_langgraph_e2e_evaluation():
    # 2. Configure Identa
    api.set_workspace("e2e_test", db_url="sqlite:///e2e_test.db")
    
    # 3. Inspect and Wrap
    structure = LangGraphAdapter.inspect(graph)
    assert len(structure.nodes) >= 2 # Account for internal nodes like __start__
    
    # Wrap graph for tracing (simplistic for E2E)
    wrapped_graph = LangGraphAdapter.wrap_for_tracing(graph)
    
    # 4. Run Evaluation
    suite = [
        {"id": "test_1", "input": {"input": "hello"}, "expected": {"input": "hello", "data": "hello -> A -> B"}}
    ]
    
    with api.start_run("langgraph_baseline") as run_ctx:
        results = api.evaluate(
            agent=wrapped_graph.invoke,
            suite=suite,
            run_id=run_ctx.run.id,
            metrics=["exact_match", "latency"],
            resolution="node",
            structure=structure
        )
        
    # 5. Verify Results
    assert len(results.per_test) == 1
    assert results.per_test[0].scores["exact_match"] == 1.0
    assert results.aggregates[0].value == 1.0 # exact_match aggregate

if __name__ == "__main__":
    test_langgraph_e2e_evaluation()
