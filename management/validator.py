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
	if provider in key_map:
		env_key = key_map[provider]
		if not os.getenv(env_key):
			errors.append(f".env: falta {env_key} (requerido para provider '{provider}')")

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

	try:
		with open(ws / "tools.yaml", "r", encoding="utf-8") as f:
			tools = yaml.safe_load(f) or {}
	except yaml.YAMLError as e:
		errors.append(f"tools.yaml tiene YAML invalido: {e}")
		return errors

	for tool_def in tools.get("optional", []):
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

	return errors


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
	sys.exit(1 if errors else 0)
