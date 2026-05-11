from identa.core.utils.lazy import lazy_import
np = lazy_import("numpy")
from typing import List, Optional
from collections import deque

class ADWIN:
    """
    Adaptive Windowing algorithm for online drift detection.
    Reference: Bifet & Gavalda, 2007
    """
    def __init__(self, delta: float = 0.002):
        self.delta = delta
        self.window = []
        self.width = 0
        
    def _cut_expression(self, n0: int, n1: int, abs_diff: float) -> bool:
        m = 1 / (1 / n0 + 1 / n1)
        delta_prime = self.delta / (self.width if self.width > 0 else 1)
        epsilon = np.sqrt(2 / m * np.log(2 / delta_prime))
        return abs_diff > epsilon
    
    def add_element(self, value: float) -> bool:
        self.window.append(value)
        self.width = len(self.window)
        
        # Check for optimal cut point
        for i in range(1, self.width):
            w0 = self.window[:i]
            w1 = self.window[i:]
            if len(w0) < 10 or len(w1) < 10:
                continue
            
            mean0, mean1 = np.mean(w0), np.mean(w1)
            if self._cut_expression(len(w0), len(w1), abs(mean0 - mean1)):
                # Drift detected at i - drop older elements
                self.window = self.window[i:]
                self.width = len(self.window)
                return True
        
        return False
    
    def get_info(self) -> dict:
        if not self.window:
            return {"mean": 0, "variance": 0, "width": 0}
        return {
            "mean": float(np.mean(self.window)),
            "variance": float(np.var(self.window)),
            "width": self.width
        }

class TemporalDriftAnalyzer:
    def __init__(self, delta: float = 0.002):
        self.adwin = ADWIN(delta=delta)
        self.history = deque(maxlen=10000)
    
    def update(self, drift_score: float) -> dict:
        drift_detected = self.adwin.add_element(drift_score)
        self.history.append(drift_score)
        
        info = self.adwin.get_info()
        info["drift_detected"] = drift_detected
        info["cumulative_mean"] = float(np.mean(self.history)) if self.history else 0
        info["trend"] = self._compute_trend()
        
        return info
    
    def _compute_trend(self, window: int = 100) -> float:
        if len(self.history) < window * 2:
            return 0.0
        recent = list(self.history)[-window:]
        older = list(self.history)[-(window*2):-window]
        return float(np.mean(recent) - np.mean(older))

    def get_state(self) -> dict:
        return {
            "window": self.adwin.window,
            "history": list(self.history)
        }
        
    def set_state(self, state: dict) -> None:
        if "window" in state:
            self.adwin.window = state["window"]
            self.adwin.width = len(self.adwin.window)
        if "history" in state:
            self.history = deque(state["history"], maxlen=10000)
