"""E2E test for LangGraph integration using the transparent adapter API.

No manual adapter import, no manual wrap — the graph is passed directly
to identa.evaluate() and the SDK handles detection + tracing internally.
"""
from typing import TypedDict
import pytest
from langgraph.graph import StateGraph, START, END
import identa


# ── Simple two-node graph ────────────────────────────────────────────────────

class State(TypedDict):
    input: str
    data: str


def node_a(state: State) -> dict:
    return {"data": state.get("input", "") + " -> A"}


def node_b(state: State) -> dict:
    return {"data": state.get("data", "") + " -> B"}


builder = StateGraph(State)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)
graph = builder.compile()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_langgraph_e2e_evaluation():
    """Verify boundary evaluation works end-to-end with the transparent adapter."""
    identa.set_workspace("e2e_langgraph", db_url="sqlite:///e2e_test.db")

    suite = [
        {"id": "test_1", "input": {"input": "hello"}, "expected": {"input": "hello", "data": "hello -> A -> B"}}
    ]

    with identa.start_run("langgraph_baseline") as run_ctx:
        results = identa.evaluate(
            agent=graph,
            suite=suite,
            metrics=["exact_match", "latency"],
            resolution="boundary",
        )
        run_ctx.log_results(results)

    assert len(results.per_test) == 1
    assert results.per_test[0].scores.get("exact_match") == 1.0


def test_langgraph_inspect_structure():
    """Verify identa.inspect() returns a valid AgentStructure without running eval."""
    structure = identa.inspect(graph)
    assert structure is not None
    assert len(structure.nodes) >= 2
    assert structure.version_hash is not None


if __name__ == "__main__":
    test_langgraph_e2e_evaluation()
    test_langgraph_inspect_structure()
