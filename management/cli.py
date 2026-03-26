"""
CLI de Onboarding v5 - Genera, diagnostica y reconfigura el workspace.

Comandos:
	python -m management.cli              # Setup wizard (genera workspace + .env)
	python -m management.cli doctor       # Diagnostica y repara problemas
	python -m management.cli configure    # Reconfigura una seccion especifica
	python -m management.cli fallback     # Configura modelo fallback
	python -m management.cli audio        # Configura audio (STT/TTS)

Genera:
	workspace/config.yaml
	workspace/instructions.md
	workspace/tools.yaml
	workspace/mcp.yaml
	workspace/knowledge/urls.yaml
	workspace/agents/teams.yaml
	.env
"""
import sys
import os
import yaml
from pathlib import Path

from dotenv import load_dotenv
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
		"2": "Claude Sonnet 4 (Anthropic - directo)",
		"3": "Claude Sonnet 4.6 via Bedrock (AWS - sin API key Anthropic)",
		"4": "Claude Opus 4.6 via Bedrock (AWS - mas capaz)",
		"5": "GPT-4.1 (OpenAI)",
		"6": "Amazon Nova Pro (AWS Bedrock)",
	}
	model_choice = _prompt_choice("PASO 2: Modelo de IA", model_options)

	model_map: dict[str, tuple[str, str, str]] = {
		"1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
		"2": ("anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY"),
		"3": ("aws_bedrock_claude", "us.anthropic.claude-sonnet-4-6", "AWS_ACCESS_KEY_ID"),
		"4": ("aws_bedrock_claude", "us.anthropic.claude-opus-4-6-v1", "AWS_ACCESS_KEY_ID"),
		"5": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
		"6": ("aws_bedrock", "amazon.nova-pro-v1:0", "AWS_ACCESS_KEY_ID"),
	}
	provider, model_id, key_name = model_map.get(model_choice, model_map["1"])

	# Si es AWS Bedrock, pedir credenciales AWS
	aws_vars: dict[str, str] = {}
	api_key = ""
	if provider.startswith("aws_bedrock"):
		aws_vars["AWS_ACCESS_KEY_ID"] = _prompt("AWS Access Key ID")
		aws_vars["AWS_SECRET_ACCESS_KEY"] = _prompt("AWS Secret Access Key")
		aws_vars["AWS_REGION"] = _prompt("AWS Region", "us-east-1")
	else:
		api_key = _prompt(f"-> {key_name}")

	# -- PASO 2b: Audio / Transcripcion --
	audio_config: dict[str, object] = {
		"auto_transcribe": False,
		"stt_model": "whisper-1",
		"tts_enabled": False,
		"tts_model": "tts-1",
		"tts_voice": "nova",
	}
	non_audio_providers = {"aws_bedrock", "aws_bedrock_claude", "anthropic"}

	if provider in non_audio_providers:
		print(f"\nPASO 2b: Configuracion de Audio")
		print(f"  El modelo {model_id} no soporta audio nativo.")
		auto_transcribe = _prompt_yn(
			"Activar transcripcion automatica de audios (Whisper)?", default=True
		)
		audio_config["auto_transcribe"] = auto_transcribe
		if auto_transcribe:
			stt_choice = _prompt_choice("Modelo de transcripcion", {
				"1": "Whisper (whisper-1 - rapido, economico)",
				"2": "GPT-4o Mini Transcribe (mas preciso)",
			})
			audio_config["stt_model"] = (
				"whisper-1" if stt_choice == "1" else "gpt-4o-mini-transcribe"
			)

	tts_enabled = _prompt_yn("Activar respuestas por voz (TTS)?")
	audio_config["tts_enabled"] = tts_enabled
	if tts_enabled:
		voice_choice = _prompt_choice("Voz para TTS", {
			"1": "Nova (femenina, natural)",
			"2": "Alloy (neutral)",
			"3": "Echo (masculina)",
			"4": "Onyx (masculina, profunda)",
		})
		audio_config["tts_voice"] = {
			"1": "nova", "2": "alloy", "3": "echo", "4": "onyx"
		}.get(voice_choice, "nova")

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
		slack_vars["SLACK_TOKEN"] = _prompt("Bot Token (xoxb-...)")
		slack_vars["SLACK_SIGNING_SECRET"] = _prompt("Signing Secret")

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

	# -- PASO 5b: Scheduler y knowledge (F5) --
	scheduler_enabled = _prompt_yn("Activar scheduler de AgentOS (cron via API / Studio)?", default=True)
	auto_ingest_docs = _prompt_yn("Auto-ingestar documentos de knowledge/docs al arrancar?", default=True)
	auto_ingest_urls = _prompt_yn("Auto-ingestar URLs de knowledge/urls.yaml al arrancar?", default=True)

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
	model_config: dict = {"provider": provider, "id": model_id}
	if provider.startswith("aws_bedrock"):
		model_config["aws_region"] = aws_vars.get("AWS_REGION", "us-east-1")

	config = {
		"agent": {
			"name": agent_name,
			"id": "agnobot-main",
			"description": agent_desc,
		},
		"model": model_config,
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
		"a2a": {"enabled": False},
		"scheduler": {
			"enabled": scheduler_enabled,
			"poll_interval": 15,
			"timezone": "America/Guayaquil",
		},
		"knowledge": {
			"auto_ingest_docs": auto_ingest_docs,
			"auto_ingest_urls": auto_ingest_urls,
			"skip_if_exists": True,
		},
		"audio": audio_config,
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
			{"name": "workspace", "enabled": True, "description": "Auto-configuracion del workspace (CRUD agentes, instrucciones, tools)"},
			{"name": "scheduler_mgmt", "enabled": True, "description": "Gestion de recordatorios y crons via API REST nativa"},
			{
				"name": "audio",
				"enabled": audio_config.get("auto_transcribe", False) or audio_config.get("tts_enabled", False),
				"description": "Transcripcion de audio (STT) y sintesis de voz (TTS)",
				"config": audio_config,
			},
		],
		"custom": [],
	}
	_write_yaml(workspace_dir / "tools.yaml", tools)

	# --- mcp.yaml ---
	mcp_servers: list[dict] = [
		{
			"name": "agno_docs",
			"enabled": True,
			"transport": "streamable-http",
			"url": "https://docs.agno.com/mcp",
		},
	]
	if tavily_enabled:
		mcp_servers.append({
			"name": "tavily",
			"enabled": True,
			"transport": "streamable-http",
			"url": "https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}",
			"description": "Busqueda web avanzada con Tavily",
		})
	mcp = {"servers": mcp_servers, "expose": {"enabled": True}}
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

	# --- schedules.yaml (plantilla F5, deshabilitada por defecto) ---
	schedules_template = {
		"schedules": [
			{
				"name": "Resumen matutino",
				"enabled": False,
				"agent_id": "agnobot-main",
				"cron": "0 9 * * 1-5",
				"timezone": "America/Guayaquil",
				"message": "Genera un resumen breve de noticias de tecnologia.",
				"user_id": "scheduler-admin",
			},
		],
	}
	_write_yaml(workspace_dir / "schedules.yaml", schedules_template)

	# --- knowledge/urls.yaml ---
	_write_yaml(workspace_dir / "knowledge" / "urls.yaml", {"urls": []})

	# --- .env ---
	env_lines = [
		"# ===================================",
		f"# {agent_name} - Variables de Entorno",
		"# ===================================",
		"",
		"# === API Keys ===",
	]
	if api_key:
		env_lines.append(f"{key_name}={api_key}")
	if openai_key and key_name != "OPENAI_API_KEY":
		env_lines.append(f"OPENAI_API_KEY={openai_key}")
	if tavily_key:
		env_lines.append(f"TAVILY_API_KEY={tavily_key}")
	if aws_vars:
		env_lines.extend(["", "# === AWS Bedrock (F6) ==="])
		for k, v in aws_vars.items():
			env_lines.append(f"{k}={v}")

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

	# Recargar .env para que la validacion inline vea las credenciales recien escritas
	load_dotenv(override=True)

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
	print(f"  workspace/schedules.yaml - Plantilla cron (referencia; registrar en AgentOS)")
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
	print(f"  Scheduler: POST /schedules (cron) si scheduler.enabled en config.yaml")

	if "whatsapp" in channels:
		url = whatsapp_vars.get("WHATSAPP_WEBHOOK_URL", "tu-url")
		print(f"  WhatsApp: Configura webhook en Meta -> {url}")

	print("=" * 50)
	print()


