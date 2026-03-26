# 🚀 Plan de Implementación v3: Plataforma de Agentes IA con Agno

## Evolucion: AgnoBot v3

**Objetivo:** Plataforma open-source construida sobre **Agno Framework**, con agentes auto-configurables, workspace parametrizable, persistencia unificada en PostgreSQL/Supabase (PgVector), y acceso autonomo a documentacion oficial de Agno.

**Cambios clave respecto a v2:**

| Aspecto | v2 | v3 |
|---------|----|----|
| Vector DB | LanceDB (local) | **PgVector/Supabase** (unificado) |
| Configuración | Hardcoded en gateway.py | **Workspace parametrizable** (YAML/JSON + archivos .md) |
| Autonomía del agente | Sin acceso a docs | **MCP a docs.agno.com** para autoayuda |
| Onboarding | CLI básico → .env | **CLI → Workspace completo** con instructions.md, tools, MCP |
| Canales | WhatsApp + Slack | **WhatsApp + Slack + Web (AG-UI/Control Plane)** |
| Personalización | Manual en código | **Agente se auto-modifica** via workspace |
| Orquestación | Agente único | **Agent crea Teams, Workflows, sub-agentes** |

---

## 🏗️ ARQUITECTURA v3

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE USUARIO                                  │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  WhatsApp  │  │   Slack    │  │  Web (AG-UI  │  │ CLI Onboard  │   │
│  │ (Interface)│  │ (Interface)│  │  /ControlPlane│  │  + Admin     │   │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘   │
│        │               │                │                  │           │
│        └───────────────┬┼────────────────┘                 │           │
│                        ▼▼                                  │           │
│  ┌───────────────────────────────────────────────────┐     │           │
│  │            GATEWAY (AgentOS Principal)             │◄────┘           │
│  │  • Punto de entrada unificado (FastAPI)           │                 │
│  │  • JWT/RBAC Security                              │                 │
│  │  • Registry (tools, modelos, DBs)                 │                 │
│  │  • Scheduler (cron jobs)                          │                 │
│  │  • Studio (editor visual) [ALPHA]                 │                 │
│  │  • MCP Server (/mcp endpoint)                     │                 │
│  └──────────┬──────────────┬─────────────────────────┘                 │
│             │              │                                            │
│     ┌───────▼──────┐ ┌────▼────────────┐                              │
│     │ Agente       │ │ RemoteAgent(s)  │                              │
│     │ Principal    │ │ (Especializados)│                              │
│     │              │ │ • Research Bot  │                              │
│     │ • Gemini/    │ │ • Data Bot      │                              │
│     │   Claude/    │ │ • Custom Bots   │                              │
│     │   GPT        │ └─────────────────┘                              │
│     │ • Memoria    │                                                   │
│     │ • RAG        │      ┌──────────────────────────┐                │
│     │ • Tools      │      │   WORKSPACE (por agente)  │                │
│     │ • MCP        │      │   workspace/               │                │
│     └──────────────┘      │   ├── config.yaml          │                │
│                           │   ├── instructions.md      │                │
│  ┌──────────────────┐     │   ├── tools.yaml           │                │
│  │   PostgreSQL/    │     │   ├── mcp.yaml             │                │
│  │   Supabase       │     │   ├── knowledge/           │                │
│  │   (UNIFICADO)    │     │   │   └── *.pdf, *.md      │                │
│  │   • Sesiones     │     │   ├── agents/              │                │
│  │   • Memorias     │     │   │   └── sub_agents.yaml  │                │
│  │   • Knowledge    │     │   └── schedules.yaml       │                │
│  │   • Vectores     │     └──────────────────────────┘                │
│  │   • Trazas       │                                                  │
│  │   • Studio       │     ┌──────────────────────────┐                │
│  └──────────────────┘     │  MCP: docs.agno.com/mcp   │                │
│                           │  (Autonomía del agente)   │                │
│                           └──────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 CAMBIO PRINCIPAL: LanceDB → PgVector/Supabase

### Justificación

| Criterio | LanceDB | PgVector/Supabase |
|----------|---------|-------------------|
| Persistencia | Archivos locales | PostgreSQL managed |
| Escalabilidad | Limitada | Horizontal con Supabase |
| Unificación | DB separada para vectores | **Misma DB** para sesiones + memorias + vectores |
| Búsqueda híbrida | Requiere Tantivy | **Nativo** con `SearchType.hybrid` |
| Filtros metadata | Limitados | **JSONB nativo** — filtros SQL completos |
| Backups | Manual | Automáticos en Supabase |
| Multi-tenant | Complejo | Natural con filtros `user_id` |
| Costo | Gratis (local) | Free tier Supabase / self-hosted |

### Patrón de Implementación (extraído de Veredix)

```python
import os
from agno.db.postgres import PostgresDb
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector, SearchType

# === Conexión unificada ===
# Parámetros desde .env — compatible con Supabase Session Pooler
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5532")
db_user = os.getenv("DB_USER", "ai")
db_password = os.getenv("DB_PASSWORD", "ai")
db_name = os.getenv("DB_NAME", "ai")
db_sslmode = os.getenv("DB_SSLMODE", "prefer")  # "require" para Supabase

db_url = (
    f"postgresql+psycopg://{db_user}:{db_password}"
    f"@{db_host}:{db_port}/{db_name}"
    f"?sslmode={db_sslmode}"
)

# === PostgresDb — Sesiones, memorias, contents ===
db = PostgresDb(
    db_url=db_url,
    id="agnobot_db",
    knowledge_table="agnobot_knowledge_contents",
)

# === PgVector — Vectores + búsqueda híbrida ===
knowledge = Knowledge(
    vector_db=PgVector(
        table_name="agnobot_knowledge_vectors",
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=db,
    max_results=5,
)
```

### Docker: PostgreSQL con pgvector

```yaml
# Para desarrollo local (alternativa a Supabase)
services:
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
```

### Supabase (Producción)

```bash
# Variables para Supabase — Session Pooler (IPv4)
DB_HOST=aws-0-us-west-1.pooler.supabase.com
DB_PORT=5432
DB_USER=postgres.tu_tenant_id
DB_PASSWORD=tu_password_seguro
DB_NAME=postgres
DB_SSLMODE=require
```

---

## 📁 ESTRUCTURA DEL WORKSPACE

El concepto central de v3 es el **Workspace**: una carpeta que contiene toda la configuración del agente de forma declarativa. El agente puede leer y modificar estos archivos para auto-configurarse.

### Estructura de Archivos

```
agnobot/
├── gateway.py                    # Punto de entrada — lee workspace y construye AgentOS
├── loader.py                     # Carga dinámica del workspace → objetos Agno
├── workspace/                    # ★ WORKSPACE PARAMETRIZABLE ★
│   ├── config.yaml               # Configuración central (DB, modelo, canales)
│   ├── instructions.md           # Instrucciones/personalidad del agente principal
│   ├── tools.yaml                # Tools habilitados + configuración
│   ├── mcp.yaml                  # Servidores MCP externos
│   ├── knowledge/                # Documentos para RAG
│   │   ├── docs/                 # PDFs, TXT, DOCX para ingestión
│   │   └── urls.yaml             # URLs para scraping/ingestión
│   ├── agents/                   # Definición de sub-agentes y teams
│   │   ├── research_agent.yaml   # Agente de investigación
│   │   └── teams.yaml            # Definición de teams
│   └── schedules.yaml            # Tareas programadas (cron)
├── management/
│   ├── __init__.py
│   ├── cli.py                    # CLI de onboarding (genera workspace/)
│   └── admin.py                  # Admin via AgentOSClient
├── tools/
│   ├── __init__.py
│   └── custom_tools.py           # Toolkits personalizados
├── routes/
│   ├── __init__.py
│   └── knowledge_routes.py       # Endpoints de knowledge (upload/list/delete)
├── .env                          # Solo secretos (API keys, contraseñas)
├── .env.example
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

### workspace/config.yaml

```yaml
# ═══════════════════════════════════════
# AgnoBot — Configuración Central
# ═══════════════════════════════════════

# Identidad del agente
agent:
  name: "AgnoBot"
  id: "agnobot-main"
  description: "Asistente personal multimodal autónomo"

# Modelo de IA
model:
  provider: "google"        # google | openai | anthropic
  id: "gemini-2.0-flash"    # ID específico del modelo
  # Las API keys van en .env, NO aquí

# Base de datos
database:
  # Si type=supabase, lee DB_HOST, DB_PORT, etc. de .env
  # Si type=local, usa Docker pgvector local
  # Si type=sqlite, usa SQLite para desarrollo rápido
  type: "supabase"          # supabase | local | sqlite
  knowledge_table: "agnobot_knowledge_contents"
  vector_table: "agnobot_knowledge_vectors"

# Vector DB
vector:
  search_type: "hybrid"     # hybrid | vector | keyword
  embedder: "text-embedding-3-small"
  max_results: 5

# Canales habilitados
channels:
  - whatsapp
  # - slack
  # - web  # AG-UI / Control Plane (siempre disponible via os.agno.com)

# Memoria
memory:
  enable_agentic_memory: true
  enable_user_memories: true
  enable_session_summaries: true
  num_history_runs: 5

# AgentOS
agentos:
  id: "agnobot-gateway"
  name: "AgnoBot Platform"
  port: 8000
  tracing: true
  enable_mcp_server: true   # Exponer como MCP en /mcp
  # security_key en .env como OS_SECURITY_KEY

# Studio (ALPHA)
studio:
  enabled: true  # Requiere PostgreSQL
```

### workspace/instructions.md

```markdown
# Instrucciones del Agente

Eres **AgnoBot**, un asistente personal multimodal autónomo.

## Personalidad
- Amable, eficiente y proactivo
- Respondes en el idioma del usuario
- Usas formato Markdown cuando es apropiado

## Capacidades
- Puedes analizar imágenes, videos y audios enviados
- Buscas en la web cuando necesitas información actualizada
- Usas la base de conocimiento para responder sobre documentos cargados
- Recuerdas información importante del usuario entre sesiones

## Reglas
- Si no estás seguro de algo, búscalo antes de responder
- Siempre cita tus fuentes cuando uses información de la web
- Si el usuario carga documentos, confírmaselo y ofrece analizarlos
- Puedes consultar la documentación de Agno si necesitas información técnica sobre tus propias capacidades

## Contexto
- Fecha y hora actual: se agrega automáticamente
- Historial de conversación: disponible
- Memorias del usuario: disponibles
```

### workspace/tools.yaml

```yaml
# ═══════════════════════════════════════
# Tools — Herramientas del Agente
# ═══════════════════════════════════════

# Tools nativos de Agno (siempre disponibles)
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

# Tools que requieren configuración (API keys en .env)
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

  - name: spotify
    enabled: false
    # Requiere SPOTIFY_ACCESS_TOKEN en .env

  - name: shell
    enabled: false
    # ⚠️ RIESGO DE SEGURIDAD — solo activar si es necesario

# Toolkits personalizados (archivos Python en tools/)
custom:
  # - module: tools.custom_tools
  #   class: MyCustomToolkit
  #   config: {}
```

### workspace/mcp.yaml

```yaml
# ═══════════════════════════════════════
# MCP — Servidores Model Context Protocol
# ═══════════════════════════════════════
# Referencia: https://docs.agno.com/tools/mcp/overview

# MCP Servers que el agente puede usar como herramientas
servers:
  # Documentación de Agno — permite al agente buscar en docs oficiales
  - name: agno_docs
    enabled: true
    transport: "streamable-http"
    url: "https://docs.agno.com/mcp"

  # Ejemplo: GitHub MCP
  # - name: github
  #   enabled: false
  #   transport: "stdio"
  #   command: "npx -y @modelcontextprotocol/server-github"
  #   env:
  #     GITHUB_TOKEN: "${GITHUB_TOKEN}"

  # Ejemplo: Supabase MCP (gestión de DB)
  # - name: supabase
  #   enabled: false
  #   transport: "stdio"
  #   command: "npx -y @supabase/mcp-server-supabase@latest --access-token=${SUPABASE_ACCESS_TOKEN}"

  # Ejemplo: Filesystem MCP
  # - name: filesystem
  #   enabled: false
  #   transport: "stdio"
  #   command: "npx -y @modelcontextprotocol/server-filesystem /home/user/docs"

# Configuración del servidor MCP propio (expuesto por AgentOS)
expose:
  enabled: true  # Exponer AgentOS como MCP server en /mcp
  # Permite a otros agentes/clientes conectarse a este AgentOS via MCP
```

### workspace/agents/research_agent.yaml

```yaml
# ═══════════════════════════════════════
# Sub-Agente: Investigador
# ═══════════════════════════════════════

agent:
  name: "Research Agent"
  id: "research-agent"
  role: "Realiza búsquedas web profundas y sintetiza información"
  
  model:
    provider: "google"
    id: "gemini-2.0-flash"
  
  tools:
    - duckduckgo
    - crawl4ai
  
  instructions:
    - "Eres un agente especializado en investigación profunda."
    - "Busca en la web, scrapea páginas y sintetiza información."
    - "Siempre cita tus fuentes con URLs."
    - "Sé conciso pero completo."
  
  config:
    tool_call_limit: 5
    enable_user_memories: true
    add_datetime_to_context: true
    markdown: true

# Modo de ejecución
execution:
  type: "local"  # local | remote
  # Si remote:
  # remote_url: "http://research-server:7778"
```

### workspace/agents/teams.yaml

```yaml
# ═══════════════════════════════════════
# Teams — Equipos Multi-Agente
# ═══════════════════════════════════════
# Referencia: https://docs.agno.com/teams

teams: []
  # Ejemplo:
  # - name: "Research Team"
  #   id: "research-team"
  #   mode: "coordinate"  # coordinate | route | collaborate
  #   members:
  #     - research-agent
  #     - agnobot-main
  #   model:
  #     provider: "google"
  #     id: "gemini-2.0-flash"
  #   instructions:
  #     - "Coordina entre los agentes para dar la mejor respuesta."
```

### workspace/schedules.yaml

```yaml
# ═══════════════════════════════════════
# Scheduler — Tareas Programadas
# ═══════════════════════════════════════
# Referencia: https://docs.agno.com/agent-os/scheduler/overview

schedules: []
  # Ejemplo:
  # - name: "Resumen matutino"
  #   agent_id: "agnobot-main"
  #   cron: "0 9 * * *"        # Todos los días a las 9am
  #   timezone: "America/Guayaquil"
  #   message: "Genera un resumen de las noticias más importantes del día"
  #   user_id: "admin"
```

### workspace/knowledge/urls.yaml

```yaml
# ═══════════════════════════════════════
# Knowledge — URLs para Ingestión
# ═══════════════════════════════════════

urls: []
  # Ejemplo:
  # - url: "https://example.com/docs/guide.pdf"
  #   name: "Guía de Usuario"
  #   metadata:
  #     category: "documentacion"
  #     source: "manual"
```

---

## ⚙️ CARGA DINÁMICA DEL WORKSPACE

### loader.py — Motor de Configuración

```python
"""
Loader — Carga dinámica del workspace y construye objetos Agno.

Lee archivos YAML/MD del workspace/ y construye:
- Agentes con sus tools, instrucciones y MCP
- Knowledge base con PgVector/Supabase
- Configuración de canales (WhatsApp, Slack, Web)
- Sub-agentes, teams y schedules
"""
import os
import yaml
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.db.sqlite import SqliteDb
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from agno.tools.mcp import MCPTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.reasoning import ReasoningTools
from agno.utils.log import logger

load_dotenv()

WORKSPACE_DIR = Path(os.getenv("AGNOBOT_WORKSPACE", "workspace"))


def _resolve_env(value: str) -> str:
    """Resuelve referencias ${VAR} en valores de configuración."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.getenv(env_key, "")
    return value


def _resolve_config(config: dict) -> dict:
    """Resuelve todas las referencias ${VAR} en un dict."""
    resolved = {}
    for k, v in config.items():
        if isinstance(v, str):
            resolved[k] = _resolve_env(v)
        elif isinstance(v, dict):
            resolved[k] = _resolve_config(v)
        else:
            resolved[k] = v
    return resolved


def load_yaml(filename: str) -> dict:
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
    # Retorna como lista de un solo elemento (el markdown completo)
    return [content]


def build_db_url(db_config: dict) -> str:
    """Construye la URL de conexión según el tipo de DB."""
    db_type = db_config.get("type", "local")

    if db_type == "sqlite":
        return f"sqlite:///tmp/agnobot.db"

    # Para supabase y local, construir URL PostgreSQL
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


def build_db(db_url: str, db_config: dict):
    """Construye el objeto de base de datos."""
    if db_url.startswith("sqlite"):
        return SqliteDb(db_file="tmp/agnobot.db")
    return PostgresDb(
        db_url=db_url,
        id="agnobot_db",
        knowledge_table=db_config.get("knowledge_table", "agnobot_knowledge_contents"),
    )


def build_knowledge(db_url: str, db, vector_config: dict, db_config: dict) -> Knowledge:
    """Construye la Knowledge base con PgVector."""
    if db_url.startswith("sqlite"):
        # SQLite no soporta PgVector — retornar None
        logger.warning("SQLite no soporta PgVector. Knowledge deshabilitada.")
        return None

    search_type_map = {
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


def build_tools(tools_config: dict) -> list:
    """Construye la lista de tools según tools.yaml."""
    tools = []

    # Tools builtin
    TOOL_MAP = {
        "duckduckgo": lambda cfg: DuckDuckGoTools(**cfg),
        "crawl4ai": lambda cfg: Crawl4aiTools(**cfg),
        "reasoning": lambda cfg: ReasoningTools(**cfg),
    }

    for tool_def in tools_config.get("builtin", []):
        if not tool_def.get("enabled", True):
            continue
        name = tool_def["name"]
        config = _resolve_config(tool_def.get("config", {}))
        if name in TOOL_MAP:
            tools.append(TOOL_MAP[name](config))
        else:
            logger.warning(f"Tool builtin desconocido: {name}")

    # Tools opcionales (requieren API keys)
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
            logger.warning("⚠️ ShellTools activado — riesgo de seguridad")
            tools.append(ShellTools())

    return tools


def build_mcp_tools(mcp_config: dict) -> list:
    """Construye MCPTools según mcp.yaml."""
    mcp_tools = []

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
                # Para stdio, se necesita contexto async — se maneja en gateway
                mcp_tools.append({
                    "type": "stdio",
                    "command": command,
                    "env": {**os.environ, **env},
                    "name": server.get("name", "mcp-server"),
                })

    return mcp_tools


def build_model(model_config: dict):
    """Construye el modelo según la configuración."""
    provider = model_config.get("provider", "google")
    model_id = model_config.get("id", "gemini-2.0-flash")

    if provider == "google":
        from agno.models.google import Gemini
        return Gemini(id=model_id)
    elif provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(id=model_id, api_key=os.getenv("OPENAI_API_KEY"))
    elif provider == "anthropic":
        from agno.models.anthropic import Claude
        return Claude(id=model_id)
    else:
        raise ValueError(f"Proveedor de modelo no soportado: {provider}")


def build_sub_agents(db, knowledge) -> list[Agent]:
    """Carga sub-agentes desde workspace/agents/*.yaml."""
    agents = []
    agents_dir = WORKSPACE_DIR / "agents"
    if not agents_dir.exists():
        return agents

    for yaml_file in agents_dir.glob("*.yaml"):
        if yaml_file.name in ("teams.yaml",):
            continue

        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        agent_def = data.get("agent", {})
        if not agent_def:
            continue

        # Construir modelo del sub-agente
        model = build_model(agent_def.get("model", {"provider": "google", "id": "gemini-2.0-flash"}))

        # Construir tools del sub-agente
        agent_tools = []
        for tool_name in agent_def.get("tools", []):
            if tool_name == "duckduckgo":
                agent_tools.append(DuckDuckGoTools())
            elif tool_name == "crawl4ai":
                agent_tools.append(Crawl4aiTools(max_length=2000))
            elif tool_name == "reasoning":
                agent_tools.append(ReasoningTools(add_instructions=True))

        config = agent_def.get("config", {})

        agent = Agent(
            name=agent_def.get("name", "Sub Agent"),
            id=agent_def.get("id", yaml_file.stem),
            role=agent_def.get("role", ""),
            model=model,
            db=db,
            knowledge=knowledge,
            search_knowledge=True,
            tools=agent_tools,
            instructions=agent_def.get("instructions", []),
            tool_call_limit=config.get("tool_call_limit", 3),
            enable_user_memories=config.get("enable_user_memories", True),
            add_datetime_to_context=config.get("add_datetime_to_context", True),
            markdown=config.get("markdown", True),
        )
        agents.append(agent)
        logger.info(f"Sub-agente cargado: {agent.name} ({agent.id})")

    return agents


def load_workspace() -> dict[str, Any]:
    """
    Carga completa del workspace — retorna un dict con todos los objetos
    necesarios para construir el AgentOS.
    """
    # 1. Cargar configuración
    config = load_yaml("config.yaml")
    tools_config = load_yaml("tools.yaml")
    mcp_config = load_yaml("mcp.yaml")

    # 2. Construir DB
    db_config = config.get("database", {})
    db_url = build_db_url(db_config)
    db = build_db(db_url, db_config)

    # 3. Construir Knowledge
    vector_config = config.get("vector", {})
    knowledge = build_knowledge(db_url, db, vector_config, db_config)

    # 4. Construir Tools + MCP
    tools = build_tools(tools_config)
    mcp_tools = build_mcp_tools(mcp_config)

    # Agregar MCPTools de tipo streamable-http/sse directamente
    for mcp_tool in mcp_tools:
        if isinstance(mcp_tool, MCPTools):
            tools.append(mcp_tool)

    # 5. Cargar instrucciones
    instructions = load_instructions()

    # 6. Construir modelo
    model = build_model(config.get("model", {}))

    # 7. Cargar sub-agentes
    sub_agents = build_sub_agents(db, knowledge)

    # 8. Configuración de memoria
    mem_config = config.get("memory", {})

    # 9. Construir agente principal
    agent_config = config.get("agent", {})
    main_agent = Agent(
        name=agent_config.get("name", "AgnoBot"),
        id=agent_config.get("id", "agnobot-main"),
        description=agent_config.get("description", "Asistente personal multimodal"),
        model=model,
        db=db,
        knowledge=knowledge,
        search_knowledge=True if knowledge else False,
        tools=tools,
        instructions=instructions,
        enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
        enable_user_memories=mem_config.get("enable_user_memories", True),
        enable_session_summaries=mem_config.get("enable_session_summaries", True),
        add_history_to_context=True,
        num_history_runs=mem_config.get("num_history_runs", 5),
        add_datetime_to_context=True,
        markdown=True,
    )

    return {
        "config": config,
        "db_url": db_url,
        "db": db,
        "knowledge": knowledge,
        "main_agent": main_agent,
        "sub_agents": sub_agents,
        "mcp_config": mcp_config,
        "tools_config": tools_config,
    }
```

---

## 🚀 GATEWAY PRINCIPAL

### gateway.py

```python
"""
AgnoBot Gateway — Punto de entrada principal.
Lee el workspace/ y construye el AgentOS completo.
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agno.os import AgentOS
from agno.registry import Registry
from agno.utils.log import logger

from loader import load_workspace, load_yaml, WORKSPACE_DIR

# === Cargar workspace ===
ws = load_workspace()
config = ws["config"]
db = ws["db"]
main_agent = ws["main_agent"]
sub_agents = ws["sub_agents"]
knowledge = ws["knowledge"]

# === FastAPI base (para rutas custom como knowledge upload) ===
base_app = FastAPI()
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configurar según entorno
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Rutas de Knowledge (upload/list/delete) ===
if knowledge:
    from routes.knowledge_routes import create_knowledge_router
    knowledge_router = create_knowledge_router(knowledge)
    base_app.include_router(knowledge_router)

# === Interfaces (canales) ===
interfaces = []
channels = config.get("channels", ["whatsapp"])

if "whatsapp" in channels:
    from agno.os.interfaces.whatsapp import Whatsapp
    interfaces.append(Whatsapp(agent=main_agent))
    logger.info("✅ Canal WhatsApp habilitado")

if "slack" in channels:
    from agno.os.interfaces.slack import Slack
    interfaces.append(Slack(agent=main_agent))
    logger.info("✅ Canal Slack habilitado")

# Web (AG-UI) siempre disponible via os.agno.com
logger.info("✅ Canal Web disponible via os.agno.com (Control Plane)")

# === Registry para Studio ===
studio_config = config.get("studio", {})
registry = None
if studio_config.get("enabled", True) and not ws["db_url"].startswith("sqlite"):
    from agno.tools.duckduckgo import DuckDuckGoTools
    from agno.tools.crawl4ai import Crawl4aiTools
    registry = Registry(
        name="AgnoBot Registry",
        tools=[DuckDuckGoTools(), Crawl4aiTools()],
        models=[main_agent.model],
        dbs=[db],
    )
    logger.info("✅ Studio Registry configurado")

# === AgentOS ===
os_config = config.get("agentos", {})
all_agents = [main_agent] + sub_agents

agent_os = AgentOS(
    id=os_config.get("id", "agnobot-gateway"),
    name=os_config.get("name", "AgnoBot Platform"),
    agents=all_agents,
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

## 🧙 ONBOARDING CLI v3

### management/cli.py

```python
"""
CLI de Onboarding v3 — Genera el workspace/ completo.
Ejecutar: python -m management.cli
"""
import os
import sys
import yaml
from pathlib import Path


def run_onboarding():
    """Wizard interactivo que genera el workspace/ con toda la configuración."""
    workspace_dir = Path("workspace")

    print("\n═══════════════════════════════════════════")
    print("  🤖 AgnoBot — Setup Wizard v3")
    print("  Generador de Workspace Parametrizable")
    print("═══════════════════════════════════════════\n")

    # ──────────────────────────────────
    # PASO 1: Identidad del agente
    # ──────────────────────────────────
    agent_name = input("📋 Nombre del agente [AgnoBot]: ").strip() or "AgnoBot"
    agent_desc = input("   Descripción breve: ").strip() or "Asistente personal multimodal"

    print("\n📝 ¿Deseas escribir instrucciones personalizadas?")
    print("   [1] Usar instrucciones por defecto")
    print("   [2] Escribir instrucciones personalizadas")
    instr_choice = input("   Selección [1]: ").strip() or "1"

    custom_instructions = None
    if instr_choice == "2":
        print("   Escribe las instrucciones (termina con línea vacía):")
        lines = []
        while True:
            line = input("   ")
            if not line:
                break
            lines.append(line)
        custom_instructions = "\n".join(lines)

    # ──────────────────────────────────
    # PASO 2: Modelo de IA
    # ──────────────────────────────────
    print("\n🧠 Modelo de IA:")
    print("  [1] Gemini 2.0 Flash (Google — multimodal, recomendado)")
    print("  [2] Claude Sonnet 4 (Anthropic)")
    print("  [3] GPT-4.1 (OpenAI)")
    print("  [4] GPT-5-mini (OpenAI)")
    model_choice = input("  Selección [1]: ").strip() or "1"

    model_map = {
        "1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
        "2": ("anthropic", "claude-sonnet-4-0", "ANTHROPIC_API_KEY"),
        "3": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
        "4": ("openai", "gpt-5-mini", "OPENAI_API_KEY"),
    }
    provider, model_id, key_name = model_map.get(model_choice, model_map["1"])

    api_key = input(f"  → {key_name}: ").strip()

    # ──────────────────────────────────
    # PASO 3: Base de datos
    # ──────────────────────────────────
    print("\n💾 Base de datos:")
    print("  [1] Supabase (PostgreSQL managed — recomendado)")
    print("  [2] PostgreSQL local (Docker)")
    print("  [3] SQLite (solo desarrollo, sin RAG)")
    db_choice = input("  Selección [1]: ").strip() or "1"

    db_type = {"1": "supabase", "2": "local", "3": "sqlite"}.get(db_choice, "supabase")
    db_vars = {}

    if db_type == "supabase":
        db_vars["DB_HOST"] = input("  → DB Host (Supabase pooler): ").strip()
        db_vars["DB_PORT"] = input("  → DB Port [5432]: ").strip() or "5432"
        db_vars["DB_USER"] = input("  → DB User: ").strip()
        db_vars["DB_PASSWORD"] = input("  → DB Password: ").strip()
        db_vars["DB_NAME"] = input("  → DB Name [postgres]: ").strip() or "postgres"
        db_vars["DB_SSLMODE"] = "require"
    elif db_type == "local":
        db_vars["DB_HOST"] = "localhost"
        db_vars["DB_PORT"] = "5532"
        db_vars["DB_USER"] = "ai"
        db_vars["DB_PASSWORD"] = "ai"
        db_vars["DB_NAME"] = "ai"
        db_vars["DB_SSLMODE"] = "prefer"
        print("  ℹ️  Ejecuta: docker-compose up -d db")

    # ──────────────────────────────────
    # PASO 4: Canales
    # ──────────────────────────────────
    print("\n📡 Canales de comunicación:")
    print("  [1] WhatsApp")
    print("  [2] Slack")
    print("  [3] WhatsApp + Slack")
    print("  ℹ️  Web (Control Plane) siempre disponible")
    channel_choice = input("  Selección [1]: ").strip() or "1"
    channels = {
        "1": ["whatsapp"], "2": ["slack"], "3": ["whatsapp", "slack"]
    }.get(channel_choice, ["whatsapp"])

    whatsapp_vars = {}
    if "whatsapp" in channels:
        print("\n📱 Configuración WhatsApp (Meta Business API):")
        whatsapp_vars["WHATSAPP_ACCESS_TOKEN"] = input("  → Access Token: ").strip()
        whatsapp_vars["WHATSAPP_PHONE_NUMBER_ID"] = input("  → Phone Number ID: ").strip()
        whatsapp_vars["WHATSAPP_VERIFY_TOKEN"] = input("  → Verify Token: ").strip()
        whatsapp_vars["WHATSAPP_WEBHOOK_URL"] = input("  → Webhook URL: ").strip()

    slack_vars = {}
    if "slack" in channels:
        print("\n💬 Configuración Slack:")
        slack_vars["SLACK_TOKEN"] = input("  → Bot Token: ").strip()

    # ──────────────────────────────────
    # PASO 5: Tools
    # ──────────────────────────────────
    print("\n🔧 Herramientas adicionales:")
    email_enabled = input("  ¿Activar Gmail? [s/N]: ").strip().lower() == "s"
    tavily_enabled = input("  ¿Activar Tavily (búsqueda web)? [s/N]: ").strip().lower() == "s"
    
    email_vars = {}
    if email_enabled:
        email_vars["GMAIL_SENDER"] = input("  → Email remitente: ").strip()
        email_vars["GMAIL_PASSKEY"] = input("  → App password: ").strip()
        email_vars["GMAIL_RECEIVER"] = input("  → Email receptor default: ").strip()

    tavily_key = ""
    if tavily_enabled:
        tavily_key = input("  → TAVILY_API_KEY: ").strip()

    # ──────────────────────────────────
    # PASO 6: Embeddings (para RAG)
    # ──────────────────────────────────
    openai_key = ""
    if db_type != "sqlite":
        print("\n🔢 Embeddings (requerido para RAG):")
        if key_name == "OPENAI_API_KEY":
            openai_key = api_key  # Ya lo tiene
            print(f"  ✅ Usando {key_name} para embeddings")
        else:
            openai_key = input("  → OPENAI_API_KEY (para text-embedding-3-small): ").strip()

    # ──────────────────────────────────
    # GENERAR WORKSPACE
    # ──────────────────────────────────
    print("\n⏳ Generando workspace...")

    # Crear directorios
    for d in ["", "knowledge/docs", "agents"]:
        (workspace_dir / d).mkdir(parents=True, exist_ok=True)

    # config.yaml
    config = {
        "agent": {
            "name": agent_name,
            "id": "agnobot-main",
            "description": agent_desc,
        },
        "model": {"provider": provider, "id": model_id},
        "database": {
            "type": db_type,
            "knowledge_table": "agnobot_knowledge_contents",
            "vector_table": "agnobot_knowledge_vectors",
        },
        "vector": {
            "search_type": "hybrid",
            "embedder": "text-embedding-3-small",
            "max_results": 5,
        },
        "channels": channels,
        "memory": {
            "enable_agentic_memory": True,
            "enable_user_memories": True,
            "enable_session_summaries": True,
            "num_history_runs": 5,
        },
        "agentos": {
            "id": "agnobot-gateway",
            "name": f"{agent_name} Platform",
            "port": 8000,
            "tracing": True,
            "enable_mcp_server": True,
        },
        "studio": {"enabled": db_type != "sqlite"},
    }
    _write_yaml(workspace_dir / "config.yaml", config)

    # instructions.md
    instructions_content = custom_instructions or f"""# Instrucciones de {agent_name}

Eres **{agent_name}**, un asistente personal multimodal autónomo.

## Personalidad
- Amable, eficiente y proactivo
- Respondes en el idioma del usuario
- Usas formato Markdown cuando es apropiado

## Capacidades
- Puedes analizar imágenes, videos y audios enviados
- Buscas en la web cuando necesitas información actualizada
- Usas la base de conocimiento para responder sobre documentos cargados
- Recuerdas información importante del usuario entre sesiones
- Puedes consultar la documentación de Agno para resolver dudas técnicas

## Reglas
- Si no estás seguro de algo, búscalo antes de responder
- Siempre cita tus fuentes cuando uses información de la web
- Si el usuario carga documentos, confírmaselo y ofrece analizarlos
"""
    (workspace_dir / "instructions.md").write_text(instructions_content, encoding="utf-8")

    # tools.yaml
    tools = {
        "builtin": [
            {"name": "duckduckgo", "enabled": True, "config": {}},
            {"name": "crawl4ai", "enabled": True, "config": {"max_length": 2000}},
            {"name": "reasoning", "enabled": True, "config": {"add_instructions": True}},
        ],
        "optional": [
            {
                "name": "email", "enabled": email_enabled,
                "config": {
                    "sender_email": "${GMAIL_SENDER}",
                    "sender_name": agent_name,
                    "sender_passkey": "${GMAIL_PASSKEY}",
                    "receiver_email": "${GMAIL_RECEIVER}",
                }
            },
            {"name": "tavily", "enabled": tavily_enabled},
            {"name": "spotify", "enabled": False},
            {"name": "shell", "enabled": False},
        ],
        "custom": [],
    }
    _write_yaml(workspace_dir / "tools.yaml", tools)

    # mcp.yaml
    mcp = {
        "servers": [
            {
                "name": "agno_docs",
                "enabled": True,
                "transport": "streamable-http",
                "url": "https://docs.agno.com/mcp",
            },
        ],
        "expose": {"enabled": True},
    }
    _write_yaml(workspace_dir / "mcp.yaml", mcp)

    # agents/research_agent.yaml
    research = {
        "agent": {
            "name": "Research Agent",
            "id": "research-agent",
            "role": "Realiza búsquedas web profundas y sintetiza información",
            "model": {"provider": provider, "id": model_id},
            "tools": ["duckduckgo", "crawl4ai"],
            "instructions": [
                "Eres un agente especializado en investigación.",
                "Busca en la web y sintetiza información.",
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

    # agents/teams.yaml
    _write_yaml(workspace_dir / "agents" / "teams.yaml", {"teams": []})

    # schedules.yaml
    _write_yaml(workspace_dir / "schedules.yaml", {"schedules": []})

    # knowledge/urls.yaml
    _write_yaml(workspace_dir / "knowledge" / "urls.yaml", {"urls": []})

    # .env
    env_lines = [
        "# ═══════════════════════════════════",
        f"# AgnoBot — Variables de Entorno",
        "# ═══════════════════════════════════",
        "",
        "# === API Keys ===",
        f"{key_name}={api_key}",
    ]
    if openai_key and key_name != "OPENAI_API_KEY":
        env_lines.append(f"OPENAI_API_KEY={openai_key}")
    if tavily_key:
        env_lines.append(f"TAVILY_API_KEY={tavily_key}")

    env_lines.extend(["", "# === Base de datos ==="])
    for k, v in db_vars.items():
        env_lines.append(f"{k}={v}")

    if whatsapp_vars:
        env_lines.extend(["", "# === WhatsApp ==="])
        for k, v in whatsapp_vars.items():
            env_lines.append(f"{k}={v}")

    if slack_vars:
        env_lines.extend(["", "# === Slack ==="])
        for k, v in slack_vars.items():
            env_lines.append(f"{k}={v}")

    if email_vars:
        env_lines.extend(["", "# === Gmail ==="])
        for k, v in email_vars.items():
            env_lines.append(f"{k}={v}")

    env_lines.extend(["", "# === Seguridad ===", "# OS_SECURITY_KEY=genera_una_clave_con_openssl_rand_hex_32"])

    Path(".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # ──────────────────────────────────
    # RESUMEN FINAL
    # ──────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  ✅ Workspace generado exitosamente!")
    print("═══════════════════════════════════════════")
    print(f"  📁 workspace/config.yaml    — Configuración central")
    print(f"  📝 workspace/instructions.md — Personalidad del agente")
    print(f"  🔧 workspace/tools.yaml     — Herramientas")
    print(f"  🔌 workspace/mcp.yaml       — Servidores MCP")
    print(f"  📚 workspace/knowledge/     — Documentos RAG")
    print(f"  🤖 workspace/agents/        — Sub-agentes")
    print(f"  🔐 .env                     — Secretos")
    print()

    if db_type == "local":
        print("  📦 Paso 1: docker-compose up -d db")
    print(f"  🚀 Paso {'2' if db_type == 'local' else '1'}: python gateway.py")
    print(f"  🌐 Web UI: os.agno.com → Add OS → Local → http://localhost:8000")

    if "whatsapp" in channels:
        print(f"  📱 WhatsApp: Configura webhook en Meta → {whatsapp_vars.get('WHATSAPP_WEBHOOK_URL', 'tu-url')}")

    print("═══════════════════════════════════════════\n")


def _write_yaml(path: Path, data: dict):
    """Escribe un dict como YAML."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    run_onboarding()
```

---

## 📊 PLAN DE FASES ACTUALIZADO

### FASE 1: MVP — Workspace + PgVector + WhatsApp (Semana 1-2)

**Objetivo:** Workspace funcional con agente multimodal en WhatsApp, persistencia Supabase/PgVector, MCP a docs de Agno.

**Entregables:**
1. `loader.py` — Carga dinámica del workspace
2. `gateway.py` — Gateway que lee workspace y arranca AgentOS
3. `workspace/` — Estructura completa con config.yaml, instructions.md, tools.yaml, mcp.yaml
4. PgVector/Supabase configurado y funcionando
5. Canal WhatsApp operativo
6. MCP a `docs.agno.com` habilitado (autonomía del agente)
7. Knowledge routes (upload/list/delete documentos)

**Setup:**
```bash
mkdir agnobot && cd agnobot
python -m venv .venv && source .venv/bin/activate

uv pip install -U "agno[os]" \
    openai anthropic google-genai \
    crawl4ai duckduckgo-search \
    psycopg[binary] sqlalchemy pgvector \
    pyyaml python-dotenv mcp
```

---

### FASE 2: Onboarding CLI + Admin (Semana 2-3)

**Objetivo:** CLI que genera workspace/ completo + admin via AgentOSClient.

**Entregables:**
1. `management/cli.py` — Wizard interactivo
2. `management/admin.py` — Admin con AgentOSClient
3. Generación automática de .env, config.yaml, instructions.md
4. Validación de configuración al arrancar

**Admin via AgentOSClient:**
```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:8000")

# Verificar estado
config = await client.aget_config()

# Listar sesiones
sessions = await client.get_sessions(user_id="+593991234567")

# Ver memorias
memories = await client.get_memories(user_id="+593991234567")

# Ejecutar agente
result = await client.run_agent(agent_id="agnobot-main", message="Hola!")
```

---

### FASE 3: Multi-Canal + Studio + Sub-Agentes (Semana 3-4)

**Objetivo:** Slack + Web + Studio visual + carga dinámica de sub-agentes.

**Entregables:**
1. Canal Slack habilitado via `workspace/config.yaml`
2. Canal Web via AG-UI / Control Plane (os.agno.com)
3. Studio habilitado con Registry
4. Sub-agentes definidos en `workspace/agents/*.yaml`
5. Teams definidos en `workspace/agents/teams.yaml`

**Studio Setup:**
1. Abrir **os.agno.com** → Iniciar sesión
2. **Add new OS** → **Local** → `http://localhost:8000`
3. Studio detecta automáticamente el Registry y los agentes
4. Crear/editar agentes visualmente → Draft → Test → Publish

---

### FASE 4: Remote Execution + MCP Avanzado (Semana 4-5)

**Objetivo:** Agentes distribuidos + MCP servers configurables.

**Entregables:**
1. Remote Agents definidos en workspace (execution.type = "remote")
2. Gateway Pattern con múltiples AgentOS
3. MCP servers configurables via `workspace/mcp.yaml`
4. Agente puede consultar Supabase via MCP

**Remote Agent Pattern:**
```python
from agno.agent import Agent, RemoteAgent
from agno.os import AgentOS

gateway = AgentOS(
    id="agnobot-gateway",
    agents=[
        main_agent,
        RemoteAgent(
            base_url="http://research-server:7778",
            agent_id="research-agent",
        ),
    ],
)
```

**MCP a Supabase (gestión de DB por el propio agente):**
```yaml
# workspace/mcp.yaml
servers:
  - name: supabase
    enabled: true
    transport: "stdio"
    command: "npx -y @supabase/mcp-server-supabase@latest --access-token=${SUPABASE_ACCESS_TOKEN}"
```

---

### FASE 5: Scheduler + RAG Avanzado (Semana 5-6)

**Objetivo:** Tareas programadas + ingesta robusta de documentos.

**Entregables:**
1. Scheduler habilitado en AgentOS
2. Schedules definidos en `workspace/schedules.yaml`
3. Ingesta de documentos desde `workspace/knowledge/docs/`
4. Ingesta de URLs desde `workspace/knowledge/urls.yaml`
5. Knowledge routes con filtros por `user_id` y metadata

---

### FASE 6: Seguridad + Deploy Producción (Semana 6-7)

**Objetivo:** JWT/RBAC + Docker multi-servicio + monitoreo.

**Entregables:**
1. JWT/RBAC con `AuthorizationConfig`
2. `docker-compose.yml` multi-servicio (gateway + research + db)
3. Dockerfile optimizado para Cloud Run
4. Monitoreo via Control Plane (trazas, sesiones, memorias)
5. MCP Server habilitado para integraciones externas

---

## ✅ CHECKLIST v3

| # | Capacidad | Implementación | Fase |
|---|-----------|---------------|------|
| 1 | Multimodal (imagen, video, audio) | Gemini / modelo configurable | F1 |
| 2 | Memoria persistente (agentic) | `enable_agentic_memory=True` + PostgresDb | F1 |
| 3 | Sesiones automáticas | Por teléfono (WA) / usuario (Slack/Web) | F1 |
| 4 | Historial contextual | `add_history_to_context=True` | F1 |
| 5 | **RAG con PgVector/Supabase** | `PgVector` + `SearchType.hybrid` + `OpenAIEmbedder` | F1 |
| 6 | Búsqueda web | `DuckDuckGoTools()` | F1 |
| 7 | Web scraping | `Crawl4aiTools()` | F1 |
| 8 | **Workspace parametrizable** | `workspace/` con YAML + Markdown | F1 |
| 9 | **Instructions en archivo** | `workspace/instructions.md` | F1 |
| 10 | **Tools configurables** | `workspace/tools.yaml` | F1 |
| 11 | **MCP configurables** | `workspace/mcp.yaml` | F1 |
| 12 | **Acceso a docs Agno (MCP)** | `MCPTools(url="https://docs.agno.com/mcp")` | F1 |
| 13 | WhatsApp | `Whatsapp(agent=agent)` | F1 |
| 14 | **Onboarding CLI → Workspace** | Genera workspace/ completo | F2 |
| 15 | Admin programático | `AgentOSClient` | F2 |
| 16 | Slack | `Slack(agent=agent)` | F3 |
| 17 | **Web (AG-UI / Control Plane)** | os.agno.com + MCP Server | F3 |
| 18 | Studio (editor visual) | `Registry` + os.agno.com | F3 |
| 19 | **Sub-agentes en YAML** | `workspace/agents/*.yaml` | F3 |
| 20 | **Teams configurables** | `workspace/agents/teams.yaml` | F3 |
| 21 | Remote Execution | `RemoteAgent` + Gateway | F4 |
| 22 | **MCP Supabase (auto-gestión)** | Agente gestiona su propia DB | F4 |
| 23 | A2A Protocol | `A2AClient` inter-framework | F4 |
| 24 | Scheduler | `workspace/schedules.yaml` | F5 |
| 25 | Knowledge upload/list/delete | Endpoints REST + PgVector | F5 |
| 26 | JWT/RBAC Security | `AuthorizationConfig` | F6 |
| 27 | Docker multi-servicio | `docker-compose.yml` | F6 |
| 28 | Monitoreo (trazas) | Control Plane + tracing | F6 |

---

## 📋 VARIABLES DE ENTORNO (.env)

```bash
# ═══════════════════════════════════════
# AgnoBot — Variables de Entorno
# ═══════════════════════════════════════

# === API Keys ===
GOOGLE_API_KEY=...            # Gemini (si es el modelo principal)
OPENAI_API_KEY=...            # Embeddings + modelo opcional
ANTHROPIC_API_KEY=...         # Claude (si es el modelo principal)
TAVILY_API_KEY=...            # Búsqueda web Tavily (opcional)

# === Base de Datos (Supabase) ===
DB_HOST=aws-0-us-west-1.pooler.supabase.com
DB_PORT=5432
DB_USER=postgres.tu_tenant_id
DB_PASSWORD=tu_password_seguro
DB_NAME=postgres
DB_SSLMODE=require

# === WhatsApp (Meta Business API) ===
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_WEBHOOK_URL=https://tu-dominio.com/webhook

# === Slack (opcional) ===
# SLACK_TOKEN=xoxb-...

# === Gmail (opcional) ===
# GMAIL_SENDER=tu_email@gmail.com
# GMAIL_PASSKEY=tu_app_password
# GMAIL_RECEIVER=default_receptor@email.com

# === MCP (opcional) ===
# SUPABASE_ACCESS_TOKEN=...  # Para MCP Supabase
# GITHUB_TOKEN=...           # Para MCP GitHub

# === Seguridad ===
# OS_SECURITY_KEY=genera_con_openssl_rand_hex_32

# === Entorno ===
APP_ENV=development
```

---

## 🐳 Docker Compose

```yaml
version: "3.8"
services:
  # PostgreSQL con pgvector (solo desarrollo local)
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

  # Gateway principal
  gateway:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
    volumes:
      - ./workspace:/app/workspace          # Workspace parametrizable
      - ./workspace/knowledge/docs:/app/workspace/knowledge/docs  # Documentos RAG

  # Servidor de investigación (remoto, opcional)
  # research:
  #   build: .
  #   command: python research_server.py
  #   ports:
  #     - "7778:7778"
  #   env_file: .env
  #   depends_on:
  #     - db

volumes:
  pgdata:
```

---

## 🔑 DIFERENCIAS CLAVE vs PLAN v2

| Aspecto | Plan v2 | Plan v3 |
|---------|---------|---------|
| Vector DB | LanceDB (archivos locales) | **PgVector/Supabase** (PostgreSQL unificado) |
| Configuración | Hardcoded en Python | **Workspace declarativo** (YAML + MD) |
| Instrucciones | Inline en código | **workspace/instructions.md** (editable) |
| Tools | Lista fija en gateway.py | **workspace/tools.yaml** (togglable) |
| MCP | No configurado | **workspace/mcp.yaml** + acceso a docs Agno |
| Sub-agentes | Manual en código | **workspace/agents/*.yaml** (declarativo) |
| Teams | No implementado | **workspace/agents/teams.yaml** |
| Onboarding | Genera .env solamente | **Genera workspace/ completo** |
| Autonomía | Sin acceso a docs | **MCP a docs.agno.com** — agente autoayuda |
| Canales | WA + Slack | **WA + Slack + Web** (AG-UI/Control Plane) |
| DB Config | Un solo string hardcoded | **Parametrizable** (Supabase/local/SQLite) |
| Escalabilidad | Monolítico | **Remote Agents** + Gateway Pattern |

---

## 📚 DOCUMENTACIÓN DE REFERENCIA

| Recurso | URL |
|---------|-----|
| Agno Docs (completa) | https://docs.agno.com |
| Agno LLMs.txt (índice) | https://docs.agno.com/llms.txt |
| PgVector | https://docs.agno.com/knowledge/vector-stores/pgvector/overview |
| Hybrid Search | https://docs.agno.com/knowledge/concepts/search-and-retrieval/hybrid-search |
| MCPTools | https://docs.agno.com/tools/mcp/overview |
| MCPTools en AgentOS | https://docs.agno.com/agent-os/mcp/tools |
| AgentOS como MCP Server | https://docs.agno.com/agent-os/mcp/mcp |
| WhatsApp Interface | https://docs.agno.com/agent-os/interfaces/whatsapp/introduction |
| Slack Interface | https://docs.agno.com/agent-os/interfaces/slack/introduction |
| AG-UI (Web) | https://docs.agno.com/agent-os/interfaces/ag-ui/introduction |
| Studio | https://docs.agno.com/agent-os/studio/introduction |
| Remote Execution | https://docs.agno.com/agent-os/remote-execution/overview |
| AgentOSClient | https://docs.agno.com/agent-os/client/agentos-client |
| Scheduler | https://docs.agno.com/agent-os/scheduler/overview |
| RBAC / Security | https://docs.agno.com/agent-os/security/rbac |
| Registry | https://docs.agno.com/agent-os/studio/introduction |
| Teams | https://docs.agno.com/teams |
| Workflows | https://docs.agno.com/workflows |
| AgentOS Demo | https://docs.agno.com/examples/agent-os/demo |
| Supabase MCP | https://docs.agno.com/tools/mcp/usage/supabase |

---

*Plan v3 generado el 25 de marzo de 2026*
*Incluye: PgVector/Supabase, Workspace Parametrizable, MCP Configurable, AG-UI*
*Basado en documentación oficial de Agno + implementación Veredix*
