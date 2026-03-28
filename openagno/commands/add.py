"""`openagno add ...` commands."""

from __future__ import annotations

import typer

from openagno.commands._common import (
	console,
	project_root,
	toggle_optional_tool,
	update_channels,
	update_config_section,
)

add_app = typer.Typer(help="Add channels and tools to the current workspace.")


@add_app.command("whatsapp")
def add_whatsapp(
	mode: str = typer.Option("cloud_api", help="Modo WhatsApp: cloud_api, qr_link o dual."),
) -> None:
	root = project_root()
	update_channels(root, "whatsapp", {"mode": mode})
	console.print(f"[green]Canal WhatsApp agregado.[/green] mode={mode}")


@add_app.command("slack")
def add_slack() -> None:
	root = project_root()
	update_channels(root, "slack")
	console.print("[green]Canal Slack agregado.[/green]")


@add_app.command("telegram")
def add_telegram() -> None:
	root = project_root()
	update_channels(root, "telegram")
	console.print("[green]Canal Telegram agregado.[/green]")


@add_app.command("agui")
def add_agui() -> None:
	root = project_root()
	update_channels(root, "agui")
	console.print("[green]Canal AG-UI agregado.[/green]")


@add_app.command("a2a")
def add_a2a() -> None:
	root = project_root()
	update_config_section(root, "a2a", {"enabled": True})
	console.print("[green]Protocolo A2A habilitado.[/green]")


@add_app.command("tool")
def add_tool(
	tool_name: str = typer.Argument(..., help="Nombre del tool opcional."),
	enable: bool = typer.Option(True, "--enable/--disable", help="Activar o desactivar el tool."),
) -> None:
	root = project_root()
	toggle_optional_tool(root, tool_name, enabled=enable)
	state = "activado" if enable else "desactivado"
	console.print(f"[green]Tool {tool_name} {state}.[/green]")
