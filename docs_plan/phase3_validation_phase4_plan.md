# AgnoBot v3 — Validación Fase 3 + Plan de Implementación Fase 4

---

## PARTE 1: VALIDACIÓN COMPLETA DE FASE 3

### Resumen de Validación

| Archivo | Estado | Issues |
|---------|--------|--------|
| `loader.py` (F3) | ⚠️ 4 issues | `enable_user_memories` en sub-agentes, import Team/TeamMode, BUILTIN_TOOL_MAP referenciado sin definir, `build_teams` no valida modelo del team |
| `gateway.py` (F3) | ⚠️ 2 issues | Teams sin pasar a AgentOS correctamente, Registry tools vacía |
| `workspace/agents/teams.yaml` | ✅ Correcto | Estructura válida, modos correctos |
| `workspace/agents/research_agent.yaml` | ⚠️ 1 issue | `enable_user_memories` no documentado en Agno |
| `management/validator.py` (F3) | ✅ Correcto | Validación de sub-agentes y teams incluida |
| `workspace/config.yaml` (F3) | ✅ Correcto | Canal Slack agregado |
| `README.md` | ✅ Correcto | Documentación actualizada |
| `.env.example` | ⚠️ 1 issue | Falta `SLACK_SIGNING_SECRET` |

---

### ISSUE 1 (CRÍTICO): `enable_user_memories` en sub-agentes

**Archivo:** `loader.py` — función `build_sub_agents()`

**Problema:** El código del plan original (F1) usa `enable_user_memories=True` en sub-agentes, pero este parámetro **no existe en la documentación oficial de Agno**. La versión corregida de F3 en la base de conocimiento ya lo eliminó del agente principal, pero lo mantiene en la definición YAML del `research_agent.yaml`.

**Código actual en `workspace/agents/research_agent.yaml`:**
```yaml
config:
  tool_call_limit: 5
  enable_user_memories: true   # ← NO DOCUMENTADO EN AGNO
  add_datetime_to_context: true
  markdown: true
```

**Código corregido en `build_sub_agents()` (loader.py F3):**
El loader.py de F3 ya NO lee `enable_user_memories` y usa `enable_agentic_memory` correctamente con `MemoryManager`. ✅

**Corrección necesaria:**
```yaml
# workspace/agents/research_agent.yaml — DESPUÉS
config:
  tool_call_limit: 5
  enable_agentic_memory: false  # Sub-agentes no necesitan memoria propia
  add_datetime_to_context: true
  markdown: true
```

**Impacto:** Bajo. El parámetro es ignorado por el loader.py de F3, pero mantenerlo en el YAML puede causar confusión.

---

### ISSUE 2 (MODERADO): Import de `Team` y `TeamMode`

**Archivo:** `loader.py`

**Problema:** El código F3 referencia `Team`, `TeamMode`, y `BUILTIN_TOOL_MAP` pero la sección de imports visible en la base de conocimiento no los incluye explícitamente. Según la documentación oficial de Agno:

```python
from agno.team import Team
from agno.team.mode import TeamMode
```

**Validación contra docs oficiales:**
- `Team` se importa de `agno.team` ✅ (confirmado en docs: `building-teams`)
- `TeamMode` se importa de `agno.team.mode` ✅ (confirmado en docs: `building-teams`)
- Modos válidos: `coordinate`, `route`, `broadcast`, `tasks` ✅

**Código correcto (ya presente en F3):**
```python
TEAM_MODE_MAP: dict[str, TeamMode] = {
    "coordinate": TeamMode.coordinate,
    "route": TeamMode.route,
    "broadcast": TeamMode.broadcast,
    "tasks": TeamMode.tasks,
}
```

**Nota:** El plan original de F1 listaba `collaborate` como modo válido en `teams.yaml`. Este modo NO existe en Agno. Los modos correctos son: `coordinate`, `route`, `broadcast`, `tasks`. El código F3 ya corrige esto.

---

### ISSUE 3 (MODERADO): `BUILTIN_TOOL_MAP` no definido en el código visible

**Archivo:** `loader.py`

**Problema:** Las funciones `build_tools()` y `build_sub_agents()` referencian `BUILTIN_TOOL_MAP` pero la definición como constante a nivel de módulo no es visible en los snippets de la base de conocimiento. Se necesita confirmar que existe:

```python
BUILTIN_TOOL_MAP: dict[str, Callable] = {
    "duckduckgo": lambda cfg: DuckDuckGoTools(**cfg),
    "crawl4ai": lambda cfg: Crawl4aiTools(**cfg),
    "reasoning": lambda cfg: ReasoningTools(**cfg),
}
```