def _load_current_config() -> dict:
	"""Carga config.yaml actual."""
	path = Path("workspace/config.yaml")
	if not path.exists():
		return {}
	with open(path, "r", encoding="utf-8") as f:
		return yaml.safe_load(f) or {}


def _load_current_env() -> dict[str, str]:
	"""Carga .env como dict."""
	env: dict[str, str] = {}
	path = Path(".env")
	if not path.exists():
		return env
	for line in path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		if "=" in line:
			k, v = line.split("=", 1)
			env[k.strip()] = v.strip()
	return env


def _update_env_var(key: str, value: str) -> None:
	"""Actualiza o agrega una variable en .env."""
	path = Path(".env")
	if not path.exists():
		path.write_text(f"{key}={value}\n", encoding="utf-8")
		return
	lines = path.read_text(encoding="utf-8").splitlines()
	found = False
	for i, line in enumerate(lines):
		stripped = line.strip()
		if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
			lines[i] = f"{key}={value}"
			found = True
			break
	if not found:
		lines.append(f"{key}={value}")
	path.write_text("\n".join(lines) + "\n", encoding="utf-8")
	os.environ[key] = value


# ==============================
# DOCTOR - Diagnostico y reparacion
# ==============================

def run_doctor() -> None:
	"""Diagnostica problemas del workspace y ofrece reparacion automatica."""
	print()
	print("=" * 50)
	print("  OpenAgno Doctor - Diagnostico y Reparacion")
	print("=" * 50)

	load_dotenv(override=True)
	errors = validate_workspace()
	config = _load_current_config()
	env = _load_current_env()
	fixes_applied = 0

	if not errors:
		print("\n  [OK] Workspace saludable - no se encontraron problemas")
		# Verificar conexion a DB
		_doctor_check_db(config)
		# Verificar modelo
		_doctor_check_model(config, env)
		print()
		return

	print(f"\n  Se encontraron {len(errors)} problema(s):\n")

	for i, error in enumerate(errors, 1):
		print(f"  {i}. {error}")

		# Intentar reparar automaticamente
		if ".env: falta" in error:
			var_name = error.split("falta ")[1].split(" ")[0]
			fix = _doctor_fix_env_var(var_name, config)
			if fix:
				fixes_applied += 1

		elif "Falta " in error and ".yaml" in error:
			filename = error.split("Falta ")[1].split(" ")[0]
			fix = _doctor_fix_missing_file(filename)
			if fix:
				fixes_applied += 1

	# Chequeos extra
	print("\n  --- Chequeos adicionales ---")
	_doctor_check_db(config)
	_doctor_check_model(config, env)
	_doctor_check_ssl()
	_doctor_check_fallback(config)

	print()
	if fixes_applied:
		print(f"  Se aplicaron {fixes_applied} reparacion(es)")
	print(f"  Ejecuta 'python -m management.validator' para re-validar")
	print("=" * 50)
	print()


