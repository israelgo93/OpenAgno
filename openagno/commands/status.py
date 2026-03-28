"""`openagno status` command."""

from __future__ import annotations

from openagno.commands._common import project_root


def status_command() -> None:
	"""Show current workspace and runtime status."""
	_ = project_root()
	from management.cli import run_status

	run_status()
