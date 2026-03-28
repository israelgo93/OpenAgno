"""`openagno templates ...` commands."""

from __future__ import annotations

import typer

from openagno.commands._common import console, get_template_definition, read_template_registry

templates_app = typer.Typer(help="Inspect packaged workspace templates.")


@templates_app.command("list")
def list_templates() -> None:
	"""List available workspace templates."""
	for template in read_template_registry():
		console.print(f"[cyan]{template['id']}[/cyan] - {template.get('name', template['id'])}")


@templates_app.command("show")
def show_template(template_id: str) -> None:
	"""Show one template definition."""
	template = get_template_definition(template_id)
	console.print(f"[bold]{template.get('name', template_id)}[/bold]")
	console.print(template.get("description", "Sin descripcion"))
	if template.get("channels"):
		console.print(f"Canales: {', '.join(template['channels'])}")
	if template.get("tools"):
		console.print(f"Tools: {', '.join(template['tools'])}")
