import click
from flask.cli import with_appcontext
from app.models import AiModel, SUPPORTED_PROVIDERS
from app import db


@click.command('seed-ai-models')
@with_appcontext
def seed_ai_models_command():
    click.echo("No default models to seed. Use the admin API at /api/v1/admin/models to add models manually.")
    click.echo(f"Supported providers: {', '.join(p['id'] for p in SUPPORTED_PROVIDERS)}")


@click.command('list-ai-models')
@with_appcontext
def list_ai_models_command():
    models = AiModel.query.order_by(AiModel.provider, AiModel.model_name).all()
    if not models:
        click.echo("No AI models found. Use the admin API to add models.")
        return
    click.echo(f"{'ID':<4} {'Provider':<12} {'Model Name':<35} {'Active':<8}")
    click.echo("-" * 65)
    for m in models:
        click.echo(f"{m.id:<4} {m.provider:<12} {m.model_name:<35} {str(m.is_active):<8}")
