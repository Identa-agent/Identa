from typing import List, Dict, Optional, Any
from identa.core.domain.drift import UnifiedDriftReport, DriftTestResult, DriftLayer, DriftSeverity
from identa.core.domain.drift_structural import StructuralDriftAnalyzer
from identa.core.domain.drift_semantic import SemanticDriftAnalyzer
from identa.core.domain.drift_behavioral import BehavioralDriftAnalyzer
from identa.core.domain.drift_causal import CausalAttributionAnalyzer
from identa.core.domain.drift_temporal import TemporalDriftAnalyzer
from identa.core.domain.structure import AgentStructure

class EnterpriseDriftEngine:
    def __init__(self, embedding_provider=None, llm_judge=None):
        self.structural = StructuralDriftAnalyzer()
        self.semantic = SemanticDriftAnalyzer(embedding_provider)
        self.behavioral = BehavioralDriftAnalyzer()
        self.causal = CausalAttributionAnalyzer()
        self.temporal = TemporalDriftAnalyzer()
        self.llm_judge = llm_judge

    
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
               drift_mode: str = "hybrid",
               ) -> UnifiedDriftReport:

        
        results = []
        
        # L1: Structural
        if drift_mode in ("standard", "hybrid") and baseline_structure and current_structure:
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
        
        # L2: Semantic & LLM Judge
        if drift_mode in ("vanguard", "hybrid") and baseline_texts and current_texts:
            sem = self.semantic.analyze(baseline_texts, current_texts)
            semantic_score = sem["semantic_drift_score"]
            
            # Incorporate LLM Judge if available
            if self.llm_judge:
                total_q_drift = 0.0
                for b_text, c_text in zip(baseline_texts, current_texts):
                    total_q_drift += self.llm_judge.judge_drift(b_text, c_text)
                qualitative_drift = total_q_drift / len(baseline_texts)
                semantic_score = 0.6 * semantic_score + 0.4 * qualitative_drift
            
            results.append(DriftTestResult(
                layer=DriftLayer.SEMANTIC,
                metric_name="mmd_classifier_ensemble_with_judge" if self.llm_judge else "mmd_classifier_ensemble",
                score=semantic_score,
                raw_statistic=sem["mmd"],
                p_value=sem["mmd_p_value"],
                effect_size=sem["mmd_effect_size"],
                is_drift=sem["is_drift"],
                severity=DriftSeverity(sem["severity"]),
                recommendation="Semantic drift detected. Review prompt templates or model temperature." if sem["is_drift"] else None,
            ))
        
        # L3: Behavioral
        if drift_mode in ("standard", "hybrid") and baseline_traces and current_traces:
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
        if drift_mode in ("vanguard", "hybrid") and baseline_node_outputs and current_node_outputs and results:
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
        
        # Composite score calculation
        drift_layers = [r for r in results if r.is_drift]
        overall = len(drift_layers) > 0
        
        # Weighted composite (structural = 0.2, semantic = 0.35, behavioral = 0.35, causal = 0.1)
        weights = {DriftLayer.STRUCTURAL: 0.2, DriftLayer.SEMANTIC: 0.35, 
                   DriftLayer.BEHAVIORAL: 0.35, DriftLayer.CAUSAL: 0.1}
        composite = sum(r.score * weights.get(r.layer, 0.1) for r in results)
        
        # L5: Temporal
        if drift_mode in ("vanguard", "hybrid"):
            # Use semantic score if available, otherwise use composite
            temp_score = 0.0
            sem_result = next((r for r in results if r.layer == DriftLayer.SEMANTIC), None)
            if sem_result:
                temp_score = sem_result.score
            else:
                temp_score = composite
                
            temp_info = self.temporal.update(temp_score)
            results.append(DriftTestResult(
                layer=DriftLayer.TEMPORAL,
                metric_name="adwin_adaptive_windowing",
                score=temp_info["mean"],
                raw_statistic=temp_info["cumulative_mean"],
                is_drift=temp_info["drift_detected"],
                severity=DriftSeverity.HIGH if temp_info["drift_detected"] else DriftSeverity.NONE,
                recommendation="Gradual temporal drift detected. Consider re-baselining or model fine-tuning." if temp_info["drift_detected"] else None,
                metadata=temp_info
            ))

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
