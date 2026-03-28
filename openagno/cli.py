"""OpenAgno CLI entrypoint."""

from __future__ import annotations

import typer

from openagno.commands.add import add_app
from openagno.commands.create import create_app
from openagno.commands.deploy import deploy_app
from openagno.commands.init import init_command
from openagno.commands.logs import logs_command
from openagno.commands.restart import restart_command
from openagno.commands.start import start_command
from openagno.commands.status import status_command
from openagno.commands.stop import stop_command
from openagno.commands.templates import templates_app
from openagno.commands.validate import validate_command

app = typer.Typer(
	name="openagno",
	help="Build autonomous AI agents with declarative YAML configuration.",
	no_args_is_help=True,
)

app.command("init")(init_command)
app.command("start")(start_command)
app.command("stop")(stop_command)
app.command("restart")(restart_command)
app.command("status")(status_command)
app.command("logs")(logs_command)
app.command("validate")(validate_command)

app.add_typer(create_app, name="create", help="Create agents and resources")
app.add_typer(add_app, name="add", help="Add channels and tools")
app.add_typer(templates_app, name="templates", help="Manage workspace templates")
app.add_typer(deploy_app, name="deploy", help="Deploy to local or container targets")


def main() -> None:
	"""Console-script wrapper."""
	app()
