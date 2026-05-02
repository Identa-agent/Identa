from typing import Dict, List, Optional, Literal, Set
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

    @classmethod
    def compute(
        cls, 
        intended: Optional[AgentStructure], 
        results: List[Any] # PerTestResult
    ) -> "ObservedStructureDelta":
        """Analyzes results to find differences between intended and observed structure."""
        total_test_count = len(results)
        traced_results = [r for r in results if r.trace_ref]
        traced_test_count = len(traced_results)
        
        intended_node_ids = {n.id for n in intended.nodes} if intended else set()
        
        observed_counts: Dict[str, int] = {}
        for res in traced_results:
            # We assume node_ids are captured in span metadata or similar
            # For now, we'll look at the test's output or some internal state
            # In a real impl, we'd need to fetch the TraceArtifact and check span node_ids.
            # But we don't want to fetch all traces here.
            # So we rely on the fact that evaluate() could have tracked node hits.
            
            # Placeholder: extracting node hits from trace_ref is expensive.
            # Let's assume the resolution was performed and we have some summary.
            pass

        # Since we don't have the full trace content here, we'll implement a skeleton
        # that returns zero deltas for now, but with the correct structure.
        return cls(
            missing_nodes={},
            unexpected_nodes={},
            mismatched_ids=[],
            observed_frequency={},
            traced_test_count=traced_test_count,
            total_test_count=total_test_count
        )
