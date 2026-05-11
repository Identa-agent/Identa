# Identa Core 🧠

The engine room of Identa. This package contains the pure domain logic, ports, and application handlers following a strict **Hexagonal Architecture** and **CQRS** pattern.

## Architecture

Identa Core is designed to be framework-agnostic and side-effect free. It enforces a clean separation between "how we evaluate" and "how we store/trace".

### Hexagonal Layers

1.  **Domain**: Pure Pydantic models (Runs, Spans, AgentStructure) and core logic (Metric computation, Migration validation).
2.  **Ports**: Abstract interfaces for storage and artifacts.
3.  **Application**:
    *   **Commands**: Mutation logic (Start Run, Log Results).
    *   **Queries**: Data retrieval logic (List Runs, Get Comparison).
4.  **Persistence (Adapters)**: Concrete implementations of ports (SQLite, Postgres).

## Key Components

- **Evaluation Engine**: A high-concurrency engine that executes agents against test suites and computes metrics.
- **Tracing Service**: A context-aware span collector with multi-threaded support.
- **Drift Engine**: Multi-layer analysis (Structural, Semantic, Behavioral, Causal, Temporal).
- **Reproduction Engine**: Logic to replay experiments with structural drift detection.

## Drift Analysis Tracks

Identa Core supports three distinct evaluation pipelines:

1. **Standard Track**: Robust, statistical observability.
   - Normalized Structural Drift (Jaccard Similarity).
   - Behavioral Drift (Markov-Chain Transition Divergence).
   - Node-level resolution.

2. **Vanguard Track**: State-of-the-art semantic/causal detection.
   - Semantic Embedding Drift (MMD + Classifier Ensemble).
   - LLM-as-a-Judge (Qualitative Drift scoring).
   - Causal Attribution (Shapley-based root cause analysis).
   - Temporal Drift (ADWIN adaptive windowing).

3. **Hybrid Track**: A combination of both for maximum coverage.

*Note: Vanguard features require the `enterprise` extra.*

## Graceful Degradation

Identa Core is built for resiliency. The `EnterpriseDriftEngine` supports graceful degradation: if heavy ML dependencies (`numpy`, `scipy`) are missing, it will warn the user and skip advanced analysis layers instead of crashing the SDK.

## How to Use Core

While typical users will interact with the `identa-sdk`, developers building custom evaluation pipelines or extending Identa can use `identa-core` directly.

### 1. Executing CQRS Commands

```python
from identa.core.domain.models import Run
from identa.core.application.commands import StartRunCommand
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter

# Initialize storage
storage = SQLiteStorageAdapter("sqlite:///identa.db")

# Execute a command
command = StartRunCommand(workspace_id="default", run_name="test-run")
run_record = command.execute(storage=storage)
```

## Development

This package is managed by `uv`.

```bash
# Run unit tests
uv run pytest tests/
```

## License

Apache-2.0
