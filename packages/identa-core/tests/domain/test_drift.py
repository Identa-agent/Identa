import pytest
import numpy as np
from identa.core.domain.drift_semantic import SemanticDriftAnalyzer
from identa.core.domain.drift_structural import StructuralDriftAnalyzer
from identa.core.domain.drift_behavioral import BehavioralDriftAnalyzer
from identa.core.domain.drift_temporal import TemporalDriftAnalyzer
from identa.core.domain.structure import AgentStructure, AgentNode, AgentEdge

class MockEmbeddingProvider:
    def get_embedding(self, text: str) -> np.ndarray:
        # More "semantic" embeddings for testing with small noise
        noise = np.random.normal(0, 0.01, 4)
        if "apple" in text:
            return np.array([1.0, 0.0, 0.0, 0.0]) + noise
        elif "orange" in text:
            return np.array([0.0, 1.0, 0.0, 0.0]) + noise
        elif "text" in text:
            # For null hypothesis test
            return np.array([0.0, 0.0, 1.0, 0.0]) + noise
        return np.array([0.0, 0.0, 0.0, 1.0]) + noise

@pytest.fixture
def semantic_analyzer():
    return SemanticDriftAnalyzer(embedding_provider=MockEmbeddingProvider())

def test_mmd_null_hypothesis(semantic_analyzer):
    """Verify p-value uniformity under null hypothesis (same distribution)."""
    np.random.seed(42)
    # Generate identical distributions
    baseline = [f"text_{i}" for i in range(20)]
    current = [f"text_{i}" for i in range(20)]
    
    # We expect p_value to be large (no drift)
    mmd, p_value, effect_size = semantic_analyzer.mmd_permutation_test(baseline, current, n_permutations=100)
    assert p_value > 0.05

def test_mmd_drift_detection(semantic_analyzer):
    """Verify drift detection when distributions differ."""
    # Use more samples and more distinct data
    baseline = [f"apple_{i}" for i in range(50)]
    current = [f"orange_{i}" for i in range(50)]
    
    mmd, p_value, effect_size = semantic_analyzer.mmd_permutation_test(baseline, current, n_permutations=200)
    assert p_value < 0.05 
    assert effect_size > 1.0

def test_structural_drift():
    analyzer = StructuralDriftAnalyzer()
    
    base_structure = AgentStructure(
        id="s1",
        nodes=[
            AgentNode(id="n1", type="llm", name="N1", id_stability="stable"),
            AgentNode(id="n2", type="tool", name="N2", id_stability="stable")
        ],
        edges=[AgentEdge(from_node="n1", to_node="n2")],
        version_hash="v1"
    )
    
    # No change
    res = analyzer.analyze(base_structure, base_structure)
    assert res["structural_drift_score"] == 0.0
    assert not res["is_drift"]
    
    # Add a node
    curr_structure = AgentStructure(
        id="s1",
        nodes=[
            AgentNode(id="n1", type="llm", name="N1", id_stability="stable"),
            AgentNode(id="n2", type="tool", name="N2", id_stability="stable"),
            AgentNode(id="n3", type="tool", name="N3", id_stability="stable")
        ],
        edges=[
            AgentEdge(from_node="n1", to_node="n2"),
            AgentEdge(from_node="n2", to_node="n3")
        ],
        version_hash="v2"
    )
    res = analyzer.analyze(base_structure, curr_structure)
    assert res["structural_drift_score"] > 0
    assert "n3" in res["added_nodes"]

def test_behavioral_drift():
    analyzer = BehavioralDriftAnalyzer()
    
    # Use multiple paths to satisfy Chi-square requirements (Cochran's rule)
    # We need expected frequencies > 5 in most cells.
    # Total samples = 200. 4 paths.
    baseline_traces = [["n1", "n2", "n3"]] * 40 + [["n1", "n4"]] * 30 + [["n1", "n5"]] * 20 + [["n1"]] * 10
    current_traces = [["n1", "n3"]] * 40 + [["n1", "n4"]] * 30 + [["n1", "n5"]] * 20 + [["n1"]] * 10
    
    res = analyzer.analyze(baseline_traces, current_traces)
    assert res["behavioral_drift_score"] > 0.1
    assert res["is_drift"]
    assert res["path_p_value"] < 0.1

def test_temporal_adwin():
    analyzer = TemporalDriftAnalyzer(delta=0.01)
    
    # Stationary phase
    for _ in range(100):
        analyzer.update(0.1 + np.random.normal(0, 0.01))
    
    # Drift phase
    drift_detected = False
    for _ in range(200):
        info = analyzer.update(0.8 + np.random.normal(0, 0.01))
        if info["drift_detected"]:
            drift_detected = True
            break
            
    assert drift_detected
