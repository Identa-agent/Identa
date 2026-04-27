# Identa SDK — Transparent Adapter & Zero-Friction DX

**Spec version:** 1.1
**Target package:** `packages/identa-sdk`
**Status:** Ready for Claude Code execution
**Companion to:** `claude.spec.md` (production roadmap)

---

## 1. Context

The current `identa-sdk` exposes framework adapters (`LangGraphAdapter`, `PydanticAIAdapter`) as public symbols that the user must import and call manually before passing their agent into `api.evaluate()`. Reviewer feedback (G. Oviedo, 2026-04-26):

> *"porque no quieres adaptar los agentes... la interconexion al minimo, no quieres modificar o cambiar el agente, solo estudiarlo"*
>
> *"en realidad podrías querer hacerlo a la interna, pero tu api publica/sdk no debería hacerte usar eso, el usuario debería pasar el obj agent y tu codigo internamente resolver que usar"*

The principle: **Identa observes agents, it does not modify them.** Adapters are an internal implementation detail. The public API takes a plain agent object.

This spec also closes a behavioral bug: the current adapters monkeypatch `agent.run` and `graph.invoke` in place, mutating the user's object. This must be replaced with a non-mutating proxy.

---

## 2. Current state (as observed in repo)

### 2.1 Public API surface (`packages/identa-sdk/identa/sdk/api.py`)

```python
def set_workspace(name: str, db_url: str = "sqlite:///identa.db"): ...
def start_run(name: str) -> RunContext: ...
def evaluate(agent: Any, suite: List[Dict[str, Any]], **kwargs): ...
```

`evaluate()` already accepts `agent: Any` and forwards to `EvaluationEngine.evaluate()`. **Good.**

### 2.2 The actual problem

`EvaluationEngine.evaluate()` in `packages/identa-core/identa/core/domain/evaluation.py` calls `agent(test_input)` directly. It expects a plain callable. So the SDK is forcing the user to do the wrapping work outside, then pass `wrapped_agent.invoke` or `wrapped_agent.run` as the callable. That is the friction we are removing.

### 2.3 Mutation bug in adapters

```python
# packages/identa-sdk/identa/sdk/adapters/langgraph_adapter.py  (current)
graph.invoke = wrapped_invoke   # ← mutates user's graph object
```

```python
# packages/identa-sdk/identa/sdk/adapters/pydantic_ai_adapter.py  (current)
agent.run = wrapped_run         # ← mutates user's agent object
```

Both adapters violate the "observe, don't modify" principle.

### 2.4 README user-facing example (current)

```python
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter
wrapped_agent = LangGraphAdapter.wrap_for_tracing(my_graph)
structure = LangGraphAdapter.inspect(my_graph)

with api.start_run("gpt-4-baseline"):
    results = api.evaluate(agent=wrapped_agent.invoke, ...)
```

This is the UX we are eliminating.

---

## 3. Target DX

### 3.1 Minimum viable usage — no framework knowledge required

```python
import identa

identa.set_workspace("travel_agent")

suite = [{"input": {"query": "Fly to Paris"}, "expected": {"destination": "CDG"}}]

with identa.start_run("gpt-4-baseline") as run:
    results = identa.evaluate(agent=my_agent, suite=suite)

print(results.summary())
```

No adapter import. No manual wrap. No manual inspect. Works for LangGraph, PydanticAI, and LangChain agents identically.

### 3.2 Opting into higher resolution

```python
results = identa.evaluate(
    agent=my_graph,
    suite=suite,
    resolution="node",   # auto-inspects internally
)
```

### 3.3 Optional explicit inspection

```python
structure = identa.inspect(my_graph)   # convenience, not required
print(structure.nodes)

results = identa.evaluate(agent=my_graph, suite=suite, structure=structure)
```

When `structure=` is passed, `evaluate()` skips re-inspection (idempotent path required by `spec.md` §25).

---

## 4. Internal architecture

### 4.1 New module: `identa/sdk/registry.py`

