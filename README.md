# Identa 🧠

| Package | Version | Status |
| :--- | :--- | :--- |
| **identa-sdk** | [![PyPI version](https://img.shields.io/pypi/v/identa-sdk.svg)](https://pypi.org/project/identa-sdk/) | [![Release](https://github.com/identa-ai/identa/actions/workflows/release.yml/badge.svg)](https://github.com/identa-ai/identa/actions/workflows/release.yml) |
| **identa-core** | [![PyPI - core](https://img.shields.io/pypi/v/identa-core.svg?label=pypi%20-%20core)](https://pypi.org/project/identa-core/) | [![Release](https://github.com/identa-ai/identa/actions/workflows/release.yml/badge.svg)](https://github.com/identa-ai/identa/actions/workflows/release.yml) |

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Identa is a Behavioral Intelligence platform providing an MLflow-shaped evaluation and migration substrate for notebook-driven agent experimentation. It delivers a zero-friction experience for **LangGraph**, **PydanticAI**, and **LangChain** agents, ensuring developers have a comprehensive suite for multi-resolution performance tracking, structural drift detection, and automated model-binding migrations.

## What is Identa?

Identa serves as the foundational platform for agent observability, reproducibility, and rigorous evaluation. By bridging the gap between rapid experimentation and production readiness, it enables developers to:
- **Track Agent Behavior:** Observe fine-grained execution metrics at the node level across your agent architectures.
- **Detect Drift:** Identify both structural changes and behavioral shifts in your agents through advanced metrics and semantic evaluation (Standard, Vanguard, and Hybrid tracks).
- **Automate Migrations:** Confidently swap underlying LLMs or toolings using structurally-aware migration plans.
- **Reproduce Runs:** Persist full execution contexts to precisely replay and debug past interactions.

By combining powerful **CLI workflows** with intuitive **SDK integration patterns**, Identa ensures that developers can seamlessly integrate robust behavioral analytics into their existing AI lifecycles.

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

## Drift Evaluation Modes

Identa now supports three evaluation tracks for drift detection:

- **Standard**: Industry standard statistical drift detection (Normalized Structural Drift + PSI Behavioral Drift).
- **Vanguard**: State-of-the-art semantic/causal detection (Semantic Embedding Drift + LLM-as-a-Judge + Causal Bottleneck Analysis).
- **Hybrid**: A comprehensive evaluation combining both Standard statistical observability and Vanguard semantic/causal detection for maximum coverage.

You can switch between them when evaluating your agent:

```python
# Vanguard track example
results = identa.evaluate(
    agent=my_agent,
    suite=my_suite,
    drift_mode="vanguard"
)
```

Or via the CLI:

```bash
identa run --drift-mode vanguard my_suite.toml
```

## CLI Usage

The Identa CLI provides powerful tools for managing runs and detecting behavioral drift across agent versions:

```bash
# Evaluate an agent with the vanguard drift mode
identa run --drift-mode vanguard my_suite.toml

# List recent runs
identa runs list --workspace my_experiment

# View details of a specific run
identa runs show <run_id>

# Compare two runs to detect structural and behavioral drift
identa drift compare <run_id_A> <run_id_B>

# Reproduce a past run against the current agent architecture
identa drift reproduce <run_id>
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
