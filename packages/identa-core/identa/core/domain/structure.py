from typing import Dict, List, Optional, Literal, Set, Any
from pydantic import BaseModel, Field

class AgentNode(BaseModel):
    id: str
    type: Literal["llm", "tool", "router", "custom"]
    name: str
    model: Optional[str] = None
    provider: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    id_stability: Literal["stable", "ephemeral"]

class AgentEdge(BaseModel):
    from_node: str
    to_node: str

class AgentStructure(BaseModel):
    id: str
    version_hash: str
    nodes: List[AgentNode]
    edges: List[AgentEdge]

class ObservedStructureDelta(BaseModel):
    missing_nodes: Dict[str, int]
    unexpected_nodes: Dict[str, int]
    mismatched_ids: List[str]
    observed_frequency: Dict[str, float]
    traced_test_count: int
    total_test_count: int
    normalized_structural_drift: float = 0.0

    @classmethod
    def compute(
        cls, 
        intended: Optional[AgentStructure], 
        unexpected_nodes: Dict[str, int],
        missing_nodes: Dict[str, int],
        total_unique_nodes: int,
        observed_frequency: Dict[str, float],
        traced_test_count: int,
        total_test_count: int
    ) -> "ObservedStructureDelta":
        """Analyzes results to find differences between intended and observed structure."""
        
        drift = 0.0
        if total_unique_nodes > 0:
            drift = (len(unexpected_nodes) + len(missing_nodes)) / total_unique_nodes
            
        return cls(
            missing_nodes=missing_nodes,
            unexpected_nodes=unexpected_nodes,
            mismatched_ids=[],
            observed_frequency=observed_frequency,
            traced_test_count=traced_test_count,
            total_test_count=total_test_count,
            normalized_structural_drift=drift
        )
