import json
from typing import Optional
from identa.core.ports.exporter import ExporterPort
from identa.core.domain.results import EvaluationResult

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
        """Exports metrics and metadata to MLflow."""
        print(f"📦 Exporting run {result.run_id} to MLflow...")
        
        with mlflow.start_run(run_name=result.run_id):
            # Log metrics
            for agg in result.aggregates:
                mlflow.log_metric(agg.metric_name, agg.value)
            
            # Log parameters and tags if available
            mlflow.set_tag("suite_hash", result.suite_hash)
            
        # Return the MLflow run URL if possible, or a mock
        run = mlflow.active_run()
        if run:
            return f"mlflow-run://{run.info.run_id}"
        return f"https://mlflow.internal/runs/{result.run_id}"
