"""`openagno start` command."""

from __future__ import annotations


import typer

from openagno.commands._common import console, project_root, run_python_script


def start_command(
	daemon: bool = typer.Option(True, "--daemon/--foreground", help="Ejecutar supervisor en background."),
) -> None:
	"""Start OpenAgno gateway."""
	root = project_root()

	if daemon:
		pid = run_python_script("service_manager.py", ["start"], root=root, detach=True)
		console.print(f"[green]Supervisor iniciado en background.[/green] PID={pid}")
		return

	raise typer.Exit(code=run_python_script("gateway.py", [], root=root, detach=False))
