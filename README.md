<p align="center">
  <h1 align="center">OpenAgno</h1>
  <p align="center">
    <strong>Plataforma de agentes IA multimodal con workspace declarativo</strong>
  </p>
  <p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://docs.agno.com"><img src="https://img.shields.io/badge/Agno-Framework-6366F1?style=flat-square" alt="Agno"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square" alt="License"></a>
    <a href="https://github.com/israelgo93/OpenAgno"><img src="https://img.shields.io/badge/Status-MVP-orange?style=flat-square" alt="Status"></a>
  </p>
</p>

---

## Que es OpenAgno?

OpenAgno es una plataforma open-source para construir agentes IA autonomos y multimodales. Combina un **workspace declarativo** (YAML + Markdown) con **persistencia unificada** en PostgreSQL/Supabase, permitiendo configurar agentes completos sin escribir codigo.

Construido sobre [Agno Framework](https://docs.agno.com), OpenAgno ofrece:

- **Configuracion sin codigo** — Define tu agente con archivos YAML y Markdown
- **Multimodal** — Procesa texto, imagenes, video y audio
- **Memoria persistente** — Recuerda contexto entre sesiones con PostgresDb
- **RAG hibrido** — Busqueda semantica + keyword con PgVector
- **Multi-canal** — WhatsApp, Slack y Web desde un unico gateway
- **Autonomia via MCP** — El agente consulta la documentacion de Agno por si mismo

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
     +---------+------------+
               |
     +---------v------------+
     |   Agente Principal    |
     |   - Gemini/Claude/GPT |
     |   - Tools (DuckDuckGo, Crawl4AI, Reasoning)
     |   - MCP (docs.agno.com)
     |   - Memoria Agentic   |
     +---------+-------------+
               |
     +---------v-------------+
     |   PostgreSQL/Supabase  |
     |   - Sesiones           |
     |   - Memorias           |
     |   - Knowledge (PgVector)|
     |   - Vectores (Hybrid)  |
     +------------------------+
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

```bash
cp .env.example .env
# Editar .env con tus API keys y credenciales de base de datos
```

### 3. Ejecutar

```bash
# Opcion A: Con Supabase (produccion)
python gateway.py

# Opcion B: Con PostgreSQL local (desarrollo)
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
| `workspace/agents/` | Sub-agentes y teams |
| `workspace/schedules.yaml` | Tareas programadas |

Modifica cualquier archivo y reinicia para aplicar los cambios.

---

## Features

| Feature | Descripcion |
|---------|-------------|
| Multimodal | Procesa imagenes, video, audio y texto |
| Workspace declarativo | Configura con YAML y Markdown |
| PgVector + Hybrid Search | Busqueda semantica y por keywords |
| Memoria Agentic | Recuerda informacion entre sesiones |
| MCP a docs.agno.com | El agente consulta su propia documentacion |
| WhatsApp | Canal via Meta Business API |
| Knowledge Base | Upload, busqueda y eliminacion de documentos |
| Multi-modelo | Gemini, Claude, GPT configurables |
| Studio | Editor visual via os.agno.com |

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
  gateway.py               # Punto de entrada AgentOS
  loader.py                # Motor de carga del workspace
  workspace/
    config.yaml            # Configuracion central
    instructions.md        # Personalidad del agente
    tools.yaml             # Herramientas
    mcp.yaml               # Servidores MCP
    knowledge/
      urls.yaml            # URLs para ingestion
    agents/
      teams.yaml           # Equipos multi-agente
    schedules.yaml         # Tareas programadas
  routes/
    knowledge_routes.py    # Endpoints REST para RAG
  docs_plan/
    plan_agno_agent_platform.md
  .env.example             # Template de variables
  requirements.txt         # Dependencias
  docker-compose.yml       # PostgreSQL pgvector local
```

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `POST` | `/knowledge/upload` | Subir documento a la Knowledge Base |
| `GET` | `/knowledge/list` | Listar documentos |
| `DELETE` | `/knowledge/{doc_id}` | Eliminar documento |
| `POST` | `/knowledge/search` | Busqueda semantica |
| `GET` | `/whatsapp/status` | Estado del webhook WhatsApp |
| `POST` | `/whatsapp/webhook` | Webhook para mensajes WhatsApp |

---

## Documentacion de Referencia

| Recurso | Enlace |
|---------|--------|
| Agno Docs | [docs.agno.com](https://docs.agno.com) |
| PgVector | [Vector Stores](https://docs.agno.com/knowledge/vector-stores/pgvector/overview) |
| Hybrid Search | [Busqueda Hibrida](https://docs.agno.com/knowledge/concepts/search-and-retrieval/hybrid-search) |
| MCPTools | [MCP Overview](https://docs.agno.com/tools/mcp/overview) |
| WhatsApp | [WhatsApp Interface](https://docs.agno.com/agent-os/interfaces/whatsapp/introduction) |
| AgentOS | [Demo](https://docs.agno.com/examples/agent-os/demo) |

---

## Licencia

Este proyecto esta licenciado bajo [Apache License 2.0](LICENSE).
