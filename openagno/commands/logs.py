"""`openagno logs` command."""

from __future__ import annotations

import typer

from openagno.commands._common import project_root, tail_file
from openagno.commands._output import header, step_info


def logs_command(
	follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs in real time."),
	lines: int = typer.Option(80, min=1, help="Number of lines to show."),
) -> None:
	"""Tail gateway logs."""
	root = project_root()
	header("Gateway logs")
	step_info(f"Reading `{root / 'gateway.log'}`")
	tail_file(root / "gateway.log", follow=follow, lines=lines)
