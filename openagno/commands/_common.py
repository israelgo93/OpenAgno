"""Shared helpers for OpenAgno Typer commands."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console

console = Console()


def project_root() -> Path:
	return Path(os.getenv("OPENAGNO_ROOT", Path.cwd())).resolve()


def workspace_dir(root: Path | None = None) -> Path:
	base = root or project_root()
	return base / "workspace"


def ensure_workspace_exists(root: Path | None = None) -> Path:
	ws = workspace_dir(root)
	if not ws.exists():
		console.print("[red]Workspace no encontrado. Ejecuta `openagno init` primero.[/red]")
		raise typer.Exit(code=1)
	return ws


def load_yaml_file(path: Path) -> dict[str, Any]:
	if not path.exists():
		return {}
	return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml_file(path: Path, data: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
		encoding="utf-8",
	)


def read_template_registry() -> list[dict[str, Any]]:
	registry_resource = files("openagno.templates").joinpath("registry.yaml")
	with as_file(registry_resource) as registry_path:
		registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
	return registry.get("templates", [])


def get_template_definition(template_id: str) -> dict[str, Any]:
	for template in read_template_registry():
		if template.get("id") == template_id:
			return template
	console.print(f"[red]Template no encontrado: {template_id}[/red]")
	raise typer.Exit(code=1)


def copy_template_workspace(template_id: str, root: Path, force: bool = False) -> Path:
	get_template_definition(template_id)
	target_workspace = workspace_dir(root)

	if target_workspace.exists() and any(target_workspace.iterdir()) and not force:
		console.print(
			f"[red]El workspace destino ya existe en {target_workspace}. Usa --force para sobrescribir.[/red]"
		)
		raise typer.Exit(code=1)

	if target_workspace.exists() and force:
		shutil.rmtree(target_workspace)

	template_resource = files("openagno.templates").joinpath(template_id)
	with as_file(template_resource) as template_path:
		shutil.copytree(template_path, target_workspace, dirs_exist_ok=True)

	console.print(f"[green]Template '{template_id}' copiado en {target_workspace}[/green]")
	return target_workspace


def sanitize_agent_id(name: str) -> str:
	value = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
	while "--" in value:
		value = value.replace("--", "-")
	return value or "agent"


def read_config(root: Path | None = None) -> dict[str, Any]:
	ws = ensure_workspace_exists(root)
	return load_yaml_file(ws / "config.yaml")


def update_channels(root: Path, channel: str, extra_config: dict[str, Any] | None = None) -> None:
	config_path = ensure_workspace_exists(root) / "config.yaml"
	config = load_yaml_file(config_path)
	channels = config.setdefault("channels", [])
	if channel not in channels:
		channels.append(channel)
	if extra_config:
		current = config.setdefault(channel, {})
		if isinstance(current, dict):
			current.update(extra_config)
	write_yaml_file(config_path, config)


def toggle_optional_tool(root: Path, tool_name: str, enabled: bool = True) -> None:
	tools_path = ensure_workspace_exists(root) / "tools.yaml"
	tools_config = load_yaml_file(tools_path)
	optional = tools_config.setdefault("optional", [])

	for tool in optional:
		if tool.get("name") == tool_name:
			tool["enabled"] = enabled
			write_yaml_file(tools_path, tools_config)
			return

	optional.append({"name": tool_name, "enabled": enabled})
	write_yaml_file(tools_path, tools_config)


def run_python_script(script_name: str, args: list[str], root: Path, detach: bool = False) -> int:
	command = [sys.executable, script_name, *args]
	if detach:
		process = subprocess.Popen(
			command,
			cwd=str(root),
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			start_new_session=True,
			env={**os.environ, "OPENAGNO_ROOT": str(root)},
		)
		return process.pid

	result = subprocess.run(
		command,
		cwd=str(root),
		env={**os.environ, "OPENAGNO_ROOT": str(root)},
		check=False,
	)
	return result.returncode


def tail_file(path: Path, follow: bool = False, lines: int = 80) -> None:
	if not path.exists():
		console.print(f"[yellow]Log no encontrado: {path}[/yellow]")
		raise typer.Exit(code=1)

	content = path.read_text(encoding="utf-8", errors="replace").splitlines()
	for line in content[-lines:]:
		console.print(line)

	if not follow:
		return

	console.print("[dim]Siguiendo logs. Presiona Ctrl+C para salir.[/dim]")
	last_size = path.stat().st_size
	try:
		while True:
			time.sleep(1)
			current_size = path.stat().st_size
			if current_size == last_size:
				continue
			with path.open("r", encoding="utf-8", errors="replace") as handle:
				handle.seek(last_size)
				for line in handle:
					console.print(line.rstrip("\n"))
			last_size = current_size
	except KeyboardInterrupt:
		console.print("\n[dim]Logs finalizados.[/dim]")
