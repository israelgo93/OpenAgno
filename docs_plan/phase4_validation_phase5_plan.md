# AgnoBot v3 — Validación Fase 4 + Plan de Implementación Fase 5

---

## PARTE 1: VALIDACIÓN COMPLETA DE FASE 4

### Resumen de Validación

| Archivo | Estado | Issues |
|---------|--------|--------|
| `remote_server.py` | ⚠️ 3 issues | MCPTools lifecycle, memoria en server aislado, falta healthcheck endpoint |
| `loader.py` (F4) | ⚠️ 2 issues | `RemoteAgent` import path, `build_sub_agents` no propaga `BUILTIN_TOOL_MAP` a remotos |
| `gateway.py` (F4) | ⚠️ 2 issues | `remote_agents` atributo `agent_id` vs `id`, A2A interface import no verificado |
| `workspace/agents/research_agent.yaml` (F4) | ✅ Correcto | Estructura `execution.type: remote` válida |
| `workspace/mcp.yaml` (F4) | ⚠️ 2 issues | Falta Tavily MCP, MCP stdio lifecycle no resuelto |
| `workspace/config.yaml` (F4) | ✅ Correcto | Sección `a2a` agregada |
| `docker-compose.yml` (F4) | ⚠️ 1 issue | `research` sin healthcheck, gateway depende de `service_started` |
| `management/validator.py` (F4) | ✅ Correcto | Valida remote URLs y MCP configs |
| `Dockerfile` | ✅ Correcto | Node.js para MCP stdio incluido |
| `requirements.txt` (F4) | ⚠️ 1 issue | Falta `tavily-python` |
| `.env.example` (F4) | ⚠️ 1 issue | Falta `TAVILY_API_KEY` |

---

### ISSUE 1 (CRÍTICO): MCPTools lifecycle en `remote_server.py`

**Archivo:** `remote_server.py`

**Problema:** El `remote_server.py` instancia `MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")` directamente en la lista de tools del agente. Según la documentación oficial de Agno, cuando MCPTools se usa dentro de AgentOS, **la conexión se gestiona automáticamente** (startup/shutdown). Sin embargo, el remote_server usa `enable_mcp_server=False`, lo cual es correcto para un servidor secundario.

El problema real es que `MCPTools` con transport `streamable-http` se instancia a nivel de módulo y AgentOS maneja el lifecycle. Pero si el servidor MCP externo (docs.agno.com) no está disponible al arrancar, **el startup fallará silenciosamente** sin retry.

**Código actual:**
```python
tools = [
    DuckDuckGoTools(),
    Crawl4aiTools(max_length=3000),
    ReasoningTools(add_instructions=True),
    MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp"),
]
```

**Recomendación:** Agregar manejo de error en caso de que el MCP no esté disponible:
```python
# Opción: envolver en try/except para que el server arranque aunque MCP falle
mcp_tools_list = []
try:
    mcp_tools_list.append(
        MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")
    )
except Exception as e:
    logger.warning(f"MCP docs.agno.com no disponible: {e}")

tools = [
    DuckDuckGoTools(),
    Crawl4aiTools(max_length=3000),
    ReasoningTools(add_instructions=True),
    *mcp_tools_list,
]
```

**Impacto:** Medio. Si docs.agno.com está caído, el server remoto no arrancará.

---

### ISSUE 2 (MODERADO): `RemoteAgent` import path

**Archivo:** `loader.py` (F4)

**Problema:** El código F4 importa `RemoteAgent` desde `agno.agent`:
```python
from agno.agent import Agent, RemoteAgent
```

**Verificación contra docs oficiales:** Según la documentación de Agno en `agent-os/remote-execution/overview`, el import correcto es:
```python
from agno.agent import Agent, RemoteAgent  # ✅ Correcto según docs recientes
```

Esto se confirma en la documentación oficial. Sin embargo, en versiones anteriores de Agno, `RemoteAgent` estaba en `agno.agent.remote`. Hay que verificar la versión instalada.

**Estado:** Correcto para `agno>=0.5.0`. Verificar que `requirements.txt` especifique la versión mínima.

---

### ISSUE 3 (MODERADO): Atributo `agent_id` vs `id` en RemoteAgent

**Archivo:** `gateway.py` (F4)

**Problema:** Al loguear agentes remotos, el gateway usa:
```python
logger.info(f"Agentes remotos: {[getattr(a, 'agent_id', 'unknown') for a in remote_agents]}")
```

El `RemoteAgent` tiene `agent_id` como parámetro de constructor, pero al ser una subclase o wrapper, puede no exponer `agent_id` como atributo directo. Según la documentación:

```python
remote_agent = RemoteAgent(
    base_url="http://localhost:7778",
    agent_id="research-agent",
)
```

El `agent_id` se usa para construir la URL de comunicación `{base_url}/v1/agents/{agent_id}`, pero no necesariamente es un atributo accesible después.

**Corrección:**
```python
# Usar getattr con fallback, que ya está implementado
# Pero mejor usar un try/except más robusto:
if remote_agents:
    remote_ids = []
    for ra in remote_agents:
        ra_id = getattr(ra, 'agent_id', None) or getattr(ra, 'id', 'unknown')
        remote_ids.append(ra_id)
    logger.info(f"Agentes remotos: {remote_ids}")
```

**Impacto:** Bajo. Solo afecta al logging.

---

### ISSUE 4 (MODERADO): A2A Interface import no verificado

**Archivo:** `gateway.py` (F4)

**Problema:** El código importa `A2A` condicionalmente:
```python
if config.get("a2a", {}).get("enabled", False):
    from agno.os.interfaces.a2a import A2A
    interfaces.append(A2A(agent=main_agent))
```

**Verificación:** La documentación de Agno lista A2A como interface en `agent-os/interfaces`, pero el import path exacto `agno.os.interfaces.a2a` necesita verificación. El paquete `agno[os]` incluye las interfaces, y `agno[a2a]` es un extra separado en PyPI.

