# OpenAgno — Validación Fase 2 + Plan de Implementación Fase 3

---

## PARTE 1: VALIDACIÓN COMPLETA DE FASE 2

### Resumen Ejecutivo

| Archivo | Estado | Issues |
|---------|--------|--------|
| `loader.py` | ✅ Correcto | MemoryManager implementado correctamente |
| `gateway.py` | ✅ Correcto | Validación integrada, patrones correctos |
| `routes/knowledge_routes.py` | ⚠️ 2 issues | Endpoints list/delete siguen siendo stub |
| `management/__init__.py` | ✅ Correcto | Exporta `validate_workspace` |
| `management/validator.py` | ✅ Correcto | Validación completa de workspace + .env |
| `management/cli.py` | ⚠️ 1 issue menor | Falta generar `research_agent.yaml` |
| `management/admin.py` | ⚠️ 3 issues | API AgentOSClient no validada contra docs |
| `workspace/config.yaml` | ✅ Correcto | Params no documentados eliminados |
| `requirements.txt` | ✅ Correcto | `rich` agregado |
| `docker-compose.yml` | ✅ Correcto | pgvector:pg17 |
| `.env.example` | ✅ Correcto | Variables completas |

---

### Validaciones Positivas (Fase 2 aplicada correctamente)

#### 1. MemoryManager implementado — `loader.py` ✅

**Verificado contra:** `docs.agno.com/reference/memory/memory` y `docs.agno.com/memory/agent/agentic-memory`

```python
# Import correcto (confirmado en docs oficiales)
from agno.memory import MemoryManager

# Construcción correcta
memory_manager = None
if mem_config.get("enable_agentic_memory", True):
    memory_manager = MemoryManager(model=model, db=db)

# Uso correcto en Agent
main_agent = Agent(
    ...
    memory_manager=memory_manager,
    enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
    ...
)
```

**Estado:** El import path `from agno.memory import MemoryManager` está confirmado en la documentación oficial (standalone-memory, memory-optimization). El patrón `MemoryManager(model=model, db=db)` es correcto.

#### 2. Params no documentados eliminados — `config.yaml` ✅

```yaml
# Correcto: solo params documentados
memory:
  enable_agentic_memory: true
  num_history_runs: 5
```

`enable_user_memories` y `enable_session_summaries` fueron eliminados correctamente. La docs oficial solo documenta `enable_agentic_memory` como flag principal de memoria.

#### 3. Validación integrada en gateway.py ✅

```python
from management.validator import validate_workspace, print_validation

validation_errors = validate_workspace()
if validation_errors:
    print_validation(validation_errors)
    logger.warning(f"Workspace tiene {len(validation_errors)} advertencia(s)")
```

**Correcto:** No bloquea el arranque, solo advierte. Permite desarrollo iterativo.

#### 4. Knowledge routes — `skip_if_exists` aplicado ✅

```python
knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
```

**Verificado:** Parámetro documentado en la API de Knowledge.

#### 5. Validator — Lógica completa ✅

El validador cubre:
- Archivos requeridos del workspace
- YAML válido
- Secciones requeridas en config.yaml
- API keys según provider del modelo
- Variables de DB según tipo (supabase/local/sqlite)
- Variables de canales (WhatsApp/Slack)
- Variables de tools opcionales (Tavily/Email)
- Directorios requeridos

#### 6. CLI — Genera workspace completo ✅

Genera correctamente: config.yaml, instructions.md, tools.yaml, mcp.yaml, agents/teams.yaml, schedules.yaml, knowledge/urls.yaml, .env.

#### 7. Patrones de código validados ✅

