# Prompt de Implementación — Fase 9: Estabilización + CLI Producto

*Fecha: 28 de marzo de 2026*
*Issues: DAT-252 a DAT-258*
*Versión actual: v1.0.0 (post-F8)*
*Versión objetivo: v1.1.0*

---

## Contexto

OpenAgno es una plataforma de agentes IA auto-configurables construida sobre Agno Framework. Fases 1-8 completadas. La Fase 9 estabiliza la base, cierra deuda técnica y transforma el proyecto en un producto CLI distribuible.

## Reglas Obligatorias

1. **Solo Agno Framework** — nunca LangChain, CrewAI, ni otros
2. **Imports**: `from agno.os import AgentOS`, `from agno.vectordb.pgvector import PgVector`
3. **PgVector**: siempre `SearchType.hybrid` con `OpenAIEmbedder(id="text-embedding-3-small")`
4. **PostgresDb unificado** — sesiones, memorias, contents
5. **Memoria**: `enable_agentic_memory=True`, NO combinar con `update_memory_on_run=True`
6. **MCP**: no usar `reload=True` con MCPTools en AgentOS
7. **Secretos**: solo en `.env` con `${VAR}` en YAML
8. **AWS Bedrock Claude**: `from agno.models.aws import Claude` (NO `AwsBedrock`)
9. **Verificar contra docs.agno.com** antes de asumir compatibilidad

---

## Orden de Implementación

### Paso 1: Fix bugs críticos (DAT-252, DAT-253, DAT-254)

#### 1.1 — DAT-252: Deduplicación WhatsApp

En `gateway.py`, agregar deduplicación ANTES del procesamiento:

```python
import time
from collections import OrderedDict

class MessageDeduplicator:
    """Cache LRU con TTL para deduplicar mensajes."""
    def __init__(self, ttl: int = 60, max_size: int = 1000):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size

    def is_duplicate(self, message_id: str) -> bool:
        now = time.time()
        # Limpiar expirados
        while self._cache:
            oldest_key, oldest_time = next(iter(self._cache.items()))
            if now - oldest_time > self.ttl:
                self._cache.pop(oldest_key)
            else:
                break
        # Limitar tamaño
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        if message_id in self._cache:
            return True
        self._cache[message_id] = now
        return False

_dedup = MessageDeduplicator()
```

Aplicar en el handler de WhatsApp Cloud API:
```python
# Dentro del webhook handler de WhatsApp
message_id = request_data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0].get("id", "")
if message_id and _dedup.is_duplicate(message_id):
    logger.info(f"Mensaje duplicado ignorado: {message_id}")
    return {"status": "ok"}  # 200 para que Meta no reintente
```

Y en `/whatsapp-qr/incoming`:
```python
@app.post("/whatsapp-qr/incoming")
async def wa_qr_incoming(request: dict):
    msg_id = request.get("message_id", "")
    if msg_id and _dedup.is_duplicate(msg_id):
        return {"status": "duplicate_ignored"}
    # ... resto del handler
```

**IMPORTANTE:** Siempre retornar 200 a Meta, incluso si es duplicado. Si no, Meta reintenta.

#### 1.2 — DAT-253: Sanitizar historial cross-model

En `gateway.py` o donde se llame `agent.arun()`:

```python
def sanitize_history_for_provider(messages: list, provider: str) -> list:
    """Limpia tool_use entries incompatibles al cambiar de provider."""
    if provider in ("anthropic", "aws_bedrock"):
        clean = []
        for msg in messages:
            # Filtrar mensajes con tool_use_id no-string (Gemini genera dicts)
            if hasattr(msg, 'role') and msg.role == 'tool':
                if hasattr(msg, 'tool_use_id'):
                    if not isinstance(msg.tool_use_id, str) or not msg.tool_use_id:
                        continue  # Skip este mensaje
            clean.append(msg)
        return clean
    return messages
```

Alternativa más simple — en `tools/workspace_tools.py`, al cambiar modelo:
```python
async def update_model(self, provider: str, model_id: str):
    """Cambia el modelo del agente. LIMPIA sesiones si cambia provider."""
    current_provider = self._get_current_provider()
    if current_provider != provider:
        logger.warning(f"Cambiando provider {current_provider} → {provider}. Sesiones previas pueden ser incompatibles.")
        # Agregar nota en instrucciones del agente
    # ... actualizar config.yaml
```

#### 1.3 — DAT-254: Fix MCP stdio

**ANTES de implementar**, verificar la API de MCPTools en docs.agno.com:

```python
# Verificar contra docs.agno.com/tools/mcp/overview
# La firma correcta para stdio es:
from agno.tools.mcp import MCPTools

# HTTP transport
mcp_http = MCPTools(url="https://docs.agno.com/mcp")

# Stdio transport — verificar parámetros exactos
mcp_stdio = MCPTools(
    command="npx",
    args=["-y", "@supabase/mcp-server-supabase@latest", "--access-token", token],
    # env=... si es necesario
)
```

