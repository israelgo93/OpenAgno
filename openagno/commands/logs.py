"""`openagno logs` command."""

from __future__ import annotations

from pathlib import Path

import typer

from openagno.commands._common import project_root, tail_file


def logs_command(
	follow: bool = typer.Option(False, "--follow", "-f", help="Seguir logs en tiempo real."),
	lines: int = typer.Option(80, min=1, help="Numero de lineas a mostrar."),
) -> None:
	"""Tail gateway logs."""
	root = project_root()
	tail_file(root / "gateway.log", follow=follow, lines=lines)
