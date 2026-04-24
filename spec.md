🧠 Identa — PRD + Engineering Design (v7)
Identa is an MLflow-shaped evaluation and migration substrate for notebook-driven agent experimentation, with framework shims for LangChain, LangGraph, and PydanticAI, persistent runs/baselines/artifacts, and optional delegation to external optimizers such as DSPy.


Changelog: v6 → v7
#
Area
Change
1
evaluate() API
resolution= and structure= and strict_structure= params added; evaluation resolution contract defined
2
evaluate() API
Boundary vs structure-aware resolution split explicit: inspection required iff resolution ≠ "boundary"
3
evaluate() API
Implicit inspect-then-evaluate convenience path documented alongside explicit recommended workflow
4
run.reproduce()
Semantics clarified: config replay with structural drift detection, not executable freezing
5
run.reproduce()
strict_structure= param added; structural drift warning/tag/fail behavior defined
6
Frozen agents
Future freezable-agent extension described and explicitly excluded from MVP with rationale
7
ObservedStructureDelta
Semantics clarified: speaks about observed execution over traced sample, not per-test logical necessity
8
ObservedStructureDelta
Warning policy made explicit: unexpected_nodes non-empty OR frequency above delta_warning_threshold (default 0.1)
9
Data model
EvaluationResult.resolution field added; ReproducibilityBundle.resolution field added
10
Execution flows
Evaluation flow updated to reflect resolution-driven inspect-or-skip decision



1. Product Definition
Identa is an evaluation and migration toolkit for LLM-based agents, built for data scientists and AI engineers working in notebooks, scripts, and CI evaluation jobs.

It allows users to:

Run structured experiments against agents built with LangChain, LangGraph, or PydanticAI
Measure performance at multiple resolutions (agent, sub-agent, tool, LLM call) within the limits of each framework
Track runs, baselines, comparisons, and artifacts with an MLflow-style API
Delegate prompt optimization to external tools like DSPy
Plan and execute model-binding migrations across agent graphs as diffable, replayable artifacts


2. Core Value Proposition
Most teams today cannot measure agent quality reliably, cannot compare models apples-to-apples, and cannot safely migrate models in non-trivial graphs. Identa solves this by being the evaluation substrate that other tools plug into — not by replacing them.
The alignment triangle
The central design invariant:

AgentStructure  ←→  Span.metadata.node_id  ←→  Metric attribution

Every architectural decision exists to keep this triangle intact at runtime. node_id is assigned once at inspect() time and persisted. structure_hash propagates across EvaluationResult, MigrationPlan, and TraceArtifact. The v7 addition: evaluation resolution is now a first-class parameter that determines whether inspection is required — making the triangle opt-in for boundary evaluation and mandatory for everything finer.


3. Audience & Usage Context
Audience: data scientists and AI engineers.

Where it runs: notebooks, experiment scripts, CI evaluation jobs.

Where it does not run: production traffic. Identa is not an APM, not a sidecar, not a proxy.


4. MVP Scope
Included
✔ MLflow-style workspace / run / artifact API
✔ Framework shims: LangChain, LangGraph, PydanticAI
✔ Best-effort autologging per framework (with explicit fidelity guarantees — see §6)
✔ Test suites (TOML + programmatic) with version field
✔ MetricSpec for weighted, thresholded, multi-objective metric composition
✔ Built-in metrics + custom metrics
✔ CostModel / CostEstimate with confidence levels and defined aggregation rules
✔ Baselines + comparisons + cmp.assert_no_regressions()
✔ run.diff(other_run) for non-baseline comparisons
✔ run.reproduce(strict_structure=) — config replay with structural drift detection
✔ results.by_node() with defined aggregation semantics
✔ results.slice(...) and results.trace(test_id=) for interactive debugging
✔ results.cost_total() / results.cost_per_test()
✔ DSPy bridge
✔ MigrationPlan as serializable artifact — model-binding replacements only
✔ plan.validate() + plan.apply(mode=) gated on structure_hash match
✔ Canonical AgentStructure with id + version_hash, persisted as artifact
✔ node_id assigned once at inspect() time, never recomputed
✔ structure_hash propagated to EvaluationResult, MigrationPlan, TraceArtifact
✔ ObservedStructureDelta with frequency counts and explicit warning policy
✔ TraceConfig with test-level sampling semantics
✔ evaluate() resolution= parameter with boundary / node / tool / llm levels
✔ Reproducibility bundle on every run
✔ Local persistence (SQLite + gzip JSONL filesystem artifacts)
✔ Optional HTTP server for team-shared workspaces
✔ CQRS enforced via application.commands / application.queries package split
Non-goals (MVP)
✖ Production request shadowing
✖ Online traffic replay
✖ Distributed evaluation farm
✖ Generic observability backend
✖ Arbitrary agent graph editing or rewrites
✖ Fine-tuning / weight optimization / checkpoint management
✖ UI (CLI + notebook only)
✖ Advanced authz (basic auth only on server)
✖ Billing-accurate cost tracking (estimates only)
✖ Freezable/serializable executable agent artifacts (future extension — see §8.6)


