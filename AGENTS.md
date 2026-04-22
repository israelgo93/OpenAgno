# AGENTS.md

This file follows the [`AGENTS.md` convention](https://agents.md) so any agent-capable IDE (Claude Code, Cursor, Windsurf, VS Code with Copilot, Aider, etc.) can bootstrap its understanding of this repository from a single place. Read it end to end before opening other files.

## Scope

This repository is `OpenAgno`, the **open source agent runtime and CLI**. It pairs with the sibling SaaS repo `../OpenAgnoCloud`. Keep work scoped to this repo unless the user explicitly asks for coordinated multi-repo changes.

OpenAgno owns:

- the packaged Python CLI (`openagno`)
- the FastAPI + AgentOS runtime (`gateway.py`, `loader.py`)
- the declarative `workspace/` source of truth
- packaged templates in `openagno/templates/`
- channel integrations under `openagno/channels/` plus the Node-based WhatsApp QR bridge in `bridges/whatsapp-qr/`
- knowledge ingestion and semantic search over PgVector
- MCP client/server support
- public Mintlify docs in `docs/` (English and `docs/es/`)
- CLI-facing skills for agent-capable IDEs in `.agents/skills/`

It does **not** own:

- the SaaS dashboard, onboarding UI, or operator portal (those live in `OpenAgnoCloud`)
- Supabase control-plane state beyond the tables the runtime reads
- Stripe billing
- Next.js product UI
- AWS hosting for Cloud

## Current baseline

- OSS version: `1.3.x`
- Agno floor: `agno[os,scheduler]>=2.5.14`
- Python: `>=3.10`
- WhatsApp QR bridge: Node 20 + `@whiskeysockets/baileys@7.0.0-rc.9` (ESM)
- Supabase tables consumed by OSS: `public.tenants`, `public.whatsapp_cloud_channels`
- License: Apache 2.0

## Prerequisites for a developer or agent to run this

Minimum to run the CLI and the runtime:

- Python 3.10+ with `venv`
- PostgreSQL with the `pgvector` extension (either local via `docker compose up -d db` using the included `pgvector/pgvector:pg17` service, or a hosted Postgres such as Supabase with `pgvector`)
- An LLM API key for the chosen provider (e.g. `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or AWS Bedrock credentials)
- Optional: Node 20+ if you are going to enable the WhatsApp QR bridge

Platform-specific extras:

- WhatsApp Cloud API single-tenant: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, optional `WHATSAPP_APP_SECRET`
- WhatsApp Cloud API multi-tenant (OpenAgnoCloud): `CHANNEL_SECRETS_KEY` (32 bytes base64, identical to the key set in the Cloud Next.js app)
- Slack: `SLACK_TOKEN`, `SLACK_SIGNING_SECRET`
- Telegram: `TELEGRAM_TOKEN`

## Setup commands

Canonical developer bootstrap:

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,protocols]'
cp .env.example .env   # then edit values
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground
```

The CLI wizard (`openagno init`) interactively collects `.env` values. Non-interactive setups should fill `.env` directly.

## Repository map

- `gateway.py`: FastAPI entry point, mounts AgentOS interfaces and the custom OpenAgno routes, wires the `TenantLoader`, and attaches channel routers
- `loader.py`: resolves a workspace directory into an Agno agent bundle (`main_agent`, `sub_agents`, `teams`, `db`, `knowledge`, `config`). `load_workspace_from_dir(path)` is the canonical entry point; `load_workspace()` is a legacy wrapper
- `openagno/cli.py`: CLI bootstrap (maps to subcommands in `openagno/commands/`)
- `openagno/commands/`: packaged CLI commands (`init`, `start`, `stop`, `status`, `logs`, `validate`, `create`, `add`, `templates`, `deploy`)
- `openagno/core/tenant.py`: `Tenant` dataclass, `TenantStore`, `slugify_tenant`, `normalize_tenant_id`, knowledge-scoping helpers
- `openagno/core/tenant_loader.py`: LRU cache of per-tenant workspace bundles. The gateway injects the default workspace as tenant `default` to avoid duplicate model objects
- `openagno/core/tenant_middleware.py`: resolves `X-Tenant-ID` (or query/path) for tenant-aware routes
- `openagno/core/workspace_store.py`: provisions tenant workspaces from templates and writes `config.yaml` + derived Markdown files
- `openagno/channels/`: OpenAgno-owned channel routers that complement the Agno-provided interfaces (currently `whatsapp_cloud.py` for multi-tenant Cloud API)
- `routes/tenant_routes.py`: `/tenants/*` CRUD plus workspace and `/runs`
- `routes/knowledge_routes.py`: `/knowledge/upload`, `/ingest-urls`, `/list`, `/{doc_name}`, `/search`
- `bridges/whatsapp-qr/index.js`: Baileys-based Node bridge, one session per tenant under `/sessions/:tenantSlug/*`. Routes to the OSS runtime via `POST /whatsapp-qr/incoming`
- `workspace/`: canonical checked-in workspace content (source of truth for the repo)
- `workspaces/`: runtime-created tenant workspace root (ignored, NOT canonical project content)
- `openagno/templates/`: packaged starter templates used by `openagno init`
- `docs/`: public Mintlify documentation (English at root, Spanish under `docs/es/`)
- `ide-configs/`: copy-ready MCP configs for Cursor, VS Code, Windsurf, Claude Code
- `.agents/skills/`: IDE-agnostic skills that agent-capable IDEs can surface
- `management/`: runtime admin and validation helpers
- `tests/`: pytest suite (network layer is mocked, no external calls)
- `.github/`: issue and PR templates

## Setup + validation commands

Run the smallest relevant set first. Widen when the change is cross-cutting.

- Unit tests: `pytest -q`
- Focused tests: `pytest tests/test_<module>.py -x --tb=short`
- Lint: `ruff check .` (or `ruff check <paths>` when scoped)
- Package build: `python -m build`
- Docs validate: `cd docs && npm run validate`
- Docs links: `cd docs && npm run broken-links`

Minimum expectations by change type:

- Python runtime / CLI / routes: `pytest -q` and `ruff check`
- Packaging / dependency / version: add `python -m build`
- Docs / Mintlify nav: `npm run validate` and `npm run broken-links`
- WhatsApp QR bridge (`bridges/whatsapp-qr/`): `node --check index.js` and a manual boot in foreground

## Project-specific rules

- Public docs are English in `docs/`, Spanish mirrors in `docs/es/`. Keep them in sync when the surface changes.
- Do not reintroduce internal planning notes or `docs_plan/` material into the tracked tree.
- `workspace/` is the checked-in source of truth. `workspaces/` is runtime-generated, never committed, never hand-edited.
- Do not hand-edit generated artifacts (`dist/`, `openagno.egg-info/`, `gateway.log`, `openagno.pid`) unless the user explicitly asks.
- Preserve the tenant HTTP surface in `routes/tenant_routes.py` and the channel routers in `openagno/channels/`; do not broaden the contract casually.
- Prefer backward-compatible changes to CLI, runtime routes, and workspace YAML shape.
- If a version or packaging change is made, keep `openagno/__init__.py`, `pyproject.toml`, and `docs/changelog.mdx` in sync.

## Runtime contract consumed by OpenAgnoCloud

Cloud may call this runtime over HTTP only, using the documented surface:

- `GET /admin/health` (accepts `?tenant_slug=<slug>`; returns `tenant_model` and `tenancy.cache`)
- `POST /admin/reload`
- `POST /admin/fallback/activate`, `POST /admin/fallback/restore`
- `GET /tenants`, `POST /tenants`
- `GET /tenants/{tenant_id}`, `PATCH /tenants/{tenant_id}`, `DELETE /tenants/{tenant_id}`
- `GET /tenants/{tenant_id}/workspace`, `PUT /tenants/{tenant_id}/workspace`
- `POST /tenants/{tenant_id}/reload`
- `POST /tenants/{tenant_id}/agents/{agent_id}/runs`
- `POST /whatsapp-qr/incoming` (Baileys bridge hands off inbound messages; body carries `tenant_slug`)
- `GET/POST /whatsapp-cloud/{tenant_id}/webhook` (per-tenant Meta webhook; requires `CHANNEL_SECRETS_KEY` to be set so the runtime can decrypt credentials from `public.whatsapp_cloud_channels`)

Multi-tenant runtime notes (Phase A complete):

- `loader.load_workspace_from_dir(path)` lets the runtime load any workspace without relying on a global `WORKSPACE_DIR`. The legacy `load_workspace()` passes `WORKSPACE_DIR` automatically
- `TenantLoader` keeps an LRU cache (`OPENAGNO_TENANT_CACHE_SIZE`, default 32). The gateway pre-populates it with the default workspace as tenant `default`
- After every `PUT /tenants/{id}/workspace`, Cloud must `POST /tenants/{id}/reload` to invalidate the cache
- The Baileys bridge isolates one session per tenant under `/sessions/:tenantSlug/*`; inbound messages go to `POST /whatsapp-qr/incoming` with `tenant_slug` in the body
- Multi-tenant Cloud API resolves credentials from `public.whatsapp_cloud_channels` (AES-256-GCM cipher + nonce columns) using `CHANNEL_SECRETS_KEY`. See `openagno/channels/whatsapp_cloud.py`

BYOK (bring your own key) per tenant:

- `loader._build_single_model(provider, model_id, aws_region, api_key=?, aws_access_key_id=?, aws_secret_access_key=?)` accepts per-tenant credentials from `workspace/config.yaml` (`model.api_key`, `model.aws_access_key_id`, `model.aws_secret_access_key`)
- When a tenant provides its own API key (customer), Agno receives it as a kwarg
- When a tenant does not provide credentials (operator/default), Agno falls back to `os.environ` (the server-level `.env`)
- `GET /admin/health?tenant_slug=X` redacts credentials: returns only `provider`, `id`, `aws_region`

Do not widen this contract casually. In particular:

- do not assume Cloud may call `/knowledge/*`
- do not add Supabase or Stripe logic in this repo
- do not add Next.js app concerns here

## Security and safety

- Never commit secrets, `.env`, tokens, or tenant data (see `.gitignore` and `SECURITY.md`)
- Preserve API-key protection on admin and tenant routes unless the user explicitly requests an auth change
- `WHATSAPP_SKIP_SIGNATURE_VALIDATION=true` exists for local development only; never set it in production
- Avoid destructive tenant or workspace cleanup unless the user clearly asked for it
- Multi-tenant Cloud API credentials (`access_token`, `verify_token`, `app_secret`) are AES-256-GCM encrypted in Supabase. The shared master key `CHANNEL_SECRETS_KEY` must be identical to the value set in the Cloud Next.js app, and rotating it requires re-encrypting existing rows

## Agent workflow

1. Read this file and `.agents/skills/openagno/SKILL.md` before searching broadly
2. Trust these instructions unless the code clearly contradicts them; in that case flag the contradiction in your response
3. Keep edits minimal and local to the task
4. Add or update tests when behavior changes
5. Update docs (English + Spanish) when a user-visible surface changes
6. Before finishing, run the relevant validation commands and report any gaps
7. If a task requires changes in both `OpenAgno` and `OpenAgnoCloud`, make them as separate repo-scoped changes and separate commits

## IDE and agent integration

- MCP config templates: `ide-configs/cursor-mcp.json`, `ide-configs/vscode-mcp.json`, `ide-configs/windsurf-mcp.json`, `ide-configs/claude-code-setup.sh`
- Skills for agent-capable IDEs: `.agents/skills/openagno/SKILL.md`, `.agents/skills/openagno-channels/SKILL.md`, `.agents/skills/mintlify/SKILL.md`
- Public docs MCP endpoint: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- `llms-full.txt`: `https://docs.openagno.com/llms-full.txt`

See [`docs/ide-integration.mdx`](./docs/ide-integration.mdx) for step-by-step setup per tool.
