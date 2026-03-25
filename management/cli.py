"""
CLI de Onboarding v3 - Genera el workspace/ completo.

Ejecutar:
	python -m management.cli

Genera:
	workspace/config.yaml
	workspace/instructions.md
	workspace/tools.yaml
	workspace/mcp.yaml
	workspace/knowledge/urls.yaml
	workspace/agents/teams.yaml
	.env
"""
import os
import yaml
from pathlib import Path

from management.validator import validate_workspace, print_validation


def _write_yaml(path: Path, data: dict) -> None:
	"""Escribe un dict como YAML con formato legible."""
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _prompt(text: str, default: str = "") -> str:
	"""Input con valor por defecto."""
	suffix = f" [{default}]" if default else ""
	value = input(f"  {text}{suffix}: ").strip()
	return value or default


def _prompt_choice(text: str, options: dict[str, str], default: str = "1") -> str:
	"""Input de seleccion numerica."""
	print(f"\n{text}")
	for key, label in options.items():
		print(f"  [{key}] {label}")
	return input(f"  Seleccion [{default}]: ").strip() or default


def _prompt_yn(text: str, default: bool = False) -> bool:
	"""Input si/no."""
	suffix = "[s/N]" if not default else "[S/n]"
	value = input(f"  {text} {suffix}: ").strip().lower()
	if not value:
		return default
	return value in ("s", "si", "y", "yes")