5. Subsystems
Subsystem
Responsibility
Evaluation
Run tests at the requested resolution; inspect if required; compute metrics; aggregate results
Tracing
Capture spans from framework callbacks; manage trace config and volume
Inspection
Derive canonical AgentStructure; assign and persist node_id; detect runtime divergence
Migration
Validate and apply MigrationPlan; gate on structure_hash alignment
Optimization
Expose MetricSpec to external optimizers (DSPy, etc.)



6. Autologging — Fidelity Statement
Autologging is best-effort and framework-dependent.

Guaranteed (all supported frameworks):

Boundary-level evaluation logging (input, output, latency, cost estimate)

Best-effort, depends on framework callback/event surface:

Sub-agent / node spans with stable node_id
Tool call capture
Prompt capture (post-template-rendering)
Model configuration capture

identa.langchain.autolog()

identa.langgraph.autolog()

identa.pydantic_ai.autolog()


7. Framework Capability Matrix
Capability
LangChain
LangGraph
PydanticAI
Boundary evaluation
Yes
Yes
Yes
Autolog spans
Yes
Yes
Partial
Tool call capture
Yes
Yes
Partial
Prompt capture
Yes
Yes
Partial
Inspect structure
Partial
Yes
Partial
Stable node_id
Partial
Yes
Partial
Migration patching
Partial
Yes
Partial



8. Core API
8.1 Workspaces
import identa

identa.set_workspace("agente_viajes")

identa.set_workspace("team:agente_viajes")
8.2 Runs
with identa.start_run(name="gpt4_baseline") as run:

    run.log_params({"model": "gpt-4", "temperature": 0.2})

    run.set_tags({"experiment": "prompt_v3", "owner": "german"})

    results = identa.evaluate(

        agent_v1,

        suite="tests.toml",

        metrics=[

            identa.MetricSpec("quality",  "semantic_similarity", weight=0.7, threshold=0.85),

            identa.MetricSpec("cost",     "token_cost",          weight=0.3, minimize=True),

            identa.MetricSpec("latency",  "latency"),

        ],

        mode="controlled",

        resolution="node",

        trace_config=identa.TraceConfig(

            capture_prompts=True,

            capture_outputs="truncated",

            max_tokens=2000,

            sampling_rate=1.0,

        ),

    )

    run.log_results(results)

    run.register_baseline()

Nested runs:

with identa.start_run(name="model_sweep") as parent:

    for model in ["gpt-4", "claude-sonnet-4-5", "mistral-large"]:

        with identa.start_run(name=f"trial_{model}", nested=True) as child:

            child.log_params({"model": model})

            child.log_results(

                identa.evaluate(build_agent(model), suite="tests.toml", mode="controlled")

            )
8.3 Reproduce a run
run.reproduce()

run.reproduce(strict_structure=True)   # fail if structure has drifted

See §8.6 for full reproduction semantics.
8.4 Comparisons
cmp = run.compare_to_baseline()

cmp.summary()

cmp.regressions()

cmp.improvements()

cmp.assert_no_regressions()     # raises ComparisonError if any MetricSpec threshold breached — CI use

cmp.to_df()

diff = run_a.diff(run_b)        # non-baseline comparison

diff.summary()

diff.regressions()

diff.to_df()


8.5 Evaluation Resolution & Inspection Requirement (v7)
Identa supports two classes of evaluation resolution:
Boundary resolution
No structural snapshot is required.

Use this when evaluation is limited to whole-agent behavior:

End-to-end input/output quality
Whole-agent metrics
End-to-end latency
End-to-end cost estimates

In boundary resolution, evaluate() may run directly against the agent object without an AgentStructure snapshot.
Structure-aware resolution
A structural snapshot is required.

Use this when the requested resolution includes any of:

Node-level attribution
Tool-level attribution
LLM-call attribution
results.by_node()
ObservedStructureDelta
Migration planning or validation
Any trace that depends on stable node_id

In these cases, inspection must occur before evaluation. evaluate() must operate against an AgentStructure snapshot produced before execution. That snapshot is the source of truth for node_id, structure_hash, node stability (stable / ephemeral), and structural alignment across traces, metrics, and migration.
API contract
identa.evaluate(

    agent,

    suite="tests.toml",

    resolution="boundary" | "node" | "tool" | "llm",

    structure: AgentStructure | None = None,

    strict_structure: bool = False,

)
Resolution behavior
resolution="boundary" (default):

Inspection not required
structure parameter optional and usually ignored
No node_id, no ObservedStructureDelta, no by_node()

resolution in {"node", "tool", "llm"}:

