# AGENTS.md

## Scope

This repository is `OpenAgno`, the OSS runtime and CLI project.

It owns:

- the packaged Python CLI
- the FastAPI and AgentOS runtime
- the checked in `workspace/`
- packaged templates in `openagno/templates`
- channel integrations and runtime services
- public docs in `docs/`
- knowledge internals and `/knowledge/*` routes
- tenant APIs and tenant workspace provisioning

It does not own:

- the SaaS dashboard
- Supabase control plane state
- Stripe billing flows
- Next.js product UI
- AWS hosting for the Cloud control plane

Those belong to the sibling repository `../OpenAgnoCloud`.

If a task appears to require changes in both repos, do not silently edit both. Keep work scoped to this repo unless the user explicitly asks for multi repo work. If the HTTP contract must change, call out the interface impact clearly.

## Phase 10.5 baseline

- OSS repo baseline after Phase 10.5 is `1.2.1`
- Agno dependency floor is `agno[os,scheduler]>=2.5.0`
- `openagno/commands/validate.py` is expected to stay clean and lintable
- Cloud integration is still HTTP only and contract bound
- `/knowledge/*` exists for OSS users, but it is not part of the Cloud contract in 10.5

## Repository map

- `gateway.py`: main runtime entry point
- `loader.py`: loads `workspace/` and builds the runtime
- `openagno/cli.py`: CLI bootstrap
- `openagno/commands/`: packaged CLI commands such as `init`, `start`, `templates`, and `validate`
- `openagno/core/workspace_store.py`: tenant workspace provisioning and storage rules
- `openagno/core/tenant.py` and `openagno/core/tenant_middleware.py`: tenant runtime behavior
- `routes/tenant_routes.py`: tenant CRUD and workspace routes
- `routes/knowledge_routes.py`: OSS knowledge upload, list, delete, and search routes
- `management/`: runtime admin and validation helpers
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

Run the smallest relevant set first, then the broader set when the change is cross cutting.

- Tests: `pytest -q`
- Package build: `python -m build`
- Ruff on touched files: `ruff check <paths>`
- Docs install: `cd docs && npm install`
- Docs validate: `cd docs && npm run validate`
- Docs links: `cd docs && npm run broken-links`

Minimum expectations:

- Python runtime, CLI, or route changes: run `pytest -q`
- Packaging, dependency, or version changes: run `python -m build`
- Lint cleanup or command refactors: run `ruff check` on touched files when available
- Docs or Mintlify nav changes: run both docs commands

## Project specific rules

- Keep public docs in English at `docs/`. Put Spanish pages in `docs/es/`.
- Do not reintroduce internal planning files or `docs_plan/` material into the tracked OSS tree.
- Treat `workspace/` as the checked in source of truth. Do not treat `workspaces/` as versioned project content.
- Do not hand edit generated or runtime artifacts such as `dist/`, `openagno.egg-info/`, `gateway.log`, or `openagno.pid` unless the user explicitly asks.
- Preserve the tenant HTTP surface in `routes/tenant_routes.py` unless the user explicitly requests a contract change.
- Keep tenant workspace provisioning logic in `openagno/core/workspace_store.py` aligned with the runtime contract.
- If a version or packaging change is made, keep `openagno/__init__.py`, `pyproject.toml`, dependency files, and `docs/changelog.mdx` in sync.
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

Do not widen that contract casually in 10.5. In particular:

- do not assume Cloud may call `/knowledge/*`
- do not add Supabase or Stripe logic here
- do not add Next.js app concerns here

If a task truly needs coordinated OSS and SaaS changes, make them as separate repo scoped changes and separate commits.

## Security and safety

- Never commit secrets, `.env` files, tokens, or tenant data.
- Preserve API key protection on admin and tenant routes unless the user explicitly requests an auth change.
- Avoid destructive tenant or workspace cleanup unless the user clearly asked for it.

## Agent workflow

- Read this file before searching broadly.
- Trust these instructions unless the code clearly contradicts them.
- Keep edits minimal and local to the task.
- Add or update tests when behavior changes.
- Before finishing, run the relevant validation commands and report any gaps.
