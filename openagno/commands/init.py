"""`openagno init` command."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

from openagno.commands._common import copy_template_workspace
from openagno.commands._output import header, next_step, step_info, step_ok


def init_command(
	template: Optional[str] = typer.Option(None, help="Workspace template to use."),
	directory: Path = typer.Option(Path("."), help="Project root directory."),
	force: bool = typer.Option(False, help="Overwrite an existing workspace."),
) -> None:
	"""Create a workspace interactively or from a packaged template."""
	root = directory.resolve()
	root.mkdir(parents=True, exist_ok=True)

	if template:
		header("Initializing OpenAgno...")
		step_info(f"Copying template `{template}` into `{root / 'workspace'}`")
		copy_template_workspace(template, root=root, force=force)
		step_ok("Workspace initialized from packaged template.")
		next_step("Fill in `.env`, then run `openagno validate`.")
		return

	header("Initializing OpenAgno...")
	step_info("Launching the interactive setup wizard.")
	step_info("This path still uses the legacy onboarding flow internally.")
	cwd = Path.cwd()
	try:
		os.chdir(root)
		from management.cli import run_onboarding

		run_onboarding()
	finally:
		os.chdir(cwd)
	next_step("Run `openagno validate` before starting the runtime.")
