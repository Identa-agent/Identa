import logging
from typing import Optional
from identa.core.ports.exporter import ExporterPort
from identa.core.domain.results import EvaluationResult

logger = logging.getLogger(__name__)

try:
    import mlflow
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

class MLflowExporter(ExporterPort):
    def __init__(self, tracking_uri: Optional[str] = None):
        if not HAS_MLFLOW:
            raise RuntimeError(
                "MLflow is not installed. Please install identa-core[mlflow] to use this exporter."
            )
        self.tracking_uri = tracking_uri
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

    def export_result(self, result: EvaluationResult) -> str:
        logger.info("📦 Exporting run %s to MLflow...", result.run_id)
        
        # FIX: Capture the ActiveRun object from the context manager yield
        with mlflow.start_run(run_name=result.run_id) as run:
            for agg in result.aggregates:
                mlflow.log_metric(agg.metric_name, agg.value)
            
            mlflow.set_tag("suite_hash", result.suite_hash)
            
            # Extract run_id while the context is still active
            mlflow_run_id = run.info.run_id if run else None
            
        if mlflow_run_id:
            return f"mlflow-run://{mlflow_run_id}"
        return f"https://mlflow.internal/runs/{result.run_id}"