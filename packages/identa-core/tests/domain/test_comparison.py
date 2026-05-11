import pytest
import uuid
from identa.core.domain.comparison import ComparisonEngine, ComparisonResult
from identa.core.domain.results import EvaluationResult
from identa.core.domain.models import MetricAggregate

def test_comparison_engine_metric_deltas():
    source = EvaluationResult(
        id=str(uuid.uuid4()),
        run_id="run_1",
        suite_hash="hash",
        suite_version="1.0",
        resolution="boundary",
        metric_specs=[],
        per_test=[],
        aggregates=[
            MetricAggregate(metric_name="exact_match", value=0.8, count=10),
            MetricAggregate(metric_name="latency", value=100.0, count=10)
        ]
    )
    
    target = EvaluationResult(
        id=str(uuid.uuid4()),
        run_id="run_2",
        suite_hash="hash",
        suite_version="1.0",
        resolution="boundary",
        metric_specs=[],
        per_test=[],
        aggregates=[
            MetricAggregate(metric_name="exact_match", value=0.9, count=10),
            MetricAggregate(metric_name="latency", value=115.0, count=10)
        ]
    )
    
    result = ComparisonEngine.compare(source, target)
    
    assert result.source_run_id == "run_1"
    assert result.target_run_id == "run_2"
    
    # exact_match: (0.9 - 0.8) / 0.8 = 0.125
    assert pytest.approx(result.metric_deltas["exact_match"]) == 0.125
    
    # latency: (115 - 100) / 100 = 0.15
    assert pytest.approx(result.metric_deltas["latency"]) == 0.15
    
    # Regression check: latency increased by 15% (>10% tolerance)
    assert "latency" in result.regressions
    # exact_match improved, so not in regressions
    assert "exact_match" not in result.regressions

def test_comparison_engine_no_regressions():
    source = EvaluationResult(
        id=str(uuid.uuid4()),
        run_id="run_1",
        suite_hash="hash",
        suite_version="1.0",
        resolution="boundary",
        metric_specs=[],
        per_test=[],
        aggregates=[MetricAggregate(metric_name="exact_match", value=0.8, count=10)]
    )
    
    target = EvaluationResult(
        id=str(uuid.uuid4()),
        run_id="run_2",
        suite_hash="hash",
        suite_version="1.0",
        resolution="boundary",
        metric_specs=[],
        per_test=[],
        aggregates=[MetricAggregate(metric_name="exact_match", value=0.85, count=10)]
    )
    
    result = ComparisonEngine.compare(source, target)
    assert not result.regressions

def test_comparison_report_format():
    result = ComparisonResult(
        source_run_id="run_1",
        target_run_id="run_2",
        metric_deltas={"exact_match": 0.125, "latency": -0.05},
        regressions=["accuracy"]
    )
    
    report = result.report()
    assert "Comparison: run_1 → run_2" in report
    assert "exact_match: +12.50%" in report
    assert "latency: -5.00%" in report
    assert "⚠️  Regressions: accuracy" in report