**Estado:** Presumiblemente correcto (el código lo usa), pero debe verificarse que esté definido a nivel de módulo antes de `build_tools()`.

---

### ISSUE 4 (MENOR): Registry con `tools=[]` vacía

**Archivo:** `gateway.py` (F3)

**Problema:** El gateway F3 crea el Registry con `tools=[]`:
```python
registry = Registry(
    name="AgnoBot Registry",
    tools=[],          # ← Vacía
    models=all_models,
    dbs=[db],
)
```

**En la versión F1 era:**
```python
registry = Registry(
    name="AgnoBot Registry",
    tools=[DuckDuckGoTools(), Crawl4aiTools()],  # ← Con tools
    models=[main_agent.model],
    dbs=[db],
)
```

**Recomendación:** El Registry necesita tools para que Studio pueda asignarlos a agentes creados visualmente. Se debe poblar desde los tools cargados del workspace:

```python
# Recopilar tools únicos para Registry
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.crawl4ai import Crawl4aiTools

registry_tools = [DuckDuckGoTools(), Crawl4aiTools()]
registry = Registry(
    name="AgnoBot Registry",
    tools=registry_tools,
    models=all_models,
    dbs=[db],
)
```

---

### ISSUE 5 (MENOR): `.env.example` falta `SLACK_SIGNING_SECRET`

**Archivo:** `.env.example`

**Problema:** El validator.py de F3 valida `SLACK_SIGNING_SECRET` además de `SLACK_TOKEN`, pero el `.env.example` podría no incluirlo.

**Corrección:**
```bash
# === Slack ===
SLACK_TOKEN=xoxb-tu-bot-token
SLACK_SIGNING_SECRET=tu_signing_secret
```

---

### Patrones Validados Correctamente en F3

| Patrón | Archivo | Verificación |
|--------|---------|-------------|
| `from agno.team import Team` | loader.py | ✅ Docs: `teams/building-teams` |
| `from agno.team.mode import TeamMode` | loader.py | ✅ Docs: `teams/building-teams` |
| `TeamMode.coordinate / route / broadcast / tasks` | loader.py | ✅ Docs confirma 4 modos |
| `Team(name, id, mode, members, model, db, instructions)` | loader.py | ✅ Docs: `building-teams` |
| `team.members` requiere `list[Agent]` con `name` y `role` | loader.py | ✅ Docs: "Each member should have a name and role" |
| `Slack(agent=main_agent)` | gateway.py | ✅ Docs: `interfaces/slack/introduction` |
| `AgentOS(teams=teams)` | gateway.py | ✅ Docs: `agent-os/usage/demo` |
| `MemoryManager(model=model, db=db)` en sub-agentes | loader.py | ✅ Coherente con corrección F2 |
| `build_teams()` resuelve miembros por ID | loader.py | ✅ Lógica correcta |
| `build_teams()` valida mínimo 2 miembros | loader.py | ✅ Requisito lógico |
| `build_sub_agents()` excluye `teams.yaml` | loader.py | ✅ Correcto |
| Validator valida YAML de sub-agentes | validator.py | ✅ Robusto |
| Validator valida `SLACK_TOKEN` y `SLACK_SIGNING_SECRET` | validator.py | ✅ Correcto |

---

### Código Corregido: Cambios Necesarios para F3

```python
# ═══ CAMBIO 1: workspace/agents/research_agent.yaml ═══
# Reemplazar enable_user_memories por enable_agentic_memory
config:
  tool_call_limit: 5
  enable_agentic_memory: false
  add_datetime_to_context: true
  markdown: true

# ═══ CAMBIO 2: gateway.py — Registry con tools ═══
registry = Registry(
    name="AgnoBot Registry",
    tools=[DuckDuckGoTools(), Crawl4aiTools()],
    models=all_models,
    dbs=[db],
)

# ═══ CAMBIO 3: .env.example — Agregar SLACK_SIGNING_SECRET ═══
# En la sección Slack:
SLACK_TOKEN=xoxb-tu-bot-token
SLACK_SIGNING_SECRET=tu_signing_secret
```

---

## PARTE 2: REVISIÓN DE LA BASE DE CONOCIMIENTO

### Estado General del Proyecto

