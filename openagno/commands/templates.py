"""`openagno templates ...` commands."""

from __future__ import annotations

import typer

from openagno.commands._common import get_template_definition, read_template_registry
from openagno.commands._output import header, step_info

templates_app = typer.Typer(help="Inspect packaged workspace templates.")


@templates_app.command("list")
def list_templates() -> None:
	"""List available workspace templates."""
	header("Available templates")
	for template in read_template_registry():
		step_info(f"{template['id']} - {template.get('name', template['id'])}")


@templates_app.command("show")
def show_template(template_id: str) -> None:
	"""Show one template definition."""
	template = get_template_definition(template_id)
	header(template.get("name", template_id))
	step_info(template.get("description", "No description provided."))
	if template.get("channels"):
		step_info(f"Channels: {', '.join(template['channels'])}")
	if template.get("tools"):
		step_info(f"Tools: {', '.join(template['tools'])}")
