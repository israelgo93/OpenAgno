"""`openagno deploy ...` commands."""

from __future__ import annotations

import subprocess

import typer

from openagno.commands._common import console, project_root

deploy_app = typer.Typer(help="Deployment helpers.")


@deploy_app.command("local")
def deploy_local() -> None:
	"""Start the local supervisor in background."""
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
	result = subprocess.run(command, cwd=str(root), check=False)
	raise typer.Exit(code=result.returncode)


@deploy_app.command("aws")
def deploy_aws() -> None:
	"""Guidance placeholder for AWS deployment."""
	console.print(
		"[yellow]Deploy AWS aun no esta automatizado en esta fase.[/yellow] "
		"Usa `openagno deploy docker` o los archivos de `deploy/` como base."
	)
