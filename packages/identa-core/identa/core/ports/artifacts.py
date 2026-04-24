from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

class ArtifactPort(ABC):
    @abstractmethod
    def save_artifact(self, run_id: str, name: str, content: BinaryIO) -> str:
        """Returns the artifact_id"""
        pass

    @abstractmethod
    def get_artifact(self, artifact_id: str) -> Optional[BinaryIO]:
        pass
