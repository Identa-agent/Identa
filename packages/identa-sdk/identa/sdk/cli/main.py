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

@cli.group()
def runs():
    """Manage runs"""
    pass

@runs.command(name="list")
@click.option('--workspace', required=True, help='Workspace ID')
@click.pass_context
def list_runs(ctx, workspace):
    storage = ctx.obj['storage']
    runs = storage.list_runs(workspace)
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

if __name__ == '__main__':
    cli()
