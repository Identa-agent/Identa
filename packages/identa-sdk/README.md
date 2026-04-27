# Identa SDK 🚀

The user-facing toolkit for evaluating and migrating LLM-based agents. Identa provides a zero-friction experience for **LangGraph**, **PydanticAI**, and **LangChain** agents.

## Getting Started

### 1. Installation

```bash
pip install identa-sdk
```

### 2. Basic Evaluation

Identa automatically detects your agent's framework. You don't need to import framework-specific adapters.

```python
import identa

# 1. Initialize your workspace
identa.set_workspace("travel_agent")

# 2. Define a test suite
suite = [
    {"input": {"query": "Fly to Paris"}, "expected": {"destination": "CDG"}}
]

# 3. Run evaluation directly on your agent object
with identa.start_run("gpt-4-baseline") as run:
    results = identa.evaluate(
        agent=my_agent,   # Works with LangGraph, PydanticAI, etc.
        suite=suite,
        metrics=["exact_match", "latency"],
        resolution="node", # Optional: auto-inspects for node-level attribution
    )

print(results.summary())
```

### 3. Usage with PydanticAI

```python
from pydantic_ai import Agent
import identa

agent = Agent("openai:gpt-4o")

# No manual wrapping required!
identa.evaluate(agent=agent, suite=suite)
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

| Feature | LangGraph | PydanticAI | LangChain |
| :--- | :--- | :--- | :--- |
| **Boundary Eval** | ✅ | ✅ | ✅ |
| **Node Tracing** | ✅ | ✅ | ✅ |
| **Structural Inspection** | ✅ | ✅ | 🚧 |
| **Model Migration** | ✅ | 🚧 | 🚧 |
