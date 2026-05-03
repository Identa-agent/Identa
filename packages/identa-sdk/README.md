# Identa SDK 🚀

The user-facing toolkit for evaluating and migrating LLM-based agents. Identa provides a zero-friction experience for **LangGraph**, **PydanticAI**, and **LangChain** agents.

## Getting Started

### 1. Installation

```bash
pip install identa-sdk
```

## Features

### 1. Evaluation Engine
The `evaluate` function executes your agent against test suites and computes metrics across your agent's graph/flow.

```python
import identa

# Define a test suite
suite = [
    {"input": {"query": "Fly to Paris"}, "expected": {"destination": "CDG"}}
]

# Run evaluation with node-level resolution
results = identa.evaluate(
    agent=my_agent, 
    suite=suite,
    metrics=["accuracy", "latency"],
    resolution="node"
)

print(results.report())
```

### 2. Tracing Service
Use the context-aware span collector to debug agent execution in real-time.

```python
import identa

# Start a trace session
with identa.trace("flight-booking-flow") as tracer:
    # Any agent calls within this block are automatically spanned
    response = my_agent.run("Book a flight to Tokyo")
    
# Retrieve trace data
spans = tracer.get_spans()
```

### 3. Migration Engine
Validate and apply model-binding swaps (e.g., swapping `gpt-4o` for `claude-3-5-sonnet`) safely.

```python
from identa.core.domain.migration import MigrationEngine, MigrationPlan

# Validate if a model swap is safe based on structural drift
plan = MigrationPlan(id="swap-to-claude", source_structure_hash="...", changes=[])
plan.replace_model(node="llm_1", to="claude-3-5-sonnet")

results = identa.evaluate(agent=my_agent, suite=suite)
report = MigrationEngine.validate(plan, agent=my_agent, current_structure=results.structure)

if report.ok:
    print("Migration is safe!")
```

### 4. Reproduction Engine
Replay previous experiments and detect structural drift between the original run and the current state.

```python
# Replay a previous run with structural parity checks
results = identa.reproduce(
    run_id="run_123",
    agent=my_agent,
    suite=suite
)
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
