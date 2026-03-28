"""`openagno restart` command."""

from __future__ import annotations

import typer

from openagno.commands._common import console, project_root, run_python_script


def restart_command() -> None:
	"""Restart the background supervisor."""
	root = project_root()
	run_python_script("service_manager.py", ["stop"], root=root, detach=False)
	pid = run_python_script("service_manager.py", ["start"], root=root, detach=True)
	console.print(f"[green]Supervisor reiniciado.[/green] PID={pid}")
