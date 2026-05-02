from typing import Any, Dict, List, Callable
from identa.core.domain.results import EvaluationResult

class CalibrationEngine:
    def __init__(self, evaluator: Callable):
        self.evaluator = evaluator

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
