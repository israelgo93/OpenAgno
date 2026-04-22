# Contributing to OpenAgno

Thanks for helping move OpenAgno forward. This guide captures what we expect from a healthy contribution so reviews go fast and the runtime stays coherent with the docs.

## Scope of the project

OpenAgno is the declarative **runtime** for Agno-based agents. It ships:

- a CLI (`openagno`) for workspace lifecycle, validation and deploy helpers
- a FastAPI + AgentOS runtime
- packaged workspace templates
- channel integrations (WhatsApp Cloud API, WhatsApp QR via Baileys bridge, Slack, Telegram, AG-UI, A2A)
- multi-tenant provisioning with tenant-scoped workspaces and knowledge filters
- PgVector-backed knowledge ingestion and semantic search
- MCP client and server

The runtime is self-contained. External control planes, dashboards, or orchestrators integrate with it strictly through the documented HTTP contract. Contributions here should not tie the runtime to any specific hosted service, billing system, or vendor-specific UI.

## Development setup

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,protocols]'
openagno validate
pytest -q
```

Python >= 3.10. Agno `2.5.x`.

### Optional bridges and databases

If your change touches the WhatsApp QR bridge:

```bash
cd bridges/whatsapp-qr
npm install
node --check index.js
```

If your change touches knowledge / vector search, run a local Postgres with PgVector (the `docker-compose.yml` in the repo ships `pgvector/pgvector:pg17`).

## Before you open a PR

- `ruff check` is clean
- `pytest -q` passes
- workspace templates still validate with `openagno validate`
- docs are updated together with the code when a public contract changes (see the [documentation policy](#documentation-policy) below)
- no secret material committed (`.env` is ignored; use `.env.example` for the required shape)

## Documentation policy

The Mintlify docs under `docs/` are the public source of truth for operators and for any external system that talks to this runtime. When you change any of the following, update the related docs in the same PR.

For larger syncs after a long stretch of unreleased commits, use [`DOCS_SYNC_PROMPT.md`](./DOCS_SYNC_PROMPT.md) at the repo root. It is a structured prompt that any agent-capable IDE (Claude Code, Cursor, Windsurf, Copilot Workspace) can run end-to-end: verify the code base, then reconcile the docs.

| Code change | Docs to update |
|-------------|----------------|
| New or changed HTTP route | `docs/api.mdx`, `docs/es/api.mdx` |
| New channel or mode | `docs/channels.mdx`, `docs/es/channels.mdx`, and a dedicated page if the surface is large (see `docs/whatsapp-cloud-api.mdx` for the pattern) |
| New env var or secret storage | `docs/security.mdx`, `docs/deployment.mdx`, `.env.example` |
| New template | `docs/workspace/templates.mdx` |
| New CLI command | `docs/cli.mdx` |
| Runtime contract change | `docs/api.mdx` and clearly document the breaking behavior in `docs/changelog.mdx` |

The navigation index for docs lives in `docs/docs.json`. Add new pages there in the appropriate group and mirror them in the `es` tree when relevant.

## Code style

- Indent with tabs. Match the existing file style.
- Prefer small, direct changes. Avoid speculative abstractions.
- Type annotations for any new Python function. `from __future__ import annotations` at the top of new modules.
- Don't add narration comments (`# increment x by one`). Comments should explain intent, trade-offs, or non-obvious constraints.
- Log lines that can fire often should stay at `info` or lower. Use `warning` for recoverable problems and `error` for real failures.

## Tests

- Python: `pytest` with fixtures in `tests/`. Mock the network layer (`httpx`, `psycopg`) instead of using real services; see `tests/test_whatsapp_cloud.py` for the pattern.
- Ruff: `ruff check .` should be clean.
- If a change touches multi-tenant behavior, add a test covering the tenant resolution path so we don't regress tenant isolation.

## Adding a new channel

1. Decide whether it fits the current Agno interface (most do). If yes, activate it in `gateway.py` under the existing `if "<channel>" in channels:` block. If no, add a module under `openagno/channels/<name>.py` following the `whatsapp_cloud.py` pattern.
2. Document activation, env vars, and public routes in `docs/channels.mdx` and mirror the changes to `docs/es/channels.mdx`.
3. If the channel requires secrets that flow from an external system into Supabase (as in the multi-tenant WhatsApp Cloud API flow), document the env var and the persistence model in `docs/security.mdx`.
4. Add at least one test covering the happy path and one covering signature or auth rejection.

## Commit messages

- One focused change per commit.
- English or Spanish, both acceptable in this repository. Be descriptive: explain *why*, not just *what*.
- Group type prefixes used in history: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`. Optional scope in parentheses (`feat(channels): ...`).
- Reference related issues when available.

## Reporting bugs and requesting features

Use GitHub Issues with the templates under `.github/ISSUE_TEMPLATE/`. The templates ask for the info we need to reproduce and triage without a round-trip.

Security issues go to `security@datatensei.com` directly, never to the public tracker. See [`SECURITY.md`](./SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0 (see [`LICENSE`](./LICENSE)).
