"""E2E test for PydanticAI integration using the transparent adapter API.

No manual adapter import, no manual wrap — the agent is passed directly
to identa.evaluate() and the SDK handles detection + tracing internally.
"""
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
import identa


# ── Agent under test ─────────────────────────────────────────────────────────

agent = Agent(TestModel(), output_type=str)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_pydantic_ai_e2e_evaluation():
    """Verify boundary evaluation works end-to-end with the transparent adapter."""
    identa.set_workspace("e2e_pydantic_ai", db_url="sqlite:///e2e_test.db")

    suite = [
        {"id": "test_1", "input": "hello", "expected": "success"}
    ]

    with identa.start_run("pydantic_ai_baseline") as run_ctx:
        results = identa.evaluate(
            agent=agent,
            suite=suite,
            metrics=["latency"],
            resolution="boundary",
        )
        run_ctx.log_results(results)

    assert len(results.per_test) == 1
    # TestModel always returns something — just check latency metric was captured.
    assert "latency" in results.per_test[0].scores


def test_pydantic_ai_agent_not_mutated():
    """The agent object must be returned to the user unmodified after evaluate()."""
    original_run = agent.run
    original_run_sync = agent.run_sync

    identa.set_workspace("e2e_mutation_check", db_url="sqlite:///e2e_test.db")
    with identa.start_run("mutation_check"):
        identa.evaluate(agent=agent, suite=[{"input": "hi", "expected": "x"}])

    assert agent.run.__func__ is original_run.__func__, "agent.run was monkeypatched"
    assert agent.run_sync.__func__ is original_run_sync.__func__, "agent.run_sync was monkeypatched"


def test_pydantic_ai_inspect_structure():
    """Verify identa.inspect() returns a valid AgentStructure for a PydanticAI agent."""
    structure = identa.inspect(agent)
    assert structure is not None
    assert len(structure.nodes) >= 1
    assert structure.version_hash is not None


if __name__ == "__main__":
    test_pydantic_ai_e2e_evaluation()
    test_pydantic_ai_agent_not_mutated()
    test_pydantic_ai_inspect_structure()
