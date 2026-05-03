# Identa 🧠

| Package | Version | Status |
| :--- | :--- | :--- |
| **identa-sdk** | [![PyPI version](https://img.shields.io/pypi/v/identa-sdk.svg)](https://pypi.org/project/identa-sdk/) | [![Release](https://github.com/identa-ai/identa/actions/workflows/release.yml/badge.svg)](https://github.com/identa-ai/identa/actions/workflows/release.yml) |
| **identa-core** | [![PyPI - core](https://img.shields.io/pypi/v/identa-core.svg?label=pypi%20-%20core)](https://pypi.org/project/identa-core/) | [![Release](https://github.com/identa-ai/identa/actions/workflows/release.yml/badge.svg)](https://github.com/identa-ai/identa/actions/workflows/release.yml) |

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

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

## Installation

### From PyPI (Recommended)

To install the user-facing SDK:

```bash
pip install identa-sdk
```

### From Source (Development)

1. **Requirements**
   - Python 3.10+
   - [uv](https://docs.astral.sh/uv/)

2. **Clone and Sync**
   ```bash
   git clone https://github.com/identa-ai/identa.git
   cd identa
   uv sync
   ```

## Quick Start

### 1. Run Your First Evaluation

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
identa runs list --workspace travel_agent

# Inspect a specific run
identa runs show <run_id>
```

## Build & Development

Identa uses `hatchling` as the build backend and `uv` for workspace management.

### Building Packages Locally

To build the wheel and sdist for each package:

```bash
# Build identa-core
uv build --package identa-core

# Build identa-sdk
uv build --package identa-sdk
```

The distributions will be located in the `dist/` directory.

### Running Tests

Run the full E2E suite:

```bash
uv run pytest tests/
```

## Architecture Summary

Identa follows a **Hexagonal Architecture** with **CQRS** enforced via package structure:

- **Commands**: Mutate run state and artifacts (e.g., `LogResults`).
- **Queries**: Materialize history and comparisons (e.g., `CompareRuns`).
- **Ports**: Abstract storage (SQLite, Postgres) and artifact stores (FS, S3).

## Architecture & Contributing Guidelines

To maintain clean architectural boundaries, all contributions must follow these rules:

- **The Adapter Rule**: If you are integrating a new third-party framework (e.g., LlamaIndex, LangChain), it goes in `identa-sdk/adapters/`. If you are adding a new internal domain concept, metric, or tracing algorithm, it goes in `identa-core`.
- **The Import Rule**: Application code (end-users) should only import from `identa.sdk`. Internal tools (like `identa-cli`) are permitted to instantiate `identa.core` commands directly, provided they use the `sdk.api.execute()` bus for execution.
- **Stateless Core**: Core handlers must be stateless. All dependencies (Storage, Exporters) must be injected via constructors. Core should never import from the SDK.

## License

Apache-2.0
