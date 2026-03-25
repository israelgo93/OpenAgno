"""
AgnoBot Gateway - Punto de entrada principal.
Lee el workspace/ y construye el AgentOS completo.

Fase 5: Scheduler, auto-ingesta Knowledge, Tavily MCP.
"""
import inspect
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from agno.os import AgentOS
from agno.registry import Registry
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.utils.log import logger

from loader import load_workspace
from management.validator import print_validation, validate_workspace, workspace_warnings

validation_errors = validate_workspace()
if validation_errors:
	print_validation(validation_errors)
	logger.warning(f"Workspace tiene {len(validation_errors)} advertencia(s)")
for _w in workspace_warnings():
	logger.warning(_w)

ws = load_workspace()
config = ws["config"]
db = ws["db"]
main_agent = ws["main_agent"]
sub_agents = ws["sub_agents"]
teams = ws["teams"]
knowledge = ws["knowledge"]
schedules = ws["schedules"]
knowledge_doc_paths = ws["knowledge_doc_paths"]
knowledge_urls = ws["knowledge_urls"]


async def _auto_ingest_knowledge() -> None:
	"""Ingesta automatica de documentos y URLs al arrancar."""
	if not knowledge:
		return

	knowledge_config = config.get("knowledge", {})

	if knowledge_config.get("auto_ingest_docs", True) and knowledge_doc_paths:
		logger.info(f"Auto-ingesta: {len(knowledge_doc_paths)} archivo(s) en knowledge/docs/")
		for doc_path in knowledge_doc_paths:
			try:
				knowledge.insert(
					path=str(doc_path),
					name=doc_path.name,
					skip_if_exists=True,
				)
				logger.info(f"  Ingestado: {doc_path.name}")
			except Exception as e:
				logger.warning(f"  Error ingestando {doc_path.name}: {e}")

	if knowledge_config.get("auto_ingest_urls", True) and knowledge_urls:
		logger.info(f"Auto-ingesta: {len(knowledge_urls)} URL(s) desde urls.yaml")
		for url_entry in knowledge_urls:
			url = url_entry.get("url", "")
			name = url_entry.get("name", url)
			if not url:
				continue
			try:
				knowledge.insert(
					url=url,
					name=name,
					skip_if_exists=True,
				)
				logger.info(f"  Ingestado URL: {name}")
			except Exception as e:
				logger.warning(f"  Error ingestando URL {name}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
	await _auto_ingest_knowledge()
	yield


base_app = FastAPI(
	title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
	version="0.5.0",
	lifespan=lifespan,
)
base_app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@base_app.get("/")
async def root() -> RedirectResponse:
	"""La raiz no tiene UI de AgentOS; redirige a la documentacion interactiva OpenAPI."""
	return RedirectResponse(url="/docs", status_code=307)


if knowledge:
	from routes.knowledge_routes import create_knowledge_router
	knowledge_router = create_knowledge_router(knowledge)
	base_app.include_router(knowledge_router)

interfaces = []
channels = config.get("channels", ["whatsapp"])

if "whatsapp" in channels:
	from agno.os.interfaces.whatsapp import Whatsapp
	interfaces.append(Whatsapp(agent=main_agent))
	logger.info("Canal WhatsApp habilitado")

if "slack" in channels:
	from agno.os.interfaces.slack import Slack
	interfaces.append(Slack(agent=main_agent))
	logger.info("Canal Slack habilitado")

if config.get("a2a", {}).get("enabled", False):
	try:
		from agno.os.interfaces.a2a import A2A
		interfaces.append(A2A(agent=main_agent))
		logger.info("Protocolo A2A habilitado")
	except ImportError:
		logger.warning("A2A no disponible. Instalar: pip install agno[a2a]")

logger.info("Canal Web disponible via os.agno.com (Control Plane)")

studio_config = config.get("studio", {})
registry = None
if studio_config.get("enabled", True) and not ws["db_url"].startswith("sqlite"):
	all_models = [main_agent.model]
	for sa in sub_agents:
		if sa.model not in all_models:
			all_models.append(sa.model)

	registry = Registry(
		name="AgnoBot Registry",
		tools=[DuckDuckGoTools(), Crawl4aiTools()],
		models=all_models,
		dbs=[db],
	)
	logger.info("Studio Registry configurado")

all_agents = [main_agent] + sub_agents
logger.info(f"Agentes cargados: {[a.id for a in all_agents]}")
if teams:
	logger.info(f"Teams cargados: {[t.id for t in teams]}")
if schedules:
	logger.info(f"Schedules cargados: {[s['name'] for s in schedules]}")

os_config = config.get("agentos", {})
scheduler_cfg = config.get("scheduler", {})

_agent_os_params = inspect.signature(AgentOS.__init__).parameters
_scheduler_kwargs: dict[str, object] = {}
if scheduler_cfg.get("enabled", True) and "scheduler" in _agent_os_params:
	_scheduler_kwargs["scheduler"] = True
	if "scheduler_poll_interval" in _agent_os_params:
		_scheduler_kwargs["scheduler_poll_interval"] = int(
			scheduler_cfg.get("poll_interval", 15)
		)
	logger.info(
		"Scheduler AgentOS habilitado (poll cada %ss)",
		_scheduler_kwargs.get("scheduler_poll_interval", 15),
	)

if schedules:
	if not scheduler_cfg.get("enabled", True):
		logger.info(
			"schedules.yaml: referencia cargada; scheduler.enabled=false, cron de AgentOS desactivado."
		)
	elif "scheduler" not in _agent_os_params:
		logger.warning(
			"schedules.yaml tiene entradas pero AgentOS no expone scheduler; usa agno[os,scheduler]."
		)

agent_os = AgentOS(
	id=os_config.get("id", "agnobot-gateway"),
	name=os_config.get("name", "AgnoBot Platform"),
	agents=all_agents,
	teams=teams if teams else None,
	interfaces=interfaces,
	knowledge=[knowledge] if knowledge else None,
	db=db,
	registry=registry,
	tracing=os_config.get("tracing", True),
	enable_mcp_server=ws["mcp_config"].get("expose", {}).get("enabled", True),
	base_app=base_app,
	on_route_conflict="preserve_base_app",
	**_scheduler_kwargs,
)

app = agent_os.get_app()

if __name__ == "__main__":
	port = int(os.getenv("PORT", os_config.get("port", 8000)))
	agent_os.serve(app="gateway:app", host="0.0.0.0", port=port)