def _doctor_fix_env_var(var_name: str, config: dict) -> bool:
	"""Intenta reparar una variable de entorno faltante."""
	print(f"\n    -> Reparar {var_name}?")
	value = _prompt(f"Valor para {var_name} (Enter para omitir)")
	if value:
		_update_env_var(var_name, value)
		print(f"    [FIXED] {var_name} configurado")
		return True
	print(f"    [SKIP] {var_name} omitido")
	return False


def _doctor_fix_missing_file(filename: str) -> bool:
	"""Intenta reparar archivos faltantes."""
	path = Path("workspace") / filename
	if path.suffix == ".yaml":
		print(f"    -> Creando {filename} con valores por defecto...")
		path.parent.mkdir(parents=True, exist_ok=True)
		_write_yaml(path, {})
		print(f"    [FIXED] {filename} creado")
		return True
	return False


def _doctor_check_db(config: dict) -> None:
	"""Verifica conectividad a la base de datos."""
	db_type = config.get("database", {}).get("type", "sqlite")
	if db_type == "sqlite":
		print("  [OK] SQLite (sin conexion remota)")
		return
	try:
		import psycopg
		host = os.getenv("DB_HOST", "")
		port = os.getenv("DB_PORT", "5432")
		user = os.getenv("DB_USER", "")
		password = os.getenv("DB_PASSWORD", "")
		name = os.getenv("DB_NAME", "postgres")
		sslmode = os.getenv("DB_SSLMODE", "require")
		conn = psycopg.connect(
			f"host={host} port={port} user={user} password={password} dbname={name} sslmode={sslmode}",
			connect_timeout=5,
		)
		conn.close()
		print(f"  [OK] Base de datos: {db_type} ({host}:{port})")
	except Exception as e:
		print(f"  [ERROR] Base de datos: {e}")


