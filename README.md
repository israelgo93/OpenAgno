# OpenAgno

OpenAgno is a declarative agent platform built on **Agno**. It packages a CLI, an AgentOS/FastAPI runtime, reusable workspace templates, MCP support, channel integrations, vector knowledge with PgVector, and a tenant-aware provisioning layer for multi-tenant deployments.

OpenAgno es una plataforma declarativa para agentes construida sobre **Agno**. Incluye una CLI empaquetada, runtime AgentOS/FastAPI, templates reutilizables, soporte MCP, canales, knowledge vectorial con PgVector y una capa tenant-aware para despliegues multi-tenant.

## English

### What exists today

- packaged CLI: `openagno`
- declarative `workspace/` with YAML + Markdown
- AgentOS runtime with admin, knowledge, and channel routes
- packaged templates for common assistants
- WhatsApp, Slack, Telegram, AG-UI, and A2A support
- PgVector-backed knowledge on PostgreSQL or Supabase
- public docs with MCP and `llms.txt`
- tenant provisioning routes and tenant-scoped agent runs

### Installation

If `openagno` is already available in your Python index, use:

```bash
pip install openagno
```

If not, install from source:

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For contributors, builds, tests, and protocol extras:

```bash
pip install -e '.[dev,protocols]'
```

### Quickstart

```bash
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground
```

Health check:

```bash
curl http://127.0.0.1:8000/admin/health
```

### Tenant provisioning

OpenAgno now includes tenant-aware routes:

- `POST /tenants`
- `GET /tenants/{tenant_id}`
- `PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`

The runtime uses Agno-native isolation with `Knowledge(..., isolate_vector_search=True)` and `knowledge_filters={"linked_to": "<tenant>"}`.

### IDE and AI integration

- MCP: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- config exports in `ide-configs/`
- project skill in `.agents/skills/openagno/SKILL.md`

## Español

### Qué existe hoy

- CLI empaquetada: `openagno`
- `workspace/` declarativo en YAML + Markdown
- runtime AgentOS con rutas admin, knowledge y canales
- templates empaquetados para asistentes comunes
- soporte para WhatsApp, Slack, Telegram, AG-UI y A2A
- knowledge con PgVector sobre PostgreSQL o Supabase
- documentación pública con MCP y `llms.txt`
- rutas de provisioning tenant-aware y ejecuciones por tenant

### Instalación

Si `openagno` ya existe en tu índice Python, usa:

```bash
pip install openagno
```

Si todavía no aparece en tu índice o mirror, instala desde el repositorio:

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Para contributors, builds, tests y extras de protocolos:

```bash
pip install -e '.[dev,protocols]'
```

### Inicio rápido

```bash
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground
```

Chequeo de salud:

```bash
curl http://127.0.0.1:8000/admin/health
```

### Aprovisionamiento multi-tenant

OpenAgno ahora incluye rutas tenant-aware:

- `POST /tenants`
- `GET /tenants/{tenant_id}`
- `PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`

El runtime usa aislamiento nativo de Agno con `Knowledge(..., isolate_vector_search=True)` y `knowledge_filters={"linked_to": "<tenant>"}`.

### Integración con IDEs y asistentes

- MCP: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- exports en `ide-configs/`
- skill local en `.agents/skills/openagno/SKILL.md`

## Docs

Local preview:

```bash
cd docs
npm install
npm run dev
```

Validation:

```bash
cd docs
npm run validate
npm run broken-links
```

## License

Apache 2.0.
