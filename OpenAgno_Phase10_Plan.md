# OpenAgno — Phase 10 Implementation Plan

*Date: March 28, 2026*
*Current version: v1.1.0 (post-F9.5, PR #1 + PR #3 merged)*
*Target version: v1.2.0*
*Branch: `feature/phase-10`*
*Final deliverable: PR #4 → main*

---

## 0. Pre-Phase Validation Summary

### Phases 9 + 9.5: VERIFIED COMPLETE

| Issue | Status | Verified |
|-------|--------|----------|
| DAT-252 WhatsApp dedup | ✅ Done | MessageDeduplicator in gateway.py |
| DAT-253 Cross-model sanitization | ✅ Done | sanitize_session_history_pre_hook |
| DAT-254 MCP stdio fix | ✅ Done | build_mcp_tools() returns MCPTools |
| DAT-255 CLI pip package | ✅ Done | openagno/cli.py + pyproject.toml |
| DAT-256 5 workspace templates | ✅ Done | registry.yaml + templates/ |
| DAT-257 Tests pytest | ✅ Done | 52 tests passing |
| DAT-258 Rate limiting | ✅ Done | slowapi + requirements.lock |
| DAT-260 CLI visual style | ✅ Done | _output.py formatter, English |
| DAT-261 Mintlify 4 pages | ✅ Done | getting-started-no-code, whatsapp-tunnel, changelog, contributing |
| DAT-262 MCP docs + llms.txt | ✅ Done | mcp.mdx updated |
| DAT-264 Windows compat | ✅ Done | process_utils cross-platform |
| DAT-265 Cleanup legacy | ✅ Done | setup.sh rewritten, management/cli deprecated |
| DAT-250 WhatsApp phantom | ✅ Done | Superseded by DAT-252 |
| DAT-241 Tests backlog | ✅ Done | Superseded by DAT-257 |

### Open Issues Carried Into Phase 10

| Issue | Status | Action in F10 |
|-------|--------|---------------|
| DAT-259 | Backlog | **RESOLVE** — PyPI publication |
| DAT-263 | Backlog | **RESOLVE** — WhatsApp tunnel guide |
| DAT-266 | Backlog | **RESOLVE** — Tech debt (4 items) |
| DAT-217 | Backlog | Deferred to post-MVP (Remote Execution) |

### Project Structure Post-Purge: VERIFIED

PR #3 removed `docs_plan/` (12 MD files, -10,570 lines). Code review confirmed:
- Zero runtime/config files deleted
- management/cli.py + validator.py: only docstrings changed
- 52 tests passing post-merge
- No broken references to docs_plan/ anywhere

### Mintlify Documentation: VERIFIED

- `docs.json` navigation: 5 groups, 23 pages
- `npm run broken-links`: success
- `mintlify validate`: success
- Pages present: index, quickstart, getting-started-no-code, architecture, workspace/*, channels, whatsapp-tunnel, tools, knowledge, mcp, cli, studio, api, security, troubleshooting, deployment, structure, reference, changelog, contributing
- MCP active at `https://docs.openagno.com/mcp` with `search_open_agno` tool

### Documentation Gaps Found

1. **Docs language inconsistency** — Mix of Spanish and English across .mdx pages. F10 standardizes to English.
2. **quickstart.mdx** — Still leads with `git clone`. Must lead with `pip install openagno` after DAT-259.
3. **No IDE integration guide** — MCP and llms.txt exist but no page explaining how to use them in Cursor, Claude Code, VS Code, Windsurf.
4. **No API reference page** — `api.mdx` exists but lacks OpenAPI spec or endpoint catalog.

---

## 1. Phase 10 Objectives

1. **Publish to PyPI** — `pip install openagno` works globally
2. **IDE/AI Integration Export** — MCP, llms.txt, skills files for Cursor/Claude Code/Windsurf
3. **Multi-tenancy foundation** — Knowledge isolation via `isolate_vector_search`, tenant routing
4. **Provisioning API** — REST endpoints to create/manage tenants + workspaces
5. **Documentation English-first** — All .mdx pages in English, API reference
6. **Close all open Linear issues** — DAT-259, DAT-263, DAT-266
7. **End in PR #4** with verification checkpoints

---

## 2. Implementation Steps

### Step 1: Close Carried Issues (DAT-259, DAT-263, DAT-266)

**DAT-259 — PyPI Publication**

```bash
# 1. Bump version
# pyproject.toml: version = "1.2.0"

# 2. Build
python -m build

# 3. Upload to PyPI
twine upload dist/*

# 4. Verify clean install
pip install openagno && openagno --help
```

Post-publish updates:
- README.md: `pip install openagno` as first installation method
- quickstart.mdx: same change
- Add PyPI badge to README

**DAT-263 — WhatsApp Tunnel Guide**

The `whatsapp-tunnel.mdx` page was created in F9.5 but verify content includes:
- ngrok setup (`ngrok http 8000`)
- cloudflared alternative
- Meta Developer Console webhook URL config
- `WHATSAPP_SKIP_SIGNATURE_VALIDATION=true` for dev
- Link from channels.mdx

**DAT-266 — Tech Debt (4 items)**

1. Fix mixed tabs/spaces with `ruff format .`
2. Fix unreachable ternary in validate.py
3. Restore Knowledge/PgVector pointer in README
4. Update setup.sh to install `[dev,protocols]` extras

### Step 2: IDE/AI Integration Export

Create `docs/ide-integration.mdx` — comprehensive guide for connecting OpenAgno docs to AI-powered IDEs.

**2.1 — MCP Server (already active)**

```
URL: https://docs.openagno.com/mcp
Tool: search_open_agno
Transport: HTTP (streamable)
```

Connection instructions per IDE:

| IDE | Method |
|-----|--------|
| Claude Desktop | Settings > Connectors > Custom > URL |
| Claude Code | `claude mcp add openagno https://docs.openagno.com/mcp` |
| Cursor | `npx mint-mcp add openagno` or Settings > MCP > Add |
| Windsurf | Settings > MCP Servers > Add URL |
| VS Code (Copilot) | `.vscode/mcp.json` with server URL |

**2.2 — llms.txt**

Verify `docs.json` has:
```json
{
  "ai": { "llmsTxt": true }
}
```

This auto-generates `https://docs.openagno.com/llms.txt` and `llms-full.txt`.

**2.3 — Skills File for IDEs**

Create `.agents/skills/openagno/SKILL.md` in the repo:

```markdown
---
name: openagno
description: Build autonomous AI agents with OpenAgno. Use when creating agents,
  configuring workspaces, working with Agno Framework, or managing agent deployments.
---

# OpenAgno skill

OpenAgno wraps Agno Framework into a CLI + declarative workspace.

## Key rules
- Only Agno Framework — never LangChain, CrewAI
- PgVector: always SearchType.hybrid with OpenAIEmbedder(id="text-embedding-3-small")
- Memory: enable_agentic_memory=True, NEVER combine with update_memory_on_run=True
- MCP: never use reload=True with MCPTools in AgentOS
- Secrets: only in .env with ${VAR} references in YAML
- AWS Bedrock Claude: from agno.models.aws import Claude (NOT AwsBedrock)

## CLI commands
- openagno init [--template NAME]
- openagno start [--daemon]
- openagno stop / restart / status / logs
- openagno create agent NAME
- openagno add whatsapp|slack|telegram
- openagno validate
- openagno deploy docker|local

## Workspace structure
workspace/config.yaml, instructions.md, tools.yaml, mcp.yaml,
self_knowledge.md, knowledge/docs/, knowledge/urls.yaml,
agents/*.yaml, agents/teams.yaml, schedules.yaml

## MCP Documentation
https://docs.openagno.com/mcp — search_open_agno tool
```

**2.4 — Export configs for popular IDEs**

Create `ide-configs/` directory in repo root:

```
ide-configs/
├── cursor-mcp.json          # Cursor MCP server config
├── claude-code-setup.sh      # claude mcp add command
├── vscode-mcp.json           # VS Code .vscode/mcp.json template
├── windsurf-mcp.json         # Windsurf config
└── README.md                 # Which file goes where
```

Each file is a ready-to-copy config snippet.

### Step 3: Documentation Standardization

**3.1 — English-first migration**

All .mdx pages migrated to English:
- Titles and descriptions in English
- Body text in English
- Code comments can stay bilingual where relevant
- docs.json `search.prompt` updated to English

**3.2 — API Reference**

Create `docs/api-reference.mdx` with endpoint catalog:

| Method | Path | Description |
|--------|------|-------------|
| POST | /agents/{id}/runs | Send message to agent |
| GET | /agents | List registered agents |
| GET | /admin/health | Health check |
| POST | /admin/reload | Hot-reload workspace |
| GET | /knowledge/list | List knowledge docs |
| POST | /knowledge/upload | Upload document |
| DELETE | /knowledge/{name} | Remove document |
| POST | /knowledge/search | Semantic search |
| POST | /knowledge/ingest-urls | Ingest URLs |
| CRUD | /schedules/* | Schedule management |

**3.3 — Updated navigation**

```json
{
  "groups": [
    {
      "group": "Getting Started",
      "pages": ["index", "quickstart", "getting-started-no-code", "architecture"]
    },
    {
      "group": "Workspace",
      "pages": ["workspace/overview", "workspace/config", "workspace/templates",
                 "workspace/integrations", "models", "channels", "whatsapp-tunnel",
                 "tools", "knowledge", "mcp"]
    },
    {
      "group": "Operations",
      "pages": ["cli", "studio", "api-reference", "security", "troubleshooting"]
    },
    {
      "group": "Deploy",
      "pages": ["deployment", "structure"]
    },
    {
      "group": "Integrations",
      "pages": ["ide-integration"]
    },
    {
      "group": "Reference",
      "pages": ["reference", "changelog", "contributing"]
    }
  ]
}
```

### Step 4: Multi-Tenancy Foundation

**4.1 — Knowledge Isolation (Agno native)**

Agno provides `isolate_vector_search` natively. This isolates knowledge search per `user_id`/`linked_to` without separate schemas.

```python
# In loader.py — build_knowledge()
knowledge = Knowledge(
    vector_db=PgVector(
        table_name="openagno_vectors",
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=db,
    max_results=5,
)

# In agent config
agent = Agent(
    knowledge=knowledge,
    isolate_vector_search=True,  # Agno native — filters by user_id
    ...
)
```

**4.2 — Tenant Model**

Create `openagno/core/tenant.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Tenant:
    id: str                      # UUID
    name: str                    # Display name
    slug: str                    # URL-safe identifier
    plan: str = "free"           # free | pro | enterprise
    workspace_s3_key: Optional[str] = None
    db_schema: Optional[str] = None  # For future schema isolation
    created_at: datetime = None
    active: bool = True
    max_agents: int = 1
    max_messages_per_day: int = 100
```

**4.3 — Tenant Database Table**

Migration via `routes/tenant_routes.py` or Supabase migration:

```sql
CREATE TABLE IF NOT EXISTS openagno_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT DEFAULT 'free',
    workspace_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    active BOOLEAN DEFAULT true,
    max_agents INT DEFAULT 1,
    max_messages_per_day INT DEFAULT 100
);

CREATE INDEX idx_tenants_slug ON openagno_tenants(slug);
```

**4.4 — Tenant Middleware**

```python
# openagno/core/tenant_middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = (
            request.headers.get("X-Tenant-ID")
            or request.query_params.get("tenant_id")
            or "default"
        )
        request.state.tenant_id = tenant_id
        response = await call_next(request)
        return response
```

**4.5 — Workspace Templates in S3 (optional, config-driven)**

```python
# openagno/core/workspace_store.py
import json
from pathlib import Path
from typing import Optional

class WorkspaceStore:
    """Loads workspace from local FS or S3."""

    def __init__(self, backend: str = "local", s3_bucket: Optional[str] = None):
        self.backend = backend
        self.s3_bucket = s3_bucket

    def load(self, tenant_slug: str) -> Path:
        if self.backend == "s3":
            return self._load_from_s3(tenant_slug)
        return Path(f"workspaces/{tenant_slug}/workspace")

    def _load_from_s3(self, tenant_slug: str) -> Path:
        import boto3
        local_path = Path(f"/tmp/workspaces/{tenant_slug}")
        local_path.mkdir(parents=True, exist_ok=True)
        s3 = boto3.client("s3")
        # Download workspace files from S3
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"tenants/{tenant_slug}/workspace/"
        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(prefix):]
                target = local_path / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(self.s3_bucket, key, str(target))
        return local_path
```

### Step 5: Provisioning API

Create `routes/tenant_routes.py`:

```python
from fastapi import APIRouter, HTTPException, Depends
from security import verify_api_key

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("/")
async def create_tenant(data: dict, _=Depends(verify_api_key)):
    """Create a new tenant with default workspace."""
    # 1. Insert into openagno_tenants
    # 2. Copy template workspace to tenant path
    # 3. Return tenant_id + API key
    ...

@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, _=Depends(verify_api_key)):
    """Get tenant info."""
    ...

@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, data: dict, _=Depends(verify_api_key)):
    """Update tenant config (plan, limits)."""
    ...

@router.delete("/{tenant_id}")
async def deactivate_tenant(tenant_id: str, _=Depends(verify_api_key)):
    """Soft-delete tenant."""
    ...

@router.get("/{tenant_id}/workspace")
async def get_workspace_config(tenant_id: str, _=Depends(verify_api_key)):
    """Read tenant workspace config."""
    ...

@router.put("/{tenant_id}/workspace")
async def update_workspace_config(tenant_id: str, data: dict, _=Depends(verify_api_key)):
    """Update tenant workspace config."""
    ...
```

### Step 6: Tests

New test files:

```
tests/
├── test_tenant.py          # Tenant CRUD, middleware, isolation
├── test_provisioning.py    # Provisioning API endpoints
├── test_ide_configs.py     # Validate IDE config files are valid JSON
├── test_pypi_package.py    # Verify package builds cleanly
└── (existing tests)        # 52 existing tests unchanged
```

Target: **65+ tests passing**.

### Step 7: Version Bump + Changelog

- `pyproject.toml`: version = "1.2.0"
- `openagno/__init__.py`: `__version__ = "1.2.0"`
- `docs/changelog.mdx`: Add v1.2.0 entry

---

## 3. Verification Checkpoints

| # | Checkpoint | Verification Command | Gate |
|---|------------|---------------------|------|
| CP1 | DAT-259/263/266 closed | Linear status check | All Done |
| CP2 | PyPI published | `pip install openagno==1.2.0 && openagno --help` | Exit 0 |
| CP3 | IDE configs valid | `python -m json.tool ide-configs/*.json` | All valid |
| CP4 | Docs English + no broken links | `cd docs && npm run broken-links` | 0 errors |
| CP5 | Tenant table created | SQL migration runs | Table exists |
| CP6 | Knowledge isolation works | Test with 2 user_ids, verify no cross-bleed | Pass |
| CP7 | Provisioning API responds | `curl /tenants` returns 200 | Pass |
| CP8 | All tests pass | `pytest -q` | 65+ passed |
| CP9 | Package builds | `python -m build` | sdist + wheel |
| CP10 | PR #4 ready | `git diff --stat main..feature/phase-10` | Clean diff |

---

## 4. Linear Issues for Phase 10

| Issue | Priority | Title |
|-------|----------|-------|
| DAT-259 | Urgent | F10: Publish to PyPI — pip install openagno |
| DAT-263 | High | F10: Verify WhatsApp tunnel guide completeness |
| DAT-266 | High | F10: Close tech debt (ruff format, validate.py, README, setup.sh) |
| DAT-267 | High | F10: IDE integration guide + export configs (MCP, llms.txt, skills) |
| DAT-268 | High | F10: Docs English-first migration + API reference |
| DAT-269 | High | F10: Multi-tenancy foundation — isolate_vector_search + tenant model |
| DAT-270 | Medium | F10: Provisioning API — tenant CRUD endpoints |
| DAT-271 | Medium | F10: Workspace store — local + S3 backend |
| DAT-272 | Medium | F10: Tests for tenancy, provisioning, IDE configs |
| DAT-273 | Low | F10: Version bump v1.2.0 + changelog + PR #4 |

---

## 5. Files Changed/Created

### New files
- `openagno/core/tenant.py`
- `openagno/core/tenant_middleware.py`
- `openagno/core/workspace_store.py`
- `routes/tenant_routes.py`
- `docs/ide-integration.mdx`
- `docs/api-reference.mdx`
- `ide-configs/cursor-mcp.json`
- `ide-configs/claude-code-setup.sh`
- `ide-configs/vscode-mcp.json`
- `ide-configs/windsurf-mcp.json`
- `ide-configs/README.md`
- `.agents/skills/openagno/SKILL.md`
- `tests/test_tenant.py`
- `tests/test_provisioning.py`
- `tests/test_ide_configs.py`

### Modified files
- `pyproject.toml` (version bump, new deps if needed)
- `gateway.py` (add TenantMiddleware, register tenant_routes)
- `loader.py` (add isolate_vector_search support from config)
- `docs/docs.json` (new navigation, English labels, ai.llmsTxt)
- `docs/*.mdx` (English migration)
- `docs/changelog.mdx` (v1.2.0 entry)
- `README.md` (pip install first, PyPI badge, knowledge pointer)
- `setup.sh` (install [dev,protocols])
- `workspace/config.yaml` (add tenancy section)

---

## 6. Estimated Timeline

| Week | Deliverables |
|------|-------------|
| W1 (days 1-3) | CP1-CP4: PyPI, DAT closures, IDE configs, docs English |
| W1 (days 4-5) | CP5-CP7: Tenant model, migration, middleware, provisioning API |
| W2 (days 1-2) | CP8-CP9: Tests, workspace store, S3 backend |
| W2 (day 3) | CP10: Version bump, changelog, PR #4 |

**Total: ~8 working days**

---

## 7. Rules Carried Forward

1. **Only Agno Framework** — never LangChain, CrewAI
2. **Imports**: `from agno.os import AgentOS`, `from agno.vectordb.pgvector import PgVector`
3. **PgVector**: always `SearchType.hybrid` with `OpenAIEmbedder(id="text-embedding-3-small")`
4. **PostgresDb unified** — sessions, memories, contents
5. **Memory**: `enable_agentic_memory=True`, NEVER combine with `update_memory_on_run=True`
6. **MCP**: never use `reload=True` with MCPTools in AgentOS
7. **Secrets**: only in `.env` with `${VAR}` in YAML
8. **AWS Bedrock Claude**: `from agno.models.aws import Claude` (NOT `AwsBedrock`)
9. **Verify against docs.agno.com** before assuming compatibility
10. **Knowledge isolation**: use Agno's `isolate_vector_search=True` — not custom schema-per-tenant
