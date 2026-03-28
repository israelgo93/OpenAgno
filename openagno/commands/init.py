"""`openagno init` command."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

from openagno.commands._common import console, copy_template_workspace


def init_command(
	template: Optional[str] = typer.Option(None, help="Template de workspace a usar."),
	directory: Path = typer.Option(Path("."), help="Directorio raiz del proyecto."),
	force: bool = typer.Option(False, help="Sobrescribir workspace existente."),
) -> None:
	"""Create a workspace interactively or from a packaged template."""
	root = directory.resolve()
	root.mkdir(parents=True, exist_ok=True)

	if template:
		copy_template_workspace(template, root=root, force=force)
		console.print("[green]Workspace inicializado desde template.[/green]")
		return

	cwd = Path.cwd()
	try:
		os.chdir(root)
		from management.cli import run_onboarding

		run_onboarding()
	finally:
		os.chdir(cwd)
