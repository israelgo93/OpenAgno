---
name: openagno
description: Use OpenAgno when building or operating Agno-based agents with declarative workspaces, multi-tenant runtime, channel integrations, PgVector knowledge, MCP, or packaged CLI deploys.
---

# OpenAgno skill

OpenAgno wraps Agno into a declarative workspace, an operational FastAPI + AgentOS runtime, a packaged CLI, and a set of channel integrations (WhatsApp Cloud API single-tenant or multi-tenant, WhatsApp QR, Slack, Telegram, AG-UI, A2A).

This skill is IDE-agnostic. It works the same way whether you are in Claude Code, Cursor, VS Code, Windsurf, Aider, or Zed: the agent reads this file, cross-references `AGENTS.md` at the repo root, and uses the MCP server at `https://docs.openagno.com/mcp` for authoritative documentation.

## When to apply this skill

- The user asks for "a chat agent on WhatsApp", "a custom agent with my docs", or similar.
- The user wants to deploy an agent behind a channel (WhatsApp, Slack, Telegram).
- The user mentions Agno and wants a declarative setup instead of hand-rolled scripts.
- The user is troubleshooting `gateway.py`, `workspace/config.yaml`, `/admin/health`, `/tenants/*`, or `/whatsapp-*` routes.

## Core rules

- Use Agno-native primitives first. Do not build a custom agent orchestration when `Agent`, `Team`, `Knowledge`, or `Tools` already cover the case.
- Prefer `Knowledge(..., isolate_vector_search=True)` plus `knowledge_filters` over custom vector-search hacks.
- Keep secrets in `.env` and reference them from YAML with `${VAR}` syntax.
- Run `openagno validate` before `openagno start`.
- Treat `workspace/` as the source of truth for runtime behavior. `workspaces/` is runtime-generated and never committed.
- For multi-tenant changes, always go through `TenantLoader.get_or_load(slug)`; do not build ad-hoc workspace loaders.

## Prerequisites

- Python 3.10+
- PostgreSQL with `pgvector` (local container `pgvector/pgvector:pg17`, or a hosted Postgres like Supabase with the extension enabled)
- An LLM API key: `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or AWS Bedrock credentials
- Optional: Node 20+ if you plan to enable the WhatsApp QR bridge (`bridges/whatsapp-qr/`)
- Optional: `CHANNEL_SECRETS_KEY` (32 bytes base64) if you plan to serve multi-tenant WhatsApp Cloud API from this runtime behind an external control plane

## Install from scratch

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,protocols]'
cp .env.example .env        # then edit values
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground # stop with Ctrl+C
```

The CLI wizard (`openagno init`) collects values for `.env` interactively. For non-interactive environments (CI, Dockerfile), fill `.env` directly and run `openagno validate` before `openagno start`.

## Common commands

Daily workflow:

- `openagno validate` &mdash; checks `.env`, templates, channel requirements
- `openagno start --foreground` &mdash; run the runtime and see logs
- `openagno start` &mdash; run under the local supervisor
- `openagno stop`, `openagno status`, `openagno logs --follow`
- `openagno create agent "<name>"` &mdash; add a sub-agent YAML under `workspace/agents/`
- `openagno add slack`, `openagno add telegram`, `openagno add whatsapp --mode cloud_api`, `openagno add agui`, `openagno add a2a`
- `openagno deploy docker` &mdash; start the Postgres + gateway stack with Docker Compose
- `openagno templates list` &mdash; show packaged starter templates

Tests and docs:

- `pytest -q`
- `ruff check .`
- `python -m build`
- `cd docs && npm install && npm run validate && npm run broken-links`

## Key paths

- `workspace/config.yaml` &mdash; main runtime configuration (providers, channels, knowledge, scheduler, integrations)
- `workspace/instructions.md` &mdash; system prompt for the main agent
- `workspace/self_knowledge.md` &mdash; self-knowledge content the agent uses to answer "who are you"
- `workspace/tools.yaml` &mdash; built-in and optional tools
- `workspace/mcp.yaml` &mdash; external MCP servers
- `workspace/knowledge/urls.yaml` &mdash; URLs to ingest
- `workspace/agents/*.yaml` &mdash; sub-agent definitions
- `workspace/agents/teams.yaml` &mdash; team routing (coordinate, route, broadcast, tasks)
- `workspace/schedules.yaml` &mdash; scheduled jobs
- `gateway.py` &mdash; FastAPI + AgentOS entry point
- `loader.py` &mdash; builds the agent bundle from a workspace directory
- `openagno/core/tenant_loader.py` &mdash; per-tenant LRU cache used in multi-tenant deployments
- `openagno/channels/whatsapp_cloud.py` &mdash; multi-tenant WhatsApp Cloud API webhook
- `bridges/whatsapp-qr/` &mdash; Baileys-based Node bridge for WhatsApp QR sessions