| Patrón | Archivo | Estado |
|--------|---------|--------|
| `from agno.memory import MemoryManager` | loader.py | ✅ Confirmado en docs |
| `MemoryManager(model=model, db=db)` | loader.py | ✅ Patrón oficial |
| `PostgresDb(db_url=..., id=..., knowledge_table=...)` | loader.py | ✅ |
| `Knowledge(vector_db=PgVector(...), contents_db=db)` | loader.py | ✅ |
| `MCPTools(transport="streamable-http", url="...")` | loader.py | ✅ |
| `AgentOS(..., base_app=app, on_route_conflict="preserve_base_app")` | gateway.py | ✅ |
| `agent_os.serve(app="gateway:app")` sin `reload=True` | gateway.py | ✅ |
| `Registry(name=..., tools=[], models=[...], dbs=[...])` | gateway.py | ✅ |
| `Whatsapp(agent=main_agent)` | gateway.py | ✅ |
| Regex `ENV_VAR_PATTERN` para resolver `${VAR}` | loader.py | ✅ Mejora vs v1 |
| `match/case` para provider de modelo | loader.py | ✅ Pythonic |

---

### ISSUE 1 (MODERADO): Knowledge Routes — list y delete siguen siendo stub

**Archivo:** `routes/knowledge_routes.py`

**Problema:** Los endpoints `/knowledge/list` y `/knowledge/{doc_id}` no implementan funcionalidad real.

- `list_documents()` siempre retorna `{"documents": [], "message": "Knowledge Base activa"}` — no consulta la DB
- `delete_document()` solo logea y retorna éxito sin eliminar nada

**Impacto:** Funcionalidad incompleta. El upload funciona, pero no hay forma de ver ni eliminar documentos via REST.

**Nota:** AgentOS expone endpoints nativos de Knowledge (`/v1/knowledge/{knowledge_id}/content` y `/v1/knowledge/{knowledge_id}/sources`). Para Fase 2, estos stubs son aceptables. Se recomienda implementar consultas reales en Fase 5 (RAG avanzado) o delegar a los endpoints nativos de AgentOS.

**Corrección recomendada (opcional, puede posponerse a F5):**

