<p align="center">
  <h1 align="center">OpenAgno</h1>
  <p align="center">
    <strong>Plataforma de agentes IA multimodal con workspace declarativo</strong>
  </p>
  <p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://docs.agno.com"><img src="https://img.shields.io/badge/Agno-Framework-6366F1?style=flat-square" alt="Agno"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square" alt="License"></a>
    <a href="https://github.com/israelgo93/OpenAgno"><img src="https://img.shields.io/badge/Fase-3_Validada-green?style=flat-square" alt="Status"></a>
  </p>
</p>

---

## Que es OpenAgno?

OpenAgno es una plataforma open-source para construir agentes IA autonomos y multimodales. Combina un **workspace declarativo** (YAML + Markdown) con **persistencia unificada** en PostgreSQL/Supabase, permitiendo configurar agentes completos sin escribir codigo.

Construido sobre [Agno Framework](https://docs.agno.com), OpenAgno ofrece:

- **Configuracion sin codigo** — Define tu agente con archivos YAML y Markdown
- **Multimodal** — Procesa texto, imagenes, video y audio
- **Sub-agentes dinamicos** — Carga sub-agentes desde YAML sin tocar codigo
- **Teams multi-agente** — Equipos con modos coordinate, route, broadcast y tasks
- **Memoria persistente** — MemoryManager + PostgresDb para memoria agentic entre sesiones
- **RAG hibrido** — Busqueda semantica + keyword con PgVector
- **Multi-canal** — WhatsApp, Slack y Web desde un unico gateway
- **Autonomia via MCP** — El agente consulta la documentacion de Agno por si mismo
- **CLI de Onboarding** — Genera workspace completo con un wizard interactivo
- **Admin programatico** — Gestiona sesiones, memorias y knowledge via CLI o codigo

---

## Arquitectura

```
                    Canales
          +---------+---------+
          |         |         |
      WhatsApp    Slack      Web
          |         |     (os.agno.com)
          +----+----+---------+
               |
     +---------v-----------+
     |   Gateway (AgentOS)  |
     |   FastAPI + CORS     |
     |   + Validacion auto  |
     +---------+------------+
               |
     +---------v------------------+
     |   Agente Principal          |
     |   - Gemini/Claude/GPT      |
     |   - Tools (DuckDuckGo,     |
     |     Crawl4AI, Reasoning)   |
     |   - MCP (docs.agno.com)    |
     |   - MemoryManager          |
     +---------+------------------+
               |
     +---------v------------------+
     |   Sub-Agentes (YAML)       |
     |   - Research Agent         |
     |   - (Extensible via YAML)  |
     +---------+------------------+
               |
     +---------v------------------+
     |   Teams Multi-Agente       |
     |   - Research Team          |
     |   - Modos: coordinate,    |
     |     route, broadcast, tasks|
     +---------+------------------+
               |
     +---------v------------------+
     |   PostgreSQL/Supabase      |
     |   - Sesiones               |
     |   - Memorias               |
     |   - Knowledge (PgVector)   |
     |   - Vectores (Hybrid)      |
     +----------------------------+
```

---

## Quickstart

### 1. Clonar e instalar

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
python -m venv .venv && source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configurar

**Opcion A** — Wizard interactivo (recomendado):

```bash
python -m management.cli
```

El wizard genera `workspace/`, `.env` y valida la configuracion automaticamente. Incluye generacion de sub-agentes y teams de ejemplo.

**Opcion B** — Manual:

```bash
cp .env.example .env
# Editar .env con tus API keys y credenciales
```

### 3. Validar (opcional)

```bash
python -m management.validator
```

Verifica que el workspace tenga la estructura correcta, las variables de entorno necesarias, y valida sub-agentes y teams.

### 4. Ejecutar

```bash
# Con Supabase (produccion)
python gateway.py

# Con PostgreSQL local (desarrollo)
docker compose up -d db
python gateway.py
```

El agente estara disponible en `http://localhost:8000`.
Conecta desde [os.agno.com](https://os.agno.com) > Add OS > Local.

---

## Workspace

El corazon de OpenAgno es el **workspace**: una carpeta con archivos declarativos que definen completamente al agente.

| Archivo | Funcion |
|---------|---------|
| `workspace/config.yaml` | Configuracion central (modelo, DB, canales, memoria) |
| `workspace/instructions.md` | Personalidad y reglas del agente |
| `workspace/tools.yaml` | Herramientas habilitadas |
| `workspace/mcp.yaml` | Servidores MCP externos |
| `workspace/knowledge/` | Documentos y URLs para RAG |
| `workspace/agents/research_agent.yaml` | Sub-agente de investigacion |
| `workspace/agents/teams.yaml` | Equipos multi-agente |
| `workspace/schedules.yaml` | Tareas programadas |

Modifica cualquier archivo y reinicia para aplicar los cambios.

### Sub-Agentes

Los sub-agentes se definen en archivos YAML dentro de `workspace/agents/`. Cada archivo (excepto `teams.yaml`) se carga automaticamente como un sub-agente.

```yaml
agent:
  name: "Research Agent"
  id: "research-agent"
  role: "Realiza busquedas web profundas"
  model:
    provider: "google"
    id: "gemini-2.0-flash"
  tools:
    - duckduckgo
    - crawl4ai
    - reasoning
  instructions:
    - "Busca en la web y sintetiza informacion."
  config:
    tool_call_limit: 5
    enable_agentic_memory: false
    markdown: true
execution:
  type: "local"
```

### Teams

Los teams coordinan multiples agentes. Se configuran en `workspace/agents/teams.yaml`:

```yaml
teams:
  - name: "Research Team"
    id: "research-team"
    mode: "coordinate"  # coordinate | route | broadcast | tasks
    members:
      - agnobot-main
      - research-agent
    model:
      provider: "google"
      id: "gemini-2.0-flash"
    instructions:
      - "Coordina entre los agentes para dar la mejor respuesta."
```

---

## Management CLI

OpenAgno incluye un modulo de gestion completo:

### Onboarding — Genera workspace desde cero

```bash
python -m management.cli
```

Wizard interactivo de 6 pasos: identidad, modelo, base de datos, canales, tools y embeddings. Genera sub-agentes y teams de ejemplo.

### Validacion — Verifica configuracion

```bash
python -m management.validator
```

Valida archivos requeridos, secciones en YAML, API keys, variables de DB, canales, sub-agentes y teams.

### Admin — Gestiona el agente en ejecucion

```bash
# Estado del AgentOS
python -m management.admin status

# Listar sesiones de un usuario
python -m management.admin sessions --user "+593991234567"

# Ver memorias
python -m management.admin memories --user "+593991234567"

# Ejecutar agente directamente
python -m management.admin run --agent agnobot-main --message "Hola"

# Ejecutar sub-agente
python -m management.admin run --agent research-agent --message "Busca noticias de IA" --stream

# Ejecutar team
python -m management.admin run --agent research-team --message "Investiga Agno framework" --stream

# Buscar en Knowledge Base
python -m management.admin knowledge-search --query "documento"

# Crear memoria manualmente
python -m management.admin create-memory --user admin --memory "Prefiere respuestas en espanol"
```

Tambien se puede usar como modulo Python:

```python
from management.admin import AdminClient

admin = AdminClient("http://localhost:8000")
info = await admin.status()
memories = await admin.list_memories(user_id="+593991234567")
response = await admin.run_agent(agent_id="agnobot-main", message="Hola")
```

---

## Canales

### WhatsApp

Canal via Meta Business API. Configura las variables en `.env`:

```bash
WHATSAPP_ACCESS_TOKEN=tu_token
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
WHATSAPP_VERIFY_TOKEN=tu_verify_token
```

### Slack

Canal via Slack Bot. Requiere crear una Slack App con los scopes `chat:write`, `app_mentions:read`, `im:history`, `im:read`, `im:write`.

```bash
SLACK_TOKEN=xoxb-tu-bot-token
SLACK_SIGNING_SECRET=tu_signing_secret
```

Activa el canal en `workspace/config.yaml`:

```yaml
channels:
  - whatsapp
  - slack
```

El webhook de Slack se registra automaticamente en `/slack/events`.

### Web (Studio)

Disponible via [os.agno.com](https://os.agno.com) > Add OS > Local > `http://localhost:8000`. Muestra todos los agentes, sub-agentes y teams registrados.

---

## Progreso del Proyecto

| Fase | Descripcion | Estado |
|------|-------------|--------|
| **F1: MVP** | Gateway + Agente + Knowledge + WhatsApp + MCP | Completada |
| **F2: CLI + Admin** | Onboarding wizard + Validador + Admin programatico | Completada |
| **F3: Multi-Canal + Teams** | Sub-agentes YAML + Teams + Slack + Knowledge endpoints | Validada |
| **F4: Remote Agents** | Agentes distribuidos + MCP avanzado (Supabase, GitHub) + A2A | Planificada |

### Proxima Fase: F4 — Remote Execution + MCP Avanzado

- Agentes distribuidos en multiples instancias de AgentOS
- `RemoteAgent` para agentes en servidores separados
- MCP servers configurables (Supabase, GitHub, Filesystem)
- Protocolo A2A para interoperabilidad inter-framework
- Docker multi-servicio (Gateway + Research Server + DB)

---

## Features

| Feature | Descripcion |
|---------|-------------|
| Multimodal | Procesa imagenes, video, audio y texto |
| Workspace declarativo | Configura con YAML y Markdown, sin codigo |
| Sub-agentes YAML | Carga sub-agentes dinamicamente desde archivos YAML |
| Teams multi-agente | Equipos con modos coordinate, route, broadcast, tasks |
| PgVector + Hybrid Search | Busqueda semantica y por keywords |
| MemoryManager | Memoria agentic persistente entre sesiones |
| MCP a docs.agno.com | El agente consulta su propia documentacion |
| WhatsApp | Canal via Meta Business API |
| Slack | Canal via Slack Bot con soporte de threads |
| Knowledge Base | Upload, listado, busqueda y eliminacion de documentos |
| Multi-modelo | Gemini, Claude, GPT configurables |
| Studio | Editor visual via os.agno.com |
| CLI Onboarding | Wizard que genera workspace completo |
| Admin programatico | Gestiona sesiones, memorias, knowledge via CLI |
| Validacion automatica | Verifica workspace, sub-agentes y teams al arrancar |
| Registry con tools | Studio puede asignar DuckDuckGo y Crawl4AI a agentes |

---

## Stack

| Componente | Tecnologia |
|------------|------------|
| Framework | [Agno](https://docs.agno.com) |
| Lenguaje | Python 3.11+ |
| Servidor | FastAPI + Uvicorn |
| Base de datos | PostgreSQL + PgVector |
| Cloud DB | Supabase |
| Embeddings | OpenAI text-embedding-3-small |
| LLMs | Gemini, Claude, GPT |
| Protocolo | MCP (Model Context Protocol) |

---

## Estructura del Proyecto

```
OpenAgno/
  gateway.py                 # Gateway con sub-agentes, teams, Slack
  loader.py                  # Motor de carga + build_sub_agents() + build_teams()
  workspace/
    config.yaml              # Configuracion central
    instructions.md          # Personalidad del agente
    tools.yaml               # Herramientas
    mcp.yaml                 # Servidores MCP
    knowledge/
      docs/                  # Documentos para RAG
      urls.yaml              # URLs para ingestion
    agents/
      research_agent.yaml    # Sub-agente de investigacion
      teams.yaml             # Equipos multi-agente
    schedules.yaml           # Tareas programadas
  routes/
    __init__.py
    knowledge_routes.py      # Endpoints REST funcionales para Knowledge
  management/
    __init__.py              # Modulo de gestion
    cli.py                   # Wizard de onboarding
    validator.py             # Validacion de workspace + sub-agentes + teams
    admin.py                 # Admin via AgentOSClient
  docs_plan/
    plan_agno_agent_platform.md           # Plan general del proyecto
    phase1_validation_phase2_plan.md      # Validacion F1 + Plan F2
    phase2_validation_phase3_plan.md      # Validacion F2 + Plan F3
    phase3_validation_phase4_plan.md      # Validacion F3 + Plan F4
  .env.example               # Template de variables
  requirements.txt           # Dependencias
  docker-compose.yml         # PostgreSQL pgvector local
```

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `POST` | `/knowledge/upload` | Subir documento a la Knowledge Base |
| `GET` | `/knowledge/list` | Listar documentos con IDs |
| `DELETE` | `/knowledge/{doc_name}` | Eliminar documento por nombre |
| `POST` | `/knowledge/search` | Busqueda semantica con conteo |
| `GET` | `/whatsapp/status` | Estado del webhook WhatsApp |
| `POST` | `/whatsapp/webhook` | Webhook para mensajes WhatsApp |
| `POST` | `/slack/events` | Webhook para eventos Slack |

---

## Documentacion de Referencia

| Recurso | Enlace |
|---------|--------|
| Agno Docs | [docs.agno.com](https://docs.agno.com) |
| Teams | [Building Teams](https://docs.agno.com/teams/building-teams) |
| Team Modes | [Team Overview](https://docs.agno.com/teams/overview) |
| PgVector | [Vector Stores](https://docs.agno.com/knowledge/vector-stores/pgvector/overview) |
| Hybrid Search | [Busqueda Hibrida](https://docs.agno.com/knowledge/concepts/search-and-retrieval/hybrid-search) |
| MCPTools | [MCP Overview](https://docs.agno.com/tools/mcp/overview) |
| WhatsApp | [WhatsApp Interface](https://docs.agno.com/agent-os/interfaces/whatsapp/introduction) |
| Slack | [Slack Interface](https://docs.agno.com/agent-os/interfaces/slack/introduction) |
| AgentOS | [Demo](https://docs.agno.com/examples/agent-os/demo) |
| Memory | [Agent Memory](https://docs.agno.com/agents/usage/agent-with-memory) |
| Registry | [Studio Registry](https://docs.agno.com/agent-os/studio/registry) |
| Remote Agents | [Remote Agent](https://docs.agno.com/agents/remote-agent) |

---

## Licencia

Este proyecto esta licenciado bajo [Apache License 2.0](LICENSE).
