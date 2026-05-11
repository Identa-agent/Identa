import json
import sqlite3
from typing import List, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Integer, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, declarative_base
from identa.core.domain.models import Workspace, Run, Baseline, ReproducibilityBundle, RunStatus
from identa.core.domain.results import EvaluationResult
from identa.core.domain.exceptions import StorageError, WorkspaceNotFoundError
from identa.core.ports.storage import StoragePort

Base = declarative_base()

class WorkspaceModel(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    backend_uri = Column(String, nullable=False)

class RunModel(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    parent_run_id = Column(String, nullable=True)
    params = Column(Text, nullable=False) # JSON
    tags = Column(Text, nullable=False)   # JSON
    status = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    evaluation_mode = Column(String, nullable=False)
    reproducibility_bundle_id = Column(String, nullable=True)
    artifact_ids = Column(Text, nullable=False) # JSON list

class BaselineModel(Base):
    __tablename__ = "baselines"
    name = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    registered_at = Column(DateTime, nullable=False)


class EvaluationResultModel(Base):
    """Stores the header of EvaluationResult."""
    __tablename__ = "evaluation_results"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    suite_hash = Column(String, nullable=False)
    resolution = Column(String, nullable=False)
    data = Column(Text, nullable=False)  # Full JSON blob of EvaluationResult for backward compatibility

class PerTestResultModel(Base):
    __tablename__ = "per_test_results"
    id = Column(String, primary_key=True)
    result_id = Column(String, ForeignKey("evaluation_results.id"), nullable=False, index=True)
    test_id = Column(String, nullable=False, index=True)
    input_data = Column(Text, nullable=False)  # JSON
    expected_data = Column(Text, nullable=True)  # JSON
    output_data = Column(Text, nullable=False)  # JSON
    scores = Column(Text, nullable=False)  # JSON {metric: score}
    node_scores = Column(Text, nullable=False)  # JSON {node_id: {metric: score}}
    trace_ref = Column(String, nullable=True)
    semantic_drift = Column(String, nullable=True)  # Store per-test drift if applicable

class MetricAggregateModel(Base):
    __tablename__ = "metric_aggregates"
    id = Column(String, primary_key=True)
    result_id = Column(String, ForeignKey("evaluation_results.id"), nullable=False, index=True)
    metric_name = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)  # SQLite lacks decimal; store as string or use REAL
    count = Column(Integer, nullable=False)


class ReproducibilityBundleModel(Base):
    __tablename__ = "reproducibility_bundles"
    id = Column(String, primary_key=True)
    python_version = Column(String, nullable=False)
    identa_version = Column(String, nullable=False)
    framework_versions = Column(Text, nullable=False) # JSON
    provider_models = Column(Text, nullable=False)   # JSON
    structure_hash = Column(String, nullable=True)
    resolution = Column(String, nullable=False)
    hashes = Column(Text, nullable=False) # JSON
    seed = Column(Integer, nullable=True)
    evaluation_mode = Column(String, nullable=False)

class DriftReportModel(Base):
    __tablename__ = "drift_reports"
    result_id = Column(String, ForeignKey("evaluation_results.id"), primary_key=True)
    run_id = Column(String, nullable=False, index=True)
    overall_drift = Column(Integer, nullable=False) # Boolean
    max_severity = Column(String, nullable=False)
    composite_score = Column(Text, nullable=False) # Store as String to avoid REAL precision issues or use REAL
    root_cause_nodes = Column(Text, nullable=False) # JSON list
    
class DriftTestResultModel(Base):
    __tablename__ = "drift_test_results"
    id = Column(String, primary_key=True)
    result_id = Column(String, ForeignKey("drift_reports.result_id"), nullable=False, index=True)
    layer = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    score = Column(Text, nullable=False)
    raw_statistic = Column(Text, nullable=False)
    is_drift = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)
    affected_nodes = Column(Text, nullable=False) # JSON list
    metadata_json = Column(Text, nullable=False) # JSON dict

