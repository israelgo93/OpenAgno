<p align="center">
  <h1 align="center">OpenAgno</h1>
  <p align="center">
    <strong>Plataforma de agentes IA autonomos y multimodales con workspace declarativo</strong>
  </p>
  <p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://docs.agno.com"><img src="https://img.shields.io/badge/Agno-Framework-6366F1?style=flat-square" alt="Agno"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square" alt="License"></a>
    <a href="https://github.com/israelgo93/OpenAgno"><img src="https://img.shields.io/badge/Fase-6_Autonomia-green?style=flat-square" alt="Status"></a>
  </p>
</p>

---

## Que es OpenAgno?

OpenAgno es una plataforma open-source para construir agentes IA autonomos y multimodales, listos para **WhatsApp**, **Slack** y **Web**. Combina un **workspace declarativo** (YAML + Markdown) con **persistencia unificada** en PostgreSQL/Supabase, permitiendo configurar agentes completos sin escribir codigo.

Construido sobre [Agno Framework](https://docs.agno.com) y **AgentOS**, OpenAgno ofrece:

- **Configuracion sin codigo** — Define tu agente con archivos YAML y Markdown
- **Multimodal** — Procesa texto, imagenes, video y audio
- **Multi-canal nativo** — WhatsApp, Slack y Web desde un unico gateway
- **Sub-agentes dinamicos** — Carga sub-agentes desde YAML sin tocar codigo
- **Teams multi-agente** — Equipos con modos coordinate, route, broadcast y tasks
- **Memoria persistente** — MemoryManager + PostgresDb para memoria agentic entre sesiones
- **RAG hibrido** — Busqueda semantica + keyword con PgVector
- **Multi-modelo** — Gemini, Claude, GPT, **AWS Bedrock** (Claude + Nova + Mistral)
- **Autonomia del agente** — WorkspaceTools + SchedulerTools: el agente se auto-configura
- **Daemon con hot-reload** — `service_manager.py` supervisa el gateway y reinicia sin matar sesiones
- **Background Hooks** — Hooks post-run no bloquean la respuesta
- **Scheduler AgentOS** — Cron integrado via API REST `POST /schedules`
- **Auto-ingesta Knowledge** — Documentos y URLs al arrancar
- **MCP nativo** — El agente consulta docs.agno.com y servicios externos
- **Integraciones por carpeta** — `workspace/integrations/<id>/` declarativo
- **CLI de Onboarding** — Wizard interactivo genera workspace completo
- **Admin programatico** — Gestiona sesiones, memorias y knowledge via CLI
- **Deploy listo** — systemd unit + PID file + health check

---

## Arquitectura (F6)

```
┌──────────────────────────────────────────────────────────┐
│  service_manager.py (daemon supervisor)                   │
│  - Arranca gateway como subprocess                       │
│  - Monitorea health + senales de reload                  │
│  - Reinicia sin matar la conversacion actual             │
│  └──────────┬────────────────────────────────────────┘   │
│             │                                             │
│  ┌──────────▼────────────────────────────────────────┐   │
│  │  gateway.py (AgentOS) :8000                        │   │
│  │  ├── scheduler=True (API REST nativa)             │   │
│  │  ├── run_hooks_in_background=True                 │   │
│  │  ├── Agente Principal                             │   │
│  │  │   ├── Modelo: Bedrock Claude / Gemini / GPT    │   │
│  │  │   ├── WorkspaceTools (CRUD workspace + reload) │   │
│  │  │   ├── SchedulerTools (via REST API nativa)     │   │
│  │  │   ├── ShellTools (sandboxed)                   │   │
│  │  │   └── MCP (docs.agno.com + custom)             │   │
│  │  ├── POST /admin/reload (senal al daemon)         │   │
│  │  ├── GET  /admin/health (status completo)         │   │
│  │  └── POST /schedules (API nativa AgentOS)         │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  Canales: WhatsApp | Slack | Web (os.agno.com)            │
│  DB: PostgreSQL/Supabase + PgVector                       │
│  Deploy: deploy/openagno.service (systemd)                │
└──────────────────────────────────────────────────────────┘
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

El wizard genera `workspace/`, `.env` y valida automaticamente. Soporta Gemini, Claude (directo y Bedrock), GPT, Amazon Nova.

**Opcion B** — Manual:

```bash
cp .env.example .env
# Editar .env con tus API keys y credenciales
```

### 3. Validar (opcional)

```bash
python -m management.validator
```

Verifica estructura, variables de entorno, sub-agentes, teams, schedules, URLs, MCP y credenciales AWS.

### 4. Ejecutar

```bash
# Ejecucion directa
python gateway.py

# Como servicio daemon (F6 — reinicio automatico + hot-reload)
python service_manager.py start

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
| `workspace/instructions.md` | Personalidad, reglas y auto-configuracion del agente |
| `workspace/tools.yaml` | Herramientas habilitadas (incluye WorkspaceTools y SchedulerTools) |
| `workspace/mcp.yaml` | Servidores MCP externos |
| `workspace/knowledge/` | Documentos y URLs para RAG |
| `workspace/agents/*.yaml` | Sub-agentes dinamicos |
| `workspace/agents/teams.yaml` | Equipos multi-agente |
| `workspace/schedules.yaml` | Plantilla de tareas cron (registro real via API) |
| `workspace/knowledge/docs/AGENT_OPERACIONES.md` | Runbook operativo |
| `workspace/integrations/` | Integraciones declarativas |

### Modelos soportados

```yaml
# Google Gemini (recomendado)
model:
  provider: "google"
  id: "gemini-2.5-flash"

# Anthropic Claude (directo)
model:
  provider: "anthropic"
  id: "claude-sonnet-4-20250514"

# Claude Sonnet via Bedrock (sin API key Anthropic)
model:
  provider: "aws_bedrock_claude"
  id: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  aws_region: "us-east-1"

# Amazon Nova Pro
model:
  provider: "aws_bedrock"
  id: "amazon.nova-pro-v1:0"
  aws_region: "us-east-1"

# OpenAI GPT
model:
  provider: "openai"
  id: "gpt-4.1"
```

### Sub-Agentes

Los sub-agentes se definen en archivos YAML dentro de `workspace/agents/`. Cada archivo (excepto `teams.yaml`) se carga automaticamente.

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

## Autonomia del Agente (F6)

El agente puede auto-configurarse en tiempo real gracias a dos toolkits:

### WorkspaceTools
- **read/write_workspace_file** — CRUD sobre cualquier archivo del workspace (backup automatico)
- **create_sub_agent** — Crea nuevos sub-agentes desde YAML
- **update_instructions** — Modifica sus propias instrucciones
- **toggle_tool** — Activa/desactiva herramientas
- **request_reload** — Solicita reinicio al daemon sin matar la sesion actual

### SchedulerTools
- **list_schedules** — Ver crons activos en AgentOS
- **create_schedule** — Crear recordatorios con cron (ej: `"0 9 * * 1-5"` = L-V 9am)
- **delete_schedule** — Eliminar por ID
- **trigger_schedule** — Ejecutar manualmente

Los schedules se crean via API REST nativa de AgentOS (no necesitan reload).

---

## Service Manager (F6)

El daemon `service_manager.py` supervisa el gateway como un proceso en segundo plano:

```bash
python service_manager.py start     # Arranca gateway + monitor
python service_manager.py stop      # Detiene gateway
python service_manager.py restart   # Reinicia gateway
python service_manager.py status    # PID + health check
```

Caracteristicas:
- Reinicia automaticamente si el gateway muere
- Detecta senal `.reload_requested` del agente y reinicia sin perder sesiones
- PID file para gestion de procesos
- Health check via `/admin/health`
- Unit systemd en `deploy/openagno.service` para produccion

---

## Canales

### WhatsApp

Canal via Meta Business API. Configura las variables en `.env`:

```bash
WHATSAPP_ACCESS_TOKEN=tu_token
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
WHATSAPP_VERIFY_TOKEN=tu_verify_token
```

Soporta: texto, imagen, video, audio, documentos. Phone como `user_id`, sesion automatica.
Produccion: agregar `WHATSAPP_APP_SECRET` + `APP_ENV=production`.

### Slack

Canal via Slack Bot. Requiere Slack App con scopes `chat:write`, `app_mentions:read`, `im:history`, `im:read`, `im:write`.

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

El webhook de Slack se registra automaticamente en `/slack/events`. Responde a @menciones en canales y a todos los DMs. Thread timestamps como `session_id`.

### Web (Studio)

Disponible via [os.agno.com](https://os.agno.com) > Add OS > Local > `http://localhost:8000`. Muestra todos los agentes, sub-agentes y teams registrados.

---

## Management CLI

### Onboarding — Genera workspace desde cero

```bash
python -m management.cli
```

Wizard interactivo: identidad, modelo (incluye Bedrock), base de datos, canales, tools, scheduler/auto-ingesta y embeddings. Genera sub-agentes, teams, WorkspaceTools y SchedulerTools.

### Validacion — Verifica configuracion

```bash
python -m management.validator
```

Valida archivos requeridos, YAML, API keys (incluye AWS), DB, canales, sub-agentes, teams, schedules, URLs y MCP.

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

---

## Progreso del Proyecto

| Fase | Descripcion | Estado |
|------|-------------|--------|
| **F1: MVP** | Gateway + Agente + Knowledge + WhatsApp + MCP | Completada |
| **F2: CLI + Admin** | Onboarding wizard + Validador + Admin programatico | Completada |
| **F3: Multi-Canal + Teams** | Sub-agentes YAML + Teams + Slack + Knowledge endpoints | Completada |
| **F4: Remote Agents** | Agentes distribuidos + MCP avanzado + A2A | Planificada |
| **F5: Scheduler + Knowledge** | Cron AgentOS, auto-ingesta, Tavily MCP/tool, validador extendido | Completada |
| **F6: Autonomia** | Daemon, Bedrock, WorkspaceTools, SchedulerTools, Background Hooks | **En curso** |

### Fase 6 (actual)

- **Service Manager** — Daemon supervisor con monitor + PID file + senal reload
- **AWS Bedrock** — Soporte `aws_bedrock` (Nova, Mistral) y `aws_bedrock_claude` (Claude optimizado)
- **WorkspaceTools** — El agente se auto-configura: CRUD workspace, crear sub-agentes, toggle tools
- **SchedulerTools** — Gestion de crons via API REST nativa de AgentOS
- **Background Hooks** — `run_hooks_in_background=True` para hooks no bloqueantes
- **Endpoints admin** — `POST /admin/reload` + `GET /admin/health`
- **CLI actualizado** — Soporte Bedrock en onboarding wizard
- **Validador extendido** — Valida credenciales AWS
- **Deploy systemd** — `deploy/openagno.service` para produccion

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
| WhatsApp | Canal via Meta Business API (texto, imagen, video, audio, docs) |
| Slack | Canal via Slack Bot con soporte de threads y @menciones |
| Knowledge Base | Upload, listado, busqueda, eliminacion e ingesta por URLs |
| Scheduler | Cron de AgentOS + API REST `/schedules` |
| Auto-ingesta | Documentos en `knowledge/docs/` y `urls.yaml` al iniciar |
| Tavily | Tool y/o MCP para busqueda web |
| Multi-modelo | Gemini, Claude, GPT, **AWS Bedrock** (Claude, Nova, Mistral) |
| Studio | Editor visual via os.agno.com |
| CLI Onboarding | Wizard que genera workspace completo (incluye Bedrock) |
| Admin programatico | Gestiona sesiones, memorias, knowledge via CLI |
| Validacion automatica | Verifica workspace, sub-agentes, teams y credenciales al arrancar |
| Registry con tools | Studio puede asignar DuckDuckGo y Crawl4AI a agentes |
| Integraciones por carpeta | `workspace/integrations/` fusionada con tools y MCP al arrancar |
| Runbook + Shell opt-in | Operaciones y personalizacion documentadas para el agente |
| **WorkspaceTools** | El agente se auto-configura (CRUD workspace + backup automatico) |
| **SchedulerTools** | Gestion de crons y recordatorios via API REST nativa |
| **Service Manager** | Daemon supervisor con monitor, health check y hot-reload |
| **Background Hooks** | Hooks post-run no bloquean la respuesta |
| **Deploy systemd** | Unit file para produccion con restart automatico |

---

## Stack

| Componente | Tecnologia |
|------------|------------|
| Framework | [Agno](https://docs.agno.com) + AgentOS |
| Lenguaje | Python 3.11+ |
| Servidor | FastAPI + Uvicorn |
| Base de datos | PostgreSQL + PgVector |
| Cloud DB | Supabase |
| Embeddings | OpenAI text-embedding-3-small |
| LLMs | Gemini, Claude, GPT, AWS Bedrock |
| Protocolo | MCP (Model Context Protocol) |
| Deploy | systemd + service_manager.py |

---

## Estructura del Proyecto

```
OpenAgno/
  gateway.py                 # Gateway F6: lifespan, scheduler, hooks, admin endpoints
  loader.py                  # Motor de carga + Bedrock + WorkspaceTools + SchedulerTools
  service_manager.py         # Daemon supervisor con monitor y hot-reload
  tools/
    __init__.py
    workspace_tools.py       # WorkspaceTools — auto-configuracion del agente
    scheduler_tools.py       # SchedulerTools — crons via API REST nativa
  workspace/
    config.yaml              # Configuracion central (incluye Bedrock)
    instructions.md          # Personalidad + auto-configuracion
    tools.yaml               # Herramientas (+ workspace, scheduler_mgmt)
    mcp.yaml                 # Servidores MCP
    integrations/            # Manifiestos por integracion
    knowledge/
      docs/                  # Documentos para RAG + AGENT_OPERACIONES.md
      urls.yaml              # URLs para ingestion
    agents/
      research_agent.yaml    # Sub-agente de investigacion
      teams.yaml             # Equipos multi-agente
    schedules.yaml           # Tareas programadas (plantilla)
  routes/
    __init__.py
    knowledge_routes.py      # Endpoints REST para Knowledge
  management/
    __init__.py
    cli.py                   # Wizard de onboarding (+ Bedrock)
    validator.py             # Validacion de workspace (+ AWS)
    admin.py                 # Admin via AgentOSClient
  deploy/
    openagno.service         # Unit systemd para produccion
  docs_plan/
    plan_agno_agent_platform.md
    phase1_validation_phase2_plan.md
    phase2_validation_phase3_plan.md
    phase3_validation_phase4_plan.md
    phase4_validation_phase5_plan.md
    phase5_validation_phase6_plan_CORRECTED.md
  .env.example               # Template de variables (incluye AWS)
  requirements.txt           # Dependencias (incluye boto3)
  docker-compose.yml         # PostgreSQL pgvector local
```

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/admin/health` | Health check con agentes, teams, canales y modelo |
| `POST` | `/admin/reload` | Solicitar hot-reload al daemon |
| `POST` | `/knowledge/upload` | Subir documento a la Knowledge Base |
| `POST` | `/knowledge/ingest-urls` | Ingestar una lista de URLs |
| `GET` | `/knowledge/list` | Listar documentos con IDs |
| `DELETE` | `/knowledge/{doc_name}` | Eliminar documento por nombre |
| `POST` | `/knowledge/search` | Busqueda semantica con conteo |
| `POST` | `/schedules` | Crear tarea cron (API nativa AgentOS) |
| `GET` | `/schedules` | Listar schedules activos |
| `PATCH` | `/schedules/{id}` | Actualizar schedule |
| `DELETE` | `/schedules/{id}` | Eliminar schedule |
| `POST` | `/schedules/{id}/trigger` | Ejecutar schedule manualmente |
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
| Scheduler | [AgentOS Scheduler](https://docs.agno.com/agent-os/scheduler/overview) |
| Memory | [Agent Memory](https://docs.agno.com/agents/usage/agent-with-memory) |
| Registry | [Studio Registry](https://docs.agno.com/agent-os/studio/registry) |
| AWS Bedrock | [Bedrock Claude](https://docs.agno.com/models/providers/cloud/aws-claude/overview) |
| Background Hooks | [Background Tasks](https://docs.agno.com/agent-os/background-tasks/overview) |

---

## Licencia

Este proyecto esta licenciado bajo [Apache License 2.0](LICENSE).