def run_onboarding() -> None:
	"""Wizard interactivo que genera el workspace/ con toda la configuracion."""
	workspace_dir = Path("workspace")

	print()
	print("=" * 50)
	print("  OpenAgno - Setup Wizard v3")
	print("  Generador de Workspace Parametrizable")
	print("=" * 50)

	# -- PASO 1: Identidad --
	print("\nPASO 1: Identidad del agente")
	agent_name = _prompt("Nombre del agente", "AgnoBot")
	agent_desc = _prompt("Descripcion breve", "Asistente personal multimodal")

	choice = _prompt_choice("Instrucciones del agente?", {
		"1": "Usar instrucciones por defecto",
		"2": "Escribir instrucciones personalizadas",
	})
	custom_instructions = None
	if choice == "2":
		print("  Escribe las instrucciones (linea vacia para terminar):")
		lines: list[str] = []
		while True:
			line = input("  > ")
			if not line:
				break
			lines.append(line)
		custom_instructions = "\n".join(lines)

	# -- PASO 2: Modelo --
	model_options = {
		"1": "Gemini 2.0 Flash (Google - multimodal, recomendado)",
		"2": "Claude Sonnet 4 (Anthropic)",
		"3": "GPT-4.1 (OpenAI)",
		"4": "GPT-5-mini (OpenAI)",
	}
	model_choice = _prompt_choice("PASO 2: Modelo de IA", model_options)

	model_map: dict[str, tuple[str, str, str]] = {
		"1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
		"2": ("anthropic", "claude-sonnet-4-0", "ANTHROPIC_API_KEY"),
		"3": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
		"4": ("openai", "gpt-5-mini", "OPENAI_API_KEY"),
	}
	provider, model_id, key_name = model_map.get(model_choice, model_map["1"])
	api_key = _prompt(f"-> {key_name}")

	# -- PASO 3: Base de datos --
	db_options = {
		"1": "Supabase (PostgreSQL managed - recomendado)",
		"2": "PostgreSQL local (Docker)",
		"3": "SQLite (solo desarrollo, sin RAG)",
	}
	db_choice = _prompt_choice("PASO 3: Base de datos", db_options)
	db_type = {"1": "supabase", "2": "local", "3": "sqlite"}.get(db_choice, "supabase")

	db_vars: dict[str, str] = {}
	if db_type == "supabase":
		print("\n  Configuracion Supabase (Session Pooler):")
		db_vars["DB_HOST"] = _prompt("DB Host")
		db_vars["DB_PORT"] = _prompt("DB Port", "5432")
		db_vars["DB_USER"] = _prompt("DB User")
		db_vars["DB_PASSWORD"] = _prompt("DB Password")
		db_vars["DB_NAME"] = _prompt("DB Name", "postgres")
		db_vars["DB_SSLMODE"] = "require"
	elif db_type == "local":
		db_vars = {
			"DB_HOST": "localhost",
			"DB_PORT": "5532",
			"DB_USER": "ai",
			"DB_PASSWORD": "ai",
			"DB_NAME": "ai",
			"DB_SSLMODE": "prefer",
		}
		print("\n  Ejecuta: docker compose up -d db")

	# -- PASO 4: Canales --
	channel_options = {
		"1": "WhatsApp",
		"2": "Slack",
		"3": "WhatsApp + Slack",
	}
	channel_choice = _prompt_choice("PASO 4: Canales (Web siempre disponible)", channel_options)
	channels: list[str] = {
		"1": ["whatsapp"], "2": ["slack"], "3": ["whatsapp", "slack"],
	}.get(channel_choice, ["whatsapp"])

	whatsapp_vars: dict[str, str] = {}
	if "whatsapp" in channels:
		print("\n  Configuracion WhatsApp (Meta Business API):")
		whatsapp_vars["WHATSAPP_ACCESS_TOKEN"] = _prompt("Access Token")
		whatsapp_vars["WHATSAPP_PHONE_NUMBER_ID"] = _prompt("Phone Number ID")
		whatsapp_vars["WHATSAPP_VERIFY_TOKEN"] = _prompt("Verify Token")
		whatsapp_vars["WHATSAPP_WEBHOOK_URL"] = _prompt("Webhook URL")

	slack_vars: dict[str, str] = {}
	if "slack" in channels:
		print("\n  Configuracion Slack:")
		slack_vars["SLACK_TOKEN"] = _prompt("Bot Token")

	# -- PASO 5: Tools --
	print("\nPASO 5: Herramientas adicionales")
	email_enabled = _prompt_yn("Activar Gmail?")
	tavily_enabled = _prompt_yn("Activar Tavily (busqueda web avanzada)?")

	email_vars: dict[str, str] = {}
	if email_enabled:
		email_vars["GMAIL_SENDER"] = _prompt("Email remitente")
		email_vars["GMAIL_PASSKEY"] = _prompt("App password")
		email_vars["GMAIL_RECEIVER"] = _prompt("Email receptor default")

	tavily_key = ""
	if tavily_enabled:
		tavily_key = _prompt("TAVILY_API_KEY")

	# -- PASO 6: Embeddings --
	openai_key = ""
	if db_type != "sqlite":
		print("\nPASO 6: Embeddings (requerido para RAG)")
		if key_name == "OPENAI_API_KEY":
			openai_key = api_key
			print(f"  Reutilizando {key_name} para embeddings")
		else:
			openai_key = _prompt("OPENAI_API_KEY (para text-embedding-3-small)")

	# ==============================
	# GENERAR WORKSPACE
	# ==============================
	print("\nGenerando workspace...")

	for d in ["", "knowledge/docs", "agents"]:
		(workspace_dir / d).mkdir(parents=True, exist_ok=True)

	# --- config.yaml ---
	config = {
		"agent": {
			"name": agent_name,
			"id": "agnobot-main",
			"description": agent_desc,
		},
		"model": {"provider": provider, "id": model_id},
		"database": {
			"type": db_type,
			"knowledge_table": "agnobot_knowledge_contents",
			"vector_table": "agnobot_knowledge_vectors",
		},
		"vector": {
			"search_type": "hybrid",
			"embedder": "text-embedding-3-small",
			"max_results": 5,
		},
		"channels": channels,
		"memory": {
			"enable_agentic_memory": True,
			"num_history_runs": 5,
		},
		"agentos": {
			"id": "agnobot-gateway",
			"name": f"{agent_name} Platform",
			"port": 8000,
			"tracing": True,
			"enable_mcp_server": True,
		},
		"studio": {"enabled": db_type != "sqlite"},
	}
	_write_yaml(workspace_dir / "config.yaml", config)

	# --- instructions.md ---
	instructions_content = custom_instructions or f"""# Instrucciones de {agent_name}

Eres **{agent_name}**, un asistente personal multimodal autonomo.

## Personalidad
- Amable, eficiente y proactivo
- Respondes en el idioma del usuario
- Usas formato Markdown cuando es apropiado

## Capacidades
- Puedes analizar imagenes, videos y audios enviados
- Buscas en la web cuando necesitas informacion actualizada
- Usas la base de conocimiento para responder sobre documentos cargados
- Recuerdas informacion importante del usuario entre sesiones
- Puedes consultar la documentacion de Agno para resolver dudas tecnicas

## Reglas
- Si no estas seguro de algo, buscalo antes de responder
- Siempre cita tus fuentes cuando uses informacion de la web
- Si el usuario carga documentos, confirmaselo y ofrece analizarlos
"""
	(workspace_dir / "instructions.md").write_text(instructions_content, encoding="utf-8")

	# --- tools.yaml ---
	tools = {
		"builtin": [
			{"name": "duckduckgo", "enabled": True, "config": {}},
			{"name": "crawl4ai", "enabled": True, "config": {"max_length": 2000}},
			{"name": "reasoning", "enabled": True, "config": {"add_instructions": True}},
		],
		"optional": [
			{
				"name": "email",
				"enabled": email_enabled,
				"config": {
					"sender_email": "${GMAIL_SENDER}",
					"sender_name": agent_name,
					"sender_passkey": "${GMAIL_PASSKEY}",
					"receiver_email": "${GMAIL_RECEIVER}",
				},
			},
			{"name": "tavily", "enabled": tavily_enabled},
			{"name": "spotify", "enabled": False},
			{"name": "shell", "enabled": False},
		],
		"custom": [],
	}
	_write_yaml(workspace_dir / "tools.yaml", tools)

	# --- mcp.yaml ---
	mcp = {
		"servers": [
			{
				"name": "agno_docs",
				"enabled": True,
				"transport": "streamable-http",
				"url": "https://docs.agno.com/mcp",
			},
		],
		"expose": {"enabled": True},
	}
	_write_yaml(workspace_dir / "mcp.yaml", mcp)

	# --- agents/research_agent.yaml ---
	research = {
		"agent": {
			"name": "Research Agent",
			"id": "research-agent",
			"role": "Realiza busquedas web profundas y sintetiza informacion",
			"model": {"provider": provider, "id": model_id},
			"tools": ["duckduckgo", "crawl4ai", "reasoning"],
			"instructions": [
				"Eres un agente especializado en investigacion profunda.",
				"Busca en la web, scrapea paginas y sintetiza informacion.",
				"Siempre cita tus fuentes con URLs completas.",
				"Se conciso pero completo.",
			],
			"config": {
				"tool_call_limit": 5,
				"enable_agentic_memory": False,
				"add_datetime_to_context": True,
				"markdown": True,
			},
		},
		"execution": {"type": "local"},
	}
	_write_yaml(workspace_dir / "agents" / "research_agent.yaml", research)

	# --- agents/teams.yaml ---
	teams = {
		"teams": [
			{
				"name": "Research Team",
				"id": "research-team",
				"mode": "coordinate",
				"members": ["agnobot-main", "research-agent"],
				"model": {"provider": provider, "id": model_id},
				"instructions": [
					"Coordina entre el agente principal y el agente de investigacion.",
					"Usa el agente de investigacion para busquedas web profundas.",
					"El agente principal sintetiza y responde al usuario.",
					"Responde en el idioma del usuario.",
				],
				"enable_agentic_memory": False,
			}
		]
	}
	_write_yaml(workspace_dir / "agents" / "teams.yaml", teams)

	# --- schedules.yaml ---
	_write_yaml(workspace_dir / "schedules.yaml", {"schedules": []})

	# --- knowledge/urls.yaml ---
	_write_yaml(workspace_dir / "knowledge" / "urls.yaml", {"urls": []})

	# --- .env ---
	env_lines = [
		"# ===================================",
		f"# {agent_name} - Variables de Entorno",
		"# ===================================",
		"",
		"# === API Keys ===",
		f"{key_name}={api_key}",
	]
	if openai_key and key_name != "OPENAI_API_KEY":
		env_lines.append(f"OPENAI_API_KEY={openai_key}")
	if tavily_key:
		env_lines.append(f"TAVILY_API_KEY={tavily_key}")

	if db_vars:
		env_lines.extend(["", "# === Base de datos ==="])
		for k, v in db_vars.items():
			env_lines.append(f"{k}={v}")

	if whatsapp_vars:
		env_lines.extend(["", "# === WhatsApp ==="])
		for k, v in whatsapp_vars.items():
			env_lines.append(f"{k}={v}")

	if slack_vars:
		env_lines.extend(["", "# === Slack ==="])
		for k, v in slack_vars.items():
			env_lines.append(f"{k}={v}")

	if email_vars:
		env_lines.extend(["", "# === Gmail ==="])
		for k, v in email_vars.items():
			env_lines.append(f"{k}={v}")

	env_lines.extend([
		"",
		"# === Seguridad ===",
		"# OS_SECURITY_KEY=genera_con_openssl_rand_hex_32",
		"",
		"# === Entorno ===",
		"APP_ENV=development",
	])

	Path(".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

	# -- Validar workspace generado --
	print("\nValidando workspace generado...")
	errors = validate_workspace(str(workspace_dir))

	# -- Resumen --
	print()
	print("=" * 50)
	if not errors:
		print("  Workspace generado y validado exitosamente!")
	else:
		print("  Workspace generado con advertencias")
	print("=" * 50)
	print(f"  workspace/config.yaml    - Configuracion central")
	print(f"  workspace/instructions.md - Personalidad")
	print(f"  workspace/tools.yaml     - Herramientas")
	print(f"  workspace/mcp.yaml       - Servidores MCP")
	print(f"  workspace/knowledge/     - Documentos RAG")
	print(f"  workspace/agents/        - Sub-agentes y Teams")
	print(f"  .env                     - Secretos")

	if errors:
		print()
		for e in errors:
			print(f"  [!] {e}")

	print()
	if db_type == "local":
		print("  Paso 1: docker compose up -d db")
	step = "2" if db_type == "local" else "1"
	print(f"  Paso {step}: python gateway.py")
	print(f"  Web UI: os.agno.com -> Add OS -> Local -> http://localhost:8000")

	if "whatsapp" in channels:
		url = whatsapp_vars.get("WHATSAPP_WEBHOOK_URL", "tu-url")
		print(f"  WhatsApp: Configura webhook en Meta -> {url}")

	print("=" * 50)
	print()


if __name__ == "__main__":
	run_onboarding()