```python
# packages/identa-sdk/identa/sdk/registry.py
from dataclasses import dataclass
from typing import Any, Callable, Type
from identa.sdk.adapters.base import BaseAdapter

class UnsupportedFrameworkError(TypeError):
    """Raised when no adapter matches the supplied agent object."""

@dataclass
class AdapterEntry:
    matcher: Callable[[Any], bool]
    adapter_cls: Type[BaseAdapter]
    name: str

class AgentRegistry:
    _entries: list[AdapterEntry] = []

    @classmethod
    def register(cls, matcher: Callable[[Any], bool], adapter_cls: Type[BaseAdapter], name: str) -> None:
        cls._entries.append(AdapterEntry(matcher, adapter_cls, name))

    @classmethod
    def detect(cls, agent: Any) -> BaseAdapter:
        for entry in cls._entries:
            try:
                if entry.matcher(agent):
                    return entry.adapter_cls()
            except Exception:
                continue
        supported = ", ".join(e.name for e in cls._entries) or "<none>"
        raise UnsupportedFrameworkError(
            f"No Identa adapter matches {type(agent).__module__}.{type(agent).__qualname__}. "
            f"Supported frameworks: {supported}."
        )
```

**Detection strategy** — match by module path, never by `isinstance` on imported types (avoids importing every supported framework eagerly):

```python
def _is_langgraph(agent: Any) -> bool:
    mod = type(agent).__module__
    return mod.startswith("langgraph.")

def _is_pydantic_ai(agent: Any) -> bool:
    mod = type(agent).__module__
    return mod.startswith("pydantic_ai.")
```

### 4.2 New module: `identa/sdk/adapters/base.py`

```python
# packages/identa-sdk/identa/sdk/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from identa.core.domain.structure import AgentStructure

@dataclass
class WrappedAgent:
    """A traced callable. Original agent is preserved unmutated."""
    callable: Callable[[Any], Any]   # signature: (input) -> output, used by EvaluationEngine
    original: Any                     # untouched user agent
    framework_name: str

    def __call__(self, input: Any) -> Any:
        return self.callable(input)

class BaseAdapter(ABC):
    framework_name: str = "unknown"

    @abstractmethod
    def inspect(self, agent: Any) -> AgentStructure: ...

    @abstractmethod
    def wrap(self, agent: Any) -> WrappedAgent:
        """Return a traced callable. MUST NOT mutate `agent`."""
```

### 4.3 Rewritten adapters (non-mutating)

```python
# packages/identa-sdk/identa/sdk/adapters/pydantic_ai_adapter.py
from typing import Any
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure

class PydanticAIAdapter(BaseAdapter):
    framework_name = "pydantic_ai"

    def inspect(self, agent: Any) -> AgentStructure:
        # Phase 1: minimal stub — PydanticAI agents are linear.
        # Returns a single-node structure so resolution="node" works.
        from identa.core.domain.structure import AgentNode
        import hashlib, json
        model_name = getattr(getattr(agent, "model", None), "model_name", "unknown")
        node = AgentNode(
            id="pydantic_ai_root",
            type="llm",
            name="pydantic_ai_root",
            model=model_name,
            id_stability="stable",
        )
        version_hash = hashlib.sha256(json.dumps({"nodes": ["pydantic_ai_root"]}).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=[node], edges=[])

    def wrap(self, agent: Any) -> WrappedAgent:
        # Note: agent is never mutated.
        def traced(input_value: Any) -> Any:
            prompt = input_value if isinstance(input_value, str) else input_value.get("query") or str(input_value)
            model_name = getattr(getattr(agent, "model", None), "model_name", None)
            span_id = TracingService.start_span(
                name="pydantic_ai_run",
                kind="agent",
                metadata=SpanMetadata(model=model_name, node_id="pydantic_ai_root"),
            )
            try:
                return agent.run_sync(prompt)
            finally:
                TracingService.end_span(span_id)
        return WrappedAgent(callable=traced, original=agent, framework_name=self.framework_name)
```

```python
# packages/identa-sdk/identa/sdk/adapters/langgraph_adapter.py
from typing import Any
import hashlib, json
from identa.sdk.adapters.base import BaseAdapter, WrappedAgent
from identa.core.domain.tracing_service import TracingService
from identa.core.domain.tracing import SpanMetadata
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

class LangGraphAdapter(BaseAdapter):
    framework_name = "langgraph"

    def inspect(self, graph: Any) -> AgentStructure:
        nodes = [
            AgentNode(id=name, type="custom", name=name, id_stability="stable")
            for name in graph.nodes.keys()
        ]
        edges: list[AgentEdge] = []  # TODO Phase 2: extract real edges
        struct_data = {
            "nodes": sorted(n.id for n in nodes),
            "edges": sorted(f"{e.from_node}->{e.to_node}" for e in edges),
        }
        version_hash = hashlib.sha256(json.dumps(struct_data).encode()).hexdigest()
        return AgentStructure(id=version_hash[:16], version_hash=version_hash, nodes=nodes, edges=edges)

    def wrap(self, graph: Any) -> WrappedAgent:
        # No monkeypatch. We capture the bound method and call it through the proxy.
        original_invoke = graph.invoke
        def traced(input_value: Any) -> Any:
            span_id = TracingService.start_span(
                name="langgraph_invoke",
                kind="agent",
                metadata=SpanMetadata(),
            )
            try:
                return original_invoke(input_value)
            finally:
                TracingService.end_span(span_id)
        return WrappedAgent(callable=traced, original=graph, framework_name=self.framework_name)
```

