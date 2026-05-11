import pytest
import identa
from typing import Any, Dict, List
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.sdk.registry import AgentRegistry
from identa.core.domain.structure import AgentStructure, AgentNode
from identa.sdk.api import get_client

class MockAgent:
    """A mock agent that simulates a PydanticAI-like agent."""
    def __init__(self, responses: List[str]):
        self.responses = responses
        self.call_count = 0
        self.model = type('MockModel', (), {'model_name': 'mock-gpt'})()

    def run_sync(self, prompt: str) -> Any:
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return type('MockResponse', (), {'output': resp})()

class MockAdapter(BaseAdapter):
    framework_name = "mock"
    def inspect(self, agent: Any) -> AgentStructure:
        node = AgentNode(id="mock_root", type="llm", name="mock_root", id_stability="stable")
        return AgentStructure(id="mock_v1", version_hash="mock_hash", nodes=[node], edges=[])
    def wrap(self, agent: Any) -> WrappedAgent:
        def traced(input_val):
            res = agent.run_sync(input_val)
            return res.output
        wrapped = WrappedAgent(callable=traced, original=agent, framework_name="mock")
        return wrapped

AgentRegistry.register(lambda a: isinstance(a, MockAgent), MockAdapter, "mock")

@pytest.fixture
def mock_agent():
    return MockAgent(["Paris", "4"])

@pytest.fixture
def suite():
    return [
        {"input": "What is the capital of France?", "expected": "Paris"},
        {"input": "What is 2 + 2?", "expected": "4"},
    ]

def test_full_pipeline_mocked(tmp_path, mock_agent, suite):
    """Verifies the full SDK -> Core -> Persistence pipeline works with a mocked agent."""
    db_path = tmp_path / "identa_mocked.db"
    identa.set_workspace("mock_ws", db_url=f"sqlite:///{db_path}")

    # 1. Run first evaluation (Baseline)
    with identa.start_run("baseline_run") as run:
        res1 = identa.evaluate(
            agent=mock_agent, 
            suite=suite, 
            metrics=["exact_match", "latency"],
            drift_mode="standard"
        )
    
    assert res1.aggregates[0].metric_name == "exact_match"
    # Note: res1.aggregates is a list of MetricAggregate. 
    # We should find the one named 'exact_match'.
    em_agg = next(a for a in res1.aggregates if a.metric_name == "exact_match")
    assert em_agg.value == 1.0 # 100% match
    
    # Register as baseline
    identa.register_baseline(res1.run_id, "default")
    
    # 2. Run second evaluation (Target) - with slight drift simulation
    # We change the agent response for the second test
    mock_agent.responses = ["Paris", "5"] # 2+2=5
    
    with identa.start_run("target_run") as run:
        res2 = identa.evaluate(
            agent=mock_agent, 
            suite=suite, 
            metrics=["exact_match"],
            drift_mode="hybrid"
        )
    
    em_agg2 = next(a for a in res2.aggregates if a.metric_name == "exact_match")
    assert em_agg2.value == 0.5 # 50% match
    
    # 3. Compare
    comparison = identa.compare_to_baseline(res2, "default")
    assert "exact_match" in comparison.metric_deltas
    assert comparison.metric_deltas["exact_match"] == -0.5 # -50% delta
    assert "exact_match" in comparison.regressions
    
    # 4. Reproduction check (mocked)
    identa.reproduce(res1.run_id, mock_agent, suite)

def test_temporal_drift_mocked(tmp_path, mock_agent, suite):
    """Verifies that temporal drift state is persisted and updated across runs."""
    db_path = tmp_path / "identa_temporal.db"
    identa.set_workspace("temp_ws", db_url=f"sqlite:///{db_path}")

    # Run multiple evaluations to build ADWIN history
    for i in range(5):
        responses = ["Paris"] * (5-i) + ["Wrong"] * i
        mock_agent.responses = responses
        identa.evaluate(agent=mock_agent, suite=suite, drift_mode="vanguard")
        
    # Check if temporal state exists in DB
    client = get_client()
    state = client.storage.get_temporal_state("temp_ws", "overall_drift")
    assert state is not None
    assert len(state["history"]) == 5
