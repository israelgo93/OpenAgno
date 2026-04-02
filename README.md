# OpenAgno

[![PyPI version](https://badge.fury.io/py/openagno.svg)](https://pypi.org/project/openagno/)

OpenAgno is a declarative agent platform built on **Agno**. It packages a CLI, an AgentOS/FastAPI runtime, reusable workspace templates, MCP support, channel integrations, PgVector-backed knowledge, and tenant-aware provisioning for multi-tenant deployments.

## What exists today

- packaged CLI: `openagno`
- declarative `workspace/` with YAML + Markdown
- AgentOS runtime with admin, knowledge, and channel routes
- packaged templates for common assistants
- WhatsApp, Slack, Telegram, AG-UI, and A2A support
- PgVector-backed knowledge on PostgreSQL or Supabase
- public docs with MCP and `llms.txt`
- tenant provisioning routes and tenant-scoped agent runs

## Installation

```bash
pip install openagno
```

Or install from source:

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For contributors, builds, tests, and protocol extras:

```bash
pip install -e '.[dev,protocols]'
```

## Quickstart

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

## Tenant provisioning

OpenAgno now includes tenant-aware routes:

- `POST /tenants`
- `GET /tenants/{tenant_id}`
- `PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`

The runtime uses Agno-native isolation with `Knowledge(..., isolate_vector_search=True)` and `knowledge_filters={"linked_to": "<tenant>"}`.

## Knowledge and PgVector

OpenAgno keeps knowledge in a PgVector-backed PostgreSQL or Supabase setup and exposes a REST surface for upload, listing, deletion, and semantic search through `/knowledge/*`.

If you are deploying the OSS runtime for Cloud, validate both:

- database connectivity for embeddings and vector search
- tenant-aware filters for isolated knowledge retrieval

## IDE and AI integration

- MCP: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- config exports in `ide-configs/`
- project skill in `.agents/skills/openagno/SKILL.md`

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

Spanish Mintlify pages are available under `docs/es/`.

## License

Apache 2.0.
