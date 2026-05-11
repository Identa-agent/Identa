import pytest
from identa.core.domain.drift_causal import CausalAttributionAnalyzer

def test_shapley_attribution_simple():
    analyzer = CausalAttributionAnalyzer(n_permutations=20)
    
    # Define a simple metric function: sum of node scores
    def metric_fn(outputs):
        return sum(sum(v) for v in outputs.values())
    
    baseline_outputs = {
        "node_1": [0.1, 0.1],
        "node_2": [0.1, 0.1]
    }
    
    # Only node_2 drifts significantly
    current_outputs = {
        "node_1": [0.1, 0.1],
        "node_2": [0.9, 0.9]
    }
    
    node_ids = ["node_1", "node_2"]
    
    results = analyzer.analyze(
        baseline_outputs=baseline_outputs,
        current_outputs=current_outputs,
        node_ids=node_ids,
        metric_fn=metric_fn
    )
    
    # node_2 should have much higher shapley value
    assert results["top_contributor"] == "node_2"
    assert results["shapley_values"]["node_2"] > results["shapley_values"]["node_1"]
    
    # The sum of shapley values should equal the total drift (1.8 - 0.2 = 1.6)
    total_shapley = sum(results["shapley_values"].values())
    assert pytest.approx(total_shapley) == 1.6

def test_shapley_no_drift():
    analyzer = CausalAttributionAnalyzer(n_permutations=10)
    
    def metric_fn(outputs):
        return sum(sum(v) for v in outputs.values())
        
    outputs = {"node_1": [0.1]}
    
    results = analyzer.analyze(
        baseline_outputs=outputs,
        current_outputs=outputs,
        node_ids=["node_1"],
        metric_fn=metric_fn
    )
    
    assert results["shapley_values"]["node_1"] == 0.0