```python
@router.get("/list")
async def list_documents() -> dict:
    """Lista documentos en la Knowledge Base."""
    try:
        if hasattr(knowledge, "vector_db") and knowledge.vector_db is not None:
            # Consultar documentos únicos desde la tabla de vectores
            from sqlalchemy import text, create_engine
            engine = create_engine(knowledge.vector_db.db_url)
            with engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT DISTINCT name FROM {knowledge.vector_db.table_name} WHERE name IS NOT NULL")
                )
                docs = [{"name": row[0]} for row in result]
            return {"documents": docs, "count": len(docs)}
        return {"documents": [], "message": "Vector DB no configurada"}
    except Exception as e:
        logger.error(f"Error al listar documentos: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### ISSUE 2 (MODERADO): admin.py — Métodos AgentOSClient no verificados

**Archivo:** `management/admin.py`

**Problema:** Varios métodos del `AdminClient` usan API de `AgentOSClient` que podrían no existir exactamente como están escritos. La documentación de AgentOSClient (`docs.agno.com/agent-os/client/agentos-client`) muestra la interfaz, pero algunos métodos usados en admin.py podrían no coincidir exactamente.

**Métodos a verificar en runtime:**

| Método usado | Existe en docs | Riesgo |
|--------------|---------------|--------|
| `client.aget_config()` | ✅ Documentado | Bajo |
| `client.get_sessions(user_id=...)` | ⚠️ Verificar signature | Medio |
| `client.get_session_runs(session_id=...)` | ⚠️ Verificar signature | Medio |
| `client.delete_session(session_id)` | ⚠️ Verificar si existe | Medio |
| `client.list_memories(user_id=...)` | ⚠️ Verificar signature | Medio |
| `client.create_memory(...)` | ⚠️ Verificar signature | Medio |
| `client.delete_memory(...)` | ⚠️ Verificar si existe | Medio |
| `client.run_agent(...)` | ✅ Documentado | Bajo |
| `client.run_agent_stream(...)` | ✅ Documentado | Bajo |
| `client.search_knowledge(...)` | ⚠️ Verificar signature | Medio |
| `RunContentEvent`, `RunCompletedEvent` | ⚠️ Verificar import path | Medio |

**Recomendación:** Ejecutar `python -m management.admin status` contra un gateway en vivo para validar. Los métodos que fallen se corrigen adaptativamente. El import `from agno.run.agent import RunContentEvent, RunCompletedEvent` podría necesitar ajuste — verificar con:

```python
# Alternativa si el import falla:
# from agno.client.events import RunContentEvent, RunCompletedEvent
# o usar el tipo genérico del evento
```

**Acción:** Marcar admin.py como "validación pendiente en runtime" — se testea cuando el gateway esté operativo.

---

### ISSUE 3 (MENOR): CLI no genera research_agent.yaml

**Archivo:** `management/cli.py`

**Problema:** El plan de Fase 2 indica que el CLI debe generar `workspace/agents/research_agent.yaml`, pero la implementación actual solo genera `workspace/agents/teams.yaml`. El research_agent.yaml que existía en el plan v3 no se genera automáticamente.

**Impacto:** Menor. El agente funciona sin sub-agentes. Los sub-agentes son Fase 3.

**Corrección (agregar al CLI antes de generar teams.yaml):**

```python
# --- agents/research_agent.yaml ---
research = {
    "agent": {
        "name": "Research Agent",
        "id": "research-agent",
        "role": "Realiza busquedas web profundas y sintetiza informacion",
        "model": {"provider": provider, "id": model_id},
        "tools": ["duckduckgo", "crawl4ai"],
        "instructions": [
            "Eres un agente especializado en investigacion.",
            "Busca en la web y sintetiza informacion.",
            "Siempre cita tus fuentes con URLs.",
        ],
        "config": {
            "tool_call_limit": 5,
            "enable_user_memories": True,
            "add_datetime_to_context": True,
            "markdown": True,
        },
    },
    "execution": {"type": "local"},
}
_write_yaml(workspace_dir / "agents" / "research_agent.yaml", research)
```

---

### ISSUE 4 (MENOR): loader.py — build_sub_agents eliminada pero referenciada en plan

**Archivo:** `loader.py`

**Observación:** La función `build_sub_agents()` que existía en el plan v3 fue eliminada del `loader.py` actual. El `load_workspace()` actual NO carga sub-agentes. Esto es coherente con Fase 1-2 (solo agente principal), pero requiere re-implementación en Fase 3.

**El gateway.py actual refleja esto correctamente:**
```python
agent_os = AgentOS(
    ...
    agents=[main_agent],  # Solo agente principal
    ...
)
```

**Acción:** Reimplementar `build_sub_agents()` en Fase 3.

---

### Checklist de Validación Fase 2

| # | Item | Estado | Notas |
|---|------|--------|-------|
| 1 | `management/__init__.py` creado | ✅ | Exporta validate_workspace |
| 2 | `management/validator.py` funcional | ✅ | Validación completa |
| 3 | `management/cli.py` genera workspace | ✅ | Falta research_agent.yaml (menor) |
| 4 | `management/admin.py` implementado | ⚠️ | Pendiente validación runtime |
| 5 | `loader.py` — MemoryManager corregido | ✅ | Import y patrón correctos |
| 6 | `loader.py` — params inválidos eliminados | ✅ | enable_user_memories removido |
| 7 | `routes/knowledge_routes.py` — skip_if_exists | ✅ | Aplicado |
| 8 | `routes/knowledge_routes.py` — list/delete | ⚠️ | Siguen stub |
| 9 | `workspace/config.yaml` — limpiado | ✅ | Solo params documentados |
| 10 | `gateway.py` — validación integrada | ✅ | Advierte sin bloquear |
| 11 | `requirements.txt` — rich agregado | ✅ | Dependencia incluida |
| 12 | Estructura de directorios completa | ✅ | management/, routes/, workspace/ |

### Veredicto Fase 2: **APROBADA con observaciones menores**

Las correcciones críticas (MemoryManager, params inválidos) están aplicadas. Los issues pendientes son stubs de endpoints secundarios y validación runtime del admin client, que se resolverán al ejecutar.

---

## CUÁNDO HACER LA PRIMERA PRUEBA

### Prueba inmediata: AHORA (Fase 1+2 completas)

La plataforma está lista para una prueba end-to-end con la siguiente secuencia:

```bash
# 1. Validar workspace
python -m management.validator

# 2. Arrancar DB local (si no usas Supabase)
docker compose up -d db

