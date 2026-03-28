"""`openagno create ...` commands."""

from __future__ import annotations

from typing import List, Optional

import typer

from openagno.commands._common import project_root, sanitize_agent_id
from openagno.commands._output import header, next_step, step_error, step_info, step_ok

create_app = typer.Typer(help="Create resources inside the workspace.")


@create_app.command("agent")
def create_agent(
	name: str = typer.Argument(..., help="Sub-agent display name."),
	role: str = typer.Option("General assistant", help="Sub-agent role."),
	agent_id: Optional[str] = typer.Option(None, help="Internal sub-agent ID."),
	tool: List[str] = typer.Option(None, "--tool", help="Tool enabled for the sub-agent."),
	instruction: List[str] = typer.Option(None, "--instruction", help="Additional instruction."),
	provider: str = typer.Option("google", help="Model provider."),
	model_id: str = typer.Option("gemini-2.5-flash", help="Model ID."),
) -> None:
	"""Create a workspace sub-agent YAML."""
	_ = project_root()
	agent_file = f"workspace/agents/{(agent_id or sanitize_agent_id(name)).replace('-', '_')}.yaml"
	header("Creating agent...")
	step_info(f"Writing manifest for `{name}`")
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
	if result.startswith("ERROR:"):
		step_error(result.replace("ERROR: ", "", 1))
		raise typer.Exit(code=1)
	step_ok(f"Agent `{name}` created.")
	step_info(f"Manifest: `{agent_file}`")
	next_step("Run `openagno restart` to load the new agent.")
