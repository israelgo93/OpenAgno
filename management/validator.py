"""
Validator - Valida el workspace/ antes de arrancar el gateway.

Uso:
	python -m management.validator
	# o desde codigo:
	from management.validator import validate_workspace
	errors = validate_workspace()
"""
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

from loader import (
	load_integration_manifests,
	merge_mcp_config_with_integrations,
	merge_tools_config_with_integrations,
	preload_integration_environments,
)

load_dotenv()


def validate_workspace(workspace_dir: Optional[str] = None) -> list[str]:
	"""
	Valida la estructura del workspace y las variables de entorno.
	Retorna lista de errores. Lista vacia = workspace valido.
	"""
	ws = Path(workspace_dir or os.getenv("AGNOBOT_WORKSPACE", "workspace"))
	errors: list[str] = []

	required_files = [
		("config.yaml", "Configuracion central"),
		("instructions.md", "Instrucciones del agente"),
		("tools.yaml", "Configuracion de herramientas"),
		("mcp.yaml", "Configuracion MCP"),
	]
	for filename, desc in required_files:
		if not (ws / filename).exists():
			errors.append(f"Falta {filename} ({desc})")

	if errors:
		return errors

	try:
		with open(ws / "config.yaml", "r", encoding="utf-8") as f:
			config = yaml.safe_load(f) or {}
	except yaml.YAMLError as e:
		errors.append(f"config.yaml tiene YAML invalido: {e}")
		return errors

	for section in ("agent", "model", "database"):
		if section not in config:
			errors.append(f"config.yaml: falta seccion '{section}'")

	model = config.get("model", {})
	provider = model.get("provider", "")
	key_map: dict[str, str] = {
		"google": "GOOGLE_API_KEY",
		"openai": "OPENAI_API_KEY",
		"anthropic": "ANTHROPIC_API_KEY",
	}
	aws_key_map: dict[str, list[str]] = {
		"aws_bedrock": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
		"aws_bedrock_claude": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
	}
	if provider in key_map:
		env_key = key_map[provider]
		if not os.getenv(env_key):
			errors.append(f".env: falta {env_key} (requerido para provider '{provider}')")
	elif provider in aws_key_map:
		for aws_var in aws_key_map[provider]:
			if not os.getenv(aws_var):
				errors.append(f".env: falta {aws_var} (requerido para provider '{provider}')")

	db_config = config.get("database", {})
	db_type = db_config.get("type", "local")

	if db_type in ("supabase", "local"):
		db_vars = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
		for var in db_vars:
			if not os.getenv(var):
				errors.append(f".env: falta {var} (requerido para database.type='{db_type}')")

	if db_type != "sqlite":
		if not os.getenv("OPENAI_API_KEY"):
			errors.append(".env: falta OPENAI_API_KEY (requerido para embeddings)")

	channels = config.get("channels", [])
	if "whatsapp" in channels:
		wa_vars = [
			"WHATSAPP_ACCESS_TOKEN",
			"WHATSAPP_PHONE_NUMBER_ID",
			"WHATSAPP_VERIFY_TOKEN",
		]
		for var in wa_vars:
			if not os.getenv(var):
				errors.append(f".env: falta {var} (requerido para canal WhatsApp)")

	if "slack" in channels:
		if not os.getenv("SLACK_TOKEN"):
			errors.append(".env: falta SLACK_TOKEN (requerido para canal Slack)")
		if not os.getenv("SLACK_SIGNING_SECRET"):
			errors.append(".env: falta SLACK_SIGNING_SECRET (requerido para canal Slack)")

	try:
		with open(ws / "tools.yaml", "r", encoding="utf-8") as f:
			tools_config = yaml.safe_load(f) or {}
	except yaml.YAMLError as e:
		errors.append(f"tools.yaml tiene YAML invalido: {e}")
		return errors

	ws_resolved = ws.resolve()
	integration_manifests = load_integration_manifests(ws_resolved)
	preload_integration_environments(integration_manifests)
	tools_config = merge_tools_config_with_integrations(tools_config, integration_manifests)

	for tool_def in tools_config.get("optional", []):
		if not tool_def.get("enabled", False):
			continue
		name = tool_def.get("name", "")
		if name == "tavily" and not os.getenv("TAVILY_API_KEY"):
			errors.append(".env: falta TAVILY_API_KEY (tool Tavily habilitado)")
		if name == "email":
			for var in ("GMAIL_SENDER", "GMAIL_PASSKEY"):
				if not os.getenv(var):
					errors.append(f".env: falta {var} (tool Email habilitado)")

	dirs = ["knowledge", "agents"]
	for d in dirs:
		dir_path = ws / d
		if not dir_path.exists():
			errors.append(f"Falta directorio workspace/{d}/")

	agents_dir = ws / "agents"
	if agents_dir.exists():
		for yaml_file in agents_dir.glob("*.yaml"):
			if yaml_file.name == "teams.yaml":
				continue
			try:
				with open(yaml_file, "r", encoding="utf-8") as f:
					agent_data = yaml.safe_load(f) or {}
				agent_def = agent_data.get("agent", {})
				if not agent_def:
					errors.append(f"agents/{yaml_file.name}: falta seccion 'agent'")
					continue
				if not agent_def.get("name"):
					errors.append(f"agents/{yaml_file.name}: falta 'name'")
				if not agent_def.get("id"):
					errors.append(f"agents/{yaml_file.name}: falta 'id'")
				sub_model = agent_def.get("model", {})
				sub_provider = sub_model.get("provider", "")
				if sub_provider in key_map:
					sub_key = key_map[sub_provider]
					if not os.getenv(sub_key):
						errors.append(
							f"agents/{yaml_file.name}: .env falta {sub_key} "
							f"(requerido para provider '{sub_provider}')"
						)
				elif sub_provider in aws_key_map:
					for aws_var in aws_key_map[sub_provider]:
						if not os.getenv(aws_var):
							errors.append(
								f"agents/{yaml_file.name}: .env falta {aws_var} "
								f"(requerido para provider '{sub_provider}')"
							)
			except yaml.YAMLError as e:
				errors.append(f"agents/{yaml_file.name}: YAML invalido: {e}")

	teams_file = ws / "agents" / "teams.yaml"
	if teams_file.exists():
		try:
			with open(teams_file, "r", encoding="utf-8") as f:
				teams_data = yaml.safe_load(f) or {}
			for team in teams_data.get("teams", []):
				team_name = team.get("name", "sin nombre")
				members = team.get("members", [])
				if len(members) < 2:
					errors.append(
						f"teams.yaml: team '{team_name}' necesita al menos 2 miembros"
					)
				if not team.get("model"):
					errors.append(
						f"teams.yaml: team '{team_name}' no tiene modelo configurado"
					)
		except yaml.YAMLError as e:
			errors.append(f"teams.yaml: YAML invalido: {e}")

	try:
		schedules_config = yaml.safe_load(
			(ws / "schedules.yaml").read_text(encoding="utf-8")
		) or {}
	except (yaml.YAMLError, FileNotFoundError):
		schedules_config = {}

	for sched in schedules_config.get("schedules", []):
		if not sched.get("enabled", True):
			continue
		name = sched.get("name", "sin-nombre")
		if not sched.get("cron"):
			errors.append(f"schedules.yaml: schedule '{name}' habilitado sin 'cron'")
		if not sched.get("message"):
			errors.append(f"schedules.yaml: schedule '{name}' habilitado sin 'message'")
		if not sched.get("agent_id"):
			errors.append(f"schedules.yaml: schedule '{name}' habilitado sin 'agent_id'")
		cron = sched.get("cron", "")
		if cron and len(cron.split()) != 5:
			errors.append(
				f"schedules.yaml: schedule '{name}' tiene cron invalido "
				f"(esperados 5 campos, recibidos {len(cron.split())})"
			)

	try:
		urls_config = yaml.safe_load(
			(ws / "knowledge" / "urls.yaml").read_text(encoding="utf-8")
		) or {}
	except (yaml.YAMLError, FileNotFoundError):
		urls_config = {}

	for url_entry in urls_config.get("urls", []):
		url = url_entry.get("url", "")
		if not url:
			errors.append("knowledge/urls.yaml: entrada sin 'url'")
		elif not url.startswith("http"):
			errors.append(f"knowledge/urls.yaml: URL invalida: {url}")

	try:
		mcp_config = yaml.safe_load(
			(ws / "mcp.yaml").read_text(encoding="utf-8")
		) or {}
	except (yaml.YAMLError, FileNotFoundError):
		mcp_config = {}

	mcp_config = merge_mcp_config_with_integrations(mcp_config, integration_manifests)

	tavily_mcp_enabled = False
	for server in mcp_config.get("servers", []):
		if not server.get("enabled", False):
			continue
		srv_name = server.get("name", "sin-nombre")
		transport = server.get("transport", "")

		if transport in ("streamable-http", "sse"):
			if not server.get("url"):
				errors.append(f"mcp.yaml: server '{srv_name}' habilitado sin 'url'")
		elif transport == "stdio":
			if not server.get("command"):
				errors.append(f"mcp.yaml: server '{srv_name}' habilitado sin 'command'")
			if srv_name == "supabase" and not os.getenv("SUPABASE_ACCESS_TOKEN"):
				errors.append(".env: falta SUPABASE_ACCESS_TOKEN (MCP Supabase habilitado)")
			if srv_name == "github" and not os.getenv("GITHUB_TOKEN"):
				errors.append(".env: falta GITHUB_TOKEN (MCP GitHub habilitado)")

		if srv_name == "tavily":
			tavily_mcp_enabled = True

	tavily_tool_enabled = False
	for tool in tools_config.get("optional", []):
		if tool.get("name") == "tavily" and tool.get("enabled", False):
			tavily_tool_enabled = True

	if (tavily_tool_enabled or tavily_mcp_enabled) and not os.getenv("TAVILY_API_KEY"):
		errors.append(".env: falta TAVILY_API_KEY (Tavily tool o MCP habilitado)")

	return errors


