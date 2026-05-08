from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from pydantic import BaseModel
from identa.core.domain.structure import AgentStructure

class ChangeType(str, Enum):
    REPLACE_MODEL = "replace_model"
    UPDATE_PROMPT = "update_prompt"
    ADD_TOOL = "add_tool"
    REMOVE_TOOL = "remove_tool"
    UPDATE_EDGE = "update_edge"

class MigrationChange(BaseModel):
    node_id: str
    change_type: ChangeType
    from_val: Any = None
    to_val: Any
    forced: bool = False
    validation_rules: List[str] = []  # e.g., ["tool_name_required"]

class MigrationPlan(BaseModel):
    id: str
    source_structure_hash: str
    changes: List[MigrationChange] = []

    def replace_model(self, node: str, to: str, force: bool = False):
        self.changes.append(MigrationChange(
            node_id=node,
            change_type=ChangeType.REPLACE_MODEL,
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
    _mutators: Dict[str, Callable] = {}

    @classmethod
    def register_mutator(cls, framework: str, fn: Callable):
        cls._mutators[framework] = fn

    @staticmethod
    def validate(plan: MigrationPlan, agent: Any, current_structure: AgentStructure) -> ValidationReport:
        hash_match = plan.source_structure_hash == current_structure.version_hash
        supported, unsupported = [], []
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
    def apply(plan: MigrationPlan, agent: Any, current_structure: AgentStructure, 
              framework_name: str, mode: str = "strict") -> Any:
        report = MigrationEngine.validate(plan, agent, current_structure)
        if mode == "strict" and not report.ok:
            raise ValueError(f"Migration validation failed: {report}")

        mutator = MigrationEngine._mutators.get(framework_name)
        if not mutator:
            raise NotImplementedError(f"No mutator registered for framework: {framework_name}")

        # Deep copy agent to preserve original for rollback
        import copy
        agent_copy = copy.deepcopy(agent)
        return mutator(agent_copy, plan)
