"""
Loader - Carga dinamica del workspace y construye objetos Agno.

Lee archivos YAML/MD del workspace/ y construye:
- Agente principal con tools, instrucciones y MCP
- Sub-agentes desde workspace/agents/*.yaml
- Teams multi-agente desde workspace/agents/teams.yaml
- Knowledge base con PgVector/Supabase
- Configuracion de canales (WhatsApp, Slack, Web)
"""
import os
import re
import yaml
from pathlib import Path
from typing import Any, Optional, Union

from dotenv import load_dotenv

from agno.agent import Agent
from agno.team import Team
from agno.team.mode import TeamMode
from agno.db.postgres import PostgresDb
from agno.db.sqlite import SqliteDb
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from agno.memory import MemoryManager
from agno.tools.mcp import MCPTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.reasoning import ReasoningTools
from agno.utils.log import logger

load_dotenv()

WORKSPACE_DIR = Path(os.getenv("AGNOBOT_WORKSPACE", "workspace"))

ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str) -> str:
	"""Resuelve referencias ${VAR} en valores de configuracion."""
	if not isinstance(value, str):
		return value

	def replacer(match: re.Match[str]) -> str:
		return os.getenv(match.group(1), "")

	return ENV_VAR_PATTERN.sub(replacer, value)


def _resolve_config(config: dict[str, Any]) -> dict[str, Any]:
	"""Resuelve todas las referencias ${VAR} en un dict."""
	resolved: dict[str, Any] = {}
	for k, v in config.items():
		if isinstance(v, str):
			resolved[k] = _resolve_env(v)
		elif isinstance(v, dict):
			resolved[k] = _resolve_config(v)
		else:
			resolved[k] = v
	return resolved


def load_yaml(filename: str) -> dict[str, Any]:
	"""Carga un archivo YAML del workspace."""
	path = WORKSPACE_DIR / filename
	if not path.exists():
		logger.warning(f"Archivo no encontrado: {path}")
		return {}
	with open(path, "r", encoding="utf-8") as f:
		return yaml.safe_load(f) or {}


def load_instructions() -> list[str]:
	"""Carga instrucciones desde instructions.md."""
	path = WORKSPACE_DIR / "instructions.md"
	if not path.exists():
		return ["Eres un asistente personal multimodal."]
	with open(path, "r", encoding="utf-8") as f:
		content = f.read().strip()
	return [content]


def build_db_url(db_config: dict[str, Any]) -> str:
	"""Construye la URL de conexion segun el tipo de DB."""
	db_type = db_config.get("type", "local")

	if db_type == "sqlite":
		return "sqlite:///tmp/agnobot.db"

	host = os.getenv("DB_HOST", "localhost")
	port = os.getenv("DB_PORT", "5532")
	user = os.getenv("DB_USER", "ai")
	password = os.getenv("DB_PASSWORD", "ai")
	name = os.getenv("DB_NAME", "ai")
	sslmode = os.getenv("DB_SSLMODE", "prefer" if db_type == "local" else "require")

	return (
		f"postgresql+psycopg://{user}:{password}"
		f"@{host}:{port}/{name}?sslmode={sslmode}"
	)


def build_db(db_url: str, db_config: dict[str, Any]) -> Union[PostgresDb, SqliteDb]:
	"""Construye el objeto de base de datos."""
	if db_url.startswith("sqlite"):
		return SqliteDb(db_file="tmp/agnobot.db")
	return PostgresDb(
		db_url=db_url,
		id="agnobot_db",
		knowledge_table=db_config.get("knowledge_table", "agnobot_knowledge_contents"),
	)


def build_knowledge(
	db_url: str,
	db: Union[PostgresDb, SqliteDb],
	vector_config: dict[str, Any],
	db_config: dict[str, Any],
) -> Optional[Knowledge]:
	"""Construye la Knowledge base con PgVector."""
	if db_url.startswith("sqlite"):
		logger.warning("SQLite no soporta PgVector. Knowledge deshabilitada.")
		return None

	search_type_map: dict[str, SearchType] = {
		"hybrid": SearchType.hybrid,
		"vector": SearchType.vector,
		"keyword": SearchType.keyword,
	}

	return Knowledge(
		vector_db=PgVector(
			table_name=db_config.get("vector_table", "agnobot_knowledge_vectors"),
			db_url=db_url,
			search_type=search_type_map.get(
				vector_config.get("search_type", "hybrid"),
				SearchType.hybrid,
			),
			embedder=OpenAIEmbedder(
				id=vector_config.get("embedder", "text-embedding-3-small")
			),
		),
		contents_db=db,
		max_results=vector_config.get("max_results", 5),
	)


BUILTIN_TOOL_MAP: dict[str, Any] = {
	"duckduckgo": lambda cfg: DuckDuckGoTools(**cfg),
	"crawl4ai": lambda cfg: Crawl4aiTools(**cfg),
	"reasoning": lambda cfg: ReasoningTools(**cfg),
}


