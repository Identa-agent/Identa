import os
import uuid
from typing import BinaryIO, Optional
from identa.core.ports.artifacts import ArtifactPort

class LocalArtifactAdapter(ArtifactPort):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save_artifact(self, run_id: str, name: str, content: BinaryIO) -> str:
        artifact_id = str(uuid.uuid4())
        run_path = os.path.join(self.base_path, run_id)
        os.makedirs(run_path, exist_ok=True)
        
        file_path = os.path.join(run_path, f"{artifact_id}_{name}")
        with open(file_path, "wb") as f:
            f.write(content.read())
            
        return artifact_id

    def get_artifact(self, artifact_id: str) -> Optional[BinaryIO]:
        # This implementation requires searching for the artifact_id in the base_path
        # A more efficient one would store the mapping in the database
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file.startswith(artifact_id):
                    return open(os.path.join(root, file), "rb")
        return None
