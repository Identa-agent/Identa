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
4.  **Persistence (Adapters)**: Concrete implementations of ports (SQLite, Local Filesystem).

## Key Components

- **Evaluation Engine**: The loop that executes agents against test suites and computes metrics.
- **Tracing Service**: A context-aware span collector.
- **Migration Engine**: Logic to validate and apply model-binding swaps.
- **Reproduction Engine**: Logic to replay experiments with structural drift detection.

## Drift Analysis Tracks

Identa Core supports two distinct evaluation pipelines:

1. **Standard Track**: Robust, statistical observability.
   - Normalized Structural Drift (Jaccard Similarity).
   - Behavioral Drift (Smoothed PSI).
   - Feature Weighting (MetricSpec.weight).

2. **Vanguard Track**: State-of-the-art semantic/causal detection.
   - Semantic Embedding Drift (Wasserstein Distance).
   - LLM-as-a-Judge (Qualitative Drift scoring).
   - Online Calibration (Dynamic Decision Boundaries).
   - Causal Graph Inference (Root-Cause Bottleneck analysis).

Configure your pipeline via `EvaluationConfig.drift_mode`.

## Development

This package is managed by `uv`.
...

```bash
# Run unit tests
uv run pytest tests/
```
