# AGENTS.md

## Scope

This repository is `OpenAgno`, the OSS runtime and CLI project.

It owns:

- the packaged Python CLI
- the FastAPI and AgentOS runtime
- the checked in `workspace/`
- packaged templates
- channel integrations
- public docs in `docs/`
- tenant APIs and tenant workspace provisioning

It does not own:

- the SaaS dashboard
- Supabase control plane state
- Stripe billing flows
- Next.js product UI

Those belong to the sibling repository `../OpenAgnoCloud`.

If a task appears to require changes in both repos, do not silently edit both. Keep work scoped to this repo unless the user explicitly asks for multi repo work. If the HTTP contract must change, document the interface impact clearly.

## Repository map

- `gateway.py`: main runtime entry point
- `loader.py`: loads `workspace/` and builds the runtime
- `openagno/`: reusable package code
- `routes/`: API routes, including tenant routes
- `management/`: validation and management helpers
- `workspace/`: canonical checked in workspace content
- `workspaces/`: runtime created tenant workspace root, not canonical repo source
- `docs/`: Mintlify docs, English at root and Spanish in `docs/es/`
- `ide-configs/`: exported IDE and MCP configs

## Setup commands

- Create env: `python3 -m venv .venv`
- Activate env: `source .venv/bin/activate`
- Install app: `pip install -e .`
- Install full dev stack: `pip install -e '.[dev,protocols]'`

## Validation commands

Run the smallest relevant set, then the broader set when the change is cross cutting.

- Tests: `pytest -q`
- Package build: `python -m build`
- Docs install: `cd docs && npm install`
- Docs validate: `cd docs && npm run validate`
- Docs links: `cd docs && npm run broken-links`

Minimum expectations:

- Python runtime or route changes: run `pytest -q`
- Packaging, metadata, or install changes: run `python -m build`
- Docs or Mintlify nav changes: run both docs commands

## Project specific rules

- Keep public docs in English at `docs/`. Put Spanish pages in `docs/es/`.
- Do not reintroduce internal planning files or `docs_plan/` material into the tracked OSS tree.
- Treat `workspace/` as the checked in source of truth. Do not treat `workspaces/` as versioned project content.
- Preserve the tenant HTTP surface in `routes/tenant_routes.py` unless the user explicitly requests a contract change.
- Keep tenant workspace provisioning logic in `openagno/core/workspace_store.py` aligned with the runtime contract.
- Prefer backward compatible changes to CLI, runtime, and routes.

## Cross repo boundary with OpenAgnoCloud

OpenAgnoCloud may call this repo over HTTP only. The current SaaS facing contract includes:

- `GET /admin/health`
- `GET /tenants`
- `POST /tenants`
- `GET /tenants/{tenant_id}`
- `PATCH /tenants/{tenant_id}`
- `DELETE /tenants/{tenant_id}`
- `GET /tenants/{tenant_id}/workspace`
- `PUT /tenants/{tenant_id}/workspace`

Do not add Supabase, Stripe, or Next.js app logic here. If a task truly needs coordinated OSS and SaaS changes, make them as separate repo scoped changes and separate commits.

## Security and safety

- Never commit secrets, `.env` files, tokens, or tenant data.
- Preserve API key protection on admin and tenant routes unless the user explicitly requests an auth change.
- Avoid destructive data or workspace cleanup unless the user clearly asked for it.

## Agent workflow

- Read this file before searching broadly.
- Trust these instructions unless the code clearly contradicts them.
- Keep edits minimal and local to the task.
- Add or update tests when behavior changes.
- Before finishing, run the relevant validation commands and report any gaps.