Inspection required
If structure is provided: evaluate() uses that snapshot
If structure is not provided: evaluate() calls inspect(agent) first, persists the resulting AgentStructure, and uses that snapshot for the evaluation
Strictness behavior
strict_structure=False (default): Best-effort structure-aware evaluation. If the framework cannot fully inspect or map stable nodes, Identa continues with partial coverage, marking unsupported or ephemeral areas explicitly in the results.

strict_structure=True: Fail if a usable AgentStructure snapshot cannot be produced for the requested resolution. Use in CI where silent partial coverage is unacceptable.
Design rule
Detailed evaluation is always structure-first. If the requested resolution is finer than the agent boundary, inspection must happen before evaluation — whether passed explicitly or performed implicitly by evaluate().
Recommended explicit workflow
structure = identa.inspect(agent)

results = identa.evaluate(

    agent,

    suite="tests.toml",

    structure=structure,

    resolution="node",

    strict_structure=True,

)
Convenience workflow (implicit inspect)
results = identa.evaluate(

    agent,

    suite="tests.toml",

    resolution="node",

)

# internally:

# 1. inspect(agent)

# 2. persist AgentStructure

# 3. evaluate against that snapshot

This rule prevents silent fake node-level evaluation without a real structural anchor.


8.6 Reproduction Semantics & Freezable Artifacts (v7)
run.reproduce() reproduces the experiment configuration, not necessarily the exact historical executable object.
What reproduction reuses
By default, run.reproduce() reconstructs the original run's:

Suite (same hash)
Metric specs
Model / provider settings
Evaluation mode
Seed
Trace config
Resolution level (boundary vs structure-aware)
Stored structure_hash for structural drift validation
Important limitation
If the underlying agent code has changed since the original run, reproduction may not produce the same behavior even when configuration is identical.

run.reproduce() is best understood as:

Re-run the same experiment definition against the current codebase, with structural drift detection.
Reproduction behavior
When run.reproduce() is called, Identa:

Loads the original run's reproducibility bundle
Reconstructs the evaluate() call with the same parameters
Re-inspects the current agent if resolution is structure-aware
Compares the current structure snapshot against the stored structure_hash
Warns, fails, or proceeds based on strict_structure

run.reproduce(strict_structure=False)   # default: warn on drift, tag new run, continue

run.reproduce(strict_structure=True)    # fail if current structure does not match stored hash

When structural drift is detected and strict_structure=False, the new run is tagged structural_drift_detected and the delta is logged as an artifact.
Future extension: freezable agent artifacts (not MVP)
A future version of Identa may support freezable executable objects — serialized agent snapshots captured using a pickle-compatible library capable of preserving code, closures, and dependencies.

This would enable a stronger reproduction mode:

run.freeze_agent()

run.reproduce(use_frozen_agent=True)

This is not part of the MVP.

Serialized executable artifacts introduce major complexity around environment capture, dependency compatibility, security, portability, and long-term replay guarantees. MVP reproduction is intentionally configuration-based, not executable-image-based.

Design rule: MVP reproduction is configuration replay with structural validation. Frozen executable reproduction is a future extension.


9. Testing Engine
TOML
[suite]

version = "v1.2"

[[tests]]

input = "What is the capital of France?"

expected = "Paris"

type = "qa"
Programmatic
suite = identa.TestSuite(

    version="v1.2",

    tests=[identa.Test(input="...", expected="...", metadata={...})],

)
Synthetic tests (opt-in only)
synthetic = identa.synthesize(agent, n=20, strategy="paraphrase")

Always labeled as synthetic. Never the default.


10. Metrics
10.1 MetricSpec
identa.MetricSpec(

    name="quality",

    metric="semantic_similarity",

    weight=0.7,

    threshold=0.85,

    minimize=False,

)

A plain string "semantic_similarity" is shorthand for MetricSpec(metric="semantic_similarity") with defaults.
10.2 Built-in metrics
exact_match
semantic_similarity
latency
token_cost — returns CostEstimate
success_rate
llm_judge
10.3 Custom metrics
@identa.metric

def my_metric(test, output, trace) -> float:

    ...
10.4 llm_judge guardrails
Optional. Never default.
Rubric-driven. Requires explicit rubric.
API warns when llm_judge is the sole gating metric.
10.5 CostModel and CostEstimate
identa.CostModel(

    provider="openai",

    model="gpt-4",

    input_cost_per_1k=0.03,

    output_cost_per_1k=0.06,

)

token_cost returns:

CostEstimate {

    tokens_input: int,

    tokens_output: int,

    cost_estimate: float | None,

    confidence: "high" | "approximate",

}

Aggregation rules:

Per-test: sum CostEstimate across all spans for that test
Across tests: sum per-test totals (default); mean available via agg=
tokens_input and tokens_output always summed; cost_estimate summed only when confidence is consistent

results.cost_total()             # CostEstimate summed across all tests