En `loader.py`, corregir `build_mcp_tools()`:
```python
def build_mcp_tools(mcp_config: dict) -> list:
    """Construye lista de MCPTools desde mcp.yaml."""
    tools = []
    servers = mcp_config.get("servers", [])
    for server in servers:
        if not server.get("enabled", False):
            continue
        
        name = server.get("name", "unknown")
        transport = server.get("transport", "streamable-http")
        
        try:
            if transport == "streamable-http":
                url = server.get("url", "")
                headers = server.get("headers", {})
                # Resolver variables ${VAR}
                url = _resolve_env_vars(url)
                headers = {k: _resolve_env_vars(v) for k, v in headers.items()}
                mcp = MCPTools(url=url, headers=headers if headers else None)
                tools.append(mcp)
                logger.info(f"MCP server '{name}' (HTTP): {url}")
                
            elif transport == "stdio":
                command = server.get("command", "")
                args = server.get("args", [])
                env = server.get("env", {})
                # Resolver variables ${VAR}
                args = [_resolve_env_vars(str(a)) for a in args]
                env = {k: _resolve_env_vars(v) for k, v in env.items()}
                mcp = MCPTools(command=command, args=args, env=env if env else None)
                tools.append(mcp)
                logger.info(f"MCP server '{name}' (stdio): {command} {' '.join(args[:2])}...")
                
        except Exception as e:
            logger.warning(f"MCP server '{name}' no pudo inicializarse: {e}")
    
    return tools
```

---

### Paso 2: CLI como producto (DAT-255)

#### 2.1 — Crear estructura del paquete

```bash
mkdir -p openagno/commands openagno/core openagno/templates
touch openagno/__init__.py openagno/__main__.py openagno/cli.py
touch openagno/commands/__init__.py
touch openagno/core/__init__.py
```

#### 2.2 — `openagno/__init__.py`

```python
"""OpenAgno — Build autonomous AI agents with declarative YAML."""
__version__ = "1.1.0"
```

#### 2.3 — `openagno/__main__.py`

```python
"""Allow running as `python -m openagno`."""
from openagno.cli import app
app()
```

#### 2.4 — `openagno/cli.py`

```python
"""OpenAgno CLI — main entry point."""
import typer
from rich.console import Console

app = typer.Typer(
    name="openagno",
    help="Build autonomous AI agents with declarative YAML configuration.",
    no_args_is_help=True,
)
console = Console()

# Import command groups
from openagno.commands.init import init_command
from openagno.commands.start import start_command
from openagno.commands.stop import stop_command
from openagno.commands.restart import restart_command
from openagno.commands.status import status_command
from openagno.commands.logs import logs_command
from openagno.commands.create import create_app
from openagno.commands.add import add_app
from openagno.commands.validate import validate_command
from openagno.commands.templates import templates_app
from openagno.commands.deploy import deploy_app

# Register commands
app.command("init")(init_command)
app.command("start")(start_command)
app.command("stop")(stop_command)
app.command("restart")(restart_command)
app.command("status")(status_command)
app.command("logs")(logs_command)
app.command("validate")(validate_command)

# Register sub-apps
app.add_typer(create_app, name="create", help="Create agents and resources")
app.add_typer(add_app, name="add", help="Add channels and tools")
app.add_typer(templates_app, name="templates", help="Manage agent templates")
app.add_typer(deploy_app, name="deploy", help="Deploy to various targets")

if __name__ == "__main__":
    app()
```

#### 2.5 — `openagno/commands/init.py`

