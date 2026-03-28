"""`openagno stop` command."""

from __future__ import annotations

import typer

from openagno.commands._common import project_root, run_python_script


def stop_command() -> None:
	"""Stop background supervisor."""
	root = project_root()
	raise typer.Exit(code=run_python_script("service_manager.py", ["stop"], root=root, detach=False))