results.cost_per_test()          # list[CostEstimate], one per test

Use cost_model="provider_auto" to attempt live pricing fetch with fallback to user-defined. Without a resolved cost model, token_cost reports token counts only and warns.


11. Evaluation Modes
identa.evaluate(..., mode="controlled")    # default for regression gating

identa.evaluate(..., mode="stochastic")    # variance exploration

Controlled: temperature=0 where supported, fixed seed, no retries. Reduces variance; does not eliminate it. Providers do not guarantee identical outputs at temperature=0 across versions. Best-effort signal, not a determinism guarantee.

Stochastic: natural variance, aggregates across N runs, surfaces distribution stats. Required for latency and cost profiling.

Mode is captured in the reproducibility bundle.


12. Trace Model
12.1 Span
Span {

    id: str,

    parent_id: str | None,

    name: str,

    kind: "llm" | "tool" | "agent" | "chain" | "custom",

    inputs: dict,

    outputs: dict,

    metadata: SpanMetadata,

    timing: SpanTiming,

}

SpanMetadata {

    model: str | None,

    provider: str | None,

    prompt_template: str | None,

    rendered_prompt: str | None,

    tool_name: str | None,

    node_id: str | None,

    node_id_stability: "stable" | "ephemeral",

    structure_hash: str | None,

}

SpanTiming {

    start_time: datetime,

    end_time: datetime,

    latency_ms: float,

}
12.2 node_id Stability Strategy
node_id is assigned once during inspect() and stored in the AgentStructure artifact. Traces reference those IDs; they do not recompute them.