def _doctor_check_model(config: dict, env: dict) -> None:
	"""Verifica que el modelo configurado es accesible."""
	model = config.get("model", {})
	provider = model.get("provider", "")
	model_id = model.get("id", "")
	fallback = model.get("fallback", {})

	print(f"  [INFO] Modelo principal: {provider} / {model_id}")
	if fallback.get("id"):
		print(f"  [INFO] Modelo fallback: {fallback.get('provider', provider)} / {fallback['id']}")
	else:
		print(f"  [WARN] Sin modelo fallback configurado (util para rate limits)")
		print(f"         Ejecuta: python -m management.cli fallback")


def _doctor_check_ssl() -> None:
	"""Verifica si hay reverse proxy con SSL."""
	import subprocess
	try:
		result = subprocess.run(
			["systemctl", "is-active", "caddy"],
			capture_output=True, text=True, timeout=5,
		)
		if result.stdout.strip() == "active":
			print("  [OK] Caddy (reverse proxy + SSL) activo")
		else:
			print("  [INFO] Caddy no activo (webhooks requieren HTTPS)")
	except Exception:
		print("  [INFO] Caddy no instalado (webhooks requieren HTTPS)")


def _doctor_check_fallback(config: dict) -> None:
	"""Verifica configuracion de fallback."""
	model = config.get("model", {})
	if not model.get("fallback"):
		return
	fb = model["fallback"]
	fb_provider = fb.get("provider", model.get("provider", ""))
	fb_id = fb.get("id", "")
	if fb_id:
		print(f"  [OK] Fallback configurado: {fb_provider} / {fb_id}")


# ==============================
# FALLBACK - Configura modelo alternativo
# ==============================

# IDs de modelos disponibles por proveedor para referencia del usuario
BEDROCK_MODELS = {
	"1": ("us.anthropic.claude-opus-4-6-v1", "Claude Opus 4.6 (AWS)"),
	"2": ("us.anthropic.claude-sonnet-4-6", "Claude Sonnet 4.6 (AWS)"),
	"3": ("us.anthropic.claude-sonnet-4-5-20250929-v1:0", "Claude Sonnet 4.5 (AWS)"),
	"4": ("us.anthropic.claude-opus-4-20250514-v1:0", "Claude Opus 4 (AWS)"),
	"5": ("us.anthropic.claude-sonnet-4-20250514-v1:0", "Claude Sonnet 4 (AWS)"),
	"6": ("us.anthropic.claude-haiku-4-5-20251001-v1:0", "Claude Haiku 4.5 (AWS)"),
	"7": ("amazon.nova-pro-v1:0", "Amazon Nova Pro"),
}


