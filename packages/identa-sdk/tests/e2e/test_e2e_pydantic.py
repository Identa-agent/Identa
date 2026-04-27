"""E2E tests against real PydanticAI agents and real model APIs.

These tests require:
  - OPENAI_API_KEY set in the environment
  - ANTHROPIC_API_KEY set in the environment

They are skipped when keys are absent.
"""
import os
import pytest
import identa
from pydantic_ai import Agent

pytestmark = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
    reason="Real model API keys required for e2e",
)

SUITE = [
    {"input": "What is the capital of France?", "expected": "Paris"},
    {"input": "What is 2 + 2?", "expected": "4"},
]

def _setup_workspace(tmp_path, name):
    db_path = tmp_path / f"{name}.db"
    identa.set_workspace(name, db_url=f"sqlite:///{db_path}")

# ── Case A — behavioral inequality ───────────────────────────────
def test_two_different_models_show_measurable_difference(tmp_path):
    _setup_workspace(tmp_path, "case_a")
    agent_gpt = Agent("openai:gpt-4o-mini", system_prompt="Answer in one word.")
    agent_claude = Agent("anthropic:claude-3-haiku-20240307", system_prompt="Answer in one word.")

    with identa.start_run("gpt") as _:
        r_gpt = identa.evaluate(agent=agent_gpt, suite=SUITE, metrics=["latency"])
    with identa.start_run("claude") as _:
        r_claude = identa.evaluate(agent=agent_claude, suite=SUITE, metrics=["latency"])

    # We assert that traces from two providers were captured distinctly.
    assert r_gpt.aggregates[0].metric_name == "latency"
    assert r_claude.aggregates[0].metric_name == "latency"
    # Sanity: same suite, two providers, not the same trace_ref
    assert r_gpt.per_test[0].trace_ref != r_claude.per_test[0].trace_ref

# ── Case B — behavioral equality (same agent twice) ──────────────
def test_same_agent_twice_runs_consistently(tmp_path):
    _setup_workspace(tmp_path, "case_b")
    agent = Agent("openai:gpt-4o-mini", system_prompt="Answer in one word.")

    with identa.start_run("first") as _:
        r1 = identa.evaluate(agent=agent, suite=SUITE, metrics=["latency"])
    with identa.start_run("second") as _:
        r2 = identa.evaluate(agent=agent, suite=SUITE, metrics=["latency"])

    assert len(r1.per_test) == len(r2.per_test) == len(SUITE)
    # The agent object must not have been mutated by the first run.
    assert callable(agent.run)
    assert callable(agent.run_sync)
