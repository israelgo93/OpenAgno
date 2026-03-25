"""
AgnoBot Gateway - Punto de entrada principal.
Lee el workspace/ y construye el AgentOS completo.

Fase 3: Sub-agentes, Teams, Slack, Studio mejorado.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agno.os import AgentOS
from agno.registry import Registry
from agno.utils.log import logger

from loader import load_workspace
from management.validator import validate_workspace, print_validation

validation_errors = validate_workspace()
if validation_errors:
	print_validation(validation_errors)
	logger.warning(f"Workspace tiene {len(validation_errors)} advertencia(s)")

ws = load_workspace()
config = ws["config"]
db = ws["db"]
main_agent = ws["main_agent"]
sub_agents = ws["sub_agents"]
teams = ws["teams"]
knowledge = ws["knowledge"]

base_app = FastAPI(
	title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
	version="0.3.0",
)
base_app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

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
		tools=[],
		models=all_models,
		dbs=[db],
	)
	logger.info("Studio Registry configurado")

all_agents = [main_agent] + sub_agents
logger.info(f"Agentes cargados: {[a.id for a in all_agents]}")
if teams:
	logger.info(f"Teams cargados: {[t.id for t in teams]}")

os_config = config.get("agentos", {})

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
)

app = agent_os.get_app()

if __name__ == "__main__":
	port = int(os.getenv("PORT", os_config.get("port", 8000)))
	agent_os.serve(app="gateway:app", host="0.0.0.0", port=port)