| Fase | Estado | Archivos | Observaciones |
|------|--------|----------|---------------|
| F1: MVP | ✅ Implementada + Validada | loader.py, gateway.py, workspace/*, routes/*, docker-compose.yml | Correcciones de F2 aplicadas (MemoryManager) |
| F2: CLI + Admin | ✅ Implementada + Validada | management/cli.py, admin.py, validator.py | AgentOSClient funcional |
| F3: Multi-Canal + Teams | ✅ Implementada — 5 issues menores | loader.py (build_teams), gateway.py (teams, Slack), teams.yaml | Issues documentados arriba |

### Coherencia del Código

**Aspectos positivos:**
- El patrón de workspace declarativo es coherente a lo largo de las 3 fases
- La migración de `enable_user_memories` a `enable_agentic_memory + MemoryManager` se aplicó correctamente al agente principal y sub-agentes
- La estructura de `build_teams()` con resolución de miembros por ID es robusta
- El validator.py fue actualizado para validar sub-agentes y teams
- Los 4 modos de Team (`coordinate`, `route`, `broadcast`, `tasks`) coinciden con la documentación oficial

**Deuda técnica identificada:**
1. El YAML `research_agent.yaml` aún contiene `enable_user_memories` (param fantasma)
2. Registry sin tools limita la funcionalidad de Studio
3. No hay tests automatizados (ninguna fase los incluye)
4. El `build_mcp_tools()` para transport `stdio` retorna un `dict` en vez de un `MCPTools` — esto funciona porque se filtra después, pero no es elegante

---

## PARTE 3: ¿CUÁNDO SE PUEDE HACER LA PRIMERA PRUEBA?

### Prueba Funcional Mínima: **Desde el final de la Fase 1**

La Fase 1 ya entrega un sistema funcional que se puede probar end-to-end:

```bash
# 1. Levantar PostgreSQL
docker-compose up -d db

# 2. Configurar .env con credenciales reales
cp .env.example .env
# Editar con API keys reales (GOOGLE_API_KEY o OPENAI_API_KEY, DB_*, WHATSAPP_*)

# 3. Arrancar gateway
python gateway.py

# 4. Verificar que responde
curl http://localhost:8000/health

# 5. Probar via WhatsApp (requiere webhook público + ngrok)
# o via API directa:
curl -X POST http://localhost:8000/v1/agents/agnobot-main/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿quién eres?", "user_id": "test-user"}'
```

### Prueba Completa por Fase

| Fase | Qué se puede probar | Requisitos |
|------|---------------------|------------|
| **F1** | Agente responde via API, WhatsApp funciona, Knowledge upload/search, MCP docs.agno.com | PostgreSQL + API keys + ngrok |
| **F2** | CLI genera workspace, validator detecta errores, admin CLI funciona | F1 arrancado |
| **F3** | Slack responde, Teams coordinan agentes, Studio visible en os.agno.com | Slack App creada + F1 arrancado |
| **F4** | Remote Agents distribuidos, MCP Supabase, A2A | Dos instancias de AgentOS |

### Prueba Recomendada Ahora (Post-F3)

Con las 3 fases implementadas, ya puedes hacer una prueba integral:

```bash
# 1. PostgreSQL
docker-compose up -d db

# 2. Generar workspace con CLI
python -m management.cli

# 3. Validar
python -m management.validator

# 4. Arrancar
python gateway.py

# 5. Probar agente principal
python -m management.admin run --agent agnobot-main --message "Hola" --stream

# 6. Probar Team (si hay 2+ agentes)
python -m management.admin run --agent research-team --message "Busca noticias de IA"

# 7. Studio: os.agno.com > Add OS > Local > http://localhost:8000

# 8. Slack: configurar webhook y enviar mensaje al bot
```

---

## PARTE 4: PLAN DE IMPLEMENTACIÓN — FASE 4

### Objetivo

**Remote Execution + MCP Avanzado + A2A Protocol:** Agentes distribuidos en múltiples instancias de AgentOS, con MCP servers configurables (Supabase, GitHub) y soporte para el protocolo A2A inter-framework.

### Entregables

| # | Entregable | Archivo | Descripción |
|---|------------|---------|-------------|
| 1 | Remote Agent Server | `remote_server.py` | AgentOS secundario que hospeda agentes especializados |
| 2 | Gateway con RemoteAgent | `gateway.py` (actualizado) | Integra agentes locales + remotos |
| 3 | Loader con Remote Agents | `loader.py` (actualizado) | Lee `execution.type: remote` de YAML y crea `RemoteAgent` |
| 4 | MCP Supabase habilitado | `workspace/mcp.yaml` (actualizado) | Agente gestiona su propia DB via MCP |
| 5 | MCP GitHub habilitado | `workspace/mcp.yaml` (actualizado) | Agente interactúa con repos GitHub |
| 6 | A2A Interface | `gateway.py` (actualizado) | Exponer agentes via protocolo A2A |
| 7 | Remote Agent YAML | `workspace/agents/research_agent.yaml` (actualizado) | `execution.type: remote` con URL |
| 8 | Docker multi-servicio | `docker-compose.yml` (actualizado) | Gateway + Research Server + DB |
| 9 | Validator actualizado | `management/validator.py` (actualizado) | Valida remote URLs y MCP configs |
| 10 | Admin con RemoteAgent | `management/admin.py` (actualizado) | Listar agentes remotos y su estado |

---

### Arquitectura Fase 4

```
┌─────────────────────────────────────────────────────────────┐
│                    GATEWAY (:8000)                            │
│  AgentOS Principal                                           │
│  ├── AgnoBot (local)                                        │
│  ├── RemoteAgent → Research Server (:7778)                  │
│  ├── RemoteAgent → Data Server (:7779) [futuro]             │
│  ├── Interfaces: WhatsApp, Slack, Web, A2A                  │
│  └── MCP Server (/mcp)                                      │
├─────────────────────────────────────────────────────────────┤
│                 RESEARCH SERVER (:7778)                       │
│  AgentOS Secundario                                          │
│  ├── Research Agent (local en este servidor)                │
│  ├── Tools: DuckDuckGo, Crawl4ai, Tavily                   │
│  ├── MCP: docs.agno.com + Supabase + GitHub                │
│  └── Sin interfaces (solo API)                               │
├─────────────────────────────────────────────────────────────┤
│               PostgreSQL / Supabase                          │
│  Base de datos compartida (o separada por servicio)          │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.1 — `remote_server.py`

Servidor AgentOS independiente que hospeda el Research Agent.

```python
"""
Remote Research Server — AgentOS secundario para agentes especializados.

Ejecutar:
    python remote_server.py

Este servidor se conecta desde el Gateway principal via RemoteAgent.
"""
import os

from dotenv import load_dotenv

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.memory import MemoryManager
from agno.models.google import Gemini
from agno.os import AgentOS
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.vectordb.pgvector import PgVector, SearchType
from agno.utils.log import logger

load_dotenv()

# === Base de datos (misma instancia que el gateway, o separada) ===
db_url = (
    f"postgresql+psycopg://{os.getenv('DB_USER', 'ai')}:{os.getenv('DB_PASSWORD', 'ai')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5532')}"
    f"/{os.getenv('DB_NAME', 'ai')}?sslmode={os.getenv('DB_SSLMODE', 'prefer')}"
)

db = PostgresDb(
    db_url=db_url,
    id="research_db",
    knowledge_table="research_knowledge_contents",
)

knowledge = Knowledge(
    vector_db=PgVector(
        table_name="research_knowledge_vectors",
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=db,
    max_results=5,
)

# === Modelo ===
model = Gemini(id=os.getenv("RESEARCH_MODEL", "gemini-2.0-flash"))

# === Tools ===
tools = [
    DuckDuckGoTools(),
    Crawl4aiTools(max_length=3000),
    ReasoningTools(add_instructions=True),
    MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp"),
]

# === Research Agent ===
memory_manager = MemoryManager(model=model, db=db)

research_agent = Agent(
    name="Research Agent",
    id="research-agent",
    role="Realiza búsquedas web profundas, scrapea páginas y sintetiza información con fuentes.",
    model=model,
    db=db,
    knowledge=knowledge,
    search_knowledge=True,
    tools=tools,
    instructions=[
        "Eres un agente especializado en investigación profunda.",
        "Busca en múltiples fuentes web y sintetiza la información.",
        "Siempre cita tus fuentes con URLs completas.",
        "Si la información es contradictoria, menciona ambas versiones.",
        "Responde en el idioma del usuario.",
    ],
    memory_manager=memory_manager,
    enable_agentic_memory=True,
    tool_call_limit=8,
    add_datetime_to_context=True,
    markdown=True,
)

# === AgentOS Secundario ===
agent_os = AgentOS(
    id="research-server",
    name="Research Agent Server",
    agents=[research_agent],
    knowledge=[knowledge],
    db=db,
    tracing=True,
    enable_mcp_server=False,  # Solo el gateway expone MCP
)

app = agent_os.get_app()

if __name__ == "__main__":
    port = int(os.getenv("RESEARCH_PORT", "7778"))
    logger.info(f"Research Server arrancando en puerto {port}")
    agent_os.serve(app="remote_server:app", host="0.0.0.0", port=port)
```

---

### 4.2 — `loader.py` — Actualización para Remote Agents

Agregar soporte para `execution.type: remote` en sub-agentes YAML.

```python
# ═══ NUEVO IMPORT ═══
from agno.agent import Agent, RemoteAgent

# ═══ NUEVA FUNCIÓN: build_remote_or_local_agents() ═══
def build_sub_agents(
    db: Union[PostgresDb, SqliteDb],
    knowledge: Optional[Knowledge],
) -> tuple[list[Agent], list[RemoteAgent]]:
    """
    Carga sub-agentes desde workspace/agents/*.yaml.
    Retorna tupla: (agentes_locales, agentes_remotos).
    """
    local_agents: list[Agent] = []
    remote_agents: list[RemoteAgent] = []
    agents_dir = WORKSPACE_DIR / "agents"
    if not agents_dir.exists():
        return local_agents, remote_agents

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
            continue

        execution = data.get("execution", {})
        exec_type = execution.get("type", "local")
        agent_id = agent_def.get("id", yaml_file.stem)

        # ── Remote Agent ──
        if exec_type == "remote":
            remote_url = _resolve_env(execution.get("remote_url", ""))
            if not remote_url:
                logger.warning(
                    f"Sub-agente '{agent_id}' es remoto pero sin remote_url. Omitido."
                )
                continue

            remote_agent = RemoteAgent(
                base_url=remote_url,
                agent_id=agent_id,
            )
            remote_agents.append(remote_agent)
            logger.info(
                f"Remote Agent registrado: {agent_id} → {remote_url}"
            )
            continue

        # ── Local Agent (código existente) ──
        model_cfg = agent_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"})
        try:
            model = build_model(model_cfg)
        except ValueError as e:
            logger.warning(f"Modelo invalido en {yaml_file.name}: {e}")
            continue

        agent_tools: list = []
        for tool_name in agent_def.get("tools", []):
            factory = BUILTIN_TOOL_MAP.get(tool_name)
            if factory is not None:
                agent_tools.append(factory({}))

        config = agent_def.get("config", {})

        sub_memory_manager = None
        if config.get("enable_agentic_memory", False):
            sub_memory_manager = MemoryManager(model=model, db=db)

        agent = Agent(
            name=agent_def.get("name", "Sub Agent"),
            id=agent_id,
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
        local_agents.append(agent)
        logger.info(f"Sub-agente local cargado: {agent.name} ({agent.id})")

    return local_agents, remote_agents


# ═══ ACTUALIZAR load_workspace() ═══
def load_workspace() -> dict[str, Any]:
    """Carga completa del workspace."""
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

    # ★ F4: Ahora retorna locales y remotos por separado
    local_sub_agents, remote_agents = build_sub_agents(db, knowledge)

    all_local = [main_agent] + local_sub_agents
    teams = build_teams(all_local, db)

    return {
        "config": config,
        "db_url": db_url,
        "db": db,
        "knowledge": knowledge,
        "main_agent": main_agent,
        "sub_agents": local_sub_agents,
        "remote_agents": remote_agents,
        "teams": teams,
        "mcp_config": mcp_config,
        "tools_config": tools_config,
    }
```

---

### 4.3 — `gateway.py` — Actualización con RemoteAgent + A2A

```python
"""
AgnoBot Gateway — Punto de entrada principal (Fase 4).
Soporta agentes locales, remotos, teams, y protocolo A2A.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agno.os import AgentOS
from agno.registry import Registry
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.utils.log import logger

from loader import load_workspace
from management.validator import validate_workspace, print_validation

# === Validación del workspace ===
validation_errors = validate_workspace()
if validation_errors:
    print_validation(validation_errors)
    logger.warning(f"Workspace tiene {len(validation_errors)} advertencia(s)")

# === Cargar workspace ===
ws = load_workspace()
config = ws["config"]
db = ws["db"]
main_agent = ws["main_agent"]
sub_agents = ws["sub_agents"]
remote_agents = ws["remote_agents"]   # ★ F4: Agentes remotos
teams = ws["teams"]
knowledge = ws["knowledge"]

# === FastAPI base ===
base_app = FastAPI(
    title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
    version="0.4.0",
)
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Knowledge Routes ===
if knowledge:
    from routes.knowledge_routes import create_knowledge_router
    knowledge_router = create_knowledge_router(knowledge)
    base_app.include_router(knowledge_router)

# === Interfaces ===
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

# ★ F4: A2A Interface (si habilitado)
if config.get("a2a", {}).get("enabled", False):
    from agno.os.interfaces.a2a import A2A
    interfaces.append(A2A(agent=main_agent))
    logger.info("Protocolo A2A habilitado")

logger.info("Canal Web disponible via os.agno.com (Control Plane)")

# === Registry para Studio ===
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

# === Combinar agentes locales + remotos ===
all_agents = [main_agent] + sub_agents + remote_agents
logger.info(f"Agentes locales: {[a.id for a in [main_agent] + sub_agents]}")
if remote_agents:
    logger.info(f"Agentes remotos: {[getattr(a, 'agent_id', 'unknown') for a in remote_agents]}")
if teams:
    logger.info(f"Teams: {[t.id for t in teams]}")

# === AgentOS ===
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
```

---

### 4.4 — `workspace/agents/research_agent.yaml` — Modo Remote

```yaml
# ===================================
# Sub-Agente: Investigador (Remote)
# ===================================

agent:
  name: "Research Agent"
  id: "research-agent"
  role: "Realiza búsquedas web profundas y sintetiza información con fuentes"

  model:
    provider: "google"
    id: "gemini-2.0-flash"

  tools:
    - duckduckgo
    - crawl4ai
    - reasoning

  instructions:
    - "Eres un agente especializado en investigación profunda."
    - "Busca en múltiples fuentes web y sintetiza la información."
    - "Siempre cita tus fuentes con URLs completas."
    - "Responde en el idioma del usuario."

  config:
    tool_call_limit: 8
    enable_agentic_memory: true
    add_datetime_to_context: true
    markdown: true

# ★ F4: Ejecución remota
execution:
  type: "remote"                           # local | remote
  remote_url: "http://localhost:7778"      # URL del research server
  # En Docker: remote_url: "http://research:7778"
```

---

### 4.5 — `workspace/mcp.yaml` — MCP Avanzado

```yaml
# ===================================
# MCP - Servidores Model Context Protocol
# ===================================

servers:
  # Documentación de Agno (siempre habilitado)
  - name: agno_docs
    enabled: true
    transport: "streamable-http"
    url: "https://docs.agno.com/mcp"

  # ★ F4: Supabase MCP - El agente gestiona su propia DB
  - name: supabase
    enabled: false
    transport: "stdio"
    command: "npx -y @supabase/mcp-server-supabase@latest --access-token=${SUPABASE_ACCESS_TOKEN}"
    description: "Permite al agente crear proyectos, schemas, edge functions en Supabase"

  # ★ F4: GitHub MCP - Interacción con repositorios
  - name: github
    enabled: false
    transport: "stdio"
    command: "npx -y @modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    description: "Permite al agente leer repos, crear issues, PRs"

  # ★ F4: Filesystem MCP (para acceso a archivos locales)
  - name: filesystem
    enabled: false
    transport: "stdio"
    command: "npx -y @modelcontextprotocol/server-filesystem /app/workspace/knowledge/docs"
    description: "Acceso del agente a documentos locales"

# Exposición como MCP server
expose:
  enabled: true
```

---

### 4.6 — `workspace/config.yaml` — Actualización F4

```yaml
# ===================================
# AgnoBot - Configuración Central (F4)
# ===================================

agent:
  name: "AgnoBot"
  id: "agnobot-main"
  description: "Asistente personal multimodal autónomo"

model:
  provider: "google"
  id: "gemini-2.0-flash"

database:
  type: "supabase"
  knowledge_table: "agnobot_knowledge_contents"
  vector_table: "agnobot_knowledge_vectors"

vector:
  search_type: "hybrid"
  embedder: "text-embedding-3-small"
  max_results: 5

channels:
  - whatsapp
  - slack

memory:
  enable_agentic_memory: true
  num_history_runs: 5

agentos:
  id: "agnobot-gateway"
  name: "AgnoBot Platform"
  port: 8000
  tracing: true
  enable_mcp_server: true

studio:
  enabled: true

# ★ F4: A2A Protocol
a2a:
  enabled: false  # Habilitar cuando se necesite interoperabilidad

# ★ F4: Remote Servers (informativo, los URLs van en agents/*.yaml)
remote_servers:
  research: "http://localhost:7778"
```

---

### 4.7 — `docker-compose.yml` — Multi-servicio

```yaml
version: "3.8"

services:
  # PostgreSQL con pgvector
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: ai
      POSTGRES_USER: ai
      POSTGRES_PASSWORD: ai
    ports:
      - "5532:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ★ F4: Research Server (agente remoto)
  research:
    build: .
    command: python remote_server.py
    ports:
      - "7778:7778"
    env_file: .env
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - RESEARCH_PORT=7778
    depends_on:
      db:
        condition: service_healthy

  # Gateway principal
  gateway:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - DB_HOST=db
      - DB_PORT=5432
    depends_on:
      db:
        condition: service_healthy
      research:
        condition: service_started
    volumes:
      - ./workspace:/app/workspace

volumes:
  pgdata:
```

---

### 4.8 — `management/validator.py` — Validación F4

Agregar validaciones para remote agents y MCP configs:

```python
# ═══ AGREGAR después de la validación de sub-agentes ═══

    # --- Validar Remote Agents ---
    for yaml_file in agents_dir.glob("*.yaml"):
        if yaml_file.name == "teams.yaml":
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # Ya reportado antes

        execution = data.get("execution", {})
        if execution.get("type") == "remote":
            remote_url = execution.get("remote_url", "")
            if not remote_url:
                errors.append(
                    f"agents/{yaml_file.name}: execution.type='remote' "
                    f"pero falta 'remote_url'"
                )
            elif not remote_url.startswith("http"):
                errors.append(
                    f"agents/{yaml_file.name}: remote_url debe empezar "
                    f"con http:// o https://"
                )

    # --- Validar MCP Servers ---
    try:
        mcp_config = yaml.safe_load(
            (ws / "mcp.yaml").read_text(encoding="utf-8")
        ) or {}
    except (yaml.YAMLError, FileNotFoundError):
        mcp_config = {}

    for server in mcp_config.get("servers", []):
        if not server.get("enabled", False):
            continue
        name = server.get("name", "sin-nombre")
        transport = server.get("transport", "")

        if transport in ("streamable-http", "sse"):
            if not server.get("url"):
                errors.append(f"mcp.yaml: server '{name}' habilitado sin 'url'")
        elif transport == "stdio":
            if not server.get("command"):
                errors.append(f"mcp.yaml: server '{name}' habilitado sin 'command'")
            # Validar variables de entorno requeridas
            if name == "supabase" and not os.getenv("SUPABASE_ACCESS_TOKEN"):
                errors.append(".env: falta SUPABASE_ACCESS_TOKEN (MCP Supabase habilitado)")
            if name == "github" and not os.getenv("GITHUB_TOKEN"):
                errors.append(".env: falta GITHUB_TOKEN (MCP GitHub habilitado)")
```

---

### 4.9 — `.env.example` — Variables F4

```bash
# ===================================
# AgnoBot - Variables de Entorno (F4)
# ===================================

# === API Keys ===
GOOGLE_API_KEY=...
OPENAI_API_KEY=...            # Embeddings
# ANTHROPIC_API_KEY=...       # Si usa Claude como modelo

# === Base de datos ===
DB_HOST=localhost
DB_PORT=5532
DB_USER=ai
DB_PASSWORD=ai
DB_NAME=ai
DB_SSLMODE=prefer

# === WhatsApp ===
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_WEBHOOK_URL=https://tu-dominio.com/webhook

# === Slack ===
# SLACK_TOKEN=xoxb-...
# SLACK_SIGNING_SECRET=...

# === MCP Supabase (F4) ===
# SUPABASE_ACCESS_TOKEN=...

# === MCP GitHub (F4) ===
# GITHUB_TOKEN=ghp_...

# === Remote Servers (F4) ===
RESEARCH_PORT=7778
# RESEARCH_MODEL=gemini-2.0-flash

# === Seguridad ===
# OS_SECURITY_KEY=genera_con_openssl_rand_hex_32

# === Entorno ===
APP_ENV=development
```

---

### 4.10 — `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY . .

# Puerto por defecto
EXPOSE 8000

# Comando por defecto (gateway)
CMD ["python", "gateway.py"]
```

---

### 4.11 — `requirements.txt` — F4

```
# === Core ===
agno[os]>=0.5.0
pyyaml>=6.0
python-dotenv>=1.0.0
rich>=13.0

# === Modelos ===
google-genai>=1.0
openai>=1.50
anthropic>=0.40

# === Base de datos ===
psycopg[binary]>=3.0
sqlalchemy>=2.0
pgvector>=0.3

# === Tools ===
duckduckgo-search>=6.0
crawl4ai>=0.4
mcp>=1.0

# === MCP servers (stdio) ===
# npx se usa en runtime, no es pip dependency
```

---

### Checklist Fase 4

| # | Tarea | Prioridad | Estado |
|---|-------|-----------|--------|
| 1 | `remote_server.py` — AgentOS secundario | Alta | ⬜ |
| 2 | `loader.py` — `build_sub_agents()` retorna `(locales, remotos)` | Alta | ⬜ |
| 3 | `gateway.py` — integrar `remote_agents` en `AgentOS.agents` | Alta | ⬜ |
| 4 | `workspace/agents/research_agent.yaml` — `execution.type: remote` | Alta | ⬜ |
| 5 | `docker-compose.yml` — servicio `research` + healthcheck | Alta | ⬜ |
| 6 | `Dockerfile` — con Node.js para MCP stdio | Alta | ⬜ |
| 7 | `workspace/mcp.yaml` — Supabase + GitHub servers | Media | ⬜ |
| 8 | `workspace/config.yaml` — sección `a2a` | Media | ⬜ |
| 9 | `management/validator.py` — validar remote URLs + MCP | Media | ⬜ |
| 10 | `.env.example` — variables F4 | Baja | ⬜ |
| 11 | `requirements.txt` — actualizar | Baja | ⬜ |
| 12 | `gateway.py` — A2A interface (opcional) | Baja | ⬜ |
| 13 | Testear: `docker-compose up` levanta gateway + research + db | Alta | ⬜ |
| 14 | Testear: RemoteAgent responde via gateway | Alta | ⬜ |
| 15 | Testear: MCP Supabase funciona (si habilitado) | Media | ⬜ |
| 16 | Testear: Team con RemoteAgent como miembro | Media | ⬜ |

---

### Comandos de Prueba Fase 4

```bash
# 1. Levantar todo con Docker
docker-compose up -d

# 2. Verificar que ambos servidores están arriba
curl http://localhost:8000/health     # Gateway
curl http://localhost:7778/health     # Research Server

# 3. Listar agentes (debería mostrar locales + remotos)
python -m management.admin status

# 4. Ejecutar agente remoto via gateway
python -m management.admin run \
  --agent research-agent \
  --message "Investiga las últimas noticias sobre IA en marzo 2026" \
  --stream

# 5. Ejecutar Team que incluye agente remoto
python -m management.admin run \
  --agent research-team \
  --message "Analiza el impacto de la IA en la educación" \
  --stream

# 6. Verificar MCP Supabase (si habilitado)
# Primero habilitar en workspace/mcp.yaml y configurar SUPABASE_ACCESS_TOKEN
python -m management.admin run \
  --agent agnobot-main \
  --message "Lista las organizaciones de mi cuenta Supabase"

# 7. Verificar trazas en Studio
# os.agno.com > Add OS > Local > http://localhost:8000
# Ver trazas de ejecución remota

# 8. Probar A2A (si habilitado)
# Desde otro framework (ej. Google ADK):
# curl http://localhost:8000/a2a/agents/agnobot-main -X POST ...
```

---

### Notas Importantes de Implementación

1. **RemoteAgent es async-first:** Según la documentación oficial, `RemoteAgent` usa `arun()` para ejecución. AgentOS maneja esto internamente al recibir requests HTTP.

2. **MCP stdio requiere Node.js:** Los MCP servers que usan `npx` necesitan Node.js instalado en el contenedor Docker. El Dockerfile incluye la instalación.

3. **No usar `reload=True` en gateway:** Recordar que cuando hay MCPTools en AgentOS, no se debe usar `reload=True` en `serve()`. Esto ya está correcto en el código actual.

4. **RemoteAgent no necesita `name` ni `role`:** Según la docs de Agno, `RemoteAgent` obtiene estos datos del servidor remoto via la API `/agents/{agent_id}`. Solo necesita `base_url` y `agent_id`.

5. **Teams con RemoteAgent:** Un `RemoteAgent` puede ser miembro de un `Team` local, pero el Team necesita poder resolver el agente. Como `RemoteAgent` no tiene `id` como atributo directo al momento de construcción, `build_teams()` necesitará adaptarse para manejar esto. Recomendación: no incluir RemoteAgents en Teams definidos por YAML; mejor crear Teams en código o esperar a que el RemoteAgent exponga su config.

6. **Auth en Remote:** Si en el futuro se habilita JWT/RBAC (F6), los endpoints `/config`, `/agents`, `/agents/{id}` del server remoto deben quedar sin protección para que el Gateway funcione correctamente (documentado en Agno).

---

*Documento generado el 25 de marzo de 2026*
*Incluye: Validación F3, Revisión de Base de Conocimiento, Plan F4 completo*
*Basado en documentación oficial de Agno + código existente en base de conocimiento*
