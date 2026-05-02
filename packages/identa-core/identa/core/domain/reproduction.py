import sys
import importlib.metadata
from typing import Any, Dict, Optional, List
from identa.core.domain.models import ReproducibilityBundle
from identa.core.domain.evaluation import EvaluationEngine
from identa.core.domain.structure import AgentStructure

class ReproductionEngine:
    def __init__(self, engine: EvaluationEngine):
        self.engine = engine

    def reproduce(
        self,
        bundle: ReproducibilityBundle,
        agent: Any,
        suite: List[Dict[str, Any]],
        current_structure: Optional[AgentStructure] = None,
        strict_structure: bool = False
    ):
        if bundle.resolution in ["node", "tool", "llm"]:
            if not current_structure:
                raise ValueError("Structure-aware resolution requires current_structure")
            
            if bundle.structure_hash != current_structure.version_hash:
                if strict_structure:
                    raise ValueError(f"Structural drift detected: {bundle.structure_hash} != {current_structure.version_hash}")
                else:
                    print(f"Warning: Structural drift detected. Original: {bundle.structure_hash}, Current: {current_structure.version_hash}")

        # Reconstruct evaluation
        return self.engine.evaluate(
            agent=agent,
            suite=suite,
            run_id=f"reproduction_of_{bundle.hashes.get('config', 'unknown')}",
            resolution=bundle.resolution,
            structure=current_structure,
            mode=bundle.evaluation_mode
        )

def capture_environment() -> Dict[str, Any]:
    """Captures the current Python environment and package versions."""
    frameworks = ["langgraph", "langchain", "pydantic-ai", "pydantic"]
    versions = {}
    for fw in frameworks:
        try:
            versions[fw] = importlib.metadata.version(fw)
        except importlib.metadata.PackageNotFoundError:
            pass
            
    try:
        identa_version = importlib.metadata.version("identa-core")
    except importlib.metadata.PackageNotFoundError:
        identa_version = "unknown"

    return {
        "python_version": sys.version.split()[0],
        "identa_version": identa_version,
        "framework_versions": versions
    }
