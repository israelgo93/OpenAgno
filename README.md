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

### Setup rapido (un solo comando)

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
bash setup.sh
```

`setup.sh` hace todo automaticamente: crea entorno virtual, instala dependencias, lanza el wizard de configuracion y valida el workspace.

### Setup manual (paso a paso)

```bash
# 1. Clonar e instalar
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configurar (wizard interactivo)
python -m management.cli

# 3. Validar
python -m management.validator

# 4. Ejecutar
python gateway.py
```

El agente estara disponible en `http://localhost:8000`.
Conecta desde [os.agno.com](https://os.agno.com) > Add OS > Local.

---

## Referencia completa de comandos

### Ciclo de vida del servicio

| Comando | Descripcion |
|---------|-------------|
| `python gateway.py` | Iniciar gateway en primer plano (desarrollo) |
| `python service_manager.py start` | Iniciar como daemon en segundo plano |
| `python service_manager.py stop` | Detener el daemon y el gateway |
| `python service_manager.py restart` | Reiniciar el daemon y el gateway |
| `python service_manager.py status` | Ver PID y health check del gateway |

### Configuracion y validacion

| Comando | Descripcion |
|---------|-------------|
| `bash setup.sh` | Setup completo: venv + deps + wizard + validacion |
| `python -m management.cli` | Wizard de onboarding (genera workspace + .env) |
| `python -m management.cli doctor` | Diagnostica y repara problemas del workspace |
| `python -m management.cli configure` | Reconfigura una seccion (modelo, DB, canales, keys) |
| `python -m management.cli fallback` | Configura modelo fallback para rate limits |
| `python -m management.cli help` | Muestra todos los comandos disponibles |
| `python -m management.validator` | Validar workspace, API keys, canales, AWS |

### Administracion en tiempo real

| Comando | Descripcion |
|---------|-------------|
| `python -m management.admin status` | Estado del AgentOS (agentes, teams, config) |
| `python -m management.admin sessions --user ID` | Listar sesiones de un usuario |
| `python -m management.admin memories --user ID` | Ver memorias de un usuario |
| `python -m management.admin run --agent ID --message "..."` | Ejecutar agente directamente |
| `python -m management.admin run --agent ID --message "..." --stream` | Ejecutar con streaming |
| `python -m management.admin knowledge-search --query "..."` | Buscar en Knowledge Base |
| `python -m management.admin create-memory --user ID --memory "..."` | Crear memoria manualmente |

### Endpoints HTTP administrativos

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/admin/health` | Health check: version, agentes, teams, modelo, fallback, scheduler |
| `POST` | `/admin/reload` | Solicitar hot-reload al daemon (no mata sesiones) |
| `POST` | `/admin/fallback/activate` | Activar modelo fallback manualmente |
| `POST` | `/admin/fallback/restore` | Restaurar modelo principal |

Ejemplos:

```bash
# Health check
curl http://localhost:8000/admin/health

# Solicitar reload (el daemon reinicia el gateway)
curl -X POST http://localhost:8000/admin/reload

# Crear schedule via API nativa
curl -X POST http://localhost:8000/schedules \
  -H "Content-Type: application/json" \
  -d '{"name":"Resumen","cron_expr":"0 9 * * 1-5","endpoint":"/agents/agnobot-main/runs","method":"POST","payload":{"message":"Genera resumen"},"timezone":"America/Guayaquil"}'

# Listar schedules
curl http://localhost:8000/schedules
```

### Deploy en produccion (systemd)

```bash
# Copiar archivos al servidor
sudo cp deploy/openagno.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openagno
sudo systemctl start openagno

# Administrar servicio
sudo systemctl status openagno    # Estado
sudo systemctl restart openagno   # Reiniciar
sudo systemctl stop openagno      # Detener
sudo journalctl -u openagno -f    # Ver logs
```

### Docker (base de datos local)

| Comando | Descripcion |
|---------|-------------|
| `docker compose up -d db` | Iniciar PostgreSQL + pgvector local |
| `docker compose down` | Detener PostgreSQL local |

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

# Claude Sonnet 4.6 via Bedrock (sin API key Anthropic)
model:
  provider: "aws_bedrock_claude"
  id: "us.anthropic.claude-sonnet-4-6"
  aws_region: "us-east-1"

# Claude Opus 4.6 via Bedrock (mas capaz)
model:
  provider: "aws_bedrock_claude"
  id: "us.anthropic.claude-opus-4-6-v1"
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

## Dominio personalizado + SSL (opcional)

Para exponer OpenAgno con HTTPS (requerido para webhooks de WhatsApp y Slack en produccion), puedes configurar un dominio personalizado con certificado SSL automatico.

### Requisitos previos

- Un servidor con IP publica (ej: AWS Lightsail, EC2, DigitalOcean, VPS)
- Un dominio registrado (ej: `tu-dominio.com`) con el registro DNS **A** apuntando a la IP publica del servidor
- Puertos **80** y **443** abiertos en el firewall/security group

### Paso 1: Verificar DNS

Asegurate de que tu dominio resuelve a la IP de tu servidor:

```bash
# Desde cualquier maquina
dig +short tu-dominio.com
# Debe devolver la IP publica de tu servidor
```

### Paso 2: Instalar Caddy (reverse proxy con SSL automatico)

[Caddy](https://caddyserver.com) obtiene y renueva certificados Let's Encrypt automaticamente.

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y caddy

# Verificar instalacion
caddy version
```

### Paso 3: Configurar reverse proxy

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null << 'EOF'
tu-dominio.com {
    reverse_proxy localhost:8000
}
EOF

# Aplicar configuracion (obtiene certificado SSL automaticamente)
sudo systemctl restart caddy
```

### Paso 4: Verificar HTTPS

```bash
# Verificar que el certificado SSL es valido
curl -s -o /dev/null -w "%{http_code}" https://tu-dominio.com/admin/health
# Debe devolver 200
```

### Paso 5: Configurar webhooks con tu dominio

Una vez que HTTPS esta activo, usa tu dominio para los webhooks de los canales:

| Canal | Webhook URL |
|-------|-------------|
| WhatsApp | `https://tu-dominio.com/whatsapp/webhook` |
| Slack | `https://tu-dominio.com/slack/events` |

**WhatsApp**: En Meta for Developers > Tu App > WhatsApp > Configuration, configura la Callback URL y el Verify Token.

**Slack**: En api.slack.com > Tu App > Event Subscriptions, configura la Request URL.

### Verificar webhook de WhatsApp

```bash
# Simular verificacion de Meta
curl "https://tu-dominio.com/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TU_VERIFY_TOKEN&hub.challenge=test123"
# Debe devolver: test123
```

### AWS Lightsail (ejemplo)

1. Crear instancia Ubuntu en Lightsail
2. Asignar IP estatica a la instancia
3. En **Networking**, abrir puertos **80** (HTTP) y **443** (HTTPS)
4. En **Domains & DNS**, crear zona DNS y agregar registro **A** apuntando a la IP estatica
5. Clonar OpenAgno, ejecutar `bash setup.sh` y seguir los pasos anteriores

### Notas

- Caddy renueva certificados automaticamente (no requiere cron ni certbot)
- Si prefieres nginx + certbot, consulta la [documentacion de Let's Encrypt](https://letsencrypt.org/getting-started/)
- Para desarrollo local, HTTPS no es necesario — el gateway funciona en `http://localhost:8000`
- El webhook de WhatsApp solo funciona con HTTPS y un dominio publico valido

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

Webhook: `https://tu-dominio.com/whatsapp/webhook` (requiere [dominio + SSL](#dominio-personalizado--ssl-opcional)).

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

Webhook: `https://tu-dominio.com/slack/events` (requiere [dominio + SSL](#dominio-personalizado--ssl-opcional)).

### Web (Studio)

Disponible via [os.agno.com](https://os.agno.com) > Add OS > Local > `http://localhost:8000`. Muestra todos los agentes, sub-agentes y teams registrados.

---

## Management CLI

### Onboarding — Genera workspace desde cero

```bash
python -m management.cli
```

Wizard interactivo: identidad, modelo (incluye Bedrock), base de datos, canales, tools, scheduler/auto-ingesta y embeddings. Genera sub-agentes, teams, WorkspaceTools y SchedulerTools.

### Doctor — Diagnostica y repara

```bash
python -m management.cli doctor
```

Verifica: archivos del workspace, variables de entorno, conectividad a DB, modelo, SSL (Caddy), y configuracion de fallback. Ofrece reparacion interactiva para problemas detectados.

### Configure — Reconfigura sin regenerar

```bash
python -m management.cli configure
```

Permite cambiar una seccion especifica del workspace sin regenerar todo:
- Modelo principal (cambia provider/ID y actualiza sub-agentes)
- Base de datos (Supabase, PostgreSQL local, SQLite)
- Canales (WhatsApp, Slack)
- API Keys (.env)
- Herramientas (toggle on/off)
- Identidad del agente (nombre, descripcion)

### Fallback — Modelo alternativo para rate limits

```bash
python -m management.cli fallback
```

Configura un modelo de respaldo que se activa cuando el principal falla (rate limit, error 429, etc).

```yaml
# workspace/config.yaml
model:
  provider: aws_bedrock_claude
  id: us.anthropic.claude-opus-4-6-v1
  aws_region: us-east-1
  fallback:
    provider: google
    id: gemini-2.0-flash
```

El fallback se puede activar manualmente via API:

```bash
# Activar fallback
curl -X POST http://localhost:8000/admin/fallback/activate

# Restaurar modelo principal
curl -X POST http://localhost:8000/admin/fallback/restore
```

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
| **F6: Autonomia** | Daemon, Bedrock, WorkspaceTools, SchedulerTools, SSL/Dominio | **Completada** |

### Fase 6 (completada)

- **Service Manager** — Daemon supervisor con monitor + PID file + senal reload
- **AWS Bedrock** — Soporte `aws_bedrock` (Nova, Mistral) y `aws_bedrock_claude` (Claude optimizado)
- **WorkspaceTools** — El agente se auto-configura: CRUD workspace, crear sub-agentes, toggle tools
- **SchedulerTools** — Gestion de crons via API REST nativa de AgentOS
- **Background Hooks** — `run_hooks_in_background=True` para hooks no bloqueantes
- **Endpoints admin** — `POST /admin/reload` + `GET /admin/health`
- **CLI actualizado** — Soporte Bedrock en onboarding wizard (Claude Opus 4.6, Sonnet 4.6)
- **Validador extendido** — Valida credenciales AWS
- **Deploy systemd** — `deploy/openagno.service` para produccion
- **Dominio + SSL** — Guia para dominio personalizado con Caddy + Let's Encrypt automatico
- **Modelos actualizados** — IDs de Bedrock actualizados a Claude Opus 4.6 y Sonnet 4.6
- **Modelo Fallback** — Soporte para modelo de respaldo en caso de rate limits
- **CLI expandido** — Comandos interactivos `doctor`, `configure` y `fallback`

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
| **Dominio + SSL** | Guia para dominio personalizado con Caddy y Let's Encrypt |
| **Modelo Fallback** | Configura un modelo de respaldo activable manual o via API |

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
  setup.sh                   # Setup rapido: venv + deps + wizard + validacion
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
| `POST` | `/admin/fallback/activate` | Activar modelo fallback manualmente |
| `POST` | `/admin/fallback/restore` | Restaurar modelo principal |

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
