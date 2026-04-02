"""`openagno validate` command."""

from __future__ import annotations

import typer

from openagno.commands._common import ensure_workspace_exists, project_root


def validate_command() -> None:
    """Validate the current workspace."""
    root = project_root()
    ws = ensure_workspace_exists(root)

    from management.validator import (
        print_validation,
        validate_workspace,
        workspace_warnings,
    )

    errors = validate_workspace(str(ws))
    warnings = workspace_warnings(str(ws))

    if errors:
        print_validation(errors)
        for warning in warnings:
            typer.echo(f"Warning: {warning}")
        typer.echo("Fix the validation errors, then run `openagno validate` again.")
        raise typer.Exit(code=1)

    typer.echo("Workspace is valid.")
    for warning in warnings:
        typer.echo(f"Warning: {warning}")