def run_fallback() -> None:
	"""Configura un modelo fallback para cuando el principal falla (rate limit, etc)."""
	print()
	print("=" * 50)
	print("  OpenAgno - Configurar Modelo Fallback")
	print("=" * 50)

	config = _load_current_config()
	model = config.get("model", {})
	provider = model.get("provider", "")
	model_id = model.get("id", "")

	print(f"\n  Modelo principal actual: {provider} / {model_id}")

	if model.get("fallback", {}).get("id"):
		fb = model["fallback"]
		print(f"  Fallback actual: {fb.get('provider', provider)} / {fb['id']}")

	choice = _prompt_choice("Selecciona modelo fallback", {
		"1": "Gemini Flash Latest (Google - gratis, rapido)",
		"2": "Claude Sonnet 4.6 via Bedrock (AWS)",
		"3": "Claude Haiku 4.5 via Bedrock (AWS - economico)",
		"4": "GPT-4.1 (OpenAI)",
		"5": "Amazon Nova Pro (AWS Bedrock - economico)",
		"6": "Otro modelo de Bedrock",
		"7": "Quitar fallback",
	})

	fallback_map: dict[str, tuple[str, str, str]] = {
		"1": ("google", "gemini-flash-latest", "GOOGLE_API_KEY"),
		"2": ("aws_bedrock_claude", "us.anthropic.claude-sonnet-4-6", "AWS_ACCESS_KEY_ID"),
		"3": ("aws_bedrock_claude", "us.anthropic.claude-haiku-4-5-20251001-v1:0", "AWS_ACCESS_KEY_ID"),
		"4": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
		"5": ("aws_bedrock", "amazon.nova-pro-v1:0", "AWS_ACCESS_KEY_ID"),
	}

	if choice == "7":
		# Quitar fallback
		if "fallback" in model:
			del model["fallback"]
			config["model"] = model
			_write_yaml(Path("workspace/config.yaml"), config)
			print("\n  [OK] Fallback eliminado")
		else:
			print("\n  No habia fallback configurado")
		return

	if choice == "6":
		print("\n  Modelos Bedrock disponibles:")
		for k, (mid, label) in BEDROCK_MODELS.items():
			print(f"    [{k}] {label} ({mid})")
		sub = input(f"  Seleccion [2]: ").strip() or "2"
		fb_id, _ = BEDROCK_MODELS.get(sub, BEDROCK_MODELS["2"])
		fb_provider = "aws_bedrock_claude" if "anthropic" in fb_id else "aws_bedrock"
		fb_key = "AWS_ACCESS_KEY_ID"
	else:
		fb_provider, fb_id, fb_key = fallback_map.get(choice, fallback_map["1"])

	# Verificar que la API key del fallback existe
	if not fb_provider.startswith("aws_bedrock"):
		if not os.getenv(fb_key):
			val = _prompt(f"{fb_key} (requerido para fallback)")
			if val:
				_update_env_var(fb_key, val)

	model["fallback"] = {
		"provider": fb_provider,
		"id": fb_id,
	}
	if fb_provider.startswith("aws_bedrock"):
		model["fallback"]["aws_region"] = model.get("aws_region", "us-east-1")

	config["model"] = model
	_write_yaml(Path("workspace/config.yaml"), config)

	print(f"\n  [OK] Fallback configurado: {fb_provider} / {fb_id}")
	print(f"  Cuando el modelo principal falle (rate limit, error), se usara el fallback")
	print(f"  Reinicia el gateway para aplicar: python service_manager.py restart")
	print()


# ==============================
# CONFIGURE - Reconfigura secciones
# ==============================

def run_configure() -> None:
	"""Reconfigura una seccion especifica sin regenerar todo."""
	print()
	print("=" * 50)
	print("  OpenAgno - Reconfigurar Workspace")
	print("=" * 50)

	config = _load_current_config()
	if not config:
		print("\n  No hay workspace configurado. Ejecuta: python -m management.cli")
		return

	choice = _prompt_choice("Que deseas reconfigurar?", {
		"1": "Modelo principal",
		"2": "Modelo fallback",
		"3": "Base de datos",
		"4": "Canales (WhatsApp/Slack)",
		"5": "API Keys (.env)",
		"6": "Herramientas",
		"7": "Identidad del agente",
		"8": "Audio (transcripcion/TTS)",
	})

	match choice:
		case "1":
			_configure_model(config)
		case "2":
			run_fallback()
			return
		case "3":
			_configure_database(config)
		case "4":
			_configure_channels(config)
		case "5":
			_configure_env_keys()
		case "6":
			_configure_tools(config)
		case "7":
			_configure_identity(config)
		case "8":
			_configure_audio(config)

	print()