def workspace_warnings(workspace_dir: Optional[str] = None) -> list[str]:
	"""
	Advertencias no bloqueantes (p. ej. ShellTools habilitado).
	"""
	ws = Path(workspace_dir or os.getenv("AGNOBOT_WORKSPACE", "workspace"))
	warnings: list[str] = []
	tools_path = ws / "tools.yaml"
	if not tools_path.exists():
		return warnings
	try:
		with open(tools_path, "r", encoding="utf-8") as f:
			tools_config = yaml.safe_load(f) or {}
	except yaml.YAMLError:
		return warnings

	ws_resolved = ws.resolve()
	manifests = load_integration_manifests(ws_resolved)
	tools_config = merge_tools_config_with_integrations(tools_config, manifests)

	for tool_def in tools_config.get("optional", []):
		if tool_def.get("name") != "shell" or not tool_def.get("enabled", False):
			continue
		warnings.append(
			"ShellTools habilitado: riesgo elevado; el cwd del subprocess esta acotado por base_dir. "
			"Define OPENAGNO_ROOT en .env con la ruta absoluta del repo. "
			"Sigue workspace/knowledge/docs/AGENT_OPERACIONES.md para backup, validacion y reinicio."
		)
		if not os.getenv("OPENAGNO_ROOT", "").strip():
			warnings.append(
				"OPENAGNO_ROOT no definida: el loader usara la raiz del repo inferida desde loader.py."
			)
		break

	return warnings


def print_validation(errors: list[str]) -> None:
	"""Imprime resultados de validacion con formato."""
	if not errors:
		print("\nWorkspace valido - listo para arrancar")
		return

	print(f"\nSe encontraron {len(errors)} error(es) en el workspace:\n")
	for i, error in enumerate(errors, 1):
		print(f"  {i}. {error}")
	print()
	print("Corrige estos errores antes de ejecutar gateway.py")
	print("Tip: ejecuta 'python -m management.cli' para regenerar el workspace")


if __name__ == "__main__":
	errors = validate_workspace()
	print_validation(errors)
	for w in workspace_warnings():
		print(f"  Advertencia: {w}")
	sys.exit(1 if errors else 0)
