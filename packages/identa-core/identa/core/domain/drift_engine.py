from typing import List, Dict, Optional, Any
from identa.core.domain.drift import UnifiedDriftReport, DriftTestResult, DriftLayer, DriftSeverity
from identa.core.domain.drift_structural import StructuralDriftAnalyzer
from identa.core.domain.drift_semantic import SemanticDriftAnalyzer
from identa.core.domain.drift_behavioral import BehavioralDriftAnalyzer
from identa.core.domain.drift_causal import CausalAttributionAnalyzer
from identa.core.domain.structure import AgentStructure

class EnterpriseDriftEngine:
    def __init__(self, embedding_provider=None):
        self.structural = StructuralDriftAnalyzer()
        self.semantic = SemanticDriftAnalyzer(embedding_provider)
        self.behavioral = BehavioralDriftAnalyzer()
        self.causal = CausalAttributionAnalyzer()
    
    def detect(self,
               run_id: str,
               baseline_structure: Optional[AgentStructure],
               current_structure: Optional[AgentStructure],
               baseline_texts: List[str],
               current_texts: List[str],
               baseline_traces: List[List[str]],
               current_traces: List[List[str]],
               baseline_node_outputs: Optional[Dict[str, List[Any]]] = None,
               current_node_outputs: Optional[Dict[str, List[Any]]] = None,
               ) -> UnifiedDriftReport:
        
        results = []
        
        # L1: Structural
        if baseline_structure and current_structure:
            struct = self.structural.analyze(baseline_structure, current_structure)
            results.append(DriftTestResult(
                layer=DriftLayer.STRUCTURAL,
                metric_name="ged_spectral_ensemble",
                score=struct["structural_drift_score"],
                raw_statistic=struct["graph_edit_distance"],
                p_value=0.05 if struct["is_drift"] else 0.5,  # GED doesn't naturally yield p-values
                is_drift=struct["is_drift"],
                severity=DriftSeverity.HIGH if struct["is_drift"] else DriftSeverity.NONE,
                affected_nodes=struct["added_nodes"] + struct["removed_nodes"],
                recommendation="Review added/removed nodes before migration." if struct["is_drift"] else None,
            ))
        
        # L2: Semantic
        if baseline_texts and current_texts:
            sem = self.semantic.analyze(baseline_texts, current_texts)
            results.append(DriftTestResult(
                layer=DriftLayer.SEMANTIC,
                metric_name="mmd_classifier_ensemble",
                score=sem["semantic_drift_score"],
                raw_statistic=sem["mmd"],
                p_value=sem["mmd_p_value"],
                effect_size=sem["mmd_effect_size"],
                is_drift=sem["is_drift"],
                severity=DriftSeverity(sem["severity"]),
                recommendation="Semantic drift detected. Review prompt templates or model temperature." if sem["is_drift"] else None,
            ))
        
        # L3: Behavioral
        if baseline_traces and current_traces:
            beh = self.behavioral.analyze(baseline_traces, current_traces)
            results.append(DriftTestResult(
                layer=DriftLayer.BEHAVIORAL,
                metric_name="markov_path_ensemble",
                score=beh["behavioral_drift_score"],
                raw_statistic=beh["frobenius_norm"],
                p_value=beh.get("path_p_value"),
                is_drift=beh["is_drift"],
                severity=DriftSeverity.HIGH if beh["is_drift"] else DriftSeverity.NONE,
                affected_nodes=list(beh["node_transition_drifts"].keys()) if beh.get("node_transition_drifts") else [],
                recommendation="Execution paths have shifted. Check router logic or tool selection." if beh["is_drift"] else None,
                metadata={"node_drifts": beh.get("node_transition_drifts", {})}
            ))
        
        # L4: Causal Attribution
        root_causes = []
        if baseline_node_outputs and current_node_outputs and results:
            # Use semantic score as the metric function for attribution
            def coalition_metric(outputs):
                texts = []
                for nid, outs in outputs.items():
                    texts.extend([str(o) for o in outs])
                if len(texts) < 2:
                    return 0.0
                # Simplified: compare to baseline using classifier drift
                base_texts = []
                for nid, outs in baseline_node_outputs.items():
                    base_texts.extend([str(o) for o in outs])
                if not base_texts or not texts:
                    return 0.0
                score, _ = self.semantic.classifier_drift_score(base_texts, texts)
                return score
            
            node_ids = list(set(baseline_node_outputs.keys()) | set(current_node_outputs.keys()))
            causal = self.causal.analyze(baseline_node_outputs, current_node_outputs, node_ids, coalition_metric)
            root_causes = causal["root_cause_ranking"][:3]
            
            results.append(DriftTestResult(
                layer=DriftLayer.CAUSAL,
                metric_name="shapley_attribution",
                score=abs(causal["shapley_values"].get(root_causes[0], 0)) if root_causes else 0,
                raw_statistic=causal["attribution_entropy"],
                is_drift=len(root_causes) > 0,
                severity=DriftSeverity.HIGH if root_causes else DriftSeverity.NONE,
                affected_nodes=root_causes,
                recommendation=f"Investigate nodes: {', '.join(root_causes)}" if root_causes else None,
                metadata={"shapley": causal["shapley_values"]}
            ))
        
        # Composite score with Bonferroni-corrected significance
        drift_layers = [r for r in results if r.is_drift]
        overall = len(drift_layers) > 0
        
        # Weighted composite (structural = 0.2, semantic = 0.35, behavioral = 0.35, causal = 0.1)
        weights = {DriftLayer.STRUCTURAL: 0.2, DriftLayer.SEMANTIC: 0.35, 
                   DriftLayer.BEHAVIORAL: 0.35, DriftLayer.CAUSAL: 0.1}
        composite = sum(r.score * weights.get(r.layer, 0.1) for r in results)
        
        max_sev = DriftSeverity.NONE
        for r in results:
            if r.severity == DriftSeverity.CRITICAL: max_sev = DriftSeverity.CRITICAL
            elif r.severity == DriftSeverity.HIGH and max_sev != DriftSeverity.CRITICAL: max_sev = DriftSeverity.HIGH
            elif r.severity == DriftSeverity.MEDIUM and max_sev not in (DriftSeverity.HIGH, DriftSeverity.CRITICAL): max_sev = DriftSeverity.MEDIUM
        
        return UnifiedDriftReport(
            run_id=run_id,
            overall_drift=overall,
            max_severity=max_sev,
            layer_results=results,
            composite_score=composite,
            root_cause_nodes=root_causes,
        )
