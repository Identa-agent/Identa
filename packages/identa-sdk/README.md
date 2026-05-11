# Identa SDK 🚀

The user-facing toolkit for evaluating and migrating LLM-based agents. Identa provides a zero-friction experience for **LangGraph**, **PydanticAI**, and **LangChain** agents.

## Getting Started

### 1. Installation

```bash
pip install "identa-sdk[all]"
```

## How to Use the SDK

The Identa SDK is designed for zero-friction integration with your existing agent frameworks.

### 1. Configure Your Workspace

Before running evaluations, initialize your workspace and database connection:

```python
import identa

identa.set_workspace("travel_agent_evals", db_url="sqlite:///identa.db")
```

### 2. Evaluation Engine
The `evaluate` function executes your agent against test suites and computes metrics across your agent's graph/flow. Framework adapters are auto-detected.

```python
import identa

# Run evaluation with node-level resolution
results = identa.evaluate(
    agent=my_agent, 
    suite=suite,
    resolution="node",
    max_concurrency=5 # Parallel test execution
)

print(results.summary())
```

### 3. Async Evaluation
For long-running suites, use the async engine:

```python
import asyncio
import identa

async def run():
    results = await identa.evaluate_async(
        agent=my_agent,
        suite=suite,
        max_concurrency=10
    )
    print(results.summary())

asyncio.run(run())
```

### 4. Baseline Management
Register a specific run as a baseline for future drift detection:

```python
identa.register_baseline(run_id="run_abc", name="v1-production")
```

## CLI

Identa comes with a powerful CLI to manage your runs and detect behavioral drift.

```bash
# Evaluate an agent
identa run --workspace travel_agent --drift-mode vanguard my_suite.toml

# Manage baselines
identa baselines list --workspace travel_agent
identa baselines register <run_id> --name stable-v1

# Compare two runs
identa compare <run_id_A> <run_id_B>
```

## Framework Support

| Feature | LangGraph | PydanticAI | LangChain |
| :--- | :--- | :--- | :--- |
| **Boundary Eval** | ✅ | ✅ | ✅ |
| **Node Tracing** | ✅ | ✅ | ✅ |
| **Structural Inspection** | ✅ | ✅ | ✅ |
| **Model Migration** | ✅ | 🚧 | 🚧 |

## Architecture & Contributing Guidelines

- **The Adapter Rule**: If you are integrating a new third-party framework, it goes in `identa/sdk/adapters/`. If you are adding a new internal domain concept or metric, it goes in `identa-core`.
- **The Import Rule**: Application code should only import from `identa`.
- **Strict Public API**: Only functions explicitly listed in `identa/__init__.py`'s `__all__` are considered part of the stable public API.

## License

Apache-2.0
