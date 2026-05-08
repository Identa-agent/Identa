import numpy as np
from typing import List, Optional, Tuple, Dict
from scipy.spatial.distance import pdist, squareform
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
import warnings

class SemanticDriftAnalyzer:
    def __init__(self, embedding_provider=None, gamma: Optional[float] = None):
        self.embedding_provider = embedding_provider
        self.gamma = gamma  # RBF kernel bandwidth. If None, use median heuristic.

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        if self.embedding_provider is None:
            raise ValueError("EmbeddingProvider required for semantic drift")
        return np.array([self.embedding_provider.get_embedding(t) for t in texts])

    def _median_heuristic(self, X: np.ndarray) -> float:
        """Median heuristic for RBF bandwidth."""
        dists = pdist(X, metric='euclidean')
        return 1.0 / (2 * np.median(dists) ** 2) if len(dists) > 0 else 1.0

    def mmd_permutation_test(self, baseline_texts: List[str], current_texts: List[str],
                             n_permutations: int = 1000) -> Tuple[float, float, float]:
        """
        Maximum Mean Discrepancy with RBF kernel and permutation test.
        
        Returns:
            mmd: The MMD statistic
            p_value: Statistical significance (lower = more drift)
            effect_size: Standardized effect size (Cohen's d analog)
        """
        X = self._get_embeddings(baseline_texts)
        Y = self._get_embeddings(current_texts)
        
        if len(X) < 2 or len(Y) < 2:
            return 0.0, 1.0, 0.0
        
        gamma = self.gamma or self._median_heuristic(np.vstack([X, Y]))
        n, m = len(X), len(Y)
        
        # Kernel matrices
        XY = np.vstack([X, Y])
        sq_dists = squareform(pdist(XY, metric='sqeuclidean'))
        K = np.exp(-gamma * sq_dists)
        
        Kxx = K[:n, :n]
        Kyy = K[n:, n:]
        Kxy = K[:n, n:]
        
        # Unbiased MMD^2 estimator
        mmd_sq = (Kxx.sum() - np.diag(Kxx).sum()) / (n * (n - 1))
        mmd_sq += (Kyy.sum() - np.diag(Kyy).sum()) / (m * (m - 1))
        mmd_sq -= 2 * Kxy.mean()
        mmd = np.sqrt(max(mmd_sq, 0))
        
        # Permutation test
        observed = mmd
        permutations = []
        nm = n + m
        
        for _ in range(n_permutations):
            idx = np.random.permutation(nm)
            K_perm = K[idx][:, idx]
            Kxx_p = K_perm[:n, :n]
            Kyy_p = K_perm[n:, n:]
            Kxy_p = K_perm[:n, n:]
            
            mmd_p_sq = ((Kxx_p.sum() - np.diag(Kxx_p).sum()) / (n * (n - 1)) +
                        (Kyy_p.sum() - np.diag(Kyy_p).sum()) / (m * (m - 1)) -
                        2 * Kxy_p.mean())
            permutations.append(np.sqrt(max(mmd_p_sq, 0)))
        
        permutations = np.array(permutations)
        p_value = (np.sum(permutations >= observed) + 1) / (n_permutations + 1)
        
        # Effect size: MMD / pooled standard deviation of permutations
        pooled_std = permutations.std() if permutations.std() > 0 else 1e-9
        effect_size = observed / pooled_std
        
        return mmd, p_value, effect_size

    def classifier_drift_score(self, baseline_texts: List[str], current_texts: List[str],
                               cv_folds: int = 5) -> Tuple[float, float]:
        """
        Black-box shift detection: train a classifier to distinguish baseline from current.
        If AUC > 0.5 significantly, distributions have shifted.
        
        Returns:
            drift_score: [0, 1] where 0 = no drift, 1 = perfect separation
            auc_std: Standard deviation across CV folds
        """
        X_base = self._get_embeddings(baseline_texts)
        X_curr = self._get_embeddings(current_texts)
        
        X = np.vstack([X_base, X_curr])
        y = np.array([0] * len(X_base) + [1] * len(X_curr))
        
        # Logistic regression with strong regularization (we want to detect drift, not overfit)
        clf = LogisticRegression(max_iter=1000, C=0.1, random_state=42)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scores = cross_val_score(clf, X, y, cv=cv_folds, scoring='roc_auc')
        
        auc = scores.mean()
        auc_std = scores.std()
        
        # Normalize: 0.5 = random (no drift), 1.0 = perfect separation
        drift_score = max(0.0, (auc - 0.5) * 2.0)
        return drift_score, auc_std

    def analyze(self, baseline_texts: List[str], current_texts: List[str]) -> Dict[str, any]:
        mmd, p_value, effect_size = self.mmd_permutation_test(baseline_texts, current_texts)
        clf_drift, clf_std = self.classifier_drift_score(baseline_texts, current_texts)
        
        # Ensemble: MMD provides statistical rigor, classifier provides discriminative power
        # Weight MMD higher when sample sizes are small, classifier when large
        n_total = len(baseline_texts) + len(current_texts)
        weight_mmd = max(0.3, 1.0 - n_total / 500)  # Decreases as sample size grows
        weight_clf = 1.0 - weight_mmd
        
        # Normalize MMD to [0,1] using effect size mapping
        mmd_normalized = min(effect_size / 3.0, 1.0)  # effect_size > 3 is large drift
        
        composite = weight_mmd * mmd_normalized + weight_clf * clf_drift
        
        return {
            "mmd": mmd,
            "mmd_p_value": p_value,
            "mmd_effect_size": effect_size,
            "classifier_drift": clf_drift,
            "classifier_std": clf_std,
            "semantic_drift_score": composite,
            "is_drift": p_value < 0.05 and composite > 0.1,
            "severity": self._score_to_severity(composite),
        }
    
    @staticmethod
    def _score_to_severity(score: float) -> str:
        if score < 0.05: return "none"
        if score < 0.15: return "low"
        if score < 0.30: return "medium"
        if score < 0.50: return "high"
        return "critical"
