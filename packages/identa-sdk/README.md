# Identa SDK 🚀

The user-facing toolkit for evaluating and migrating LLM-based agents. Identa provides framework shims for **LangGraph** and **PydanticAI** to enable multi-resolution tracing and performance tracking.

## Getting Started

### 1. Installation

```bash
pip install identa-sdk
```

### 2. Basic Evaluation (LangGraph)

```python
from identa.sdk import api
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter

# Set your workspace
api.set_workspace("travel_agent")

# Inspect your graph structure
structure = LangGraphAdapter.inspect(my_graph)

# Wrap for tracing
wrapped_agent = LangGraphAdapter.wrap_for_tracing(my_graph)

# Define a test suite
suite = [
    {"input": {"query": "Fly to Paris"}, "expected": {"destination": "CDG"}}
]

# Run evaluation
with api.start_run("gpt-4-baseline") as run:
    results = api.evaluate(
        agent=wrapped_agent.invoke,
        suite=suite,
        metrics=["exact_match", "latency"],
        resolution="node",
        structure=structure
    )

print(f"Success Rate: {results.aggregates[0].value}")
```

### 3. Usage with PydanticAI

```python
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

wrapped_agent = PydanticAIAdapter.wrap_for_tracing(my_agent)

# Evaluate similarly
api.evaluate(agent=wrapped_agent.run, suite=suite)
```

## CLI

Identa comes with a CLI to manage your runs and view results.

```bash
# List all runs in a workspace
identa runs list --workspace travel_agent

# Show details of a specific run
identa runs show <run_id>
```

## Framework Support

| Feature | LangGraph | PydanticAI |
| :--- | :--- | :--- |
| **Boundary Eval** | ✅ | ✅ |
| **Node Tracing** | ✅ | ✅ |
| **Structural Inspection** | ✅ | 🚧 |
| **Model Migration** | ✅ | 🚧 |
