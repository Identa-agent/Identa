import pytest
from datetime import datetime
from identa.core.domain.models import Workspace, Run, MetricSpec
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge
from identa.core.domain.tracing import Span, SpanMetadata, SpanTiming

def test_workspace_creation():
    ws = Workspace(id="ws_1", name="Test Workspace", backend_uri="sqlite:///test.db")
    assert ws.id == "ws_1"
    assert ws.name == "Test Workspace"

def test_run_creation():
    now = datetime.now()
    run = Run(
        id="run_1",
        workspace_id="ws_1",
        name="Test Run",
        status="running",
        started_at=now,
        evaluation_mode="controlled"
    )
    assert run.id == "run_1"
    assert run.started_at == now

def test_agent_structure_serialization():
    node = AgentNode(
        id="node_1",
        type="llm",
        name="GPT-4",
        model="gpt-4",
        provider="openai",
        id_stability="stable"
    )
    edge = AgentEdge(from_node="node_1", to_node="node_2")
    structure = AgentStructure(
        id="struct_1",
        version_hash="hash_1",
        nodes=[node],
        edges=[edge]
    )
    
    data = structure.model_dump()
    assert data["nodes"][0]["id"] == "node_1"
    assert data["edges"][0]["from_node"] == "node_1"

def test_span_creation():
    timing = SpanTiming(
        start_time=datetime.now(),
        end_time=datetime.now(),
        latency_ms=100.5
    )
    metadata = SpanMetadata(node_id="node_1", node_id_stability="stable")
    span = Span(
        id="span_1",
        name="llm_call",
        kind="llm",
        metadata=metadata,
        timing=timing
    )
    assert span.id == "span_1"
    assert span.metadata.node_id == "node_1"