```python
"""openagno init — Create a new workspace."""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()

def init_command(
    template: str = typer.Option(None, "--template", "-t", help="Template to use"),
    path: Path = typer.Option(".", "--path", "-p", help="Directory to create workspace in"),
):
    """Initialize a new OpenAgno workspace."""
    workspace_dir = path / "workspace"
    
    if workspace_dir.exists():
        if not Confirm.ask(f"[yellow]workspace/ already exists at {path}. Overwrite?[/]"):
            raise typer.Abort()
    
    if template:
        _init_from_template(template, path)
    else:
        _init_wizard(path)
    
    console.print(f"\n[green]✓ Workspace created at {workspace_dir}[/]")
    console.print("\n[bold]Next steps:[/]")
    console.print("  1. Edit workspace/instructions.md with your agent's personality")
    console.print("  2. Add your API keys to .env")
    console.print("  3. Run: openagno start")


def _init_from_template(template_id: str, path: Path):
    """Create workspace from a template."""
    import shutil
    from importlib.resources import files
    
    template_dir = files("openagno.templates") / template_id
    if not template_dir.is_dir():
        console.print(f"[red]Template '{template_id}' not found.[/]")
        console.print("Run 'openagno templates list' to see available templates.")
        raise typer.Exit(1)
    
    workspace_dir = path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy template files
    for f in template_dir.iterdir():
        if f.name == "README.md":
            continue
        dest = workspace_dir / f.name
        if f.is_dir():
            shutil.copytree(f, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(f, dest)
    
    # Create .env.example
    _create_env_example(path)
    console.print(f"[green]Created workspace from template: {template_id}[/]")


def _init_wizard(path: Path):
    """Interactive wizard to create workspace."""
    # Migrar lógica existente de management/cli.py aquí
    # pero con Typer + Rich en vez de input() crudo
    
    console.print("\n[bold blue]🤖 OpenAgno Setup Wizard[/]\n")
    
    agent_name = Prompt.ask("Agent name", default="AgnoBot")
    
    provider = Prompt.ask(
        "LLM Provider",
        choices=["google", "openai", "anthropic", "aws_bedrock", "groq"],
        default="google",
    )
    
    # ... resto del wizard migrado de management/cli.py
    # Generar config.yaml, instructions.md, tools.yaml, mcp.yaml
```

#### 2.6 — `openagno/commands/start.py`

```python
"""openagno start — Start the gateway."""
import typer
from rich.console import Console

console = Console()

def start_command(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as background daemon"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
):
    """Start the OpenAgno gateway."""
    from openagno.core.service_manager import GatewayManager
    
    manager = GatewayManager()
    
    if manager.is_running():
        console.print("[yellow]Gateway is already running.[/]")
        raise typer.Exit(1)
    
    if daemon:
        manager.start_daemon(port=port)
        console.print(f"[green]✓ Gateway started as daemon on port {port}[/]")
        console.print(f"  PID: {manager.get_pid()}")
        console.print(f"  Logs: openagno logs --follow")
    else:
        console.print(f"[blue]Starting gateway on port {port}...[/]")
        manager.start_foreground(port=port)
```

---

### Paso 3: Templates (DAT-256)

Crear 5 directorios bajo `openagno/templates/` con workspace YAML válido para cada tipo de agente. Ver issue DAT-256 para detalles de cada template.

**Cada template DEBE incluir:**
- `config.yaml` — configuración completa y válida
- `instructions.md` — personalidad especializada
- `tools.yaml` — solo los tools relevantes habilitados
- `mcp.yaml` — MCP servers relevantes
- `README.md` — descripción y uso

---

### Paso 4: Tests (DAT-257)

Crear tests mínimos pero funcionales. Priorizar:
1. `test_loader.py` — que load_yaml no crashee con workspace válido
2. `test_validator.py` — que detecte configs inválidas
3. `test_templates.py` — que todos los templates tengan YAML válido
4. `test_dedup.py` — que la deduplicación funcione correctamente

---

### Paso 5: Rate limiting + deps (DAT-258)

Último paso, menor prioridad.

---

## Validación Final Fase 9

```bash
# 1. Tests pasan
pytest tests/ -v

# 2. CLI funciona
openagno --help
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start  # Ctrl+C para detener

# 3. Gateway arranca sin errores
python gateway.py  # backward compat

# 4. WhatsApp no procesa duplicados
# Enviar mensaje → verificar en logs que solo se procesa 1 vez

# 5. MCP stdio se conecta
# Habilitar supabase en mcp.yaml → verificar en logs
```

## Archivos Nuevos

| Archivo | Descripción |
|---------|-------------|
| `openagno/__init__.py` | Package version |
| `openagno/__main__.py` | `python -m openagno` |
| `openagno/cli.py` | Typer app principal |
| `openagno/commands/*.py` | Comandos CLI |
| `openagno/core/loader.py` | Refactored loader |
| `openagno/core/gateway.py` | Refactored gateway |
| `openagno/core/service_manager.py` | Daemon manager |
| `openagno/templates/*/` | 5 templates |
| `openagno/templates/registry.yaml` | Índice de templates |
| `pyproject.toml` | Package config |
| `tests/` | Tests unitarios |
| `requirements-dev.txt` | Dev dependencies |
| `.github/workflows/test.yml` | CI pipeline |

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `gateway.py` | Import desde openagno.core + deduplicación WhatsApp |
| `loader.py` | Import desde openagno.core + fix MCP stdio |
| `security.py` | Rate limiter |
| `routes/knowledge_routes.py` | @limiter decorators |
| `tools/workspace_tools.py` | Warning al cambiar provider |
| `requirements.txt` | +typer, +slowapi, +rich |

---

*Verificado contra: Linear DAT-250→258, docs.agno.com, GitHub OpenAgno, gateway.log*
*28 de marzo de 2026*