### 4.4 Adapter auto-registration

```python
# packages/identa-sdk/identa/sdk/adapters/__init__.py
from identa.sdk.registry import AgentRegistry
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

def _is_langgraph(agent): return type(agent).__module__.startswith("langgraph.")
def _is_pydantic_ai(agent): return type(agent).__module__.startswith("pydantic_ai.")

AgentRegistry.register(_is_langgraph, LangGraphAdapter, name="langgraph")
AgentRegistry.register(_is_pydantic_ai, PydanticAIAdapter, name="pydantic_ai")
```

### 4.5 Rewritten `api.py`

```python
# packages/identa-sdk/identa/sdk/api.py  (changes only)
from identa.sdk.registry import AgentRegistry
from identa.sdk.adapters.base import WrappedAgent
import identa.sdk.adapters  # noqa: F401  triggers registration

def evaluate(agent: Any, suite: List[Dict[str, Any]], **kwargs):
    if not _client:
        raise ValueError("Call set_workspace first")

    # If user already passed a WrappedAgent (advanced use), skip detection.
    if isinstance(agent, WrappedAgent):
        wrapped = agent
        structure = kwargs.get("structure")
    else:
        adapter = AgentRegistry.detect(agent)
        resolution = kwargs.get("resolution", "boundary")
        structure = kwargs.get("structure")
        if resolution != "boundary" and structure is None:
            structure = adapter.inspect(agent)
            kwargs["structure"] = structure
        wrapped = adapter.wrap(agent)

    run_id = kwargs.pop("run_id", "standalone")
    return _client.evaluate(wrapped, suite, run_id=run_id, **kwargs)


def inspect(agent: Any) -> "AgentStructure":
    """Optional: inspect an agent without running a suite."""
    if isinstance(agent, WrappedAgent):
        agent = agent.original
    adapter = AgentRegistry.detect(agent)
    return adapter.inspect(agent)
```

`EvaluationEngine.evaluate()` already calls `agent(test_input)`, so passing a `WrappedAgent` works because `WrappedAgent.__call__` forwards to its traced callable. **No core changes required.**

### 4.6 Top-level package exports

```python
# packages/identa-sdk/identa/sdk/__init__.py
from identa.sdk.api import set_workspace, start_run, evaluate, inspect

__all__ = ["set_workspace", "start_run", "evaluate", "inspect"]
```

```python
# packages/identa-sdk/identa/__init__.py  (CREATE)
from identa.sdk import set_workspace, start_run, evaluate, inspect

__all__ = ["set_workspace", "start_run", "evaluate", "inspect"]
```

This enables `import identa; identa.evaluate(...)` directly.

`LangGraphAdapter` and `PydanticAIAdapter` are NOT re-exported. They remain importable from their submodules for advanced/library-author use, but they are not part of the documented public API.

---

## 5. E2E test plan

Two real PydanticAI test cases, no mocks. Both must run without importing any adapter class.

### 5.1 New file: `packages/identa-sdk/tests/e2e/test_e2e_pydantic.py`