def build_tools(tools_config: dict[str, Any]) -> list[Any]:
	"""Construye la lista de tools segun tools.yaml."""
	tools: list[Any] = []

	for tool_def in tools_config.get("builtin", []):
		if not tool_def.get("enabled", True):
			continue
		name = tool_def["name"]
		config = _resolve_config(tool_def.get("config", {}))
		factory = BUILTIN_TOOL_MAP.get(name)
		if factory is not None:
			tools.append(factory(config))
		else:
			logger.warning(f"Tool builtin desconocido: {name}")

	for tool_def in tools_config.get("optional", []):
		if not tool_def.get("enabled", False):
			continue
		name = tool_def["name"]
		config = _resolve_config(tool_def.get("config", {}))

		if name == "email":
			from agno.tools.email import EmailTools
			if config.get("sender_email") and config.get("sender_passkey"):
				tools.append(EmailTools(**config))
		elif name == "tavily":
			from agno.tools.tavily import TavilyTools
			tools.append(TavilyTools())
		elif name == "spotify":
			from agno.tools.spotify import SpotifyTools
			tools.append(SpotifyTools())
		elif name == "shell":
			from agno.tools.shell import ShellTools
			logger.warning("ShellTools activado - riesgo de seguridad")
			tools.append(ShellTools())

	return tools


def build_mcp_tools(mcp_config: dict[str, Any]) -> list[Union[MCPTools, dict[str, Any]]]:
	"""Construye MCPTools segun mcp.yaml."""
	mcp_tools: list[Union[MCPTools, dict[str, Any]]] = []

	for server in mcp_config.get("servers", []):
		if not server.get("enabled", False):
			continue

		transport = server.get("transport", "streamable-http")

		if transport in ("streamable-http", "sse"):
			url = _resolve_env(server.get("url", ""))
			if url:
				mcp_tools.append(MCPTools(
					transport=transport,
					url=url,
				))
		elif transport == "stdio":
			command = _resolve_env(server.get("command", ""))
			env = _resolve_config(server.get("env", {}))
			if command:
				mcp_tools.append({
					"type": "stdio",
					"command": command,
					"env": {**os.environ, **env},
					"name": server.get("name", "mcp-server"),
				})

	return mcp_tools


def build_model(model_config: dict[str, Any]) -> Any:
	"""Construye el modelo segun la configuracion."""
	provider = model_config.get("provider", "google")
	model_id = model_config.get("id", "gemini-2.0-flash")

	match provider:
		case "google":
			from agno.models.google import Gemini
			return Gemini(id=model_id)
		case "openai":
			from agno.models.openai import OpenAIChat
			return OpenAIChat(id=model_id)
		case "anthropic":
			from agno.models.anthropic import Claude
			return Claude(id=model_id)
		case _:
			raise ValueError(f"Proveedor de modelo no soportado: {provider}")


TEAM_MODE_MAP: dict[str, TeamMode] = {
	"coordinate": TeamMode.coordinate,
	"route": TeamMode.route,
	"broadcast": TeamMode.broadcast,
	"tasks": TeamMode.tasks,
}


def build_sub_agents(
	db: Union[PostgresDb, SqliteDb],
	knowledge: Optional[Knowledge],
) -> list[Agent]:
	"""
	Carga sub-agentes desde workspace/agents/*.yaml.
	Excluye teams.yaml (procesado por build_teams).
	"""
	agents: list[Agent] = []
	agents_dir = WORKSPACE_DIR / "agents"
	if not agents_dir.exists():
		return agents

	excluded = {"teams.yaml"}

	for yaml_file in sorted(agents_dir.glob("*.yaml")):
		if yaml_file.name in excluded:
			continue

		try:
			data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
		except yaml.YAMLError as e:
			logger.warning(f"YAML invalido en {yaml_file.name}: {e}")
			continue

		agent_def = data.get("agent", {})
		if not agent_def:
			logger.warning(f"Sin definicion 'agent' en {yaml_file.name}")
			continue

		model_cfg = agent_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"})
		try:
			model = build_model(model_cfg)
		except ValueError as e:
			logger.warning(f"Modelo invalido en {yaml_file.name}: {e}")
			continue

		agent_tools: list[Union[DuckDuckGoTools, Crawl4aiTools, ReasoningTools]] = []
		for tool_name in agent_def.get("tools", []):
			factory = BUILTIN_TOOL_MAP.get(tool_name)
			if factory is not None:
				agent_tools.append(factory({}))
			else:
				logger.warning(f"Tool '{tool_name}' no reconocido en {yaml_file.name}")

		config = agent_def.get("config", {})

		sub_memory_manager = None
		if config.get("enable_agentic_memory", False):
			sub_memory_manager = MemoryManager(model=model, db=db)

		agent = Agent(
			name=agent_def.get("name", "Sub Agent"),
			id=agent_def.get("id", yaml_file.stem),
			role=agent_def.get("role", ""),
			model=model,
			db=db,
			knowledge=knowledge,
			search_knowledge=knowledge is not None,
			tools=agent_tools,
			instructions=agent_def.get("instructions", []),
			memory_manager=sub_memory_manager,
			enable_agentic_memory=config.get("enable_agentic_memory", False),
			tool_call_limit=config.get("tool_call_limit", 3),
			add_datetime_to_context=config.get("add_datetime_to_context", True),
			markdown=config.get("markdown", True),
		)
		agents.append(agent)
		logger.info(f"Sub-agente cargado: {agent.name} ({agent.id})")

	return agents


