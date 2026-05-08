import click
import sys
import importlib.util
from identa.sdk.api import set_workspace, evaluate, assert_no_regressions
from identa.sdk.suites import load_suite

@click.command()
@click.option('--workspace', required=True)
@click.option('--baseline', default='default')
@click.option('--agent-file', required=True)
@click.option('--suite-file', required=True)
@click.option('--max-drift', default=0.1, type=float)
def ci(workspace, baseline, agent_file, suite_file, max_drift):
    """CI-friendly evaluation. Exits non-zero on regression or drift."""
    set_workspace(workspace)
    
    # Load agent
    spec = importlib.util.spec_from_file_location("agent_module", agent_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Assume 'agent' symbol by default
    agent = getattr(module, "agent")
    
    suite = load_suite(suite_file)
    results = evaluate(agent, suite, resolution="node")
    
    # Check drift
    if results.semantic_drift > max_drift:
        click.echo(f"❌ Semantic drift {results.semantic_drift:.4f} exceeds threshold {max_drift}")
        sys.exit(1)
    
    # Check regressions
    try:
        assert_no_regressions(results, baseline)
    except AssertionError as e:
        click.echo(f"❌ {e}")
        sys.exit(1)
    
    click.echo("✅ All checks passed")