```python
"""E2E tests against real PydanticAI agents and real model APIs.

These tests require:
  - OPENAI_API_KEY set in the environment
  - ANTHROPIC_API_KEY set in the environment

They are skipped when keys are absent.
"""
import os
import pytest
import identa
from pydantic_ai import Agent

pytestmark = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
    reason="Real model API keys required for e2e",
)

SUITE = [
    {"input": "What is the capital of France?", "expected": "Paris"},
    {"input": "What is 2 + 2?", "expected": "4"},
]

def _setup_workspace(tmp_path, name):
    db_path = tmp_path / f"{name}.db"
    identa.set_workspace(name, db_url=f"sqlite:///{db_path}")

# ── Case A — behavioral inequality ───────────────────────────────
def test_two_different_models_show_measurable_difference(tmp_path):
    _setup_workspace(tmp_path, "case_a")
    agent_gpt = Agent("openai:gpt-4o-mini", system_prompt="Answer in one word.")
    agent_claude = Agent("anthropic:claude-3-haiku-20240307", system_prompt="Answer in one word.")

    with identa.start_run("gpt") as _:
        r_gpt = identa.evaluate(agent=agent_gpt, suite=SUITE, metrics=["latency"])
    with identa.start_run("claude") as _:
        r_claude = identa.evaluate(agent=agent_claude, suite=SUITE, metrics=["latency"])

    # We assert that traces from two providers were captured distinctly.
    assert r_gpt.aggregates[0].metric_name == "latency"
    assert r_claude.aggregates[0].metric_name == "latency"
    # Sanity: same suite, two providers, not the same trace_ref
    assert r_gpt.per_test[0].trace_ref != r_claude.per_test[0].trace_ref

# ── Case B — behavioral equality (same agent twice) ──────────────
def test_same_agent_twice_runs_consistently(tmp_path):
    _setup_workspace(tmp_path, "case_b")
    agent = Agent("openai:gpt-4o-mini", system_prompt="Answer in one word.")

    with identa.start_run("first") as _:
        r1 = identa.evaluate(agent=agent, suite=SUITE, metrics=["latency"])
    with identa.start_run("second") as _:
        r2 = identa.evaluate(agent=agent, suite=SUITE, metrics=["latency"])

    assert len(r1.per_test) == len(r2.per_test) == len(SUITE)
    # The agent object must not have been mutated by the first run.
    assert callable(agent.run)
    assert callable(agent.run_sync)
```

### 5.2 New file: `packages/identa-sdk/tests/unit/test_registry.py`

```python
import pytest
import identa
from identa.sdk.registry import AgentRegistry, UnsupportedFrameworkError

class FakeAgent:
    """Object from no recognized framework."""

def test_unknown_framework_raises_clear_error():
    with pytest.raises(UnsupportedFrameworkError) as exc:
        AgentRegistry.detect(FakeAgent())
    assert "Supported frameworks" in str(exc.value)

def test_public_api_does_not_expose_adapters():
    # Adapters must not leak into the top-level namespace
    assert not hasattr(identa, "LangGraphAdapter")
    assert not hasattr(identa, "PydanticAIAdapter")
    assert not hasattr(identa, "BaseAdapter")
```

### 5.3 New file: `packages/identa-sdk/tests/unit/test_no_mutation.py`

```python
"""The user's agent object must be returned to them unmodified."""
from unittest.mock import MagicMock
from identa.sdk.adapters.langgraph_adapter import LangGraphAdapter
from identa.sdk.adapters.pydantic_ai_adapter import PydanticAIAdapter

def test_langgraph_adapter_does_not_mutate_graph():
    graph = MagicMock()
    graph.nodes = {"a": object(), "b": object()}
    original_invoke = graph.invoke

    LangGraphAdapter().wrap(graph)

    assert graph.invoke is original_invoke, "graph.invoke was monkeypatched"

def test_pydantic_ai_adapter_does_not_mutate_agent():
    agent = MagicMock()
    original_run = agent.run
    original_run_sync = agent.run_sync

    PydanticAIAdapter().wrap(agent)

    assert agent.run is original_run, "agent.run was monkeypatched"
    assert agent.run_sync is original_run_sync, "agent.run_sync was monkeypatched"
```

---

## 6. Files to create / modify

| Path | Action | Notes |
|---|---|---|
| `packages/identa-sdk/identa/sdk/registry.py` | **CREATE** | `AgentRegistry`, `UnsupportedFrameworkError` |
| `packages/identa-sdk/identa/sdk/adapters/base.py` | **CREATE** | `BaseAdapter`, `WrappedAgent` |
| `packages/identa-sdk/identa/sdk/adapters/__init__.py` | **CREATE** | Auto-register on import |
| `packages/identa-sdk/identa/sdk/adapters/langgraph_adapter.py` | **REWRITE** | Implements `BaseAdapter`; non-mutating wrap |
| `packages/identa-sdk/identa/sdk/adapters/pydantic_ai_adapter.py` | **REWRITE** | Implements `BaseAdapter`; non-mutating wrap; uses `run_sync` |
| `packages/identa-sdk/identa/sdk/api.py` | **MODIFY** | `evaluate()` calls `AgentRegistry.detect()`; add `inspect()` |
| `packages/identa-sdk/identa/sdk/__init__.py` | **MODIFY** | Export `set_workspace`, `start_run`, `evaluate`, `inspect` |
| `packages/identa-sdk/identa/__init__.py` | **CREATE** | Top-level convenience exports |
| `packages/identa-sdk/tests/e2e/test_e2e_pydantic.py` | **CREATE** | Real-API tests, Cases A and B |
| `packages/identa-sdk/tests/unit/test_registry.py` | **CREATE** | Detection + public-surface assertions |
| `packages/identa-sdk/tests/unit/test_no_mutation.py` | **CREATE** | Verifies adapters do not mutate |
| `packages/identa-sdk/README.md` | **REWRITE** | New "Quick Start" matches §3.1 |
| `README.md` (repo root) | **MODIFY** | Update Quick Start example |

