from typing import Any, Dict, List, Callable, Tuple
from identa.core.domain.results import EvaluationResult

class CalibrationEngine:
    def __init__(self, evaluator: Callable = None):
        self.evaluator = evaluator

    @staticmethod
    def optimize_threshold(y_true: List[int], y_scores: List[float]) -> float:
        """Finds the threshold that maximizes F1-Score."""
        thresholds = sorted(list(set(y_scores)))
        best_threshold = 0.0
        best_f1 = -1.0
        
        for t in thresholds:
            tp = 0
            fp = 0
            fn = 0
            for i, score in enumerate(y_scores):
                pred = 1 if score >= t else 0
                actual = y_true[i]
                if pred == 1 and actual == 1:
                    tp += 1
                elif pred == 1 and actual == 0:
                    fp += 1
                elif pred == 0 and actual == 1:
                    fn += 1
            
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
        """Runs a grid search over hyperparameters to find the best agent configuration."""
        import itertools
        
        # Generate parameter combinations
        keys = param_grid.keys()
        combinations = list(itertools.product(*param_grid.values()))
        
        best_params = None
        best_score = -1.0
        
        print(f"🎯 Starting calibration loop across {len(combinations)} configurations...")
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            print(f"  🧪 Testing params: {params}")
            
            # Create agent with current params
            agent = agent_factory(**params)
            
            # Evaluate
            result = self.evaluator(agent, suite)
            
            # Extract metric
            score = 0.0
            for agg in result.aggregates:
                if agg.metric_name == metric_name:
                    score = agg.value
                    break
            
            print(f"    ✨ Score: {score:.4f}")
            
            if score > best_score:
                best_score = score
                best_params = params
                
        print(f"✅ Calibration complete. Best params: {best_params} (Score: {best_score:.4f})")
        return best_params
