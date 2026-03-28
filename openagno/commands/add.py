"""`openagno add ...` commands."""

from __future__ import annotations

import typer

from openagno.commands._common import (
	project_root,
	toggle_optional_tool,
	update_channels,
	update_config_section,
)
from openagno.commands._output import header, next_step, step_info, step_ok

add_app = typer.Typer(help="Add channels and tools to the current workspace.")


@add_app.command("whatsapp")
def add_whatsapp(
	mode: str = typer.Option("cloud_api", help="WhatsApp mode: cloud_api, qr_link, or dual."),
) -> None:
	root = project_root()
	header("Updating workspace...")
	step_info(f"Adding WhatsApp with mode `{mode}`")
	update_channels(root, "whatsapp", {"mode": mode})
	step_ok("WhatsApp channel added.")
	next_step("Add the required WhatsApp environment variables to `.env`.")


@add_app.command("slack")
def add_slack() -> None:
	root = project_root()
	header("Updating workspace...")
	step_info("Adding Slack channel")
	update_channels(root, "slack")
	step_ok("Slack channel added.")
	next_step("Set `SLACK_TOKEN` and `SLACK_SIGNING_SECRET` in `.env`.")


@add_app.command("telegram")
def add_telegram() -> None:
	root = project_root()
	header("Updating workspace...")
	step_info("Adding Telegram channel")
	update_channels(root, "telegram")
	step_ok("Telegram channel added.")
	next_step("Set `TELEGRAM_TOKEN` in `.env`.")


@add_app.command("agui")
def add_agui() -> None:
	root = project_root()
	header("Updating workspace...")
	step_info("Adding AG-UI channel")
	update_channels(root, "agui")
	step_ok("AG-UI channel added.")
	next_step("Install `.[protocols]` before exposing AG-UI in runtime.")


@add_app.command("a2a")
def add_a2a() -> None:
	root = project_root()
	header("Updating workspace...")
	step_info("Enabling A2A protocol")
	update_config_section(root, "a2a", {"enabled": True})
	step_ok("A2A protocol enabled.")
	next_step("Install `.[protocols]` before using A2A endpoints.")


@add_app.command("tool")
def add_tool(
	tool_name: str = typer.Argument(..., help="Optional tool name."),
	enable: bool = typer.Option(True, "--enable/--disable", help="Enable or disable the tool."),
) -> None:
	root = project_root()
	header("Updating workspace...")
	step_info(f"{'Enabling' if enable else 'Disabling'} optional tool `{tool_name}`")
	toggle_optional_tool(root, tool_name, enabled=enable)
	state = "enabled" if enable else "disabled"
	step_ok(f"Tool `{tool_name}` {state}.")
	next_step("Run `openagno validate` if the tool requires new environment variables.")
