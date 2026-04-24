from typing import Dict, List, Optional, Literal
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
