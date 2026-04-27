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

# Run evaluation with metrics
results = identa.evaluate(
    agent=my_agent, 
    suite=suite,
    metrics=["accuracy", "latency"],
    resolution="graph"
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
from identa.sdk.migration import MigrationEngine

engine = MigrationEngine(workspace="travel_agent")

# Validate if the swap is safe based on structural drift
is_safe = engine.validate_swap(
    source_model="gpt-4o", 
    target_model="claude-3-5-sonnet"
)

if is_safe:
    engine.apply_swap(target_model="claude-3-5-sonnet")
```

### 4. Reproduction Engine
Replay previous experiments and detect structural drift between the original run and the current state.

```python
from identa.sdk.reproduction import ReproductionEngine

repro = ReproductionEngine(workspace="travel_agent")

# Replay a failed run
analysis = repro.replay(run_id="run_123")

if analysis.has_drift:
    print(f"Structural drift detected: {analysis.drift_details}")
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
