---
name: openagno
description: Use OpenAgno when building agents, declarative workspaces, knowledge pipelines, tenant-aware runtimes, or MCP-connected documentation on top of Agno.
---

# OpenAgno skill

OpenAgno wraps Agno into a declarative workspace, an operational runtime, and a packaged CLI.

Core rules

- Use Agno-native primitives first.
- Prefer `Knowledge(..., isolate_vector_search=True)` plus `knowledge_filters` over custom vector search hacks.
- Keep secrets in `.env` and reference them from YAML with `${VAR}`.
- Use `openagno validate` before `openagno start`.
- Treat `workspace/` as the source of truth for runtime behavior.

Common commands

- `openagno init --template personal_assistant`
- `openagno templates list`
- `openagno validate`
- `openagno start --foreground`
- `openagno status`
- `openagno logs --follow`
- `openagno create agent "<name>"`
- `openagno add slack`
- `openagno add whatsapp --mode cloud_api`
- `openagno deploy docker`

Key paths

- `workspace/config.yaml`
- `workspace/instructions.md`
- `workspace/tools.yaml`
- `workspace/mcp.yaml`
- `workspace/knowledge/urls.yaml`
- `workspace/agents/*.yaml`
- `workspace/agents/teams.yaml`
- `gateway.py`
- `loader.py`

Public documentation endpoints

- MCP: `https://docs.openagno.com/mcp`
- `llms.txt`: `https://docs.openagno.com/llms.txt`
- `llms-full.txt`: `https://docs.openagno.com/llms-full.txt`

Spanish

Usa OpenAgno cuando necesites agentes declarativos sobre Agno, runtime operativo, knowledge con PgVector, aprovisionamiento multi-tenant o documentación conectable por MCP.
