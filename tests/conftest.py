import pytest
import shutil
import os
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Ensure no stray .db files from previous runs are left."""
    yield
    # No-op for now, but good hook for later
    pass

@pytest.fixture
def temp_workspace(tmp_path):
    """Provides a fresh temporary workspace for each test."""
    db_path = tmp_path / "identa_test.db"
    return f"sqlite:///{db_path}"
