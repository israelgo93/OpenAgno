"""`openagno start` command."""

from __future__ import annotations

import typer

from openagno.commands._common import project_root, run_python_script
from openagno.commands._output import header, next_step, step_info, step_ok


def start_command(
	daemon: bool = typer.Option(True, "--daemon/--foreground", help="Run supervisor in background."),
) -> None:
	"""Start OpenAgno gateway."""
	root = project_root()

	if daemon:
		header("Starting OpenAgno...")
		step_info("Launching the local supervisor in background.")
		pid = run_python_script("service_manager.py", ["start"], root=root, detach=True)
		step_ok(f"Supervisor started in background with PID {pid}.")
		next_step("Run `openagno status` or `openagno logs --follow`.")
		return

	header("Starting OpenAgno...")
	step_info("Running gateway in foreground mode.")
	raise typer.Exit(code=run_python_script("gateway.py", [], root=root, detach=False))
