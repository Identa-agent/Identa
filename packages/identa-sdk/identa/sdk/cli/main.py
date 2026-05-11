import click
import json
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter
from identa.core.domain.comparison import ComparisonEngine
from identa.core.domain.structure import AgentStructure

@click.group()
@click.option('--db-url', default='sqlite:///identa.db', help='Database URL')
@click.pass_context
def cli(ctx, db_url):
    ctx.ensure_object(dict)
    ctx.obj['storage'] = SQLiteStorageAdapter(db_url)

@cli.command()
def version():
    """Show Identa version."""
    import pkg_resources
    try:
        ver = pkg_resources.get_distribution("identa-sdk").version
        click.echo(f"Identa SDK version {ver}")
    except Exception:
        click.echo("Identa SDK (development version)")

@cli.group()
def runs():
    """Manage runs"""
    pass

@runs.command(name="list")
@click.option('--workspace', required=True, help='Workspace ID')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.pass_context
def list_runs(ctx, workspace, format):
    storage = ctx.obj['storage']
    runs = storage.list_runs(workspace)
    if format == 'json':
        click.echo(json.dumps([r.model_dump() for r in runs], indent=2, default=str))
    else:
        for run in runs:
            click.echo(f"{run.id} | {run.name} | {run.status}")

@runs.command(name="show")
@click.argument('run_id')
@click.pass_context
def show_run(ctx, run_id):
    storage = ctx.obj['storage']
    run = storage.get_run(run_id)
    if run:
        click.echo(json.dumps(run.model_dump(), indent=2, default=str))
    else:
        click.echo(f"Run {run_id} not found")

@cli.command()
@click.argument('run1')
@click.argument('run2')
@click.pass_context
def compare(ctx, run1, run2):
    """Compare two runs and show metric deltas."""
    storage = ctx.obj['storage']
    res1_list = storage.list_evaluation_results(run1)
    res2_list = storage.list_evaluation_results(run2)
    
    if not res1_list or not res2_list:
        click.echo("Error: One or both runs have no evaluation results.")
        return
        
    comparison = ComparisonEngine.compare(res1_list[0], res2_list[0])
    click.echo(comparison.report())

@cli.command()
@click.argument('run1')
@click.argument('run2')
@click.pass_context
def diff(ctx, run1, run2):
    """Show structural differences between two runs."""
    storage = ctx.obj['storage']
    r1 = storage.get_run(run1)
    r2 = storage.get_run(run2)
    
    if not r1 or not r2:
        click.echo("Error: One or both runs not found.")
        return
        
    click.echo(f"Structural Diff: {run1} vs {run2}")
    if r1.reproducibility_bundle_id == r2.reproducibility_bundle_id:
        click.echo("✅ Structures match (same bundle id).")
    else:
        click.echo("❌ Structures differ.")
        # In a real impl, we'd fetch the bundles and diff the nodes/edges.
        click.echo(f"  Run 1 Bundle: {r1.reproducibility_bundle_id}")
        click.echo(f"  Run 2 Bundle: {r2.reproducibility_bundle_id}")

@cli.command()
@click.argument('run_id')
@click.pass_context
def reproduce(ctx, run_id):
    """Check if a run can be reproduced in the current environment."""
    storage = ctx.obj['storage']
    run = storage.get_run(run_id)
    if not run or not run.reproducibility_bundle_id:
        click.echo("Error: Run not found or has no reproducibility bundle.")
        return
        
    bundle = storage.get_reproducibility_bundle(run.reproducibility_bundle_id)
    if not bundle:
        click.echo("Error: Reproducibility bundle not found in storage.")
        return
        
    click.echo(f"Checking reproduction environment for run {run_id}...")
    from identa.core.domain.reproduction import capture_environment
    current = capture_environment()
    
    if current["python_version"] != bundle.python_version:
        click.echo(f"⚠️ Python version mismatch: {bundle.python_version} vs {current['python_version']}")
    else:
        click.echo("✅ Python version matches.")
    
    # Check framework versions
    for fw, version in bundle.framework_versions.items():
        curr_v = current["framework_versions"].get(fw)
        if curr_v != version:
            click.echo(f"⚠️ {fw} version mismatch: {version} vs {curr_v}")
        else:
            click.echo(f"✅ {fw} version matches ({version}).")

from identa.sdk.api import evaluate, set_workspace
from identa.sdk.suites import load_suite
from identa.sdk.cli.ci import ci as ci_cmd

# ... existing code ...

@cli.command()
@click.option('--workspace', required=True)
@click.option('--agent-file', required=True, help='Python file path exporting `agent`')
@click.option('--agent-symbol', default='agent', help='Variable name of agent in file')
@click.option('--drift-mode', type=click.Choice(['standard', 'vanguard', 'hybrid']), default='standard')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.argument('suite_file')
def run(workspace, agent_file, agent_symbol, drift_mode, format, suite_file):
    """Run an evaluation suite against a specified agent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_module", agent_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent = getattr(module, agent_symbol)

    set_workspace(workspace)
    suite = load_suite(suite_file)

    results = evaluate(agent, suite, drift_mode=drift_mode, resolution="node")
    
    if format == 'json':
        click.echo(results.model_dump_json())
    else:
        click.echo(results.summary())
        if results.drift_report:
            click.echo(results.drift_report.summary())
    
    if results.structure_delta and results.structure_delta.normalized_structural_drift > 0.1:
        if format == 'text':
            click.echo("⚠️ Structural drift detected!")

cli.add_command(ci_cmd, name="ci")
