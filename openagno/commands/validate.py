"""`openagno validate` command."""

from __future__ import annotations

import typer

from openagno.commands._common import ensure_workspace_exists, project_root
from openagno.commands._output import header, next_step, step_error, step_ok, step_warn


def validate_command() -> None:
	"""Validate the current workspace."""
	root = project_root()
	ws = ensure_workspace_exists(root)
	from management.validator import validate_workspace, workspace_warnings

	header("Validating workspace...")
	errors = validate_workspace(str(ws))
	warnings = workspace_warnings(str(ws))
	if errors:
		for error in errors:
			step_error(error)
		next_step("Fix the validation errors, then run `openagno validate` again.")
		raise typer.Exit(code=1)

	step_ok("Workspace is valid.")
	for warning in warnings:
		step_warn(warning)
	raise typer.Exit(code=1 if errors else 0)
