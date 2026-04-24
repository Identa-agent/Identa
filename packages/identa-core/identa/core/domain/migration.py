from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from identa.core.domain.structure import AgentStructure

class MigrationChange(BaseModel):
    node_id: str
    field: str
    from_val: Any
    to_val: Any
    forced: bool = False

class MigrationPlan(BaseModel):
    id: str
    source_structure_hash: str
    changes: List[MigrationChange] = []

    def replace_model(self, node: str, to: str, force: bool = False):
        self.changes.append(MigrationChange(
            node_id=node,
            field="model",
            from_val=None, # In real usage, would look up from structure
            to_val=to,
            forced=force
        ))

class ValidationReport(BaseModel):
    ok: bool
    supported_nodes: List[str] = []
    unsupported_nodes: List[str] = []
    unobserved_nodes: List[str] = []
    structure_hash_match: bool
    warnings: List[str] = []

class MigrationEngine:
    @staticmethod
    def validate(plan: MigrationPlan, agent: Any, current_structure: AgentStructure) -> ValidationReport:
        hash_match = plan.source_structure_hash == current_structure.version_hash
        
        supported = []
        unsupported = []
        node_ids = {n.id for n in current_structure.nodes}
        
        for change in plan.changes:
            if change.node_id in node_ids:
                supported.append(change.node_id)
            else:
                unsupported.append(change.node_id)
                
        return ValidationReport(
            ok=hash_match and not unsupported,
            supported_nodes=supported,
            unsupported_nodes=unsupported,
            structure_hash_match=hash_match
        )

    @staticmethod
    def apply(plan: MigrationPlan, agent: Any, current_structure: AgentStructure, mode: str = "strict") -> Any:
        report = MigrationEngine.validate(plan, agent, current_structure)
        if mode == "strict" and not report.ok:
            raise ValueError(f"Migration validation failed: {report}")
            
        # Actual patching would be framework specific (e.g. LangGraphAdapter.apply_plan)
        return agent