**Corrección en `requirements.txt`:**
```
agno[os,a2a]>=0.5.0   # Agregar extra 'a2a' si se habilita
```

**Impacto:** Medio. Si A2A está habilitado en config pero el extra no está instalado, fallará.

---

### ISSUE 5 (MODERADO): MCP stdio lifecycle no resuelto

**Archivo:** `loader.py` — `build_mcp_tools()`

**Problema persistente desde F1:** Los MCP servers con transport `stdio` se retornan como `dict` en vez de `MCPTools`:

```python
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
```

Estos dicts se filtran en `load_workspace()` con `isinstance(mcp_tool, MCPTools)`, por lo que los MCP stdio **nunca se agregan al agente**.

**Solución correcta según docs de Agno:**
Los MCP stdio requieren un context manager async. Según la documentación (`tools/mcp/overview`), se debe usar:

```python
from agno.tools.mcp import MCPTools

# Para stdio:
mcp = MCPTools(
    transport="stdio",
    command="npx -y @supabase/mcp-server-supabase@latest",
    args=["--access-token", os.getenv("SUPABASE_ACCESS_TOKEN", "")],
)
# El lifecycle se maneja por AgentOS automáticamente cuando está en agent.tools
```

**Corrección de `build_mcp_tools()`:**
```python
def build_mcp_tools(mcp_config: dict) -> list[MCPTools]:
    """Construye MCPTools según mcp.yaml."""
    mcp_tools = []

    for server in mcp_config.get("servers", []):
        if not server.get("enabled", False):
            continue

        transport = server.get("transport", "streamable-http")
        name = server.get("name", "mcp-server")

        if transport in ("streamable-http", "sse"):
            url = _resolve_env(server.get("url", ""))
            if url:
                mcp_tools.append(MCPTools(
                    transport=transport,
                    url=url,
                ))
                logger.info(f"MCP '{name}' ({transport}): {url}")

        elif transport == "stdio":
            command_str = _resolve_env(server.get("command", ""))
            if not command_str:
                continue

            # Parsear command string en command + args
            parts = command_str.split()
            command = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []

            env = {**os.environ, **_resolve_config(server.get("env", {}))}

            try:
                mcp_tool = MCPTools(
                    transport="stdio",
                    command=command,
                    args=args,
                    env=env,
                )
                mcp_tools.append(mcp_tool)
                logger.info(f"MCP '{name}' (stdio): {command}")
            except Exception as e:
                logger.warning(f"MCP '{name}' falló: {e}")

    return mcp_tools
```

**Y actualizar `load_workspace()`:**
```python
# Ya no necesita filtrar — todos son MCPTools
mcp_tools = build_mcp_tools(mcp_config)
tools.extend(mcp_tools)  # Agregar directamente
```

**Impacto:** Alto. Sin esta corrección, MCP Supabase y GitHub (ambos stdio) **no funcionan**.

---

### ISSUE 6 (MENOR): Docker `research` sin healthcheck

**Archivo:** `docker-compose.yml`

**Problema:** El servicio `research` no tiene healthcheck, y el `gateway` depende de él con `condition: service_started` (no `service_healthy`). Si el research server tarda en arrancar, el gateway podría intentar conectarse antes de que esté listo.

**Corrección:**
```yaml
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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7778/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

gateway:
    # ...
    depends_on:
      db:
        condition: service_healthy
      research:
        condition: service_healthy  # ← Cambiar a service_healthy
```

---

### ISSUE 7 (MENOR): Falta Tavily MCP en `mcp.yaml`

**Archivo:** `workspace/mcp.yaml`

**Problema:** El usuario solicita agregar Tavily como MCP para búsqueda. Tavily ofrece un MCP server remoto oficial en `https://mcp.tavily.com/mcp/`.

**Corrección — agregar a `mcp.yaml`:**
```yaml
servers:
  # ... (servidores existentes)

  # ★ Tavily MCP - Búsqueda web avanzada
  - name: tavily
    enabled: false
    transport: "streamable-http"
    url: "https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}"
    description: "Búsqueda web avanzada con Tavily (search, extract, crawl)"
```

**Nota importante:** Tavily MCP usa transport `streamable-http` con la API key en la URL como query parameter. Esto es más sencillo que la versión stdio con `npx`.

---

### Patrones Validados Correctamente en F4

| Patrón | Archivo | Verificación |
|--------|---------|-------------|
| `RemoteAgent(base_url, agent_id)` | loader.py | ✅ Docs: `remote-execution/overview` |
| `AgentOS(agents=[...remotos...])` | gateway.py | ✅ Docs: `remote-execution/overview` |
| `AgentOS(enable_mcp_server=False)` en server secundario | remote_server.py | ✅ Correcto — solo gateway expone MCP |
| `execution.type: remote` en YAML | research_agent.yaml | ✅ Patrón válido para loader |
| `MemoryManager(model, db)` en research agent | remote_server.py | ✅ Coherente con corrección F2 |
| `agent_os.serve(app="remote_server:app")` | remote_server.py | ✅ Docs: string path para uvicorn |
| `docker-compose` con service dependency | docker-compose.yml | ✅ Patrón Docker válido |
| MCP Supabase via `stdio` | mcp.yaml | ✅ Docs: `tools/mcp/usage/supabase` |
| MCP GitHub via `stdio` | mcp.yaml | ✅ Docs: MCP cookbook |
| Validator con remote URL check | validator.py | ✅ Robusto |

---

### Código Corregido: Todos los Cambios Necesarios para F4

