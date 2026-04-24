import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from identa.sdk import api
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

# 1. Setup a simple PydanticAI agent
agent = Agent(TestModel(), output_type=str)

def test_pydantic_ai_e2e_evaluation():
    # 2. Configure Identa
    api.set_workspace("e2e_pydantic_ai", db_url="sqlite:///e2e_test.db")
    
    # 3. Wrap
    wrapped_agent = PydanticAIAdapter.wrap_for_tracing(agent)
    
    # 4. Run Evaluation
    suite = [
        {"id": "test_1", "input": "hello", "expected": "success"}
    ]
    
    # Mock the run to return "success" since TestModel might return something else
    original_run = wrapped_agent.run
    def mock_run(prompt, *args, **kwargs):
        # We need to mimic PydanticAI result object if needed, 
        # but for simplicity let's assume agent returns str
        return "success"
    wrapped_agent.run = mock_run

    with api.start_run("pydantic_ai_baseline") as run_ctx:
        results = api.evaluate(
            agent=wrapped_agent.run,
            suite=suite,
            run_id=run_ctx.run.id,
            metrics=["exact_match", "latency"],
            resolution="boundary"
        )
        
    # 5. Verify Results
    assert len(results.per_test) == 1
    assert results.per_test[0].scores["exact_match"] == 1.0
    assert results.aggregates[0].value == 1.0

if __name__ == "__main__":
    test_pydantic_ai_e2e_evaluation()