def build_teams(
	all_agents: list[Agent],
	db: Union[PostgresDb, SqliteDb],
) -> list[Team]:
	"""
	Carga Teams desde workspace/agents/teams.yaml.
	Resuelve miembros por ID contra la lista de agentes disponibles.
	"""
	teams_data = load_yaml("agents/teams.yaml")
	teams_list = teams_data.get("teams", [])
	if not teams_list:
		return []

	agent_index: dict[str, Agent] = {a.id: a for a in all_agents if a.id}

	teams: list[Team] = []

	for team_def in teams_list:
		team_name = team_def.get("name", "Unnamed Team")

		member_ids: list[str] = team_def.get("members", [])
		members: list[Agent] = []
		for mid in member_ids:
			agent = agent_index.get(mid)
			if agent is not None:
				members.append(agent)
			else:
				logger.warning(
					f"Team '{team_name}': miembro '{mid}' no encontrado. "
					f"Disponibles: {list(agent_index.keys())}"
				)

		if len(members) < 2:
			logger.warning(
				f"Team '{team_name}' necesita al menos 2 miembros, "
				f"tiene {len(members)}. Omitido."
			)
			continue

		model_cfg = team_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"})
		try:
			model = build_model(model_cfg)
		except ValueError as e:
			logger.warning(f"Modelo invalido en team '{team_name}': {e}")
			continue

		mode_str = team_def.get("mode", "coordinate")
		mode = TEAM_MODE_MAP.get(mode_str)
		if mode is None:
			logger.warning(
				f"Team '{team_name}': modo '{mode_str}' no valido. "
				f"Opciones: {list(TEAM_MODE_MAP.keys())}. Usando 'coordinate'."
			)
			mode = TeamMode.coordinate

		team = Team(
			name=team_name,
			id=team_def.get("id", team_name.lower().replace(" ", "-")),
			mode=mode,
			members=members,
			model=model,
			db=db,
			instructions=team_def.get("instructions", []),
			markdown=True,
			enable_agentic_memory=team_def.get("enable_agentic_memory", False),
		)
		teams.append(team)
		logger.info(
			f"Team cargado: {team.name} ({team.id}) — "
			f"modo={mode_str}, miembros={[m.id for m in members]}"
		)

	return teams


def load_workspace() -> dict[str, Any]:
	"""
	Carga completa del workspace - retorna un dict con todos los objetos
	necesarios para construir el AgentOS.
	"""
	config = load_yaml("config.yaml")
	tools_config = load_yaml("tools.yaml")
	mcp_config = load_yaml("mcp.yaml")

	db_config = config.get("database", {})
	db_url = build_db_url(db_config)
	db = build_db(db_url, db_config)

	vector_config = config.get("vector", {})
	knowledge = build_knowledge(db_url, db, vector_config, db_config)

	tools = build_tools(tools_config)
	mcp_tools = build_mcp_tools(mcp_config)

	for mcp_tool in mcp_tools:
		if isinstance(mcp_tool, MCPTools):
			tools.append(mcp_tool)

	instructions = load_instructions()
	model = build_model(config.get("model", {}))
	mem_config = config.get("memory", {})
	agent_config = config.get("agent", {})

	memory_manager = None
	if mem_config.get("enable_agentic_memory", True):
		memory_manager = MemoryManager(model=model, db=db)

	main_agent = Agent(
		name=agent_config.get("name", "AgnoBot"),
		id=agent_config.get("id", "agnobot-main"),
		description=agent_config.get("description", "Asistente personal multimodal"),
		model=model,
		db=db,
		knowledge=knowledge,
		search_knowledge=knowledge is not None,
		tools=tools,
		instructions=instructions,
		memory_manager=memory_manager,
		enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
		add_history_to_context=True,
		num_history_runs=mem_config.get("num_history_runs", 5),
		add_datetime_to_context=True,
		markdown=True,
	)

	sub_agents = build_sub_agents(db, knowledge)
	all_agents = [main_agent] + sub_agents
	teams = build_teams(all_agents, db)

	return {
		"config": config,
		"db_url": db_url,
		"db": db,
		"knowledge": knowledge,
		"main_agent": main_agent,
		"sub_agents": sub_agents,
		"teams": teams,
		"mcp_config": mcp_config,
		"tools_config": tools_config,
	}