```python
# ═══ CAMBIO 1: loader.py — build_mcp_tools() completo ═══
# Reemplazar función completa (ver ISSUE 5 arriba)

# ═══ CAMBIO 2: loader.py — load_workspace() ═══
# Simplificar integración de MCP tools:
mcp_tools = build_mcp_tools(mcp_config)
tools.extend(mcp_tools)  # Ya no necesita filtrar isinstance

# ═══ CAMBIO 3: gateway.py — logging robusto de remotos ═══
if remote_agents:
    remote_ids = []
    for ra in remote_agents:
        ra_id = getattr(ra, 'agent_id', None) or getattr(ra, 'id', 'unknown')
        remote_ids.append(ra_id)
    logger.info(f"Agentes remotos: {remote_ids}")

# ═══ CAMBIO 4: docker-compose.yml — healthcheck en research ═══
# Ver ISSUE 6

# ═══ CAMBIO 5: workspace/mcp.yaml — Agregar Tavily MCP ═══
# Ver ISSUE 7

# ═══ CAMBIO 6: requirements.txt — agregar dependencias ═══
# tavily-python>=0.5    (si se usa TavilyTools como tool)
# agno[os,a2a]>=0.5.0   (si se habilita A2A)

# ═══ CAMBIO 7: .env.example — agregar TAVILY_API_KEY ═══
# TAVILY_API_KEY=tvly-...
```

---

## PARTE 2: REVISIÓN DE LA BASE DE CONOCIMIENTO Y CÓDIGO

### Estado General del Proyecto