# 3. Arrancar gateway
python gateway.py

# 4. Verificar estado via admin
python -m management.admin status --url http://localhost:8000

# 5. Probar agente directamente
python -m management.admin run \
    --agent agnobot-main \
    --message "Hola, ¿qué puedes hacer?" \
    --url http://localhost:8000

# 6. Probar con streaming
python -m management.admin run \
    --agent agnobot-main \
    --message "Busca noticias sobre IA" \
    --stream \
    --url http://localhost:8000

# 7. Conectar Studio (visual)
# Abrir os.agno.com → Add OS → Local → http://localhost:8000

# 8. Probar WhatsApp (si tienes webhook configurado)
# Enviar mensaje al número de WhatsApp configurado
```

### Matriz de pruebas por Fase

| Fase | Qué se puede probar | Requisitos |
|------|---------------------|------------|
| **F1+F2 (AHORA)** | Gateway + Agente + Memoria + RAG + WhatsApp + Admin CLI + Validador | DB (Supabase o Docker) + API keys |
| F3 | + Slack + Sub-agentes + Teams + Studio visual | + SLACK_TOKEN + sub-agentes YAML |
| F4 | + Remote Agents + MCP avanzado | + servidor remoto |
| F5 | + Scheduler + Upload masivo de docs | Configuración cron |
| F6 | + JWT/RBAC + Docker multi-servicio | Producción |

### Checklist pre-prueba (Fase 1+2)

| # | Requisito | Comando de verificación |
|---|-----------|----------------------|
| 1 | `.env` configurado con API keys | `python -m management.validator` |
| 2 | DB accesible (Supabase o Docker) | `docker compose up -d db` o verificar Supabase |
| 3 | Dependencias instaladas | `pip install -r requirements.txt` |
| 4 | Workspace completo | `ls workspace/config.yaml workspace/instructions.md` |
| 5 | Puerto 8000 libre | `lsof -i :8000` |

---

## PARTE 2: PLAN DE IMPLEMENTACIÓN — FASE 3

### Objetivo

**Multi-Canal + Studio + Sub-Agentes + Teams: Expandir la plataforma con canal Slack, carga dinámica de sub-agentes desde YAML, Teams multi-agente configurables, y Studio visual completo.**

### Entregables

| # | Entregable | Archivo(s) | Descripción |
|---|------------|-----------|-------------|
| 1 | Carga de sub-agentes | `loader.py` | Reimplementar `build_sub_agents()` |
| 2 | Carga de Teams | `loader.py` | Nueva función `build_teams()` |
| 3 | Integración en gateway | `gateway.py` | Sub-agentes + Teams en AgentOS |
| 4 | Canal Slack | `gateway.py` | Slack Interface operativa |
| 5 | Sub-agente de ejemplo | `workspace/agents/research_agent.yaml` | Generado por CLI |
| 6 | Team de ejemplo | `workspace/agents/teams.yaml` | Estructura funcional |
| 7 | CLI actualizado | `management/cli.py` | Genera research_agent.yaml |
| 8 | Studio/Registry mejorado | `gateway.py` | Registry con todos los agentes |
| 9 | Knowledge routes funcionales | `routes/knowledge_routes.py` | list/delete reales |
| 10 | Validador actualizado | `management/validator.py` | Valida sub-agentes y teams |

---

### 3.1 — loader.py: Reimplementar `build_sub_agents()`

Carga sub-agentes desde archivos YAML en `workspace/agents/`.

```python
# ═══════════════════════════════════════════════════
# Agregar a loader.py — después de build_model()
# ═══════════════════════════════════════════════════

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
            logger.warning(f"YAML inválido en {yaml_file.name}: {e}")
            continue

        agent_def = data.get("agent", {})
        if not agent_def:
            logger.warning(f"Sin definición 'agent' en {yaml_file.name}")
            continue

        # Modelo del sub-agente
        model_cfg = agent_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"})
        try:
            model = build_model(model_cfg)
        except ValueError as e:
            logger.warning(f"Modelo inválido en {yaml_file.name}: {e}")
            continue

        # Tools del sub-agente
        agent_tools: list[Any] = []
        for tool_name in agent_def.get("tools", []):
            factory = BUILTIN_TOOL_MAP.get(tool_name)
            if factory is not None:
                agent_tools.append(factory({}))
            else:
                logger.warning(f"Tool '{tool_name}' no reconocido en {yaml_file.name}")

        config = agent_def.get("config", {})

        # MemoryManager para sub-agente (si tiene memoria habilitada)
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
```

---

### 3.2 — loader.py: Nueva función `build_teams()`

Carga Teams desde `workspace/agents/teams.yaml`.

```python
# ═══════════════════════════════════════════════════
# Agregar a loader.py — después de build_sub_agents()
# ═══════════════════════════════════════════════════

