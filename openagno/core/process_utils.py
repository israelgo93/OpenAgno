"""Cross-platform process helpers for OpenAgno supervisors."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

IS_WINDOWS = os.name == "nt"


def detached_process_kwargs() -> dict[str, int | bool]:
    """Return platform-specific kwargs for detached subprocesses."""
    if IS_WINDOWS:
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": creationflags}
    return {"start_new_session": True}


def read_pid_file(path: Path) -> int | None:
    """Read a PID file if it contains a valid integer."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def is_pid_running(pid: int) -> bool:
    """Check whether a process is currently alive."""
    if pid <= 0:
        return False

    if IS_WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_pid(pid: int, timeout: int = 10) -> bool:
    """Terminate a process tree and wait until it exits."""
    if pid <= 0:
        return False

    if not is_pid_running(pid):
        return False

    if IS_WINDOWS:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 or not is_pid_running(pid)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_pid_running(pid):
            return True
        time.sleep(0.25)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True

    return not is_pid_running(pid)
