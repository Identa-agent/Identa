import numpy as np
from typing import List, Dict, Callable, Any
from collections import defaultdict

class CausalAttributionAnalyzer:
    def __init__(self, n_permutations: int = 50):
        self.n_permutations = n_permutations

    def node_shapley_attribution(self, 
                                  baseline_outputs: Dict[str, List[Any]],
                                  current_outputs: Dict[str, List[Any]],
                                  node_ids: List[str],
                                  metric_fn: Callable[[Dict[str, List[Any]]], float]) -> Dict[str, float]:
        """
        Approximate Shapley values for drift attribution.
        
        baseline_outputs: {node_id: [outputs]}
        current_outputs: {node_id: [outputs]}
        metric_fn: takes a dict of node outputs and returns a drift score
        
        Returns Shapley value per node (higher = more responsible for drift).
        """
        # Build coalition outputs by mixing baseline and current per node
        def build_coalition(active_nodes: set) -> Dict[str, List[Any]]:
            result = {}
            for nid in node_ids:
                if nid in active_nodes:
                    result[nid] = current_outputs.get(nid, [])
                else:
                    result[nid] = baseline_outputs.get(nid, [])
            return result
        
        # Full baseline and full current scores
        score_baseline = metric_fn(build_coalition(set()))
        score_full = metric_fn(build_coalition(set(node_ids)))
        total_drift = score_full - score_baseline
        
        if abs(total_drift) < 1e-9:
            return {nid: 0.0 for nid in node_ids}
        
        marginal_contributions = defaultdict(list)
        
        for _ in range(self.n_permutations):
            perm = np.random.permutation(len(node_ids))
            nodes_perm = [node_ids[i] for i in perm]
            
            prev_score = score_baseline
            prev_set = set()
            
            for node in nodes_perm:
                curr_set = prev_set | {node}
                curr_score = metric_fn(build_coalition(curr_set))
                marginal = curr_score - prev_score
                marginal_contributions[node].append(marginal)
                prev_score = curr_score
                prev_set = curr_set
        
        shapley_values = {}
        for nid in node_ids:
            shapley_values[nid] = np.mean(marginal_contributions[nid])
        
        # Normalize to sum to total drift
        total_shapley = sum(shapley_values.values())
        if abs(total_shapley) > 1e-9:
            shapley_values = {k: v * (total_drift / total_shapley) for k, v in shapley_values.items()}
        
        return shapley_values

    def interventional_replay(self,
                              baseline_trace: Any,
                              current_agent: Any,
                              suite: List[Dict],
                              node_to_intervene: str,
                              evaluator: Callable) -> float:
        """
        Counterfactual: what if we replaced this node's output with the baseline?
        Not fully implementable without framework-specific injection, but the interface
        is what matters for enterprise.
        """
        if not hasattr(current_agent, "intervene_node"):
            raise NotImplementedError(
                f"The provided agent adapter ({type(current_agent).__name__}) does not support interventional replay. "
                "Implement `intervene_node` context manager in the adapter."
            )
        
        # Apply intervention
        with current_agent.intervene_node(node_to_intervene, baseline_trace):
            # Evaluate counterfactual
            return evaluator(current_agent, suite)
    def analyze(self,
                baseline_outputs: Dict[str, List[Any]],
                current_outputs: Dict[str, List[Any]],
                node_ids: List[str],
                metric_fn: Callable) -> Dict[str, any]:
        shapley = self.node_shapley_attribution(baseline_outputs, current_outputs, node_ids, metric_fn)
        
        # Rank nodes by absolute Shapley value
        ranked = sorted(shapley.items(), key=lambda x: abs(x[1]), reverse=True)
        
        return {
            "shapley_values": shapley,
            "root_cause_ranking": [nid for nid, _ in ranked],
            "top_contributor": ranked[0][0] if ranked else None,
            "attribution_entropy": -sum(abs(v) * np.log(abs(v) + 1e-10) for v in shapley.values()),
        }
