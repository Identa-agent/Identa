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

## Architecture & Contributing Guidelines

To maintain clean architectural boundaries, all contributions must follow these rules:

- **The Adapter Rule**: If you are integrating a new third-party framework (e.g., LlamaIndex, LangChain), it goes in `identa/sdk/adapters/`. If you are adding a new internal domain concept, metric, or tracing algorithm, it goes in `identa-core`.
- **The Import Rule**: Application code (end-users) should only import from `identa.sdk`. Internal tools (like `identa-cli`) are permitted to instantiate `identa.core` commands directly, provided they use the `sdk.api.execute()` bus for execution.
- **Strict Public API**: Only functions explicitly listed in `identa/__init__.py`'s `__all__` are considered part of the stable public API.
