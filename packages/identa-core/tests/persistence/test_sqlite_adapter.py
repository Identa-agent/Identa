import pytest
import uuid
from datetime import datetime, timezone
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.domain.models import Workspace, Run, RunStatus, MetricAggregate
from identa.core.domain.results import EvaluationResult, PerTestResult

@pytest.fixture
def adapter(tmp_path):
    db_file = tmp_path / "test_identa.db"
    db_url = f"sqlite:///{db_file}"
    return SQLiteStorageAdapter(db_url)

def test_sqlite_workspace_crud(adapter):
    ws = Workspace(id="ws_1", name="Test Workspace", backend_uri="sqlite:///test.db")
    adapter.save_workspace(ws)
    
    saved = adapter.get_workspace("ws_1")
    assert saved.id == "ws_1"
    assert saved.name == "Test Workspace"

def test_sqlite_run_crud(adapter):
    adapter.save_workspace(Workspace(id="ws_1", name="W", backend_uri="B"))
    
    run = Run(
        id="run_1",
        workspace_id="ws_1",
        name="Test Run",
        status=RunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        evaluation_mode="controlled"
    )
    adapter.save_run(run)
    
    saved = adapter.get_run("run_1")
    assert saved.id == "run_1"
    assert saved.status == RunStatus.RUNNING
    
    adapter.update_run_status("run_1", RunStatus.FINISHED)
    updated = adapter.get_run("run_1")
    assert updated.status == RunStatus.FINISHED

def test_sqlite_evaluation_result_crud(adapter):
    adapter.save_workspace(Workspace(id="ws_1", name="W", backend_uri="B"))
    
    result = EvaluationResult(
        id=str(uuid.uuid4()),
        run_id="run_1",
        suite_hash="h",
        suite_version="v",
        resolution="boundary",
        metric_specs=[],
        aggregates=[MetricAggregate(metric_name="m1", value=0.5, count=1)],
        per_test=[
            PerTestResult(test_id="t1", output="o", scores={"m1": 0.5})
        ]
    )
    adapter.save_evaluation_result(result)
    
    results = adapter.list_evaluation_results("run_1")
    assert len(results) == 1
    assert results[0].id == result.id
    assert results[0].aggregates[0].metric_name == "m1"