def build_teams(
    all_agents: list[Agent],
    db: Union[PostgresDb, SqliteDb],
) -> list:
    """
    Carga Teams desde workspace/agents/teams.yaml.
    Resuelve miembros por ID contra la lista de agentes disponibles.
    """
    from agno.team import Team

    teams_data = load_yaml("agents/teams.yaml")
    teams_list = teams_data.get("teams", [])
    if not teams_list:
        return []

    # Índice de agentes por ID para resolver miembros
    agent_index: dict[str, Agent] = {a.id: a for a in all_agents}

    teams: list[Team] = []

    for team_def in teams_list:
        team_name = team_def.get("name", "Unnamed Team")

        # Resolver miembros
        member_ids = team_def.get("members", [])
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
                f"Team '{team_name}' necesita al menos 2 miembros, tiene {len(members)}. Omitido."
            )
            continue

        # Modelo del team leader
        model_cfg = team_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"})
        try:
            model = build_model(model_cfg)
        except ValueError as e:
            logger.warning(f"Modelo inválido en team '{team_name}': {e}")
            continue

        # Modo del team
        mode_str = team_def.get("mode", "coordinate")
        # Los modos válidos son: "coordinate", "route", "collaborate"

        team = Team(
            name=team_name,
            id=team_def.get("id", team_name.lower().replace(" ", "-")),
            mode=mode_str,
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
```

---

### 3.3 — loader.py: Actualizar `load_workspace()`

Integrar sub-agentes y teams en la carga del workspace.

```python
# ═══════════════════════════════════════════════════
# Reemplazar load_workspace() en loader.py
# ═══════════════════════════════════════════════════

def load_workspace() -> dict[str, Any]:
    """
    Carga completa del workspace — retorna un dict con todos los objetos
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

    # === FASE 3: Sub-agentes y Teams ===
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
```

---

### 3.4 — gateway.py: Integrar sub-agentes, Teams y Slack

```python
# ═══════════════════════════════════════════════════
# gateway.py — Reescritura completa para Fase 3
# ═══════════════════════════════════════════════════

"""
AgnoBot Gateway — Punto de entrada principal.
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

# === Validar workspace ===
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
teams = ws["teams"]
knowledge = ws["knowledge"]

# === FastAPI base ===
base_app = FastAPI(
    title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
    version="0.3.0",  # Fase 3
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

# === Interfaces (Canales) ===
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

# === Registry para Studio ===
studio_config = config.get("studio", {})
registry = None
if studio_config.get("enabled", True) and not ws["db_url"].startswith("sqlite"):
    # Registrar TODOS los modelos de agentes (principal + sub-agentes)
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

# === Construir lista completa de agentes ===
all_agents = [main_agent] + sub_agents
logger.info(
    f"Agentes cargados: {[a.id for a in all_agents]}"
)
if teams:
    logger.info(f"Teams cargados: {[t.id for t in teams]}")

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

### 3.5 — workspace/agents/research_agent.yaml (ejemplo funcional)

```yaml
# ===================================
# Sub-Agente: Investigador
# ===================================

agent:
  name: "Research Agent"
  id: "research-agent"
  role: "Realiza busquedas web profundas y sintetiza informacion"

  model:
    provider: "google"
    id: "gemini-2.0-flash"

  tools:
    - duckduckgo
    - crawl4ai
    - reasoning

  instructions:
    - "Eres un agente especializado en investigacion profunda."
    - "Busca en la web, scrapea paginas relevantes y sintetiza la informacion."
    - "Siempre cita tus fuentes con URLs completas."
    - "Se conciso pero completo en tus reportes."
    - "Si una busqueda no da resultados, intenta con terminos alternativos."

  config:
    tool_call_limit: 5
    enable_agentic_memory: false
    add_datetime_to_context: true
    markdown: true

execution:
  type: "local"
```

---

### 3.6 — workspace/agents/teams.yaml (ejemplo funcional)

```yaml
# ===================================
# Teams - Equipos Multi-Agente
# ===================================
# Modos: coordinate | route | collaborate
# Referencia: https://docs.agno.com/teams

teams:
  - name: "Research Team"
    id: "research-team"
    mode: "coordinate"
    members:
      - agnobot-main
      - research-agent
    model:
      provider: "google"
      id: "gemini-2.0-flash"
    instructions:
      - "Coordina entre el agente principal y el agente de investigacion."
      - "Usa el agente de investigacion para busquedas web profundas."
      - "El agente principal sintetiza y responde al usuario."
      - "Responde en el idioma del usuario."
    enable_agentic_memory: false
```

---

### 3.7 — management/cli.py: Agregar generación de research_agent.yaml

```python
# ═══════════════════════════════════════════════════
# Agregar en cli.py, DESPUÉS de generar tools.yaml
# y ANTES de generar agents/teams.yaml
# ═══════════════════════════════════════════════════

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
```

---

### 3.8 — management/validator.py: Validar sub-agentes y teams

```python
# ═══════════════════════════════════════════════════
# Agregar al final de validate_workspace(), antes del return
# ═══════════════════════════════════════════════════

    # --- Validar sub-agentes ---
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
                # Validar modelo del sub-agente
                sub_model = agent_def.get("model", {})
                sub_provider = sub_model.get("provider", "")
                if sub_provider in key_map:
                    sub_key = key_map[sub_provider]
                    if not os.getenv(sub_key):
                        errors.append(
                            f"agents/{yaml_file.name}: .env falta {sub_key} "
                            f"(requerido para provider '{sub_provider}')"
                        )
            except yaml.YAMLError as e:
                errors.append(f"agents/{yaml_file.name}: YAML invalido: {e}")

    # --- Validar teams ---
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
```

---

### 3.9 — routes/knowledge_routes.py: Endpoints funcionales

```python
# ═══════════════════════════════════════════════════
# routes/knowledge_routes.py — Reescritura completa
# ═══════════════════════════════════════════════════

"""
Knowledge Routes - Endpoints REST para gestion de la Knowledge Base.
"""
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from pydantic import BaseModel

from agno.knowledge.knowledge import Knowledge
from agno.utils.log import logger


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


def create_knowledge_router(knowledge: Knowledge) -> APIRouter:
    """Crea el router de Knowledge con endpoints REST funcionales."""
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])

    @router.post("/upload")
    async def upload_document(file: UploadFile = File(...)) -> dict:
        """Recibe un archivo y lo inserta en la Knowledge Base."""
        allowed_extensions = {".pdf", ".txt", ".md", ".csv", ".docx"}
        file_ext = Path(file.filename or "").suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo no soportado: {file_ext}. Permitidos: {', '.join(allowed_extensions)}",
            )

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file_ext, prefix="agnobot_kb_",
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
            logger.info(f"Documento cargado: {file.filename}")
            return {
                "status": "ok",
                "message": f"Documento '{file.filename}' cargado exitosamente",
            }
        except Exception as e:
            logger.error(f"Error al cargar documento: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @router.get("/list")
    async def list_documents() -> dict:
        """Lista documentos unicos en la Knowledge Base."""
        try:
            # Intentar listar via contents_db si disponible
            if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
                contents_db = knowledge.contents_db
                # PostgresDb tiene acceso a la tabla de contenidos
                if hasattr(contents_db, "db_url"):
                    from sqlalchemy import text, create_engine
                    engine = create_engine(contents_db.db_url)
                    table = getattr(
                        contents_db, "knowledge_table", "agnobot_knowledge_contents"
                    )
                    with engine.connect() as conn:
                        result = conn.execute(
                            text(
                                f"SELECT DISTINCT name, id FROM {table} "
                                f"WHERE name IS NOT NULL ORDER BY name"
                            )
                        )
                        docs = [
                            {"id": str(row[1]), "name": row[0]}
                            for row in result
                        ]
                    return {"documents": docs, "count": len(docs)}

            return {"documents": [], "count": 0, "message": "Sin contents_db"}
        except Exception as e:
            logger.error(f"Error al listar documentos: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/{doc_name}")
    async def delete_document(doc_name: str) -> dict:
        """Elimina un documento de la Knowledge Base por nombre."""
        try:
            if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
                contents_db = knowledge.contents_db
                if hasattr(contents_db, "db_url"):
                    from sqlalchemy import text, create_engine
                    engine = create_engine(contents_db.db_url)
                    table = getattr(
                        contents_db, "knowledge_table", "agnobot_knowledge_contents"
                    )
                    vector_table = getattr(
                        knowledge.vector_db, "table_name", "agnobot_knowledge_vectors"
                    )
                    with engine.connect() as conn:
                        # Eliminar de tabla de contenidos
                        conn.execute(
                            text(f"DELETE FROM {table} WHERE name = :name"),
                            {"name": doc_name},
                        )
                        # Eliminar vectores asociados
                        conn.execute(
                            text(f"DELETE FROM {vector_table} WHERE name = :name"),
                            {"name": doc_name},
                        )
                        conn.commit()
                    logger.info(f"Documento eliminado: {doc_name}")
                    return {
                        "status": "ok",
                        "message": f"Documento '{doc_name}' eliminado",
                    }

            raise HTTPException(
                status_code=501, detail="Eliminacion no soportada sin contents_db"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al eliminar documento: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/search")
    async def search_knowledge(request: SearchRequest) -> dict:
        """Busqueda semantica en la Knowledge Base."""
        try:
            results = knowledge.search(
                query=request.query, num_documents=request.max_results
            )
            documents = []
            for doc in results:
                documents.append({
                    "content": doc.content if hasattr(doc, "content") else str(doc),
                    "name": doc.name if hasattr(doc, "name") else "unknown",
                })
            return {"results": documents, "count": len(documents)}
        except Exception as e:
            logger.error(f"Error en busqueda: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
```

---

### 3.10 — Configuración Slack

#### Requisitos previos

1. Crear Slack App en https://api.slack.com/apps
2. Habilitar Socket Mode o Event Subscriptions
3. Agregar Bot Token Scopes: `chat:write`, `app_mentions:read`, `im:history`, `im:read`, `im:write`
4. Instalar la app en el workspace

#### Variables en .env

```bash
# === Slack ===
SLACK_TOKEN=xoxb-tu-bot-token
```

#### Activar en workspace/config.yaml

```yaml
channels:
  - whatsapp
  - slack    # Descomentar para habilitar
```

#### Documentación de referencia

Según la documentación oficial de Agno (`docs.agno.com/agent-os/interfaces/slack/introduction`), la interfaz Slack se configura como:

```python
from agno.os.interfaces.slack import Slack

interfaces.append(Slack(agent=main_agent))
```

El webhook de Slack se registra automáticamente en AgentOS. La URL del webhook será `https://tu-dominio.com/slack/events`.

---

### Checklist Fase 3

| # | Tarea | Archivo | Prioridad |
|---|-------|---------|-----------|
| 1 | Implementar `build_sub_agents()` | `loader.py` | Alta |
| 2 | Implementar `build_teams()` | `loader.py` | Alta |
| 3 | Actualizar `load_workspace()` con sub-agentes y teams | `loader.py` | Alta |
| 4 | Actualizar `gateway.py` — teams + all_agents + Slack | `gateway.py` | Alta |
| 5 | Crear `workspace/agents/research_agent.yaml` | workspace | Alta |
| 6 | Actualizar `workspace/agents/teams.yaml` con ejemplo | workspace | Media |
| 7 | Actualizar CLI — generar research_agent.yaml | `management/cli.py` | Media |
| 8 | Actualizar validator — validar sub-agentes y teams | `management/validator.py` | Media |
| 9 | Knowledge routes — list/delete funcionales | `routes/knowledge_routes.py` | Media |
| 10 | Registry mejorado — todos los modelos | `gateway.py` | Baja |
| 11 | Testear: sub-agente carga desde YAML | Runtime | Alta |
| 12 | Testear: team coordina entre agentes | Runtime | Alta |
| 13 | Testear: Slack envía/recibe mensajes | Runtime | Alta |
| 14 | Testear: Studio muestra todos los agentes | os.agno.com | Media |
| 15 | Testear: Knowledge list/delete funcionan | REST API | Media |

---

### Comandos de Prueba Fase 3

```bash
# 1. Validar workspace (incluye sub-agentes y teams)
python -m management.validator

# 2. Arrancar gateway
python gateway.py
# Verificar logs:
#   "Sub-agente cargado: Research Agent (research-agent)"
#   "Team cargado: Research Team (research-team)"
#   "Canal Slack habilitado"

# 3. Estado via admin (debe mostrar todos los agentes)
python -m management.admin status

# 4. Ejecutar sub-agente directamente
python -m management.admin run \
    --agent research-agent \
    --message "Busca las ultimas noticias sobre Agno framework" \
    --stream

# 5. Ejecutar team
python -m management.admin run \
    --agent research-team \
    --message "Investiga que es Agno y dame un resumen completo" \
    --stream

# 6. Probar Knowledge list
curl http://localhost:8000/knowledge/list

# 7. Probar Knowledge upload
curl -X POST http://localhost:8000/knowledge/upload \
    -F "file=@documento.pdf"

# 8. Probar Knowledge search
curl -X POST http://localhost:8000/knowledge/search \
    -H "Content-Type: application/json" \
    -d '{"query": "agno framework", "max_results": 3}'

# 9. Probar Slack
# Enviar mensaje al bot en Slack

# 10. Studio visual
# os.agno.com → Add OS → Local → http://localhost:8000
# Verificar que aparecen: agnobot-main, research-agent, research-team
```

---

### Dependencias Adicionales Fase 3

No se requieren dependencias nuevas. Todo usa:
- `agno[os]` — incluye `Team`, `Slack`, `Registry`
- Las demás dependencias ya están en `requirements.txt`

---

### Estructura del Proyecto — Fin de Fase 3

```
OpenAgno/
├── gateway.py                    # Gateway con sub-agentes, teams, Slack
├── loader.py                     # + build_sub_agents() + build_teams()
├── workspace/
│   ├── config.yaml               # + slack en channels
│   ├── instructions.md
│   ├── tools.yaml
│   ├── mcp.yaml
│   ├── knowledge/
│   │   ├── docs/
│   │   └── urls.yaml
│   ├── agents/
│   │   ├── research_agent.yaml   # Sub-agente funcional
│   │   └── teams.yaml            # Team funcional
│   └── schedules.yaml
├── routes/
│   ├── __init__.py
│   └── knowledge_routes.py       # Endpoints list/delete funcionales
├── management/
│   ├── __init__.py
│   ├── cli.py                    # + genera research_agent.yaml
│   ├── admin.py
│   └── validator.py              # + valida sub-agentes y teams
├── .env
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

### Resumen de Cambios por Archivo

| Archivo | Cambios Fase 3 |
|---------|---------------|
| `loader.py` | + `build_sub_agents()`, + `build_teams()`, actualizar `load_workspace()`, + `from agno.team import Team` |
| `gateway.py` | Usar `all_agents`, pasar `teams`, Registry con todos los modelos, version 0.3.0 |
| `management/cli.py` | + generar `research_agent.yaml` |
| `management/validator.py` | + validar sub-agentes YAML, + validar teams.yaml |
| `routes/knowledge_routes.py` | list/delete funcionales con SQLAlchemy |
| `workspace/agents/research_agent.yaml` | Nuevo archivo |
| `workspace/agents/teams.yaml` | Actualizado con team de ejemplo |
| `workspace/config.yaml` | + `slack` en channels (cuando se active) |