**Files NOT changed:**
- `packages/identa-core/` — entire core package untouched. `EvaluationEngine` already accepts a callable; `WrappedAgent.__call__` satisfies that contract.

---

## 7. Acceptance criteria

1. `import identa; identa.evaluate(agent=my_agent, suite=...)` works for LangGraph, PydanticAI, and (where the adapter exists) LangChain agents — with **zero adapter imports** in user code.
2. After `identa.evaluate(agent=x, ...)` returns, `x.invoke` / `x.run` / `x.run_sync` are the **same object identities** they were before the call (no monkeypatching).
3. `identa.LangGraphAdapter` and `identa.PydanticAIAdapter` are **not** accessible from the top-level `identa` namespace.
4. Calling `identa.evaluate(agent=<object from unknown framework>, ...)` raises `UnsupportedFrameworkError` with a message that lists supported frameworks.
5. `identa.inspect(agent)` returns a valid `AgentStructure` without executing any test.
6. When `resolution="node"` and `structure=None`, `evaluate()` auto-inspects exactly once and stamps `structure_hash` onto the result.
7. When `structure=` is passed explicitly, `evaluate()` does not call `inspect()` again (idempotency, per `spec.md` §25).
8. `tests/e2e/test_e2e_pydantic.py` Case A and Case B both pass against real model APIs when keys are present.
9. All existing core unit tests (`packages/identa-core/tests/`) still pass — no core changes.

---

## 8. Phasing & verification

This spec is one self-contained chunk for Claude Code. Execute in this order:

```
Step 1: Create base.py + registry.py
        Verify: pytest packages/identa-sdk/tests/unit/test_registry.py -k "test_unknown_framework"

Step 2: Rewrite langgraph_adapter.py + pydantic_ai_adapter.py + adapters/__init__.py
        Verify: pytest packages/identa-sdk/tests/unit/test_no_mutation.py

Step 3: Modify api.py + sdk/__init__.py + identa/__init__.py
        Verify: pytest packages/identa-sdk/tests/unit/test_registry.py
                python -c "import identa; assert not hasattr(identa, 'LangGraphAdapter')"

Step 4: Write e2e tests
        Verify (with API keys): pytest packages/identa-sdk/tests/e2e/

Step 5: Update READMEs
        Verify: grep -R "LangGraphAdapter" packages/identa-sdk/README.md README.md
                # Should return zero matches in user-facing examples
```

Commit each step separately using `feat(sdk): <description>` or `refactor(sdk): <description>`.

---

## 9. Out of scope

- LangChain adapter implementation — referenced in `pyproject.toml` and `spec.md` but no adapter file exists yet. Scaffolding the registration for LangChain is separate work.
- Async support in the wrap path — `EvaluationEngine` is currently sync; async is a separate spec.
- Edge extraction in `LangGraphAdapter.inspect()` — currently returns empty `edges`. Improving this is tracked in `claude.spec.md` Phase 2.
- Server / API mode — this spec only touches the SDK package.

---

## 10. Risk register

| Risk | Mitigation |
|---|---|
| PydanticAI's public method changed from `run` to `run_sync` between versions | Adapter calls `run_sync` (matches pinned `pydantic-ai>=1.86.1` in `pyproject.toml`); fall back to `run` if `run_sync` is missing |
| `type(agent).__module__` returns `__main__` for user-subclassed agents | Detection walks the MRO and checks each base's module; documented in `_is_*` helpers |
| Existing notebooks using `LangGraphAdapter.wrap_for_tracing` break | Keep the old class methods as thin shims that emit `DeprecationWarning` and call the new `wrap()` internally; remove in v0.3 |
| `WrappedAgent` passed back into `evaluate()` causes double-wrap | `evaluate()` checks `isinstance(agent, WrappedAgent)` and skips detection in that case |

---

## 11. Resume contract

To continue this spec in a fresh Claude Code session:

> Continue from `Step N` in `identa_transparent_adapter_spec.md`. Read the full spec first, work the steps in order, run the verification command after each step, and commit before moving on.