class SQLiteStorageAdapter(StoragePort):
    def __init__(self, database_url: str):
        try:
            self.engine = create_engine(database_url)
            self._run_migrations()
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to initialize storage: {e}")

    def _run_migrations(self) -> None:
        """Handles manual SQL schema migrations."""
        try:
            with self.engine.connect() as conn:
                pass
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Migration failed: {e}")

    def save_workspace(self, workspace: Workspace) -> None:
        try:
            with self.Session() as session:
                model = WorkspaceModel(
                    id=workspace.id,
                    name=workspace.name,
                    backend_uri=workspace.backend_uri
                )
                session.merge(model)
                session.commit()
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to save workspace {workspace.id}: {e}")

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        try:
            with self.Session() as session:
                model = session.query(WorkspaceModel).filter_by(id=workspace_id).first()
                if model:
                    return Workspace(id=model.id, name=model.name, backend_uri=model.backend_uri)
                return None
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to get workspace {workspace_id}: {e}")

    def list_workspaces(self) -> List[Workspace]:
        try:
            with self.Session() as session:
                models = session.query(WorkspaceModel).all()
                return [Workspace(id=m.id, name=m.name, backend_uri=m.backend_uri) for m in models]
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to list workspaces: {e}")

    def save_run(self, run: Run) -> None:
        try:
            with self.Session() as session:
                model = RunModel(
                    id=run.id,
                    workspace_id=run.workspace_id,
                    name=run.name,
                    parent_run_id=run.parent_run_id,
                    params=json.dumps(run.params),
                    tags=json.dumps(run.tags),
                    status=run.status,
                    started_at=run.started_at,
                    ended_at=run.ended_at,
                    evaluation_mode=run.evaluation_mode,
                    reproducibility_bundle_id=run.reproducibility_bundle_id,
                    artifact_ids=json.dumps(run.artifact_ids)
                )
                session.merge(model)
                session.commit()
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to save run {run.id}: {e}")

    def get_run(self, run_id: str) -> Optional[Run]:
        try:
            with self.Session() as session:
                model = session.query(RunModel).filter_by(id=run_id).first()
                if model:
                    return Run(
                        id=model.id,
                        workspace_id=model.workspace_id,
                        name=model.name,
                        parent_run_id=model.parent_run_id,
                        params=json.loads(model.params),
                        tags=json.loads(model.tags),
                        status=model.status,
                        started_at=model.started_at,
                        ended_at=model.ended_at,
                        evaluation_mode=model.evaluation_mode,
                        reproducibility_bundle_id=model.reproducibility_bundle_id,
                        artifact_ids=json.loads(model.artifact_ids)
                    )
                return None
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to get run {run_id}: {e}")

    def list_runs(self, workspace_id: str) -> List[Run]:
        try:
            with self.Session() as session:
                models = session.query(RunModel).filter_by(workspace_id=workspace_id).all()
                return [
                    Run(
                        id=m.id,
                        workspace_id=m.workspace_id,
                        name=m.name,
                        parent_run_id=m.parent_run_id,
                        params=json.loads(m.params),
                        tags=json.loads(m.tags),
                        status=m.status,
                        started_at=m.started_at,
                        ended_at=m.ended_at,
                        evaluation_mode=m.evaluation_mode,
                        reproducibility_bundle_id=m.reproducibility_bundle_id,
                        artifact_ids=json.loads(m.artifact_ids)
                    ) for m in models
                ]
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to list runs for workspace {workspace_id}: {e}")

    def save_baseline(self, baseline: Baseline) -> None:
        try:
            with self.Session() as session:
                run = session.query(RunModel).filter_by(id=baseline.run_id).first()
                if not run:
                    raise StorageError(f"Run {baseline.run_id} not found")
                
                model = BaselineModel(
                    name=baseline.name,
                    workspace_id=run.workspace_id,
                    run_id=baseline.run_id,
                    registered_at=baseline.registered_at
                )
                session.merge(model)
                session.commit()
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to save baseline {baseline.name}: {e}")

    def get_baseline(self, workspace_id: str, name: str) -> Optional[Baseline]:
        try:
            with self.Session() as session:
                model = session.query(BaselineModel).filter_by(workspace_id=workspace_id, name=name).first()
                if model:
                    return Baseline(
                        name=model.name,
                        run_id=model.run_id,
                        registered_at=model.registered_at
                    )
                return None
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to get baseline {name} for workspace {workspace_id}: {e}")

    def save_evaluation_result(self, result: EvaluationResult) -> None:
        try:
            with self.Session() as session:
                # Save header
                header = EvaluationResultModel(
                    id=result.id,
                    run_id=result.run_id,
                    suite_hash=result.suite_hash,
                    resolution=result.resolution,
                    data=result.model_dump_json()
                )
                session.merge(header)

                # Save per-test results for queryability
                for pt in result.per_test:
                    pt_model = PerTestResultModel(
                        id=f"{result.id}_{pt.test_id}",
                        result_id=result.id,
                        test_id=pt.test_id,
                        input_data=json.dumps(pt.input, default=str),
                        expected_data=json.dumps(pt.expected, default=str),
                        output_data=json.dumps(pt.output, default=str),
                        scores=json.dumps(pt.scores),
                        node_scores=json.dumps(pt.node_scores),
                        trace_ref=pt.trace_ref
                    )
                    session.merge(pt_model)

                # Save aggregates
                for agg in result.aggregates:
                    agg_model = MetricAggregateModel(
                        id=f"{result.id}_{agg.metric_name}",
                        result_id=result.id,
                        metric_name=agg.metric_name,
                        value=str(agg.value),
                        count=agg.count
                    )
                    session.merge(agg_model)

                # Save Drift Report if present
                if result.drift_report:
                    dr = result.drift_report
                    dr_model = DriftReportModel(
                        result_id=result.id,
                        run_id=dr.run_id,
                        overall_drift=1 if dr.overall_drift else 0,
                        max_severity=dr.max_severity.value,
                        composite_score=str(dr.composite_score),
                        root_cause_nodes=json.dumps(dr.root_cause_nodes)
                    )
                    session.merge(dr_model)
                    
                    for i, r in enumerate(dr.layer_results):
                        r_model = DriftTestResultModel(
                            id=f"{result.id}_{r.layer.value}_{i}",
                            result_id=result.id,
                            layer=r.layer.value,
                            metric_name=r.metric_name,
                            score=str(r.score),
                            raw_statistic=str(r.raw_statistic),
                            is_drift=1 if r.is_drift else 0,
                            severity=r.severity.value,
                            affected_nodes=json.dumps(r.affected_nodes),
                            metadata_json=json.dumps(r.metadata)
                        )
                        session.merge(r_model)

                session.commit()
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to save evaluation result {result.id}: {e}")

    def get_evaluation_result(self, result_id: str) -> Optional[EvaluationResult]:
        try:
            with self.Session() as session:
                model = session.query(EvaluationResultModel).filter_by(id=result_id).first()
                if model:
                    return EvaluationResult.model_validate_json(model.data)
                return None
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to get evaluation result {result_id}: {e}")

    def list_evaluation_results(self, run_id: str) -> List[EvaluationResult]:
        try:
            with self.Session() as session:
                models = session.query(EvaluationResultModel).filter_by(run_id=run_id).all()
                return [EvaluationResult.model_validate_json(m.data) for m in models]
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to list evaluation results for run {run_id}: {e}")

    def save_reproducibility_bundle(self, bundle: ReproducibilityBundle) -> None:
        try:
            with self.Session() as session:
                model = ReproducibilityBundleModel(
                    id=bundle.id,
                    python_version=bundle.python_version,
                    identa_version=bundle.identa_version,
                    framework_versions=json.dumps(bundle.framework_versions),
                    provider_models=json.dumps(bundle.provider_models),
                    structure_hash=bundle.structure_hash,
                    resolution=bundle.resolution,
                    hashes=json.dumps(bundle.hashes),
                    seed=bundle.seed,
                    evaluation_mode=bundle.evaluation_mode
                )
                session.merge(model)
                session.commit()
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to save reproducibility bundle {bundle.id}: {e}")

    def get_reproducibility_bundle(self, bundle_id: str) -> Optional[ReproducibilityBundle]:
        try:
            with self.Session() as session:
                model = session.query(ReproducibilityBundleModel).filter_by(id=bundle_id).first()
                if model:
                    return ReproducibilityBundle(
                        id=model.id,
                        python_version=model.python_version,
                        identa_version=model.identa_version,
                        framework_versions=json.loads(model.framework_versions),
                        provider_models=json.loads(model.provider_models),
                        structure_hash=model.structure_hash,
                        resolution=model.resolution,
                        hashes=json.loads(model.hashes),
                        seed=model.seed,
                        evaluation_mode=model.evaluation_mode
                    )
                return None
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to get reproducibility bundle {bundle_id}: {e}")

    def update_run_status(self, run_id: str, new_status: RunStatus, reason: Optional[str] = None) -> bool:
        """Atomic update to prevent race conditions."""
        try:
            with self.Session() as session:
                # Use raw SQL for atomic update with optimistic locking/condition
                stmt = text("""
                    UPDATE runs 
                    SET status = :new_status, ended_at = :ended_at
                    WHERE id = :run_id AND status = 'running'
                """)
                
                params = {
                    "new_status": new_status.value,
                    "ended_at": datetime.now(),
                    "run_id": run_id
                }
                
                result = session.execute(stmt, params)
                
                if reason and result.rowcount > 0:
                    # Update tags if reason is provided
                    model = session.query(RunModel).filter_by(id=run_id).first()
                    if model:
                        tags = json.loads(model.tags)
                        tags["failure_reason"] = reason
                        model.tags = json.dumps(tags)
                
                session.commit()
                return result.rowcount > 0
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to update run status for {run_id}: {e}")

    def get_tests_by_metric_threshold(self, result_id: str, metric_name: str, 
                                      threshold: float, above: bool = True) -> List[dict]:
        try:
            with self.Session() as session:
                # This is a bit complex since scores is a JSON blob in SQLite
                # We fetch and filter in Python for portability, or use SQLite JSON extensions if available
                # For simplicity, we'll fetch all per-test results for the result_id
                models = session.query(PerTestResultModel).filter_by(result_id=result_id).all()
                results = []
                for m in models:
                    scores = json.loads(m.scores)
                    val = scores.get(metric_name)
                    if val is not None:
                        if (above and val >= threshold) or (not above and val <= threshold):
                            results.append({
                                "test_id": m.test_id,
                                "input": json.loads(m.input_data),
                                "output": json.loads(m.output_data),
                                "score": val
                            })
                return results
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to query tests by metric: {e}")

    def get_node_drift_timeseries(self, workspace_id: str, node_id: str, 
                                  metric_name: str, limit: int = 100) -> List[dict]:
        try:
            with self.Session() as session:
                # Join runs and evaluation_results and per_test_results
                # Filter by workspace_id and node_id
                query = (
                    session.query(RunModel.started_at, PerTestResultModel.node_scores)
                    .join(EvaluationResultModel, RunModel.id == EvaluationResultModel.run_id)
                    .join(PerTestResultModel, EvaluationResultModel.id == PerTestResultModel.result_id)
                    .filter(RunModel.workspace_id == workspace_id)
                    .order_by(RunModel.started_at.desc())
                    .limit(limit)
                )
                
                rows = query.all()
                timeseries = []
                for started_at, node_scores_json in rows:
                    node_scores = json.loads(node_scores_json)
                    if node_id in node_scores:
                        val = node_scores[node_id].get(metric_name)
                        if val is not None:
                            timeseries.append({
                                "timestamp": started_at.isoformat(),
                                "value": val
                            })
                return timeseries
        except (SQLAlchemyError, sqlite3.Error) as e:
            raise StorageError(f"Failed to query node drift timeseries: {e}")
