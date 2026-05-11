import pytest
from identa.core.domain.drift_engine import EnterpriseDriftEngine
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

def test_drift_engine_structural_drift():
    engine = EnterpriseDriftEngine()
    
    baseline_struct = AgentStructure(
        id="s1",
        nodes=[AgentNode(id="n1", type="llm", name="N1", id_stability="stable")],
        edges=[],
        version_hash="v1"
    )
    
    current_struct = AgentStructure(
        id="s2",
        nodes=[
            AgentNode(id="n1", type="llm", name="N1", id_stability="stable"),
            AgentNode(id="n2", type="tool", name="N2", id_stability="stable")
        ],
        edges=[AgentEdge(from_node="n1", to_node="n2")],
        version_hash="v2"
    )
    
    report = engine.detect(
        run_id="test_run",
        baseline_structure=baseline_struct,
        current_structure=current_struct,
        baseline_texts=[],
        current_texts=[],
        baseline_traces=[],
        current_traces=[]
    )
    
    assert report.overall_drift
    struct_result = next(r for r in report.layer_results if r.layer == "structural")
    assert struct_result.is_drift
    assert "n2" in struct_result.affected_nodes

def test_drift_engine_semantic_no_drift():
    class MockEmbeddingProvider:
        def get_embedding(self, text):
            return [0.1, 0.2, 0.3] # dummy
            
    engine = EnterpriseDriftEngine(embedding_provider=MockEmbeddingProvider())
    
    # Same texts should result in no semantic drift
    report = engine.detect(
        run_id="test_run",
        baseline_structure=None,
        current_structure=None,
        baseline_texts=["hello world"] * 10,
        current_texts=["hello world"] * 10,
        baseline_traces=[],
        current_traces=[]
    )
    
    sem_result = next(r for r in report.layer_results if r.layer == "semantic")
    assert not sem_result.is_drift
    assert sem_result.score < 0.1
