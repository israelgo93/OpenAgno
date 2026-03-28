"""`openagno restart` command."""

from __future__ import annotations

import typer

from openagno.commands._common import project_root, run_python_script
from openagno.commands._output import header, next_step, step_info, step_ok
from openagno.core.process_utils import is_pid_running, read_pid_file, terminate_pid


def restart_command() -> None:
	"""Restart the background supervisor."""
	root = project_root()
	pid_file = root / "openagno.pid"
	pid = read_pid_file(pid_file)

	header("Restarting OpenAgno...")
	if pid is not None and is_pid_running(pid):
		step_info(f"Stopping supervisor PID {pid}")
		terminate_pid(pid)
		pid_file.unlink(missing_ok=True)
	else:
		step_info("No running supervisor found. Starting a fresh one instead.")

	pid = run_python_script("service_manager.py", ["start"], root=root, detach=True)
	step_ok(f"Supervisor restarted with PID {pid}.")
	next_step("Run `openagno status` to confirm runtime health.")