| Fase | Estado | Archivos Principales | Observaciones |
|------|--------|---------------------|---------------|
| F1: MVP | ✅ Implementada + Validada | loader.py, gateway.py, workspace/*, routes/*, docker-compose.yml | MemoryManager corregido en F2 |
| F2: CLI + Admin | ✅ Implementada + Validada | management/cli.py, admin.py, validator.py | AgentOSClient funcional |
| F3: Multi-Canal + Teams | ✅ Implementada — 5 issues menores corregidos | loader.py (build_teams), gateway.py (Slack), teams.yaml | Registry con tools, SLACK_SIGNING_SECRET |
| F4: Remote + MCP | ⚠️ Implementada — 7 issues identificados | remote_server.py, loader.py (remote), gateway.py (A2A), mcp.yaml | **Issue crítico: MCP stdio no funciona** |

### Coherencia del Código Acumulado

**Aspectos positivos:**
- Arquitectura workspace declarativa coherente en las 4 fases
- Patrón `MemoryManager` correctamente aplicado desde F2
- `build_teams()` con resolución de miembros por ID es robusto
- Separación clara entre gateway (público) y remote_server (interno)
- Validator se actualiza incrementalmente por fase
- Docker multi-servicio con pgvector es correcto

**Deuda técnica acumulada (F1-F4):**

| # | Deuda | Severidad | Fase Origen |
|---|-------|-----------|-------------|
| 1 | MCP stdio nunca se integra al agente (retorna dict) | **Alta** | F1 |
| 2 | No hay tests automatizados en ninguna fase | Alta | F1 |
| 3 | `build_mcp_tools()` para stdio retorna dict en vez de MCPTools | Alta | F1 |
| 4 | Knowledge routes (`/knowledge/list`, `/knowledge/{doc_id}`) son stubs | Media | F1 |
| 5 | A2A interface require extra `agno[a2a]` no documentado en requirements | Media | F4 |
| 6 | Remote server no tiene endpoint `/health` explícito (depende de AgentOS) | Baja | F4 |
| 7 | `_resolve_env()` solo resuelve patrones exactos `${VAR}` (no embebidos) | Baja | F1 |

---

## PARTE 3: VERIFICACIÓN DE SHELL TOOLS Y TAVILY

### Shell Tools — ¿Está implementado?

**SÍ, ShellTools está implementado** en el código desde la Fase 1. Se encuentra en dos lugares:

**1. `workspace/tools.yaml` — Declaración:**
```yaml
optional:
  - name: shell
    enabled: false
    # ⚠️ RIESGO DE SEGURIDAD — solo activar si es necesario
```

**2. `loader.py` — `build_tools()` — Carga dinámica:**
```python
elif name == "shell":
    from agno.tools.shell import ShellTools
    logger.warning("⚠️ ShellTools activado — riesgo de seguridad")
    tools.append(ShellTools())
```

**3. Verificación contra docs oficiales de Agno:**
- Import: `from agno.tools.shell import ShellTools` ✅
- Docs: `https://docs.agno.com/tools/toolkits/local/shell` ✅
- Descripción: Permite al agente ejecutar comandos shell en el sistema
- Categoría: Local system operations (junto con FileTools, PythonTools, DockerTools)

**Estado:** Implementado pero **deshabilitado por defecto** (correcto por seguridad). Para activarlo, cambiar `enabled: false` a `enabled: true` en `workspace/tools.yaml`.

**Advertencia de seguridad:** ShellTools ejecuta comandos sin confirmación. La comunidad de Agno ha solicitado un "modo seguro" con confirmación antes de ejecutar comandos destructivos (issue #2452 en GitHub). Se recomienda no habilitar en producción a menos que sea estrictamente necesario.

### Tavily — Estado Actual

Tavily está parcialmente implementado en **dos modalidades**:

**Modalidad 1: Como Tool nativo de Agno (ya implementado):**
```yaml
# workspace/tools.yaml
optional:
  - name: tavily
    enabled: false
```

```python
# loader.py — build_tools()
elif name == "tavily":
    from agno.tools.tavily import TavilyTools
    tools.append(TavilyTools())
```
- Requiere: `TAVILY_API_KEY` en `.env`
- Dependencia: `tavily-python` (falta en `requirements.txt`)

**Modalidad 2: Como MCP Server (NO implementado — se agrega ahora):**
Tavily ofrece un MCP server remoto oficial que se puede integrar sin dependencias adicionales de Python.

```yaml
# workspace/mcp.yaml — AGREGAR:
  - name: tavily
    enabled: false
    transport: "streamable-http"
    url: "https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}"
    description: "Búsqueda web avanzada con Tavily via MCP (search, extract, map, crawl)"
```

**Ventaja de MCP vs Tool nativo:**
| Aspecto | TavilyTools (nativo) | Tavily MCP |
|---------|---------------------|------------|
| Dependencia Python | Sí (`tavily-python`) | No |
| Funciones disponibles | `search`, `extract` | `search`, `extract`, `map`, `crawl` |
| Actualización | Requiere actualizar pip | Automática (servidor remoto) |
| Configuración | `.env` + `tools.yaml` | `.env` + `mcp.yaml` |

**Recomendación:** Habilitar ambas opciones. El usuario puede elegir una u otra según su caso de uso.

---

## PARTE 4: ¿CUÁNDO SE PUEDE HACER LA PRIMERA PRUEBA?

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

# 5. Probar via API directa (sin WhatsApp):
curl -X POST http://localhost:8000/v1/agents/agnobot-main/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿quién eres?", "user_id": "test-user"}'
```

### Prueba Completa por Fase

| Fase | Qué se puede probar | Requisitos Mínimos |
|------|---------------------|-------------------|
| **F1** | Agente responde via API REST, WhatsApp funciona, Knowledge upload/search, MCP docs.agno.com | PostgreSQL + 1 API key + ngrok (para WA) |
| **F2** | CLI genera workspace, validator detecta errores, admin CLI funciona | F1 arrancado |
| **F3** | Slack responde, Teams coordinan agentes, Studio visible en os.agno.com | Slack App creada |
| **F4** | Remote Agents distribuidos, MCP Supabase/GitHub, A2A | Docker multi-servicio |
| **F5** | Scheduler ejecuta tareas, RAG con docs + URLs, Tavily MCP | F4 completa |

### Prueba Recomendada Ahora (Post-F4, pre-F5)

```bash
# 1. PostgreSQL + Research Server + Gateway
docker-compose up -d

# 2. Verificar health de ambos servidores
curl http://localhost:8000/health     # Gateway
curl http://localhost:7778/health     # Research Server

# 3. Probar agente principal via API
curl -X POST http://localhost:8000/v1/agents/agnobot-main/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿quién eres?", "user_id": "test"}'

# 4. Probar agente remoto via gateway
curl -X POST http://localhost:8000/v1/agents/research-agent/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Investiga las últimas noticias sobre IA", "user_id": "test"}'

# 5. Studio: os.agno.com > Add OS > Local > http://localhost:8000

# 6. Admin CLI
python -m management.admin status
python -m management.admin run --agent agnobot-main --message "Hola" --stream
```

---

## PARTE 5: PLAN DE IMPLEMENTACIÓN — FASE 5

### Objetivo

**Scheduler + RAG Avanzado + Tavily MCP:** Tareas programadas con cron, ingesta de documentos desde archivos y URLs, búsqueda web avanzada via Tavily MCP, y endpoints robustos de Knowledge.

### Entregables

| # | Entregable | Archivo | Descripción |
|---|------------|---------|-------------|
| 1 | Scheduler funcional | `loader.py` + `gateway.py` (actualizado) | Lee `workspace/schedules.yaml` y registra tareas cron |
| 2 | Knowledge Ingest: Documentos | `routes/knowledge_routes.py` (actualizado) | Upload de PDFs, MD, TXT con ingesta real en PgVector |
| 3 | Knowledge Ingest: URLs | `routes/knowledge_routes.py` + `loader.py` | Ingesta desde `workspace/knowledge/urls.yaml` al arrancar |
| 4 | Knowledge List/Delete funcional | `routes/knowledge_routes.py` (actualizado) | Endpoints que consultan y eliminan de PgVector/PostgresDb |
| 5 | Tavily MCP habilitado | `workspace/mcp.yaml` (actualizado) | Búsqueda web avanzada via MCP remoto |
| 6 | Tavily Tool + MCP en tools.yaml | `workspace/tools.yaml` + `loader.py` | Opción dual: tool nativo o MCP |
| 7 | Auto-ingesta de knowledge/docs/ | `gateway.py` (actualizado) | Ingesta automática de archivos al arrancar |
| 8 | Validator actualizado | `management/validator.py` (actualizado) | Valida schedules, URLs, Tavily config |
| 9 | CLI actualizado | `management/cli.py` (actualizado) | Pregunta por Scheduler y Knowledge URLs |
| 10 | requirements.txt actualizado | `requirements.txt` | Agregar `tavily-python`, `agno[scheduler]` |

---

### Arquitectura Fase 5

```
┌─────────────────────────────────────────────────────────────┐
│                    GATEWAY (:8000)                           │
│  AgentOS Principal                                          │
│  ├── AgnoBot (local) + Research (remoto)                    │
│  ├── Scheduler (cron jobs desde schedules.yaml)             │
│  │   ├── Resumen diario → agnobot-main                     │
│  │   ├── Ingesta URLs → knowledge                          │
│  │   └── Custom tasks                                       │
│  ├── Knowledge Routes (upload/list/delete/ingest)           │
│  │   ├── POST /knowledge/upload (PDF, MD, TXT)              │
│  │   ├── POST /knowledge/ingest-urls                        │
│  │   ├── GET  /knowledge/list                               │
│  │   └── DELETE /knowledge/{doc_id}                         │
│  ├── MCP: docs.agno.com + Tavily                            │
│  └── Interfaces: WhatsApp, Slack, Web                       │
├─────────────────────────────────────────────────────────────┤
│  Auto-Ingesta al arrancar:                                  │
│  ├── workspace/knowledge/docs/*.pdf,*.md,*.txt              │
│  └── workspace/knowledge/urls.yaml                          │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.1 — `loader.py` — Funciones de Scheduler e Ingesta

```python
# ═══ NUEVOS IMPORTS ═══
from agno.os.scheduler import Scheduler, Schedule

# ═══ NUEVA FUNCIÓN: build_schedules() ═══
def build_schedules() -> list[Schedule]:
    """Carga schedules desde workspace/schedules.yaml."""
    schedules_config = load_yaml("schedules.yaml")
    schedules = []

    for sched in schedules_config.get("schedules", []):
        if not sched.get("enabled", True):
            continue

        name = sched.get("name", "Sin nombre")
        agent_id = sched.get("agent_id", "agnobot-main")
        cron = sched.get("cron", "")
        timezone = sched.get("timezone", "America/Guayaquil")
        message = sched.get("message", "")
        user_id = sched.get("user_id", "scheduler")

        if not cron or not message:
            logger.warning(f"Schedule '{name}' incompleto (falta cron o message). Omitido.")
            continue

        schedule = Schedule(
            name=name,
            agent_id=agent_id,
            cron=cron,
            timezone=timezone,
            message=message,
            user_id=user_id,
        )
        schedules.append(schedule)
        logger.info(f"Schedule registrado: '{name}' → {agent_id} ({cron})")

    return schedules


# ═══ NUEVA FUNCIÓN: load_knowledge_urls() ═══
def load_knowledge_urls() -> list[dict]:
    """Carga URLs para ingesta desde workspace/knowledge/urls.yaml."""
    urls_config = load_yaml("knowledge/urls.yaml")
    return urls_config.get("urls", [])


# ═══ NUEVA FUNCIÓN: get_knowledge_docs_paths() ═══
def get_knowledge_docs_paths() -> list[Path]:
    """Retorna lista de archivos en workspace/knowledge/docs/."""
    docs_dir = WORKSPACE_DIR / "knowledge" / "docs"
    if not docs_dir.exists():
        return []

    supported_extensions = {".pdf", ".md", ".txt", ".docx", ".csv", ".json"}
    paths = []
    for f in sorted(docs_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in supported_extensions:
            paths.append(f)

    return paths


# ═══ ACTUALIZAR build_tools() — Agregar Tavily ═══
# Ya existe pero falta en BUILTIN_TOOL_MAP para sub-agentes:
BUILTIN_TOOL_MAP: dict[str, Callable] = {
    "duckduckgo": lambda cfg: DuckDuckGoTools(**cfg),
    "crawl4ai": lambda cfg: Crawl4aiTools(**cfg),
    "reasoning": lambda cfg: ReasoningTools(**cfg),
    "tavily": lambda cfg: __import__('agno.tools.tavily', fromlist=['TavilyTools']).TavilyTools(**cfg),
    "shell": lambda cfg: __import__('agno.tools.shell', fromlist=['ShellTools']).ShellTools(**cfg),
}


# ═══ ACTUALIZAR load_workspace() ═══
def load_workspace() -> dict[str, Any]:
    """Carga completa del workspace (F5)."""
    # ... (código existente de F4) ...

    # ★ F5: Schedules
    schedules = build_schedules()

    # ★ F5: Knowledge paths y URLs
    knowledge_doc_paths = get_knowledge_docs_paths()
    knowledge_urls = load_knowledge_urls()

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
        "schedules": schedules,               # ★ F5
        "knowledge_doc_paths": knowledge_doc_paths,  # ★ F5
        "knowledge_urls": knowledge_urls,      # ★ F5
    }
```

---

### 5.2 — `gateway.py` — Scheduler + Auto-Ingesta

```python
"""
AgnoBot Gateway — Punto de entrada principal (Fase 5).
Incluye Scheduler, auto-ingesta de knowledge, y Tavily MCP.
"""
import os
import asyncio

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
remote_agents = ws["remote_agents"]
teams = ws["teams"]
knowledge = ws["knowledge"]
schedules = ws["schedules"]                    # ★ F5
knowledge_doc_paths = ws["knowledge_doc_paths"]  # ★ F5
knowledge_urls = ws["knowledge_urls"]            # ★ F5

# === FastAPI base ===
base_app = FastAPI(
    title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
    version="0.5.0",
)
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Knowledge Routes (F5: actualizados con funcionalidad real) ===
if knowledge:
    from routes.knowledge_routes import create_knowledge_router
    knowledge_router = create_knowledge_router(knowledge, db)
    base_app.include_router(knowledge_router)

# ★ F5: Auto-ingesta de documentos al arrancar
async def auto_ingest_knowledge():
    """Ingesta automática de documentos y URLs al arrancar."""
    if not knowledge:
        return

    # Ingestar archivos locales
    if knowledge_doc_paths:
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

    # Ingestar URLs
    if knowledge_urls:
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

# Registrar evento de startup para auto-ingesta
@base_app.on_event("startup")
async def startup_ingest():
    await auto_ingest_knowledge()

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

if config.get("a2a", {}).get("enabled", False):
    try:
        from agno.os.interfaces.a2a import A2A
        interfaces.append(A2A(agent=main_agent))
        logger.info("Protocolo A2A habilitado")
    except ImportError:
        logger.warning("A2A no disponible. Instalar: pip install agno[a2a]")

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
    remote_ids = [getattr(a, 'agent_id', None) or getattr(a, 'id', 'unknown') for a in remote_agents]
    logger.info(f"Agentes remotos: {remote_ids}")
if teams:
    logger.info(f"Teams: {[t.id for t in teams]}")
if schedules:
    logger.info(f"Schedules: {[s.name for s in schedules]}")

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
    schedules=schedules if schedules else None,    # ★ F5: Scheduler
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

### 5.3 — `routes/knowledge_routes.py` — Endpoints Funcionales

```python
"""
Knowledge Routes — Endpoints REST para gestión de Knowledge (F5).
Incluye upload, ingesta de URLs, listado y eliminación funcionales.
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from agno.knowledge.knowledge import Knowledge
from agno.db.postgres import PostgresDb
from agno.utils.log import logger


def create_knowledge_router(
    knowledge: Knowledge,
    db: PostgresDb,
) -> APIRouter:
    """Crea router con endpoints de Knowledge."""
    router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

    # ── POST /knowledge/upload ──
    @router.post("/upload")
    async def upload_document(
        file: UploadFile = File(...),
        user_id: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
    ):
        """Sube un documento y lo ingesta en la Knowledge base."""
        supported = {".pdf", ".md", ".txt", ".docx", ".csv", ".json"}
        ext = Path(file.filename).suffix.lower()
        if ext not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no soportado: {ext}. Soportados: {supported}",
            )

        # Guardar archivo temporal
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir) / file.filename
        try:
            with open(tmp_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Ingestar en Knowledge con metadatos
            metadata = {}
            if user_id:
                metadata["user_id"] = user_id
            if category:
                metadata["category"] = category

            knowledge.insert(
                path=str(tmp_path),
                name=file.filename,
                skip_if_exists=True,
            )

            logger.info(f"Documento ingestado: {file.filename}")
            return {
                "status": "ok",
                "filename": file.filename,
                "message": f"Documento '{file.filename}' ingestado correctamente.",
            }
        except Exception as e:
            logger.error(f"Error ingestando {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── POST /knowledge/ingest-urls ──
    @router.post("/ingest-urls")
    async def ingest_urls(
        urls: list[dict],  # [{"url": "...", "name": "..."}]
    ):
        """Ingesta una lista de URLs en la Knowledge base."""
        results = []
        for entry in urls:
            url = entry.get("url", "")
            name = entry.get("name", url)
            if not url:
                results.append({"url": url, "status": "error", "detail": "URL vacía"})
                continue
            try:
                knowledge.insert(
                    url=url,
                    name=name,
                    skip_if_exists=True,
                )
                results.append({"url": url, "status": "ok", "name": name})
                logger.info(f"URL ingestada: {name}")
            except Exception as e:
                results.append({"url": url, "status": "error", "detail": str(e)})
                logger.warning(f"Error ingestando URL {name}: {e}")

        return {"results": results}

    # ── GET /knowledge/list ──
    @router.get("/list")
    async def list_documents(
        user_id: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
    ):
        """Lista los documentos en la Knowledge base."""
        try:
            # Consultar la tabla de contents directamente
            from sqlalchemy import create_engine, text
            engine = create_engine(db.db_url)
            table_name = db.knowledge_table or "agnobot_knowledge_contents"

            query = f"SELECT id, name, meta_data, created_at FROM {table_name}"
            params = {}
            if user_id:
                query += " WHERE meta_data->>'user_id' = :user_id"
                params["user_id"] = user_id
            query += f" ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit

            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                documents = []
                for row in result:
                    documents.append({
                        "id": str(row[0]),
                        "name": row[1],
                        "metadata": row[2],
                        "created_at": str(row[3]) if row[3] else None,
                    })

            return {"documents": documents, "total": len(documents)}

        except Exception as e:
            logger.warning(f"Error listando documentos: {e}")
            # Fallback: tabla no existe aún
            return {"documents": [], "total": 0, "message": "Knowledge table no inicializada"}

    # ── DELETE /knowledge/{doc_id} ──
    @router.delete("/{doc_id}")
    async def delete_document(doc_id: str):
        """Elimina un documento de la Knowledge base."""
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db.db_url)

            contents_table = db.knowledge_table or "agnobot_knowledge_contents"
            vectors_table = knowledge.vector_db.table_name if knowledge.vector_db else None

            with engine.begin() as conn:
                # Eliminar de contents
                result = conn.execute(
                    text(f"DELETE FROM {contents_table} WHERE id = :id"),
                    {"id": doc_id},
                )
                rows_deleted = result.rowcount

                # Eliminar vectores asociados (si existe la tabla)
                if vectors_table:
                    try:
                        conn.execute(
                            text(f"DELETE FROM {vectors_table} WHERE meta_data->>'content_id' = :id"),
                            {"id": doc_id},
                        )
                    except Exception:
                        pass  # Tabla de vectores podría no tener este campo

            if rows_deleted == 0:
                raise HTTPException(status_code=404, detail=f"Documento {doc_id} no encontrado")

            logger.info(f"Documento eliminado: {doc_id}")
            return {"status": "ok", "message": f"Documento {doc_id} eliminado"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error eliminando {doc_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ── POST /knowledge/search ──
    @router.post("/search")
    async def search_knowledge(
        query: str,
        limit: int = Query(5, ge=1, le=20),
        user_id: Optional[str] = Query(None),
    ):
        """Busca en la Knowledge base via búsqueda híbrida."""
        try:
            results = knowledge.search(query=query, num_results=limit)
            documents = []
            for doc in results:
                documents.append({
                    "content": doc.content[:500] if doc.content else "",
                    "name": doc.name,
                    "metadata": doc.meta_data,
                    "score": getattr(doc, 'score', None),
                })

            return {"query": query, "results": documents, "total": len(documents)}

        except Exception as e:
            logger.warning(f"Error buscando: {e}")
            return {"query": query, "results": [], "total": 0}

    return router
```

---

### 5.4 — `workspace/schedules.yaml` — Ejemplo Funcional

```yaml
# ===================================
# Scheduler - Tareas Programadas (F5)
# ===================================
# Referencia: https://docs.agno.com/agent-os/scheduler/overview
# Formato cron: minuto hora día_mes mes día_semana

schedules:
  # Resumen diario de noticias
  - name: "Resumen matutino"
    enabled: true
    agent_id: "agnobot-main"
    cron: "0 9 * * 1-5"             # Lunes a viernes a las 9:00 AM
    timezone: "America/Guayaquil"
    message: "Genera un resumen de las 5 noticias más importantes de tecnología e IA de hoy. Usa búsqueda web."
    user_id: "scheduler-admin"

  # Re-ingesta semanal de URLs
  - name: "Re-ingesta knowledge URLs"
    enabled: false
    agent_id: "agnobot-main"
    cron: "0 2 * * 0"               # Domingos a las 2:00 AM
    timezone: "America/Guayaquil"
    message: "Actualiza la base de conocimiento re-ingestando todas las URLs configuradas."
    user_id: "scheduler-admin"

  # Limpieza mensual de sesiones antiguas
  - name: "Limpieza sesiones"
    enabled: false
    agent_id: "agnobot-main"
    cron: "0 3 1 * *"               # Día 1 de cada mes a las 3:00 AM
    timezone: "America/Guayaquil"
    message: "Genera un reporte del uso del sistema en el último mes: sesiones activas, memorias creadas, documentos ingestados."
    user_id: "scheduler-admin"
```

---

### 5.5 — `workspace/knowledge/urls.yaml` — Ejemplo con URLs

```yaml
# ===================================
# Knowledge - URLs para Ingestión (F5)
# ===================================

urls:
  # Ejemplo: documentación interna
  # - url: "https://example.com/docs/guia.pdf"
  #   name: "Guía de Usuario v2"
  #   metadata:
  #     category: "documentacion"
  #     source: "interno"

  # Ejemplo: FAQ público
  # - url: "https://example.com/faq"
  #   name: "FAQ del Producto"
  #   metadata:
  #     category: "soporte"
  #     source: "web"
```

---

### 5.6 — `workspace/mcp.yaml` — Actualizado con Tavily

```yaml
# ===================================
# MCP - Servidores Model Context Protocol (F5)
# ===================================

servers:
  # Documentación de Agno (siempre habilitado)
  - name: agno_docs
    enabled: true
    transport: "streamable-http"
    url: "https://docs.agno.com/mcp"

  # ★ F5: Tavily MCP - Búsqueda web avanzada
  - name: tavily
    enabled: false
    transport: "streamable-http"
    url: "https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}"
    description: "Búsqueda web avanzada con Tavily (search, extract, map, crawl)"

  # Supabase MCP (F4)
  - name: supabase
    enabled: false
    transport: "stdio"
    command: "npx -y @supabase/mcp-server-supabase@latest --access-token=${SUPABASE_ACCESS_TOKEN}"
    description: "Gestión de proyectos, schemas y edge functions en Supabase"

  # GitHub MCP (F4)
  - name: github
    enabled: false
    transport: "stdio"
    command: "npx -y @modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    description: "Interacción con repos GitHub (issues, PRs, código)"

  # Filesystem MCP (F4)
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

### 5.7 — `workspace/tools.yaml` — Actualizado con Tavily habilitado

```yaml
# ===================================
# Tools - Herramientas del Agente (F5)
# ===================================

builtin:
  - name: duckduckgo
    enabled: true
    config: {}

  - name: crawl4ai
    enabled: true
    config:
      max_length: 2000

  - name: reasoning
    enabled: true
    config:
      add_instructions: true

optional:
  - name: email
    enabled: false
    config:
      sender_email: "${GMAIL_SENDER}"
      sender_name: "AgnoBot"
      sender_passkey: "${GMAIL_PASSKEY}"
      receiver_email: "${GMAIL_RECEIVER}"

  - name: tavily
    enabled: false
    # Requiere TAVILY_API_KEY en .env
    # Alternativa: usar Tavily como MCP en mcp.yaml (no requiere pip)
    config: {}

  - name: spotify
    enabled: false

  - name: shell
    enabled: false
    # ⚠️ RIESGO DE SEGURIDAD — solo activar si es necesario
    # Ejecuta comandos shell sin confirmación

custom: []
```

---

### 5.8 — `management/validator.py` — Validaciones F5

```python
# ═══ AGREGAR validaciones F5 después de las existentes ═══

    # --- Validar Schedules ---
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

        # Validar formato cron básico
        cron = sched.get("cron", "")
        if cron and len(cron.split()) != 5:
            errors.append(
                f"schedules.yaml: schedule '{name}' tiene cron inválido "
                f"(esperados 5 campos, recibidos {len(cron.split())})"
            )

    # --- Validar Knowledge URLs ---
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
            errors.append(f"knowledge/urls.yaml: URL inválida: {url}")

    # --- Validar Tavily ---
    # Verificar si Tavily está habilitado (como tool o MCP)
    tavily_tool_enabled = False
    for tool in tools_config.get("optional", []):
        if tool.get("name") == "tavily" and tool.get("enabled", False):
            tavily_tool_enabled = True

    tavily_mcp_enabled = False
    for server in mcp_config.get("servers", []):
        if server.get("name") == "tavily" and server.get("enabled", False):
            tavily_mcp_enabled = True

    if (tavily_tool_enabled or tavily_mcp_enabled) and not os.getenv("TAVILY_API_KEY"):
        errors.append(".env: falta TAVILY_API_KEY (Tavily habilitado)")

    # --- Validar Knowledge docs directory ---
    docs_dir = ws / "knowledge" / "docs"
    if docs_dir.exists():
        doc_count = len([f for f in docs_dir.iterdir() if f.is_file()])
        if doc_count > 0:
            logger.info(f"Knowledge: {doc_count} documento(s) en knowledge/docs/")
```

---

### 5.9 — `workspace/config.yaml` — Actualización F5

```yaml
# ===================================
# AgnoBot - Configuración Central (F5)
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

a2a:
  enabled: false

remote_servers:
  research: "http://localhost:7778"

# ★ F5: Scheduler
scheduler:
  enabled: true
  timezone: "America/Guayaquil"

# ★ F5: Knowledge auto-ingesta
knowledge:
  auto_ingest_docs: true     # Ingestar docs/ al arrancar
  auto_ingest_urls: true     # Ingestar urls.yaml al arrancar
  skip_if_exists: true       # No re-ingestar documentos existentes
```

---

### 5.10 — `.env.example` — Variables F5

```bash
# ===================================
# AgnoBot - Variables de Entorno (F5)
# ===================================

# === API Keys ===
GOOGLE_API_KEY=...
OPENAI_API_KEY=...            # Embeddings (text-embedding-3-small)
# ANTHROPIC_API_KEY=...       # Si usa Claude como modelo

# ★ F5: Tavily
TAVILY_API_KEY=tvly-...       # Para búsqueda web avanzada (tool o MCP)

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

# === Seguridad ===
# OS_SECURITY_KEY=genera_con_openssl_rand_hex_32

# === Entorno ===
APP_ENV=development
```

---

### 5.11 — `requirements.txt` — F5

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
tavily-python>=0.5          # ★ F5: Tavily (si se usa como tool nativo)

# === Extras opcionales ===
# agno[a2a]                 # Si se habilita A2A (F4)
# agno[scheduler]           # Si se requiere scheduler avanzado
```

---

### Checklist Fase 5

| # | Tarea | Prioridad | Estado |
|---|-------|-----------|--------|
| 1 | `loader.py` — `build_schedules()` | Alta | ⬜ |
| 2 | `loader.py` — `get_knowledge_docs_paths()` + `load_knowledge_urls()` | Alta | ⬜ |
| 3 | `gateway.py` — integrar `schedules` en `AgentOS` | Alta | ⬜ |
| 4 | `gateway.py` — auto-ingesta on startup | Alta | ⬜ |
| 5 | `routes/knowledge_routes.py` — endpoints funcionales (upload, list, delete, search) | Alta | ⬜ |
| 6 | `workspace/mcp.yaml` — agregar Tavily MCP | Alta | ⬜ |
| 7 | `workspace/schedules.yaml` — schedules de ejemplo | Media | ⬜ |
| 8 | `workspace/tools.yaml` — documentar opciones Tavily | Media | ⬜ |
| 9 | `management/validator.py` — validar schedules + URLs + Tavily | Media | ⬜ |
| 10 | `workspace/config.yaml` — sección `scheduler` + `knowledge` | Media | ⬜ |
| 11 | `.env.example` — TAVILY_API_KEY | Baja | ⬜ |
| 12 | `requirements.txt` — tavily-python | Baja | ⬜ |
| 13 | **DEUDA F1**: Corregir `build_mcp_tools()` para stdio | **Alta** | ⬜ |
| 14 | Testear: Schedule ejecuta tarea cron | Alta | ⬜ |
| 15 | Testear: Upload PDF via `/knowledge/upload` | Alta | ⬜ |
| 16 | Testear: Búsqueda Tavily MCP funciona | Media | ⬜ |
| 17 | Testear: Auto-ingesta de docs/ al arrancar | Media | ⬜ |
| 18 | Testear: `/knowledge/search` retorna resultados | Media | ⬜ |

---

### Comandos de Prueba Fase 5

```bash
# 1. Levantar todo
docker-compose up -d

# 2. Colocar un PDF de prueba en workspace/knowledge/docs/
cp mi_documento.pdf workspace/knowledge/docs/

# 3. Arrancar gateway (auto-ingesta al startup)
python gateway.py
# Logs esperados:
#   Auto-ingesta: 1 archivo(s) en knowledge/docs/
#   Ingestado: mi_documento.pdf
#   Schedule registrado: 'Resumen matutino' → agnobot-main (0 9 * * 1-5)

# 4. Probar upload vía API
curl -X POST http://localhost:8000/knowledge/upload \
  -F "file=@otro_documento.pdf" \
  -F "user_id=test-user" \
  -F "category=manual"

# 5. Listar documentos
curl http://localhost:8000/knowledge/list

# 6. Buscar en knowledge
curl -X POST http://localhost:8000/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query": "configuración del sistema"}'

# 7. Probar Tavily MCP (habilitar en mcp.yaml + TAVILY_API_KEY)
python -m management.admin run \
  --agent agnobot-main \
  --message "Usa Tavily para buscar las últimas noticias sobre Agno Framework" \
  --stream

# 8. Verificar schedules en Studio
# os.agno.com > Conectar > Schedules tab

# 9. Eliminar un documento
curl -X DELETE http://localhost:8000/knowledge/doc-id-aqui
```

---

### Notas Importantes de Implementación F5

1. **Scheduler requiere `agno[os]`**: La clase `Schedule` viene con el paquete OS de Agno. No necesita un extra separado para funcionalidad básica.

2. **`knowledge.insert(url=...)` depende del tipo de URL**: Agno soporta PDFs, páginas HTML, y archivos de texto. Para URLs complejas (SPAs, contenido dinámico), se recomienda usar Crawl4ai primero y luego ingestar el resultado.

3. **`skip_if_exists=True`**: Crítico para la auto-ingesta. Sin esto, cada restart re-ingesta todos los documentos duplicando vectores.

4. **Tavily MCP vs TavilyTools**: Se pueden usar ambos simultáneamente. El MCP ofrece más funciones (map, crawl) y no requiere dependencia Python. El tool nativo es más simple para búsquedas básicas.

5. **Knowledge routes vs AgentOS nativo**: AgentOS ya expone endpoints de knowledge en `/v1/knowledge/`. Los routes custom en `/knowledge/` son complementarios y ofrecen funcionalidades adicionales (upload, search personalizado). No entran en conflicto porque usan rutas distintas.

6. **Scheduler timezone**: Importante configurar correctamente para Ecuador (`America/Guayaquil`, UTC-5). Los cron jobs se ejecutan según esta timezone.

7. **MCP stdio corregido en F5**: La corrección del `build_mcp_tools()` (deuda de F1) es obligatoria para que MCP Supabase y GitHub funcionen. Sin esta corrección, solo los MCP con transport `streamable-http` (docs.agno.com, Tavily) funcionan.

---

*Documento generado el 25 de marzo de 2026*
*Incluye: Validación F4, Revisión de Base de Conocimiento, Verificación Shell/Tavily, Plan F5 completo*
*Basado en documentación oficial de Agno + código existente en base de conocimiento*
