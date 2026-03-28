"""`openagno create ...` commands."""

from __future__ import annotations

from typing import List, Optional

import typer

from openagno.commands._common import console, project_root, sanitize_agent_id

create_app = typer.Typer(help="Create resources inside the workspace.")


@create_app.command("agent")
def create_agent(
	name: str = typer.Argument(..., help="Nombre del sub-agente."),
	role: str = typer.Option("General assistant", help="Rol del sub-agente."),
	agent_id: Optional[str] = typer.Option(None, help="ID interno del sub-agente."),
	tool: List[str] = typer.Option(None, "--tool", help="Tool habilitado para el sub-agente."),
	instruction: List[str] = typer.Option(None, "--instruction", help="Instruccion adicional."),
	provider: str = typer.Option("google", help="Provider del modelo."),
	model_id: str = typer.Option("gemini-2.5-flash", help="ID del modelo."),
) -> None:
	"""Create a workspace sub-agent YAML."""
	_ = project_root()
	from tools.workspace_tools import WorkspaceTools

	workspace_tools = WorkspaceTools()
	result = workspace_tools.create_sub_agent(
		name=name,
		agent_id=agent_id or sanitize_agent_id(name),
		role=role,
		tools=tool or [],
		instructions=instruction or [f"Eres {name}. Mantente enfocado en tu rol."],
		model_provider=provider,
		model_id=model_id,
	)
	console.print(result)
