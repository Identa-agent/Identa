import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
from scipy.spatial.distance import jensenshannon
import scipy.stats as stats

class BehavioralDriftAnalyzer:
    def __init__(self):
        pass

    def extract_paths(self, traces: List[List[str]]) -> Dict[Tuple[str, ...], int]:
        """Extract execution path frequencies from traces (list of node_id sequences)."""
        return Counter(tuple(p) for p in traces)

    def extract_transitions(self, traces: List[List[str]]) -> Dict[str, Dict[str, int]]:
        """Extract Markov transition counts from traces."""
        transitions = defaultdict(lambda: defaultdict(int))
        for trace in traces:
            for i in range(len(trace) - 1):
                transitions[trace[i]][trace[i + 1]] += 1
        return dict(transitions)

    def path_divergence(self, baseline_traces: List[List[str]], 
                        current_traces: List[List[str]]) -> Tuple[float, float]:
        """
        Jensen-Shannon divergence on execution path distributions.
        Returns divergence and chi-square p-value approximation.
        """
        base_paths = self.extract_paths(baseline_traces)
        curr_paths = self.extract_paths(current_traces)
        
        all_paths = sorted(set(base_paths.keys()) | set(curr_paths.keys()))
        total_base = sum(base_paths.values())
        total_curr = sum(curr_paths.values())
        
        if total_base == 0 or total_curr == 0:
            return 0.0, 1.0
        
        p = np.array([base_paths.get(p, 0) / total_base for p in all_paths])
        q = np.array([curr_paths.get(p, 0) / total_curr for p in all_paths])
        
        # Add smoothing
        p = (p + 1e-10) / (p + 1e-10).sum()
        q = (q + 1e-10) / (q + 1e-10).sum()
        
        js_div = jensenshannon(p, q, base=2)
        if np.isnan(js_div):
            js_div = 0.0
        
        # Chi-square test for independence
        contingency = np.array([
            [base_paths.get(p, 0) for p in all_paths],
            [curr_paths.get(p, 0) for p in all_paths]
        ])
        # Only test if enough data
        if contingency.sum() > 100 and (contingency > 5).sum() / contingency.size > 0.7:
            _, p_value, _, _ = stats.chi2_contingency(contingency + 1)  # +1 for stability
        else:
            p_value = 1.0
        
        return js_div, p_value

    def markov_transition_divergence(self, baseline_traces: List[List[str]],
                                     current_traces: List[List[str]]) -> Dict[str, any]:
        """
        Compare Markov transition matrices using spectral norm and Frobenius norm.
        Also computes per-node transition drift.
        """
        base_trans = self.extract_transitions(baseline_traces)
        curr_trans = self.extract_transitions(current_traces)
        
        all_nodes = sorted(set(base_trans.keys()) | set(curr_trans.keys()) |
                          {k for v in base_trans.values() for k in v} |
                          {k for v in curr_trans.values() for k in v})
        n = len(all_nodes)
        node_idx = {node: i for i, node in enumerate(all_nodes)}
        
        P_base = np.zeros((n, n))
        P_curr = np.zeros((n, n))
        
        for src, dsts in base_trans.items():
            total = sum(dsts.values())
            for dst, count in dsts.items():
                P_base[node_idx[src], node_idx[dst]] = count / total
        
        for src, dsts in curr_trans.items():
            total = sum(dsts.values())
            for dst, count in dsts.items():
                P_curr[node_idx[src], node_idx[dst]] = count / total
        
        # Matrix norms
        frob_norm = np.linalg.norm(P_base - P_curr, ord='fro') / np.sqrt(n) if n > 0 else 0.0
        spec_norm = np.linalg.norm(P_base - P_curr, ord=2) if n > 0 else 0.0
        
        # Stationary distribution divergence (long-run behavior)
        try:
            # Power method for stationary distribution
            def stationary(P, max_iter=1000):
                pi = np.ones(n) / n
                for _ in range(max_iter):
                    pi_new = pi @ P
                    if np.linalg.norm(pi_new - pi) < 1e-10:
                        break
                    pi = pi_new
                return pi
            
            if n > 0:
                pi_base = stationary(P_base)
                pi_curr = stationary(P_curr)
                stat_dist = jensenshannon(pi_base + 1e-10, pi_curr + 1e-10, base=2)
                if np.isnan(stat_dist):
                    stat_dist = 0.0
            else:
                stat_dist = 0.0
        except Exception:
            stat_dist = 0.0
        
        # Per-node transition drift
        node_drifts = {}
        for node in all_nodes:
            i = node_idx[node]
            js = jensenshannon(P_base[i] + 1e-10, P_curr[i] + 1e-10, base=2)
            node_drifts[node] = 0.0 if np.isnan(js) else float(js)
        
        # Composite behavioral score
        score = 0.4 * min(frob_norm, 1.0) + 0.3 * min(spec_norm, 1.0) + 0.3 * stat_dist
        
        return {
            "frobenius_norm": frob_norm,
            "spectral_norm": spec_norm,
            "stationary_divergence": stat_dist,
            "node_transition_drifts": node_drifts,
            "behavioral_drift_score": score,
            "is_drift": score > 0.1,
            "severity": "critical" if score > 0.5 else "high" if score > 0.3 else "medium" if score > 0.15 else "low" if score > 0.05 else "none",
        }

    def analyze(self, baseline_traces: List[List[str]], current_traces: List[List[str]]) -> Dict[str, any]:
        path_div, path_p = self.path_divergence(baseline_traces, current_traces)
        markov = self.markov_transition_divergence(baseline_traces, current_traces)
        
        # Ensemble
        composite = 0.5 * path_div + 0.5 * markov["behavioral_drift_score"] if not np.isnan(path_div) else markov["behavioral_drift_score"]
        
        return {
            "path_jensen_shannon": path_div,
            "path_p_value": path_p,
            **markov,
            "behavioral_drift_score": composite,
            "is_drift": markov["is_drift"] or (path_p < 0.05 and path_div > 0.1),
        }
