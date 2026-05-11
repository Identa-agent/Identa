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
        # Search for the artifact by ID prefix in the base_path tree
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file.startswith(artifact_id):
                    file_path = os.path.join(root, file)
                    # Read into memory to avoid leaking file handles
                    import io
                    with open(file_path, "rb") as f:
                        return io.BytesIO(f.read())
        return None
