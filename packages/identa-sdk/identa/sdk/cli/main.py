import click
import json
from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter

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

if __name__ == '__main__':
    cli()
