# Identa 🧠

Identa is an MLflow-shaped evaluation and migration substrate for notebook-driven agent experimentation. It provides a zero-friction experience for **LangGraph**, **PydanticAI**, and **LangChain** agents with multi-resolution performance tracking, structural drift detection, and automated model-binding migrations.

## The Alignment Triangle 📐

Identa's core design invariant is to maintain the integrity of the following triangle:

**AgentStructure** ←→ **Span.metadata.node_id** ←→ **Metric Attribution**

Every architectural decision exists to keep this triangle intact at runtime, ensuring that metrics are correctly attributed to the specific nodes (LLMs, Tools, Routers) that produced them.

## Project Structure

This is a monorepo managed by [uv](https://docs.astral.sh/uv/).

- **`packages/identa-core`**: The hexagonal core. Contains the domain models, CQRS application layer, and persistence adapters (SQLite, Local FS).
- **`packages/identa-sdk`**: The user-facing SDK and CLI. Includes adapters for LangGraph and PydanticAI.
- **`tests/`**: End-to-end integration tests for all supported frameworks and evaluation modes.

## Quick Start

### 1. Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

### 2. Installation

Clone the repository and sync the workspace:

```bash
uv sync
```

### 3. Run Your First Evaluation

```python
import identa

# 1. Initialize workspace
identa.set_workspace("my_experiment", db_url="sqlite:///identa.db")

# 2. Evaluate (framework auto-detection handles the rest)
with identa.start_run("gpt-4-baseline"):
    results = identa.evaluate(
        agent=my_agent,   # Pass your LangGraph or PydanticAI object directly
        suite=[{"input": {"q": "hi"}, "expected": "hello"}],
        resolution="node"
    )
```

## CLI Usage

The Identa CLI allows you to inspect runs and compare baselines:

```bash
# List all runs
uv run identa runs list --workspace travel_agent

# Inspect a specific run
uv run identa runs show <run_id>
```

## Architecture Summary

Identa follows a **Hexagonal Architecture** with **CQRS** enforced via package structure:

- **Commands**: Mutate run state and artifacts (e.g., `LogResults`).
- **Queries**: Materialize history and comparisons (e.g., `CompareRuns`).
- **Ports**: Abstract storage (SQLite, Postgres) and artifact stores (FS, S3).

## Testing

Run the full E2E suite:

```bash
uv run pytest tests/
```

## License

MIT
