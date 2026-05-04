from typing import Any, Dict, List, Callable, Tuple
from identa.core.domain.results import EvaluationResult

class CalibrationEngine:
    def __init__(self, evaluator: Callable = None):
        self.evaluator = evaluator
        self.online_threshold = 0.7  # Default initial threshold
        self.learning_rate = 0.05

    def update_boundary_online(self, drift_score: float, is_success: bool) -> float:
        """Simple online update: move threshold closer to score if agent failed, or away if success."""
        if is_success:
            # If successful, perhaps increase threshold slightly to be more tolerant
            self.online_threshold += self.learning_rate * (1.0 - self.online_threshold)
        else:
            # If failed, decrease threshold to be more sensitive
            self.online_threshold -= self.learning_rate * self.online_threshold
        
        return self.online_threshold

    @staticmethod
    def optimize_threshold(y_true: List[int], y_scores: List[float]) -> float:
        # ... (Method remains same) ...
        thresholds = sorted(list(set(y_scores)))
        best_threshold = 0.0
        best_f1 = -1.0
        
        for t in thresholds:
            tp, fp, fn = 0, 0, 0
            for i, score in enumerate(y_scores):
                pred = 1 if score >= t else 0
                actual = y_true[i]
                if pred == 1 and actual == 1: tp += 1
                elif pred == 1 and actual == 0: fp += 1
                elif pred == 0 and actual == 1: fn += 1
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = t
                
        return best_threshold

    def calibrate(
        self,
        agent_factory: Callable[..., Any],
        suite: List[Dict[str, Any]],
        param_grid: Dict[str, List[Any]],
        metric_name: str = "exact_match"
    ) -> Dict[str, Any]:
        # ... (Method remains same) ...
        import itertools
        keys = param_grid.keys()
        combinations = list(itertools.product(*param_grid.values()))
        best_params, best_score = None, -1.0
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            agent = agent_factory(**params)
            result = self.evaluator(agent, suite)
            score = 0.0
            for agg in result.aggregates:
                if agg.metric_name == metric_name:
                    score = agg.value
                    break
            if score > best_score:
                best_score = score
                best_params = params
        return best_params
