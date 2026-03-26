<p align="center">
  <h1 align="center">OpenAgno</h1>
  <p align="center">
    <strong>Plataforma de agentes IA autonomos y multimodales con workspace declarativo</strong>
  </p>
  <p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://docs.agno.com"><img src="https://img.shields.io/badge/Agno-Framework-6366F1?style=flat-square" alt="Agno"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square" alt="License"></a>
    <a href="https://github.com/israelgo93/OpenAgno"><img src="https://img.shields.io/badge/v1.0.0-Production-brightgreen?style=flat-square" alt="Status"></a>
  </p>
</p>

---

## Que es OpenAgno?

OpenAgno es una plataforma open-source para construir agentes IA autonomos y multimodales, listos para **WhatsApp** (Cloud API + QR), **Slack**, **Telegram** y **Web**. Combina un **workspace declarativo** (YAML + Markdown) con **persistencia unificada** en PostgreSQL/Supabase.

Construido sobre [Agno Framework](https://docs.agno.com) y **AgentOS**.

---

## Quick Start

```bash
# 1. Clonar e instalar
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
bash setup.sh

# 2. (Alternativa manual)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m management.cli

# 3. Validar y ejecutar
python -m management.validator
python gateway.py
```

El agente estara disponible en `http://localhost:8000`.
Conecta desde [os.agno.com](https://os.agno.com) > Add OS > Local.

---

## Arquitectura (v1.0)

```
┌──────────────────────────────────────────────────────────────────┐
│  service_manager.py (daemon supervisor)                           │
│  └──────────┬─────────────────────────────────────────────────┘  │
│             │                                                     │
│  ┌──────────▼─────────────────────────────────────────────────┐  │
│  │  gateway.py (AgentOS) :8000                                 │  │
│  │  ├── _arun_wrapped (STT + Fallback + TTS)                  │  │
│  │  ├── Agente Principal (modelo configurable)                 │  │
│  │  │   ├── DuckDuckGo, Crawl4AI, Reasoning (builtin)        │  │
│  │  │   ├── YFinance, Wikipedia, Arxiv, Calculator (opcionales)│  │
│  │  │   ├── WorkspaceTools + SchedulerTools (autonomia)       │  │
│  │  │   ├── GithubTools, FileTools, PythonTools (opcionales)  │  │
│  │  │   └── MCP (docs.agno.com + custom)                      │  │
│  │  ├── Sub-agentes YAML + Teams multi-agente                  │  │
│  │  ├── Registry Studio (todos los tools del workspace)        │  │
│  │  └── Security: API Key auth                                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Canales:                                                          │
│    WhatsApp Cloud API | WhatsApp QR (Baileys) | Slack | Telegram   │
│    Web (os.agno.com) | AI SDK (Vercel)                             │
│                                                                    │
│  DB: PostgreSQL/Supabase + PgVector                                │
│  Deploy: systemd + Docker Compose                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Workspace

El corazon de OpenAgno es el **workspace**: archivos declarativos que definen completamente al agente.

| Archivo | Funcion |
|---------|---------|
| `workspace/config.yaml` | Configuracion central (modelo, DB, canales, memoria, WhatsApp mode) |
| `workspace/instructions.md` | Personalidad y reglas del agente |
| `workspace/tools.yaml` | Herramientas habilitadas (builtin + opcionales) |
| `workspace/mcp.yaml` | Servidores MCP externos |
| `workspace/self_knowledge.md` | Auto-consciencia del agente (providers, tools validos) |
| `workspace/knowledge/` | Documentos y URLs para RAG |
| `workspace/agents/*.yaml` | Sub-agentes dinamicos |
| `workspace/agents/teams.yaml` | Equipos multi-agente |
| `workspace/schedules.yaml` | Plantilla de tareas cron |
| `workspace/integrations/` | Integraciones declarativas |

### Ejemplo config.yaml

```yaml
agent:
  name: AgnoBot
  id: agnobot-main

model:
  provider: google
  id: gemini-2.5-flash

database:
  type: local  # local | supabase | sqlite

channels:
  - whatsapp
  - telegram

whatsapp:
  mode: cloud_api  # cloud_api | qr_link | dual
```

### Modelos soportados

| Provider | Modelos recomendados |
|----------|---------------------|
| `google` | `gemini-2.5-flash` (default), `gemini-2.5-pro` |
| `openai` | `gpt-4o`, `gpt-4o-mini`, `o1` |
| `anthropic` | `claude-sonnet-4-6`, `claude-haiku-3-5` |
| `aws_bedrock_claude` | `us.anthropic.claude-sonnet-4-6-v1:0` |
| `aws_bedrock` | `amazon.nova-pro-v1:0` |

> **Nota**: `gemini-2.0-flash` sera retirado el 1 de junio de 2026.

---

## Canales

### WhatsApp — Cloud API (oficial Meta)

Canal via Meta Business API. Requiere cuenta Business verificada.

```bash
WHATSAPP_ACCESS_TOKEN=tu_token
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
WHATSAPP_VERIFY_TOKEN=tu_verify_token
```

### WhatsApp — QR Link (Baileys bridge)

Vinculacion via QR como dispositivo secundario. No requiere cuenta Business.

```yaml
# workspace/config.yaml
whatsapp:
  mode: qr_link  # o "dual" para ambos
  qr_link:
    bridge_url: http://localhost:3001
```

```bash
# Iniciar bridge
docker compose --profile qr up -d whatsapp-bridge
# Ver QR
curl http://localhost:3001/qr
```

### WhatsApp — Modo Dual

Ejecuta **ambos** modos simultaneamente. Cloud API para la linea Business oficial y QR Link para una linea personal.

### Slack

Canal via Slack Bot. Scopes: `chat:write`, `app_mentions:read`, `im:history`, `im:read`, `im:write`.

### Telegram

Canal via Telegram Bot (@BotFather). Solo requiere `TELEGRAM_TOKEN` en `.env`.

### Web (Studio)

Disponible via [os.agno.com](https://os.agno.com) > Add OS > Local > `http://localhost:8000`.

### AI SDK (Vercel)

Canal experimental. AG-UI funciona automaticamente via os.agno.com.

---

## Tools disponibles

### Builtin (siempre disponibles)

| Tool | Descripcion |
|------|-------------|
| `duckduckgo` | Busqueda web |
| `crawl4ai` | Scraping de paginas web |
| `reasoning` | Razonamiento paso a paso |

### Opcionales (activar en tools.yaml)

| Tool | Descripcion | Requiere |
|------|-------------|----------|
| `workspace` | Auto-configuracion del workspace | Nada |
| `scheduler_mgmt` | Gestion de crons | Nada |
| `github` | Repositorios GitHub | `PyGithub` + `GITHUB_TOKEN` |
| `email` | Envio de correos Gmail | `GMAIL_*` env vars |
| `tavily` | Busqueda web avanzada | `TAVILY_API_KEY` |
| `audio` | STT + TTS | `OPENAI_API_KEY` |
| `yfinance` | Datos financieros en tiempo real | `yfinance` pip |
| `wikipedia` | Busqueda en Wikipedia | `wikipedia` pip |
| `arxiv` | Papers academicos | `arxiv` pip |
| `calculator` | Calculadora matematica | Nada |
| `file_tools` | Lectura/escritura de archivos | Nada |
| `python_tools` | Ejecucion de codigo Python | Nada (riesgo) |
| `shell` | Comandos del sistema | `OPENAGNO_ROOT` (riesgo) |
| `spotify` | Control de Spotify | Spotify API |

---

## Studio + AgentOSClient (DAT-238)

### Conectar Studio

1. Ejecutar `python gateway.py`
2. Ir a [os.agno.com](https://os.agno.com) > Add OS > Local
3. Ingresar `http://localhost:8000`
4. Studio muestra todos los agentes, sub-agentes y tools del Registry

### AgentOSClient (Python)

```python
from agno.os.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:8000")

# Configuracion
config = await client.aget_config()

# Listar agentes
agents = client.get_agents()

# Ejecutar agente
response = await client.run_agent(
    agent_id="agnobot-main",
    message="Hola, que puedes hacer?",
)

# Sesiones y memorias
sessions = client.get_sessions(user_id="user123")
memories = client.get_memories(user_id="user123")
```

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/admin/health` | Health check con agentes, teams, canales y modelo |
| `POST` | `/admin/reload` | Solicitar hot-reload al daemon |
| `POST` | `/admin/fallback/activate` | Activar modelo fallback |
| `POST` | `/admin/fallback/restore` | Restaurar modelo principal |
| `POST` | `/knowledge/upload` | Subir documento a la Knowledge Base |
| `POST` | `/knowledge/ingest-urls` | Ingestar URLs |
| `GET` | `/knowledge/list` | Listar documentos |
| `DELETE` | `/knowledge/{doc_name}` | Eliminar documento |
| `POST` | `/knowledge/search` | Busqueda semantica |
| `POST` | `/schedules` | Crear tarea cron |
| `GET` | `/schedules` | Listar schedules |
| `GET` | `/whatsapp-qr/status` | Estado de conexion QR |
| `GET` | `/whatsapp-qr/code` | Obtener QR para escanear |
| `POST` | `/whatsapp/webhook` | Webhook WhatsApp (Meta) |

---

## Seguridad

### API Key

```bash
# Generar key
openssl rand -hex 32
# Configurar en .env
OPENAGNO_API_KEY=tu_key_generada
```

Endpoints de Knowledge requieren `X-API-Key` header. Sin key configurada, acceso libre (dev).

### SQL Injection Prevention

Whitelist de tablas permitidas en queries de Knowledge.

### Docker

Credenciales via variables de entorno, no hardcodeadas.

---

## Desarrollo

### Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

### Docker

```bash
# DB local
docker compose up -d db

# Con WhatsApp QR bridge
docker compose --profile qr up -d
```

### Deploy (systemd)

```bash
sudo cp deploy/openagno.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openagno
sudo systemctl start openagno
```

### Service Manager

```bash
python service_manager.py start     # Daemon + gateway
python service_manager.py stop      # Detener
python service_manager.py restart   # Reiniciar
python service_manager.py status    # Health check
```

---

## Progreso del Proyecto

| Fase | Descripcion | Estado |
|------|-------------|--------|
| **F1: MVP** | Gateway + Agente + Knowledge + WhatsApp + MCP | Completada |
| **F2: CLI + Admin** | Onboarding wizard + Validador + Admin | Completada |
| **F3: Multi-Canal + Teams** | Sub-agentes YAML + Teams + Slack | Completada |
| **F4: Remote Agents** | Agentes distribuidos + MCP avanzado | Backlog |
| **F5: Scheduler + Knowledge** | Cron, auto-ingesta, Tavily | Completada |
| **F6: Autonomia** | Daemon, Bedrock, WorkspaceTools, SSL | Completada |
| **v0.7: Audio + Fallback** | AudioTools, fallback inteligente | Completada |
| **v0.8: Estabilizacion** | Auto-consciencia, seguridad, Telegram, GitHub | Completada |
| **v1.0: Produccion** | Tools expandidos, Studio completo, WhatsApp dual, tests | **Completada** |

### v1.0 (actual)

- **Model IDs actualizados** — `gemini-2.5-flash` como default (gemini-2.0-flash deprecado)
- **Workspace generico** — Defaults listos para funcionar con `bash setup.sh` + API key
- **6 nuevos tools** — YFinance, Wikipedia, Arxiv, Calculator, FileTools, PythonTools
- **Canal AI SDK** — Soporte experimental para Vercel AI SDK
- **WhatsApp dual** — Cloud API (oficial Meta) + QR Link (Baileys bridge)
- **WhatsApp QR bridge** — Servicio Node.js sidecar en `bridges/whatsapp-qr/`
- **Registry Studio completo** — Todos los tools del workspace expuestos al Registry
- **AgentOSClient documentado** — Ejemplo de uso programatico
- **Tests basicos** — `tests/` con pytest (loader, validator, security, workspace_tools)
- **CLI actualizado** — Wizard pregunta modo WhatsApp (cloud_api/qr_link/dual) y Telegram
- **README reestructurado** — Sin info repetida, estructura limpia
- **Docker Compose** — Profile `qr` para bridge WhatsApp QR

---

## Estructura del Proyecto

```
OpenAgno/
  gateway.py                 # Gateway v1.0: WhatsApp dual, AI SDK, Registry completo
  loader.py                  # Motor de carga + 6 nuevos tools + defaults actualizados
  security.py                # API Key auth para endpoints REST
  service_manager.py         # Daemon supervisor con hot-reload
  tools/
    workspace_tools.py       # Auto-configuracion del agente
    scheduler_tools.py       # Crons via API REST
    audio_tools.py           # STT + TTS
  workspace/
    config.yaml              # Configuracion central + WhatsApp mode
    instructions.md          # Personalidad generica
    tools.yaml               # 16 tools (3 builtin + 13 opcionales)
    mcp.yaml                 # MCP servers
    self_knowledge.md         # Auto-consciencia (providers, tools, canales)
    knowledge/docs/          # Documentos RAG
    agents/                  # Sub-agentes y Teams
  routes/
    knowledge_routes.py      # Endpoints Knowledge Base
  management/
    cli.py                   # Wizard + doctor + configure + fallback
    validator.py             # Validacion de workspace
    admin.py                 # Admin via AgentOSClient
  bridges/
    whatsapp-qr/             # Servicio Baileys bridge (Node.js)
      index.js               # Bridge principal
      package.json           # Dependencias
      Dockerfile             # Imagen Docker
  tests/
    conftest.py              # Fixtures
    test_loader.py           # Tests de carga
    test_validator.py        # Tests de validacion
    test_security.py         # Tests de seguridad
    test_workspace_tools.py  # Tests de WorkspaceTools
  deploy/
    openagno.service         # Unit systemd
  docker-compose.yml         # DB + gateway + bridge (profile qr)
  requirements.txt           # Dependencias produccion
  requirements-dev.txt       # Dependencias desarrollo (pytest)
  .env.example               # Template variables de entorno
```

---

## Documentacion de Referencia

| Recurso | Enlace |
|---------|--------|
| Agno Docs | [docs.agno.com](https://docs.agno.com) |
| Teams | [Building Teams](https://docs.agno.com/teams/building-teams) |
| PgVector | [Vector Stores](https://docs.agno.com/knowledge/vector-stores/pgvector/overview) |
| MCPTools | [MCP Overview](https://docs.agno.com/tools/mcp/overview) |
| WhatsApp | [WhatsApp Interface](https://docs.agno.com/agent-os/interfaces/whatsapp/introduction) |
| Slack | [Slack Interface](https://docs.agno.com/agent-os/interfaces/slack/introduction) |
| AgentOS | [Demo](https://docs.agno.com/examples/agent-os/demo) |
| Scheduler | [Scheduler](https://docs.agno.com/agent-os/scheduler/overview) |
| Registry | [Studio Registry](https://docs.agno.com/agent-os/studio/registry) |
| AWS Bedrock | [Bedrock Claude](https://docs.agno.com/models/providers/cloud/aws-claude/overview) |

---

## Licencia

Este proyecto esta licenciado bajo [Apache License 2.0](LICENSE).