def _configure_model(config: dict) -> None:
	"""Reconfigura el modelo principal."""
	model = config.get("model", {})
	print(f"\n  Modelo actual: {model.get('provider')} / {model.get('id')}")

	model_options = {
		"1": "Gemini 2.0 Flash (Google)",
		"2": "Claude Sonnet 4 (Anthropic directo)",
		"3": "Claude Sonnet 4.6 via Bedrock",
		"4": "Claude Opus 4.6 via Bedrock",
		"5": "GPT-4.1 (OpenAI)",
		"6": "Amazon Nova Pro (Bedrock)",
	}
	model_map: dict[str, tuple[str, str, str]] = {
		"1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
		"2": ("anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY"),
		"3": ("aws_bedrock_claude", "us.anthropic.claude-sonnet-4-6", "AWS_ACCESS_KEY_ID"),
		"4": ("aws_bedrock_claude", "us.anthropic.claude-opus-4-6-v1", "AWS_ACCESS_KEY_ID"),
		"5": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
		"6": ("aws_bedrock", "amazon.nova-pro-v1:0", "AWS_ACCESS_KEY_ID"),
	}

	sel = _prompt_choice("Nuevo modelo", model_options)
	provider, model_id, key_name = model_map.get(sel, model_map["1"])

	new_model: dict = {"provider": provider, "id": model_id}

	if provider.startswith("aws_bedrock"):
		if not os.getenv("AWS_ACCESS_KEY_ID"):
			_update_env_var("AWS_ACCESS_KEY_ID", _prompt("AWS Access Key ID"))
			_update_env_var("AWS_SECRET_ACCESS_KEY", _prompt("AWS Secret Access Key"))
		new_model["aws_region"] = _prompt("AWS Region", model.get("aws_region", "us-east-1"))
	else:
		if not os.getenv(key_name):
			val = _prompt(f"{key_name}")
			if val:
				_update_env_var(key_name, val)

	# Preservar fallback si existe
	if model.get("fallback"):
		new_model["fallback"] = model["fallback"]

	config["model"] = new_model
	_write_yaml(Path("workspace/config.yaml"), config)

	# Actualizar sub-agentes tambien
	agents_dir = Path("workspace/agents")
	if agents_dir.exists():
		for f in agents_dir.glob("*.yaml"):
			if f.name == "teams.yaml":
				continue
			try:
				data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
				if "agent" in data and "model" in data["agent"]:
					data["agent"]["model"] = {"provider": provider, "id": model_id}
					_write_yaml(f, data)
			except Exception:
				pass

	print(f"\n  [OK] Modelo actualizado: {provider} / {model_id}")
	print(f"  Reinicia el gateway para aplicar")


def _configure_database(config: dict) -> None:
	"""Reconfigura la base de datos."""
	db = config.get("database", {})
	print(f"\n  DB actual: {db.get('type')}")

	db_options = {
		"1": "Supabase (PostgreSQL managed)",
		"2": "PostgreSQL local (Docker)",
		"3": "SQLite (solo desarrollo)",
	}
	sel = _prompt_choice("Nueva base de datos", db_options)
	db_type = {"1": "supabase", "2": "local", "3": "sqlite"}.get(sel, "supabase")

	if db_type == "supabase":
		print("\n  Configuracion Supabase:")
		_update_env_var("DB_HOST", _prompt("DB Host", os.getenv("DB_HOST", "")))
		_update_env_var("DB_PORT", _prompt("DB Port", os.getenv("DB_PORT", "5432")))
		_update_env_var("DB_USER", _prompt("DB User", os.getenv("DB_USER", "")))
		_update_env_var("DB_PASSWORD", _prompt("DB Password"))
		_update_env_var("DB_NAME", _prompt("DB Name", os.getenv("DB_NAME", "postgres")))
	elif db_type == "local":
		for k, v in {"DB_HOST": "localhost", "DB_PORT": "5532", "DB_USER": "ai", "DB_PASSWORD": "ai", "DB_NAME": "ai"}.items():
			_update_env_var(k, v)

	config["database"]["type"] = db_type
	_write_yaml(Path("workspace/config.yaml"), config)
	print(f"\n  [OK] Base de datos actualizada: {db_type}")


