"""`openagno status` command."""

from __future__ import annotations

import json
import urllib.request

from openagno.commands._common import project_root, read_config
from openagno.commands._output import header, step_info, step_ok, step_warn
from openagno.core.process_utils import is_pid_running, read_pid_file


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.loads(response.read())


def status_command() -> None:
    """Show current workspace and runtime status."""
    root = project_root()
    config = read_config(root)

    agent = config.get("agent", {})
    model = config.get("model", {})
    fallback = config.get("fallback", {})
    channels = config.get("channels", [])
    db = config.get("database", {})
    agentos = config.get("agentos", {})
    whatsapp = config.get("whatsapp", {})

    header("OpenAgno status")
    step_info(f"Agent: {agent.get('name', '?')}")
    step_info(f"Model: {model.get('provider', '?')}/{model.get('id', '?')}")
    if fallback.get("id"):
        step_info(f"Fallback: {fallback.get('provider', model.get('provider', '?'))}/{fallback['id']}")
    step_info(f"Database: {db.get('type', '?')}")
    step_info(f"Channels: {', '.join(channels) if channels else 'none'}")
    if "whatsapp" in channels:
        step_info(f"WhatsApp mode: {whatsapp.get('mode', 'cloud_api')}")

    pid_file = root / "openagno.pid"
    pid = read_pid_file(pid_file)
    if pid and is_pid_running(pid):
        step_ok(f"Supervisor: running (PID {pid})")
    else:
        step_warn("Supervisor: not running")

    port = agentos.get("port", 8000)
    health_url = f"http://127.0.0.1:{port}/admin/health"
    try:
        health = _fetch_json(health_url)
        step_ok(f"Gateway health: OK on :{port}")
        model_info = health.get("model", {})
        if model_info:
            step_info(
                "Runtime model: "
                f"{model_info.get('provider', '?')}/{model_info.get('id', '?')}"
            )
        if health.get("agents"):
            step_info(f"Loaded agents: {', '.join(health['agents'])}")
        if health.get("channels"):
            step_info(f"Runtime channels: {', '.join(health['channels'])}")
        if model_info.get("fallback_active"):
            step_warn(f"Fallback active: {model_info.get('fallback_id', '?')}")
    except Exception:
        step_warn(f"Gateway health: unreachable on :{port}")

    if whatsapp.get("mode") in ("qr_link", "dual"):
        try:
            qr_status = _fetch_json("http://127.0.0.1:3001/status")
            step_ok(f"WhatsApp QR bridge: {qr_status.get('status', 'unknown')}")
        except Exception:
            step_warn("WhatsApp QR bridge: unreachable on :3001")