## Runtime routes (agent-readable contract)

Custom admin:

- `GET /admin/health` &mdash; agents, teams, model, channels, scheduler state. Accepts `?tenant_slug=<slug>`.
- `POST /admin/reload`, `POST /admin/fallback/activate`, `POST /admin/fallback/restore`

Tenants (public multi-tenant HTTP contract):

- `GET /tenants`, `POST /tenants`
- `GET/PATCH/DELETE /tenants/{tenant_id}`
- `GET/PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/reload`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`

Knowledge:

- `POST /knowledge/upload`, `POST /knowledge/ingest-urls`
- `GET /knowledge/list`, `DELETE /knowledge/{doc_name}`
- `POST /knowledge/search`

Channels:

- `GET/POST /whatsapp/webhook` &mdash; Agno-provided Cloud API (single-tenant)
- `GET/POST /whatsapp-cloud/{tenant_id}/webhook` &mdash; OpenAgno-provided Cloud API (multi-tenant, requires `CHANNEL_SECRETS_KEY`)
- `GET /whatsapp-qr/status`, `GET /whatsapp-qr/code`, `POST /whatsapp-qr/incoming`

AgentOS native surfaces:

- `/agents`, `/teams`, `/sessions`, `/memories`, `/schedules`, `/registry`, `/config`, `/components`, `/models`, `/health`, `/metrics`, `/traces`, `/eval-runs`

Auto-generated:

- `/docs`, `/redoc`, `/openapi.json`

## Common tasks

### Add a new sub-agent

1. Run `openagno create agent "Research Agent"` or edit `workspace/agents/research_agent.yaml`
2. Update `workspace/agents/teams.yaml` to add the new member if the team should use it
3. `openagno validate` and restart the runtime

### Add a new channel

1. Decide if it fits an Agno interface (WhatsApp, Slack, Telegram, AG-UI, A2A). If yes, activate it with `openagno add <channel>` and add the env vars
2. If it does not fit, add a module under `openagno/channels/<name>.py` following the `whatsapp_cloud.py` pattern and register it in `gateway.py`
3. Update `docs/channels.mdx` and `docs/es/channels.mdx`

### Bring your own model (BYOK)

- Per-tenant: set `model.api_key` (or AWS pair) inside the tenant's `workspace/config.yaml`
- Server-level fallback: set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or AWS Bedrock vars in `.env`

### Debug a failing run

1. `openagno validate`
2. `curl http://127.0.0.1:8000/admin/health` &mdash; check agents loaded, model, channel state
3. `journalctl -u openagno -n 100 --no-pager` if running under systemd

### Symptom: message channels return "Sorry, there was an error processing your message" or stay silent after editing config

Almost always means the runtime is still holding the previous workspace in memory. `openagno init`, `openagno add`, `openagno create agent` and manual edits of `workspace/*.yaml` or `.env` do **not** reload the process. You must restart the runtime:

- Supervisor: `openagno restart`
- Foreground: Ctrl+C and start again
- systemd: `sudo systemctl restart openagno`
- Docker Compose: `docker compose restart gateway`

After the restart, confirm the new config is loaded with:

```bash
curl http://127.0.0.1:8000/admin/health
```

The `model` field in the response must reflect what you set in `workspace/config.yaml`. If it still shows the old provider/id, the restart did not pick up the config (check `OPENAGNO_ROOT` or which process is actually bound to port 8000).

For per-tenant edits, prefer `POST /tenants/{tenant_id}/reload` over a full restart.

## Public documentation endpoints

- MCP server: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- `llms-full.txt`: `https://docs.openagno.com/llms-full.txt`

Add the MCP server to your IDE using the templates in `ide-configs/`. Full step-by-step setup in `docs/ide-integration.mdx`.

## Spanish summary

Usa OpenAgno cuando necesites agentes declarativos sobre Agno, runtime operativo, knowledge con PgVector, canales (WhatsApp Cloud API single/multi-tenant, QR, Slack, Telegram), aprovisionamiento multi-tenant o documentacion conectable por MCP. Lee `AGENTS.md` en la raiz antes que cualquier otro archivo. Siempre corre `openagno validate` antes de `openagno start` y mantene los cambios dentro del contrato HTTP publico del runtime.
