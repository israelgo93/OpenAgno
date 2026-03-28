# Auto-Conocimiento de OpenAgno

## Proveedores de Modelo Válidos

| Provider (config.yaml) | Import Agno | Modelos recomendados (marzo 2026) |
|------------------------|-------------|----------------------------------|
| `google` | `agno.models.google.Gemini` | `gemini-2.5-flash` (default), `gemini-2.5-pro`, `gemini-3-flash-preview` |
| `openai` | `agno.models.openai.OpenAIChat` | `gpt-4o`, `gpt-4o-mini`, `o1`, `o1-mini` |
| `anthropic` | `agno.models.anthropic.Claude` | `claude-sonnet-4-6`, `claude-haiku-3-5` |
| `aws_bedrock_claude` | `agno.models.aws.Claude` | `us.anthropic.claude-sonnet-4-6-v1:0` |
| `aws_bedrock` | `agno.models.aws.AwsBedrock` | `amazon.nova-pro-v1:0` |

**NUNCA usar**: `bedrock`, `aws`, `claude`, `gemini` como provider.
**NOTA**: `gemini-2.0-flash` sera retirado el 1 de junio de 2026. Usar `gemini-2.5-flash`.

## Tools Disponibles en el Loader

| Nombre (tools.yaml) | Clase | Requiere |
|---------------------|-------|----------|
| `duckduckgo` | `DuckDuckGoTools` | Nada (builtin) |
| `crawl4ai` | `Crawl4aiTools` | Nada (builtin) |
| `reasoning` | `ReasoningTools` | Nada (builtin) |
| `github` | `GithubTools` | `PyGithub` + `GITHUB_TOKEN` env var |
| `shell` | `ShellTools` | `base_dir` en config |
| `email` | `EmailTools` | `EMAIL_*` env vars |
| `tavily` | `TavilyTools` | `TAVILY_API_KEY` |
| `workspace` | `WorkspaceTools` | Nada |
| `scheduler_mgmt` | `SchedulerTools` | `GATEWAY_URL` |
| `audio` | `AudioTools` | `OPENAI_API_KEY` |
| `yfinance` | `YFinanceTools` | `yfinance` pip package |
| `wikipedia` | `WikipediaTools` | `wikipedia` pip package |
| `arxiv` | `ArxivTools` | `arxiv` pip package |
| `calculator` | `CalculatorTools` | Nada |
| `file_tools` | `FileTools` | Nada |
| `python_tools` | `PythonTools` | Nada (riesgo de seguridad) |

**NUNCA usar en sub-agentes**: `tavily_search`, `web_search`, `search` — no son nombres de tools válidos en el loader.
**OJO**: `github` es válido (F7). Requiere registrar `GithubTools` en `loader.py`.

## Cómo Crear un Sub-Agente Válido

```yaml
# workspace/agents/ejemplo.yaml
agent:
  name: "Nombre del Agente"
  id: "nombre-agente"  # sin espacios, lowercase
  model:
    provider: google  # DEBE ser uno de la tabla de arriba
    id: gemini-2.5-flash
  instructions:
    - "Instrucciones específicas del agente."
  tools:
    - duckduckgo      # DEBE existir en la tabla de tools
    - crawl4ai
  config:
    tool_call_limit: 5
    enable_agentic_memory: false
    markdown: true
execution:
  type: local
```

## MCP Servers Disponibles

| Server | URL | Tipo |
|--------|-----|------|
| Agno Docs | `https://docs.agno.com/mcp` | streamable-http |
| Tavily | Requiere API key | streamable-http |
| Supabase | Requiere `npx` + access token | stdio |
| GitHub | Requiere `GITHUB_TOKEN` | stdio |

## Canales Disponibles

| Canal | Configuración |
|-------|---------------|
| `whatsapp` | Cloud API (Meta Business) o QR Link (Baileys bridge) o Dual |
| `slack` | Slack Bot con scopes OAuth |
| `telegram` | Bot via @BotFather |
| `agui` | Interfaz AG-UI (requiere `.[protocols]`) |
| `a2a` | Protocolo A2A (requiere `a2a.enabled: true` y `.[protocols]`) |
| Web | Siempre disponible via os.agno.com |

## Reglas de Auto-Configuración

1. Antes de crear un sub-agente, **consultar este archivo** para validar provider y tools.
2. Si necesitas un tool que no existe, **consulta MCP de Agno** (`docs.agno.com/mcp`) para ver si hay un tool builtin o MCP disponible.
3. Los sub-agentes **NO heredan** los tools del agente principal. Debes declararlos explícitamente.
4. Los sub-agentes **NO heredan** MCP servers. Si necesitan acceso a MCP, deben configurarlo en su YAML.
5. Después de crear un sub-agente, siempre llama `request_reload` para que se cargue.
6. Nunca uses nombres inventados de tools. Si no estás seguro, consulta `workspace/tools.yaml`.