def _configure_channels(config: dict) -> None:
	"""Reconfigura canales."""
	current = config.get("channels", [])
	print(f"\n  Canales actuales: {', '.join(current) if current else 'ninguno'}")

	channel_options = {
		"1": "WhatsApp",
		"2": "Slack",
		"3": "WhatsApp + Slack",
	}
	sel = _prompt_choice("Canales", channel_options)
	channels = {"1": ["whatsapp"], "2": ["slack"], "3": ["whatsapp", "slack"]}.get(sel, ["whatsapp"])

	if "whatsapp" in channels and "whatsapp" not in current:
		print("\n  Configuracion WhatsApp:")
		_update_env_var("WHATSAPP_ACCESS_TOKEN", _prompt("Access Token"))
		_update_env_var("WHATSAPP_PHONE_NUMBER_ID", _prompt("Phone Number ID"))
		_update_env_var("WHATSAPP_VERIFY_TOKEN", _prompt("Verify Token"))

	if "slack" in channels and "slack" not in current:
		print("\n  Configuracion Slack:")
		_update_env_var("SLACK_TOKEN", _prompt("Bot Token (xoxb-...)"))
		_update_env_var("SLACK_SIGNING_SECRET", _prompt("Signing Secret"))

	config["channels"] = channels
	_write_yaml(Path("workspace/config.yaml"), config)
	print(f"\n  [OK] Canales actualizados: {', '.join(channels)}")


def _configure_env_keys() -> None:
	"""Actualiza API keys en .env."""
	print("\n  Variables actuales en .env:")
	env = _load_current_env()
	for k, v in env.items():
		if k.startswith("#"):
			continue
		masked = v[:8] + "..." if len(v) > 10 else v
		print(f"    {k} = {masked}")

	print("\n  Escribe VARIABLE=valor (linea vacia para terminar):")
	while True:
		line = input("  > ").strip()
		if not line:
			break
		if "=" in line:
			k, v = line.split("=", 1)
			_update_env_var(k.strip(), v.strip())
			print(f"    [OK] {k.strip()} actualizado")
		else:
			print(f"    [ERROR] Formato: VARIABLE=valor")


def _configure_tools(config: dict) -> None:
	"""Reconfigura herramientas."""
	tools_path = Path("workspace/tools.yaml")
	if not tools_path.exists():
		print("  [ERROR] tools.yaml no encontrado")
		return
	tools = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
	optional = tools.get("optional", [])

	print("\n  Herramientas opcionales:")
	for i, t in enumerate(optional):
		status = "ON" if t.get("enabled", False) else "OFF"
		print(f"    [{i+1}] {t.get('name', '?'):20s} [{status}]")

	sel = _prompt("Numero para toggle (Enter para salir)")
	if sel and sel.isdigit():
		idx = int(sel) - 1
		if 0 <= idx < len(optional):
			optional[idx]["enabled"] = not optional[idx].get("enabled", False)
			new_status = "ON" if optional[idx]["enabled"] else "OFF"
			_write_yaml(tools_path, tools)
			print(f"    [OK] {optional[idx]['name']} -> {new_status}")


def _configure_identity(config: dict) -> None:
	"""Reconfigura identidad del agente."""
	agent = config.get("agent", {})
	print(f"\n  Nombre actual: {agent.get('name')}")
	print(f"  Descripcion: {agent.get('description')}")

	new_name = _prompt("Nuevo nombre", agent.get("name", ""))
	new_desc = _prompt("Nueva descripcion", agent.get("description", ""))

	config["agent"]["name"] = new_name
	config["agent"]["description"] = new_desc
	_write_yaml(Path("workspace/config.yaml"), config)
	print(f"\n  [OK] Identidad actualizada: {new_name}")


