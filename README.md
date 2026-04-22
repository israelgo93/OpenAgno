# OpenAgno

[![PyPI version](https://badge.fury.io/py/openagno.svg)](https://pypi.org/project/openagno/)

OpenAgno is a declarative agent platform built on top of Agno. It packages a CLI, a FastAPI and AgentOS runtime, reusable workspace templates, tenant-aware provisioning, MCP connectivity, channel integrations, scheduler tooling, and PgVector-backed knowledge retrieval in a single repository.

`OpenAgnoCloud` sits in front of this runtime as the hosted control plane. Cloud owns signup, billing, customer and operator portals, and then drives this OSS runtime strictly through the supported HTTP tenant contract.

## What ships in this repo

- `openagno` CLI for workspace lifecycle, runtime control, validation, templates, and deployment helpers
- FastAPI runtime with AgentOS integration
- declarative `workspace/` configuration based on YAML and Markdown files
- built-in workspace templates for common agent setups
- tenant-aware routes and tenant-scoped workspace execution
- knowledge ingestion, listing, deletion, and semantic search over PgVector
- MCP client and MCP server support
- channel and protocol surfaces including WhatsApp, Slack, Telegram, AG-UI, and A2A
- scheduler support for recurring agent jobs
- public docs, IDE config files, and local service and container helpers

## Repository layout

- `openagno/commands` CLI commands exposed by `openagno`
- `openagno/core` tenant, workspace, and runtime primitives
- `openagno/templates` packaged starter templates
- `routes` FastAPI route builders for admin, tenants, knowledge, channels, and integrations
- `tools` optional runtime tools such as workspace and scheduler management
- `workspace` the default declarative workspace loaded by the runtime
- `workspaces` provisioned tenant workspaces when the local workspace store backend is used
- `deploy` deployment scripts, including systemd installation
- `bridges` auxiliary channel bridges such as the WhatsApp QR bridge
- `docs` Mintlify documentation, including English and Spanish trees
- `ide-configs` ready-made MCP client config files for supported editors
- `tests` automated test suite

## Installation

Install from PyPI:

```bash
pip install openagno
```

Install from source:

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install with validation and protocol extras:

```bash
pip install -e '.[dev,protocols]'
```

Python `>=3.10` is required.

## Agno compatibility

OpenAgno tracks the Agno `2.5.x` line and the direct dependency pins in this repo are aligned to Agno `2.5.14`, which was the latest stable release verified against PyPI on April 4, 2026.

The runtime code paths in this repository continue to rely on documented Agno `AgentOS`, interface routers, and `linked_to` knowledge isolation behavior, which remain present in the current Agno documentation for:

- `agno.os.AgentOS`
- `agno.os.interfaces.whatsapp`, `slack`, `telegram`, and `a2a`
- knowledge isolation through `linked_to` metadata and filter injection

## Quickstart

List available templates:

```bash
openagno templates list
```

Initialize a workspace from a template:

```bash
openagno init --template personal_assistant
```

Validate the workspace:

```bash
openagno validate
```

Start the runtime:

```bash
openagno start --foreground
```

For production or long-running WhatsApp traffic, prefer a single managed process such as the installed `systemd` unit. Do not run `systemctl`, `python gateway.py`, and `service_manager.py start` against the same workspace at the same time or you will create port and shutdown drift.

Health check:

```bash
curl http://127.0.0.1:8000/admin/health
```

## CLI surface

Main commands:

- `openagno init`
- `openagno start`
- `openagno stop`
- `openagno restart`
- `openagno status`
- `openagno logs`
- `openagno validate`

Grouped commands:

- `openagno create`
- `openagno add`
- `openagno templates`
- `openagno deploy`

The CLI entrypoint is defined in `openagno/cli.py` and maps directly to the command modules under `openagno/commands/`.

## Templates

The packaged template registry currently includes:

- `personal_assistant`
- `customer_support`
- `developer_assistant`
- `research_agent`
- `sales_agent`

Templates live in `openagno/templates/` and are copied into a new workspace through `openagno init`.

## Workspace model

The runtime is driven by the declarative files under `workspace/`.

Core files:

- `workspace/config.yaml`
- `workspace/instructions.md`
- `workspace/self_knowledge.md`
- `workspace/tools.yaml`
- `workspace/mcp.yaml`
- `workspace/schedules.yaml`
- `workspace/agents/*.yaml`
- `workspace/knowledge/urls.yaml`

Optional extension surface:

- `workspace/integrations/*`

The default workspace config in this repository currently enables:

- main agent id `agnobot-main`
- model provider `google` with `gemini-2.5-flash`
- local database mode by default
- hybrid knowledge search
- agentic memory
- scheduler polling
- AgentOS embedded MCP server

The loader merges the base workspace with enabled integrations, builds runtime tools from `tools.yaml`, builds MCP clients from `mcp.yaml`, constructs the knowledge layer, and then instantiates the main agent, sub-agents, teams, and schedules.

## Runtime routes

The runtime exposes an admin surface plus tenant and knowledge operations.

Tenant routes:

- `GET /tenants`
- `POST /tenants`
- `GET /tenants/{tenant_id}`
- `PATCH /tenants/{tenant_id}`
- `DELETE /tenants/{tenant_id}`
- `GET /tenants/{tenant_id}/workspace`
- `PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`

Knowledge routes:

- `POST /knowledge/upload`
- `POST /knowledge/ingest-urls`
- `GET /knowledge/list`
- `DELETE /knowledge/{doc_name}`
- `POST /knowledge/search`

The runtime also exposes the AgentOS and admin surfaces configured by `gateway.py`, including `/admin/health`.

WhatsApp modes currently supported by the runtime:

- `cloud_api`
- `qr_link`
- `dual`

The runtime supports QR-based WhatsApp linking through the optional Baileys bridge and the `/whatsapp-qr/*` routes. OpenAgno Cloud now exposes this as a first-class customer flow: after onboarding activation with `qr_link` mode, the customer sees a QR scanner page that polls the bridge and redirects to the dashboard once WhatsApp is connected.

For WhatsApp Cloud API (the official Meta Graph API), the runtime supports two deployment models:

- **Single-tenant**: driven by environment variables (`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`). The runtime mounts a single `/whatsapp/webhook` via Agno. This is what the CLI wizard configures.
- **Multi-tenant (OpenAgnoCloud)**: each tenant brings its own Meta credentials. Cloud stores them encrypted (AES-256-GCM) in the Supabase `whatsapp_cloud_channels` table and the OSS runtime exposes a webhook per tenant at `GET/POST /whatsapp-cloud/{tenant_id}/webhook`. Requires `CHANNEL_SECRETS_KEY` (a base64-encoded 32-byte key) to be set to the same value in Cloud and OSS so both can encrypt and decrypt.

`OpenAgnoCloud` maps the hosted workspace contract into this existing runtime surface through `whatsapp.mode` (set to `dual` for simultaneous Cloud API and QR Link support), without adding new APIs on the OSS side.

Operational notes for the tenant contract:

- collection routes support both `/tenants` and `/tenants/`
- tenant storage now fails fast with `503 Tenant storage unavailable` instead of hanging the runtime when the backing database is unavailable
- tenant storage uses defensive Postgres connections for hosted databases such as Supabase session pooling

## Multi-tenant execution

OpenAgno includes tenant-aware isolation through the tenant store and workspace store layers. Tenant execution scopes identity, metadata, and knowledge filters so each run stays bound to its tenant context.

Key runtime behaviors:

- tenant creation provisions a workspace copy from a selected template
- tenant updates can persist workspace config changes
- tenant runs scope `user_id`, `session_id`, metadata, and knowledge filters
- tenant knowledge retrieval uses isolated filters for vector search

This is the contract consumed by `OpenAgnoCloud`.

The runtime should stay focused on execution. Plan policy, customer onboarding, billing entitlements, and operator rollout logic should remain in Cloud and be translated into runtime configuration through this contract.

## Knowledge and vector search

OpenAgno uses PostgreSQL with PgVector for knowledge storage and retrieval. The default workspace config is prepared for hybrid search and can run against local Postgres or a hosted database such as Supabase.

Supported document flow:

- upload files through the knowledge API
- ingest remote URLs
- list indexed content
- delete indexed content by document name
- search semantically through the knowledge index

The default workspace is configured to auto-ingest both local docs and declared URLs when enabled.

## Tools and MCP

`workspace/tools.yaml` defines built-in and optional tools.

Built-in defaults in this repo:

- `duckduckgo`
- `crawl4ai`
- `reasoning`

Optional tools present in the default config:

- `workspace`
- `scheduler_mgmt`
- `email`
- `tavily`
- `github`
- `audio`
- `shell`
- `spotify`
- `yfinance`
- `wikipedia`
- `arxiv`
- `calculator`
- `file_tools`
- `python_tools`

`workspace/mcp.yaml` defines external MCP connections. The default file includes examples for:

- Agno Docs over `streamable-http`
- Tavily over `streamable-http`
- Supabase over `stdio`
- GitHub over `stdio`

The runtime can also expose its own MCP server when `agentos.enable_mcp_server: true` is enabled in `workspace/config.yaml`.

## IDE integration

Ready-made MCP client configs are available in:

- `ide-configs/cursor-mcp.json`
- `ide-configs/vscode-mcp.json`
- `ide-configs/windsurf-mcp.json`

Public references:

- MCP docs: `https://docs.openagno.com/mcp`
- AI index: `https://docs.openagno.com/llms.txt`
- main docs: `https://docs.openagno.com`

## Running locally

### Python process

```bash
source .venv/bin/activate
openagno start --foreground
```

### Docker Compose

```bash
docker compose up --build
```

This repository includes:

- a `pgvector/pgvector:pg17` database service
- a `gateway` service running `python gateway.py`
- an optional `whatsapp-bridge` profile

### systemd service

Install the systemd unit:

```bash
sudo bash deploy/install-service.sh
```

That script installs:

- `openagno.service`
- `openagno-whatsapp-bridge.service` when the QR bridge is present and Node.js is available

## Documentation

Run the docs site locally:

```bash
cd docs
npm install
npm run dev
```

Validate docs:

```bash
cd docs
npm run validate
npm run broken-links
```

Spanish pages are published under `docs/es/`.

## Release and validation

Local verification used for the current `v1.3.0` closeout:

```bash
source .venv/bin/activate
pytest -q
python -m build
ruff check
python -m pip install --force-reinstall --no-deps dist/openagno-1.3.0-py3-none-any.whl
python -c "import openagno; print(openagno.__version__)"
```

Expected results:

- test suite passes
- `ruff check` is clean
- wheel build succeeds
- installed package reports `1.3.0`

## Current release posture

The repository content reflects the `1.3.0` closeout work. Publishing to PyPI remains a separate operational step triggered manually by the maintainer when the `v1.3.0` wheel is ready to go live.

## License

Apache 2.0.
