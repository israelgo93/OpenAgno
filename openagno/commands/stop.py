"""`openagno stop` command."""

from __future__ import annotations

import typer

from openagno.commands._common import project_root
from openagno.commands._output import header, step_error, step_info, step_ok
from openagno.core.process_utils import is_pid_running, read_pid_file, terminate_pid


def stop_command() -> None:
	"""Stop background supervisor."""
	root = project_root()
	pid_file = root / "openagno.pid"
	pid = read_pid_file(pid_file)

	header("Stopping OpenAgno...")
	if pid is None or not is_pid_running(pid):
		if pid_file.exists():
			pid_file.unlink(missing_ok=True)
		step_info("No running supervisor process was found.")
		return

	if not terminate_pid(pid):
		step_error(f"Failed to stop supervisor PID {pid}.")
		raise typer.Exit(code=1)

	pid_file.unlink(missing_ok=True)
	step_ok(f"Supervisor PID {pid} stopped.")