def _configure_audio(config: dict) -> None:
	"""Reconfigura audio (transcripcion STT / sintesis TTS)."""
	audio = config.get("audio", {})
	print(f"\n  Configuracion de audio actual:")
	print(f"    Auto-transcripcion: {'ON' if audio.get('auto_transcribe') else 'OFF'}")
	print(f"    Modelo STT: {audio.get('stt_model', 'whisper-1')}")
	print(f"    TTS: {'ON' if audio.get('tts_enabled') else 'OFF'}")
	if audio.get("tts_enabled"):
		print(f"    Voz TTS: {audio.get('tts_voice', 'nova')}")

	# Transcripcion
	auto_transcribe = _prompt_yn(
		"Activar transcripcion automatica de audios?",
		default=audio.get("auto_transcribe", False),
	)
	audio["auto_transcribe"] = auto_transcribe
	if auto_transcribe:
		stt_choice = _prompt_choice("Modelo de transcripcion", {
			"1": "Whisper (whisper-1 - rapido, economico)",
			"2": "GPT-4o Mini Transcribe (mas preciso)",
		}, default="1" if audio.get("stt_model", "whisper-1") == "whisper-1" else "2")
		audio["stt_model"] = (
			"whisper-1" if stt_choice == "1" else "gpt-4o-mini-transcribe"
		)

	# TTS
	tts_enabled = _prompt_yn(
		"Activar respuestas por voz (TTS)?",
		default=audio.get("tts_enabled", False),
	)
	audio["tts_enabled"] = tts_enabled
	if tts_enabled:
		voice_choice = _prompt_choice("Voz para TTS", {
			"1": "Nova (femenina, natural)",
			"2": "Alloy (neutral)",
			"3": "Echo (masculina)",
			"4": "Onyx (masculina, profunda)",
		})
		audio["tts_voice"] = {
			"1": "nova", "2": "alloy", "3": "echo", "4": "onyx"
		}.get(voice_choice, "nova")
		audio["tts_model"] = "tts-1"

	config["audio"] = audio
	_write_yaml(Path("workspace/config.yaml"), config)

	# Actualizar tools.yaml para habilitar/deshabilitar audio tool
	tools_path = Path("workspace/tools.yaml")
	if tools_path.exists():
		tools = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
		optional = tools.get("optional", [])
		audio_tool = next((t for t in optional if t.get("name") == "audio"), None)
		audio_enabled = auto_transcribe or tts_enabled
		if audio_tool:
			audio_tool["enabled"] = audio_enabled
			audio_tool["config"] = audio
		else:
			optional.append({
				"name": "audio",
				"enabled": audio_enabled,
				"description": "Transcripcion de audio (STT) y sintesis de voz (TTS)",
				"config": audio,
			})
		_write_yaml(tools_path, tools)

	print(f"\n  [OK] Audio actualizado: STT={'ON' if auto_transcribe else 'OFF'}, TTS={'ON' if tts_enabled else 'OFF'}")
	print(f"  Reinicia el gateway para aplicar: python service_manager.py restart")


# ==============================
# MAIN - Router de comandos
# ==============================

def main() -> None:
	"""Punto de entrada principal del CLI."""
	args = sys.argv[1:]

	if not args:
		run_onboarding()
		return

	command = args[0].lower()

	match command:
		case "doctor":
			run_doctor()
		case "fallback":
			run_fallback()
		case "configure" | "config" | "reconfig":
			run_configure()
		case "audio":
			config = _load_current_config()
			if config:
				_configure_audio(config)
			else:
				print("  No hay workspace configurado. Ejecuta: python -m management.cli")
		case "help":
			print()
			print("  OpenAgno CLI - Comandos disponibles:")
			print()
			print("  python -m management.cli              Setup wizard (genera workspace)")
			print("  python -m management.cli doctor       Diagnostica y repara problemas")
			print("  python -m management.cli configure    Reconfigura una seccion")
			print("  python -m management.cli fallback     Configura modelo fallback")
			print("  python -m management.cli audio        Configura audio (STT/TTS)")
			print("  python -m management.cli help         Muestra esta ayuda")
			print()
		case _:
			print(f"  Comando desconocido: {command}")
			print(f"  Ejecuta: python -m management.cli help")


if __name__ == "__main__":
	main()