Run

 ├── AgentStructure snapshot (persisted; contains node_id assignments)

 └── Traces (SpanMetadata.node_id references that snapshot's IDs)

Priority chain for initial assignment at inspect() time:

Explicit user-defined name
Framework-native ID (LangGraph node name, LangChain chain name if set)
Structural path (e.g. planner>retriever>llm)
Hashed fallback: stable_hash(framework, component_type, structural_path)

If none produces a stable identifier, the node is marked ephemeral:

Excluded from MigrationPlan targets
Excluded from results.by_node() aggregates
Included in traces for diagnostics only
Triggers a warning in plan.validate() if targeted
12.3 TraceConfig
identa.TraceConfig(

    capture_prompts=True,

    capture_outputs="full" | "truncated" | "none",

    max_tokens=2000,

    compress=True,

    sampling_rate=1.0,

)

Sampling semantics: sampling operates at test level, not span level. Either the full trace for a test is captured, or the entire test is skipped for trace and delta purposes. Metrics always run on the full test suite regardless of sampling_rate. ObservedStructureDelta is computed only from traced tests; traced_test_count records this scope.

Default TraceConfig:

TraceConfig(capture_prompts=True, capture_outputs="truncated", max_tokens=2000, compress=True, sampling_rate=1.0)
12.4 TraceArtifact
TraceArtifact {

    id: str,

    structure_hash: str,

    spans: list[Span],

}

Stored as gzip JSON Lines. Loaded lazily via references in EvaluationResult.


13. Inspection — Canonical Structure Model
13.1 AgentStructure
AgentStructure {

    id: str,

    version_hash: str,

    nodes: list[AgentNode],

    edges: list[AgentEdge],

}

AgentNode {

    id: str,

    type: "llm" | "tool" | "router" | "custom",

    name: str,

    model: str | None,

    provider: str | None,

    inputs: list[str],

    outputs: list[str],

    id_stability: "stable" | "ephemeral",

}

AgentEdge {

    from_node: str,

    to_node: str,

}

AgentStructure is serialized and stored as an artifact on every run that calls inspect(). It is the source of truth for node_id values.
13.2 ObservedStructureDelta — Semantics (v7)
ObservedStructureDelta is diagnostic and sample-aware. It compares the persisted AgentStructure snapshot against the nodes actually observed in traced executions over the evaluated sample.

It does not claim to know which node was logically required for each individual test unless the framework explicitly provides that information.

ObservedStructureDelta {

    missing_nodes: dict[str, int],

    unexpected_nodes: dict[str, int],

    mismatched_ids: list[str],

    observed_frequency: dict[str, float],

    traced_test_count: int,

    total_test_count: int,

}

Field meanings:

missing_nodes — nodes present in AgentStructure but not observed in traced executions over the evaluated sample
unexpected_nodes — nodes observed in traced executions but not present in AgentStructure
mismatched_ids — nodes whose identifiers appear aligned but whose associated metadata conflicts, suggesting a mapping inconsistency
observed_frequency — fraction of traced tests in which a node appeared
traced_test_count — number of tests whose traces were captured after test-level sampling (the denominator for frequency)
total_test_count — total number of evaluated tests

Interpretation guidance:

A node with missing_nodes["retriever"] > 0 and observed_frequency["retriever"] = 0.05 should be interpreted as:

This node exists in the structure but appeared in only 5% of traced tests.

This may indicate a conditional branch, a rarely-used tool, a sampled trace artifact, or a real structural mismatch. It should not automatically be treated as a failure.

Warning policy:

results.summary() surfaces ObservedStructureDelta as a warning when:

unexpected_nodes is non-empty, or
any structure node has observed_frequency above a configurable significance threshold

delta_warning_threshold = 0.1   # default

Nodes with observed_frequency below this threshold are considered low-significance conditional paths and are not warned on by default.

Design rule: ObservedStructureDelta speaks about observed execution over a traced sample, not per-test logical necessity.
13.3 Migration alignment rule
MigrationPlan may only target nodes that are:

Present in AgentStructure
Observed in at least one trace (observed_frequency > 0)

Override with force=True:

plan.replace_model(node="planner", to="claude-sonnet-4-5", force=True)

force=True adds a warning to ValidationReport and tags the run as partial_migration.


14. Migration
14.1 Full workflow
with identa.start_run(name="migrate_to_claude") as run:

    structure = identa.inspect(agent)

    plan = identa.MigrationPlan(structure)

    plan.replace_model(node="planner",    to="claude-sonnet-4-5")

    plan.replace_model(node="researcher", to="claude-haiku-4-5")

    report = plan.validate(agent)

    if not report.ok:

        print(report.warnings)

        print(report.unsupported_nodes)

        print(report.unobserved_nodes)

    run.log_artifact("migration_plan",    plan)

    run.log_artifact("validation_report", report)

    migrated = plan.apply(agent, mode="strict")

    results = identa.evaluate(migrated, suite="tests.toml", resolution="node", structure=structure)

    run.log_results(results)

    cmp = run.compare_to_baseline()

    cmp.assert_no_regressions()

    print(plan.diff())

    print(cmp.summary())
14.2 plan.validate()
ValidationReport {

    ok: bool,

    supported_nodes: list[str],

    unsupported_nodes: list[str],

    unobserved_nodes: list[str],

    structure_hash_match: bool,

    warnings: list[str],

}
14.3 plan.apply() — structure hash gate
plan.apply(agent, mode="strict")          # raises MigrationError on any mismatch

plan.apply(agent, mode="best_effort")     # warns, proceeds, tags run as partial_migration

plan.apply(agent, force_structure=True)   # skips hash check — explicit override
14.4 Migration scope (hard limits)
MVP migration supports only model-binding replacements on nodes whose model configuration is discoverable and patchable through supported shims. Arbitrary graph rewrites are out of scope.


15. Results — Full API
results: EvaluationResult = identa.evaluate(agent, suite="tests.toml", metrics=[...])

# Aggregates

results.aggregates

results.summary()

results.to_df()

# Per-test

results.per_test

results.failures()

# Node-level (only available when resolution != "boundary")

results.by_node(agg="mean")

# Slicing

results.slice(node_id="planner")

results.slice(test_id="test_12")

results.slice(metric="quality")

# Traces

results.traces

results.trace("test_42")

# Cost

results.cost_total()

results.cost_per_test()

# Structure

results.structure_delta
results.by_node() aggregation semantics
Two-pass aggregation:

Pass 1 — per test: aggregate all spans sharing the same node_id:

latency → mean of span latencies
token_cost → sum of CostEstimate across spans
quality metrics → mean

Pass 2 — across tests:

latency → mean (default), p95 via agg="p95"
token_cost → sum (default), mean via agg="mean"
quality metrics → mean

Only spans with node_id_stability = "stable" are included. Ephemeral spans are excluded.

Output:

node_id    | metric     | value   | count | agg

-----------+------------+---------+-------+-----

planner    | quality    | 0.82    | 50    | mean

planner    | latency_ms | 340.0   | 50    | mean

retriever  | latency_ms | 120.0   | 50    | mean

retriever  | token_cost | 0.004   | 50    | sum


16. Optimization (DSPy delegation)
with identa.start_run(name="optimize_planner") as run:

    metric_fn = identa.as_dspy_metric(

        identa.MetricSpec("quality", "answer_quality", weight=1.0, threshold=0.85),

        suite="tests.toml",

    )

    optimizer = dspy.MIPROv2(metric=metric_fn)

    optimized = optimizer.compile(agent, trainset=train)

    run.log_artifact("optimized_agent", optimized)

    run.log_results(identa.evaluate(optimized, suite="tests.toml"))

Scope: prompt optimization only.


17. Artifact Taxonomy
Artifact
Produced by
Format
agent_structure
inspect()
JSON
test_suite_snapshot
evaluate()
TOML/JSON
run_config_snapshot
every run
JSON
reproducibility_bundle
every run
JSON
invocation_traces
tracing subsystem
gzip JSON Lines
evaluation_results
evaluate()
JSON + Parquet
failure_records
results.failures()
JSON
structure_delta
inspection subsystem
JSON
migration_plan
MigrationPlan
JSON
validation_report
plan.validate()
JSON
comparison_report
compare_to_baseline() / diff()
JSON + DF
optimizer_output
DSPy bridge (optional)
pickle + JSON



18. Architecture
Identa uses a hexagonal architecture with a CQRS application layer enforced via package structure. Commands mutate run state and artifacts; queries materialize history, comparisons, and tabular views. Queries never mutate state. Commands never return large dataframes.

       Notebook / Script / CLI

                │

        ┌───────────────┐

        │   identa API  │

        └───────────────┘

            │       │

   ┌────────┘       └────────┐

   ▼                         ▼

Domain core              Framework shims

(runs, metrics,         (LangChain, LangGraph,

 plans, results,         PydanticAI)

 traces)

   │

   ▼

Storage backend

(SQLite + FS local; HTTP server optional)
Package structure (CQRS enforced)
identa-core/

  domain/

  application/

    commands/       # start_run, log_results, register_baseline, apply_migration, log_artifact

    queries/        # get_runs, compare, results.to_df(), results.failures(), results.by_node()

  ports/

  persistence/


19. Packaging
pip install identa[core]

pip install identa[sdk]

pip install identa[server]

pip install identa[enterprise]

packages/

  identa-core/

    domain/

    application/

      commands/

      queries/

    ports/

    persistence/

  identa-sdk/

    api/

    adapters/

      langchain/

      langgraph/

      pydantic_ai/

    autolog/

    cli/

  identa-server/

    api/

    auth/

    persistence/

    app/

  identa-enterprise/

    authn/

    future_authz/

    tenancy/


20. Storage
Local default. SQLite for runs/metrics/baselines, filesystem for artifacts (gzip JSONL).
Server mode. Postgres + S3-compatible artifact store.
Backend via workspace URI — file://, http://.


21. Configuration
~/.config/identa/identa.toml

[default]

profile = "local"

[profile.local]

mode = "local"

  [profile.local.backend]

  type = "sqlite"

  path = "~/.identa/workspaces"

[profile.team]

mode = "remote"

  [profile.team.backend]

  type = "http"

  url = "http://identa.internal:8000"

  timeout_seconds = 30

  [profile.team.auth]

  type = "basic"

  credentials_file = "~/.config/identa/credentials.toml"

  credentials_key = "team"

[profile.prod_readonly]

mode = "remote"

  [profile.prod_readonly.backend]

  type = "http"

  url = "https://identa.company.com"

  [profile.prod_readonly.auth]

  type = "bearer"

  token_env = "IDENTA_PROD_TOKEN"
Resolution order
Profile: profile= arg → IDENTA_PROFILE env → [default].profile
Load backend + auth config
Instantiate backend driver
Resolve credentials: env vars first, then credentials file
Bind workspace
Inline construction
identa.set_workspace(backend=identa.backends.SQLite(path="~/.identa/workspaces"))

client = identa.Client(

    backend=identa.backends.HTTP(url="https://identa.company.com"),

    auth=identa.auth.Bearer(token=os.environ["IDENTA_PROD_TOKEN"]),

)


22. CLI
identa runs list --workspace agente_viajes

identa runs show <run_id>

identa runs compare <run_a> <run_b>

identa runs diff <run_a> <run_b>

identa runs reproduce <run_id> [--strict-structure]

identa baseline set <run_id> --name v1_gpt4

identa server start --port 8000


23. Data Model
Workspace { id, name, backend_uri }

Run {

    id, workspace_id, name,

    parent_run_id,

    params, tags, status,

    started_at, ended_at,

    evaluation_mode,

    reproducibility_bundle_id,

    artifact_ids[],

}

EvaluationResult {

    id, run_id,

    suite_hash, suite_version,

    structure_hash,

    resolution: "boundary" | "node" | "tool" | "llm",

    metric_specs: list[MetricSpec],

    aggregates: list[MetricAggregate],

    per_test: list[PerTestResult],

    trace_refs: list[TraceArtifactRef],

    structure_delta: ObservedStructureDelta | None,   # None when resolution="boundary"

}

MetricSpec    { name, metric, weight, threshold?, minimize }

MetricAggregate { metric_name, value, count, distribution_stats }

PerTestResult { test_id, output, scores: dict, trace_ref }

FailureRecord {

    test_id, input, expected_output, actual_output,

    scores: dict,

    trace_ref: TraceArtifactRef,

}

TraceArtifact {

    id,

    structure_hash,

    spans: list[Span],

}

Span {

    id, parent_id?,

    name,

    kind: "llm" | "tool" | "agent" | "chain" | "custom",

    inputs: dict,

    outputs: dict,

    metadata: SpanMetadata,

    timing: SpanTiming,

}

SpanMetadata {

    model?, provider?,

    prompt_template?, rendered_prompt?,

    tool_name?,

    node_id?,

    node_id_stability: "stable" | "ephemeral",

    structure_hash?,

}

SpanTiming { start_time, end_time, latency_ms }

AgentStructure {

    id: str,

    version_hash: str,

    nodes: list[AgentNode],

    edges: list[AgentEdge],

}

AgentNode {

    id: str,

    type: "llm" | "tool" | "router" | "custom",

    name: str,

    model?, provider?,

    inputs[], outputs[],

    id_stability: "stable" | "ephemeral",

}

AgentEdge { from_node, to_node }

ObservedStructureDelta {

    missing_nodes: dict[str, int],

    unexpected_nodes: dict[str, int],

    mismatched_ids: list[str],

    observed_frequency: dict[str, float],

    traced_test_count: int,

    total_test_count: int,

}

Baseline { name, run_id, registered_at }

MigrationPlan {

    id,

    source_structure_hash,

    changes: list[{ node_id, field, from, to, forced }],

}

ValidationReport {

    ok,

    supported_nodes[], unsupported_nodes[],

    unobserved_nodes[],

    structure_hash_match: bool,

    warnings[],

}

CostModel { provider, model, input_cost_per_1k, output_cost_per_1k }

CostEstimate {

    tokens_input, tokens_output,

    cost_estimate: float | None,

    confidence: "high" | "approximate",

}

TraceConfig {

    capture_prompts,

    capture_outputs: "full" | "truncated" | "none",

    max_tokens,

    compress,

    sampling_rate,

}

ReproducibilityBundle {

    python_version, identa_version,

    framework_versions: dict,

    provider_models: dict,

    structure_hash,

    resolution: "boundary" | "node" | "tool" | "llm",

    hashes: { config, suite, metrics, plan? },

    seed?,

    evaluation_mode,

}


24. Execution Flows
Evaluation
start_run

 → reproducibility bundle captured (includes structure_hash, resolution)

 → autolog hooks active (if enabled)

 → load suite (with version)

 → resolution check:

     if resolution = "boundary":

         no inspect required

         structure_hash = None

     if resolution in {node, tool, llm}:

         if structure provided: use it

         else: inspect(agent) → persist AgentStructure → use snapshot

         structure_hash = AgentStructure.version_hash

 → for each test (sampled per TraceConfig.sampling_rate):

     → invoke agent (controlled/stochastic settings)

     → capture typed spans (node_id from AgentStructure snapshot if structure-aware)

     → apply TraceConfig (truncation, compression)

     → score metrics via MetricSpec

 → metrics computed on full suite regardless of sampling

 → if structure-aware: compute ObservedStructureDelta from traced tests

 → aggregate into EvaluationResult (carries resolution + structure_hash)

 → log_results, log_artifacts

 → close run
Reproduction
run.reproduce(strict_structure=...)

 → load reproducibility bundle

 → reconstruct evaluate() parameters

 → if resolution was structure-aware:

     re-inspect current agent → new AgentStructure snapshot

     compare new version_hash against stored structure_hash

     if mismatch AND strict_structure=True: raise StructureDriftError

     if mismatch AND strict_structure=False: warn, tag run structural_drift_detected

 → invoke evaluate() with reconstructed parameters

 → log new run linked to original
Migration
start_run

 → inspect(agent) → AgentStructure (persisted; version_hash assigned)

 → run evaluation with resolution="node", structure=AgentStructure

 → build MigrationPlan (source_structure_hash = AgentStructure.version_hash)

 → plan.validate(agent):

     check structure_hash match, supported nodes, observed_frequency > 0

 → plan.apply(agent, mode=):

     re-verify structure_hash, patch model bindings

 → evaluate migrated agent with resolution="node"

 → compare_to_baseline → assert_no_regressions

 → log plan + validation report + results + structure_delta
Optimization
start_run

 → expose MetricSpec as DSPy callable

 → DSPy compiles optimized agent (each trial = nested run)

 → evaluate optimized agent

 → log artifact + results


25. Key Engineering Challenges
node_id persistence. Shims assign IDs at inspect() time; spans reference those IDs exactly. Per-framework integration tests must verify AgentStructure.nodes[*].id == SpanMetadata.node_id for every supported framework.
Resolution routing in evaluate(). The implicit inspect-then-evaluate path must be idempotent if the user supplies structure= explicitly. The resolution parameter must flow through to EvaluationResult and ReproducibilityBundle.
structure_hash propagation. Carries across EvaluationResult, TraceArtifact, MigrationPlan, ReproducibilityBundle. Every write path must set it; every cross-artifact query must verify it.
Structural drift detection in reproduce(). Re-inspection on reproduce must handle cases where inspect() now returns an ephemeral-heavy or empty structure gracefully.
ObservedStructureDelta accuracy under sampling. Frequency denominators must use traced_test_count, not total_test_count. Edge case: zero traced tests.
by_node() two-pass aggregation. Per-metric aggregation rules (mean vs sum) require a per-metric registry. Must exclude ephemeral nodes cleanly.
Canonical AgentStructure for LangChain and PydanticAI. Lossy is acceptable; inconsistent is not.
Controlled mode honesty. Temperature=0 reduces variance, does not eliminate it.
CostEstimate confidence detection. Model aliases and reasoning tokens must be reliably flagged as "approximate".


26. MVP Build Phases
Phase 1 — Foundations (canonical coding order)
Pure type definitions + Pydantic models: Span, AgentStructure (with id + version_hash), MetricSpec, CostEstimate, TraceConfig, ObservedStructureDelta
SQLite schema + gzip JSONL artifact store
LangChain boundary eval + basic tracing (typed spans, resolution="boundary", no node_id yet)
evaluate() → EvaluationResult (with resolution + structure_hash fields; structure_hash=None for boundary)
results.to_df() + results.failures()
Baseline + compare_to_baseline() + assert_no_regressions()
Phase 2 — Real evaluation workflow
LangChain autologging with node_id (stability strategy applied; AgentStructure persisted)
evaluate(resolution="node") — implicit inspect path wired
structure_hash wired into EvaluationResult and TraceArtifact
ObservedStructureDelta computation (with frequency counts + warning threshold)
results.by_node() (two-pass aggregation)
results.slice() + results.trace(test_id=)
results.cost_total() / results.cost_per_test()
run.diff() + run.reproduce(strict_structure=)
Nested runs + custom metrics + evaluation modes
CLI (including reproduce --strict-structure)
Full reproducibility bundle (includes resolution)
Phase 3 — Optimization & LangGraph migration
DSPy bridge
LangGraph autologging (full AgentStructure support, stable node_id)
inspect() → AgentStructure (persisted artifact)
MigrationPlan + plan.validate() + plan.apply() (with hash gate)
Model-binding replacement for LangGraph
Phase 4 — Breadth
PydanticAI shim
Server mode + HTTP basic auth
Shared workspaces


27. What MVP Unlocks
Compare GPT-4 vs Claude vs Mistral with reproducible, structure-anchored runs
Use resolution="boundary" for fast whole-agent eval; escalate to resolution="node" when debugging
Identify the weakest sub-agent via results.by_node() with defined aggregation semantics
Gate CI on metric regressions with cmp.assert_no_regressions()
Detect structural drift when reproducing historical experiments
Plan, validate, and execute model migrations with structure_hash alignment checks
Reproduce any past experiment exactly with run.reproduce()
Know what a missing_nodes warning actually means (frequency, not failure)


28. Honest Reality Check
Hard:

node_id assignment + consistent span emission — per-framework integration tests required
structure_hash propagation across all artifact write paths
Resolution routing in evaluate() — implicit inspect path must be idempotent
Structural drift detection in reproduce() — re-inspection edge cases
ObservedStructureDelta frequency accuracy under sampling
by_node() two-pass aggregation with per-metric rules
Canonical AgentStructure for LangChain and PydanticAI
CostEstimate confidence detection

Straightforward:

Workspace / run / baseline machinery
MetricSpec composition
TraceConfig (thin config wrapper)
assert_no_regressions() (one-liner over threshold logic)
results.slice() / results.trace() (filter over existing data)
run.diff() (same logic as baseline comparison)
run.reproduce() (load bundle, re-invoke evaluate, check hash)
ValidationReport + structure_hash_match
Delta warning threshold (one config value over existing frequency data)
SQLite + FS persistence
DSPy bridge


29. Final Take
Identa is MLflow-shaped, agent-native, and deliberately scoped.

MLflow-shaped because the audience already thinks in workspaces / runs / artifacts.

Agent-native because multi-resolution tracing, prompt-aware metrics, and graph-aware migration are things MLflow doesn't do.

Deliberately scoped because production observability, weight fine-tuning, and reinventing DSPy are all out of scope.

The v7 addition: evaluation resolution is now a first-class API contract. Boundary evaluation is lightweight and structure-free. Structure-aware evaluation is always structure-first — inspect before evaluate, whether explicit or implicit. run.reproduce() is honestly specified as config replay with structural drift detection, not executable freezing. ObservedStructureDelta is clarified as sample-aware diagnostic output, not per-test logical necessity. The spec is now complete to a level where the Pydantic models and SQL schema can be written directly from §23.
Next concrete artifacts
Pydantic models + SQL schema from §23
SQLite schema + gzip JSONL artifact store
LangChain boundary autologger (resolution="boundary")
evaluate() → EvaluationResult → to_df() + failures()
Baseline + comparison + assert_no_regressions()
LangChain node_id mapping + evaluate(resolution="node") implicit inspect path
One worked notebook: baseline → candidate → assert_no_regressions() → migration with validate() + diff()
Capability matrix doc published from day one

