"""`openagno deploy ...` commands."""

from __future__ import annotations

import subprocess

import typer

from openagno.commands._common import project_root
from openagno.commands._output import header, next_step, step_error, step_info, step_ok, step_warn

deploy_app = typer.Typer(help="Deployment helpers.")


@deploy_app.command("local")
def deploy_local() -> None:
	"""Start the local supervisor in background."""
	header("Deploying locally...")
	from openagno.commands.start import start_command

	start_command(daemon=True)


@deploy_app.command("docker")
def deploy_docker(
	include_qr: bool = typer.Option(False, help="Levantar tambien el bridge QR."),
) -> None:
	"""Launch local Docker services."""
	root = project_root()
	command = ["docker", "compose"]
	if include_qr:
		command.extend(["--profile", "qr"])
	command.extend(["up", "-d"])
	header("Deploying with Docker...")
	step_info("Launching docker compose stack.")
	result = subprocess.run(command, cwd=str(root), check=False)
	if result.returncode == 0:
		step_ok("Docker stack is up.")
		next_step("Run `docker compose ps` or `openagno status` to inspect services.")
	else:
		step_error("Docker deployment failed.")
	raise typer.Exit(code=result.returncode)


@deploy_app.command("aws")
def deploy_aws() -> None:
	"""Guidance placeholder for AWS deployment."""
	header("AWS deployment")
	step_warn("AWS deployment is not automated in this phase.")
	next_step("Use `openagno deploy docker` or the assets under `deploy/` as a starting point.")
