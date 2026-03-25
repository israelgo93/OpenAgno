# OpenAgno — Validación Fase 5 + Plan Fase 6 (CORREGIDO)

*Verificado contra documentación oficial de Agno, Linear (DAT-221), y canales MCP.*

---

## PARTE 1: VALIDACIÓN F5

### Resumen

| Componente | Estado | Notas |
|---|---|---|
| `gateway.py` | ✅ | Lifespan, auto-ingesta, scheduler introspección |
| `loader.py` | ⚠️ 2 issues | Sin Bedrock, `Schedule` import no verificado |
| `routes/knowledge_routes.py` | ✅ | Upload, ingest-urls, list, delete |
| `workspace/config.yaml` | ✅ | Scheduler + knowledge sections |
| `workspace/mcp.yaml` | ✅ | Tavily streamable-http |
| `workspace/integrations/` | ✅ | Patrón declarativo con merge en loader |
| `AGENT_OPERACIONES.md` | ✅ | Runbook completo |
| `management/validator.py` | ✅ | Valida schedules, URLs, Tavily, integraciones |
| `README.md` | ✅ | Refleja F5 correctamente |
| `requirements.txt` | ⚠️ | Falta `boto3`, `aioboto3` |
| `.env.example` | ⚠️ | Falta variables AWS |

### Canales verificados contra docs Agno

**WhatsApp** ✅ Compatible
- Import: `from agno.os.interfaces.whatsapp import Whatsapp`
- Docs: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`
- Phone como `user_id` + `session_id` automático
- Soporta: texto, imagen, video, audio, documentos
- Producción: `WHATSAPP_APP_SECRET` + `APP_ENV=production`
- Nuestro gateway: **compatible al 100%**

**Slack** ✅ Compatible
- Import: `from agno.os.interfaces.slack import Slack`
- Docs: `SLACK_TOKEN` + `SLACK_SIGNING_SECRET` (ambos requeridos)
- Soporta `agent`, `team`, o `workflow` como parámetro
- Parámetro `reply_to_mentions_only=True` (default) — responde a @menciones en canales, todos los DMs
- Thread timestamps como `session_id`
- Endpoint: `POST /slack/events`
- Nuestro gateway: **compatible** — `.env.example` ya tiene ambas variables

**Linear** ⚠️ No es canal nativo
- No existe `from agno.os.interfaces.linear import Linear`
- Linear es project management, no canal de chat
- Integración posible via: API GraphQL, webhooks, o tool custom
- Nuestro proyecto usa Linear para tracking (DAT-218, DAT-220, DAT-221)

**Web/Studio** ✅
- `os.agno.com` > Add OS > Local > `http://localhost:8000`
- MCP Server habilitado con `enable_mcp_server=True`

### Issues verificados en Linear

| Issue | Estado | Relevancia F6 |
|---|---|---|
| DAT-221 | Backlog | Resumen cambios, deuda técnica, sugerencias F6 |
| DAT-220 | Backlog | Runbook + ShellTools base_dir |
| DAT-218 | ✅ Done | F5 scheduler + knowledge + Tavily |
| DAT-190 | ✅ Done | Repo inicializado |

DAT-221 lista sugerencias directas para F6: reload controlado, systemd, CLI integraciones, tests unitarios, sub-agentes con integraciones.

### Hallazgos críticos de la verificación

**1. AWS Bedrock tiene DOS clases en Agno:**
- `from agno.models.aws import AwsBedrock` — Mistral, Nova, modelos genéricos
- `from agno.models.aws import Claude` — Anthropic Claude optimizado para Bedrock
- ID ejemplo: `us.anthropic.claude-sonnet-4-20250514-v1:0`
- Auth: `aws_access_key`, `aws_secret_key`, `aws_region` o env vars

**2. Scheduler es API REST, no solo YAML:**
- `POST /schedules` con `cron_expr`, `endpoint`, `payload`, `timezone`, `max_retries`
- `ScheduleManager` programático: `from agno.scheduler import ScheduleManager`
- `AgentOS(scheduler=True, scheduler_poll_interval=15)`
- CRUD completo: create, list, update, delete, enable/disable, trigger

**3. Background Hooks (nueva feature):**
- `AgentOS(run_hooks_in_background=True)`
- Hooks post-run no bloquean response
- Ideal para logging, analytics, evaluación

---

## PARTE 2: PLAN FASE 6 — CORREGIDO

### Objetivo

Autonomía operativa + AWS Bedrock + Background Service + Scheduler nativo + Onboarding actualizado.

### Arquitectura F6

```
┌──────────────────────────────────────────────────────────┐
│  service_manager.py (daemon supervisor)                   │
│  - Arranca gateway como subprocess                       │
│  - Monitorea health + señales de reload                  │
│  - Reinicia sin matar la conversación actual             │
│  └──────────┬────────────────────────────────────────┘   │
│             │                                             │
│  ┌──────────▼────────────────────────────────────────┐   │
│  │  gateway.py (AgentOS) :8000                        │   │
│  │  ├── scheduler=True (API REST nativa)             │   │
│  │  ├── run_hooks_in_background=True                 │   │
│  │  ├── Agente Principal                             │   │
│  │  │   ├── Modelo: Bedrock Claude / Gemini / GPT    │   │
│  │  │   ├── WorkspaceTools (CRUD workspace/ + reload)│   │
│  │  │   ├── SchedulerTools (via REST API nativa)     │   │
│  │  │   ├── ShellTools (sandboxed)                   │   │
│  │  │   └── MCP (docs.agno.com + custom)             │   │
│  │  ├── POST /admin/reload (señal al daemon)         │   │
│  │  └── POST /schedules (API nativa AgentOS)         │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  deploy/openagno.service (systemd, producción)            │
└──────────────────────────────────────────────────────────┘
```

---

### 6.1 — `service_manager.py` — Daemon Background

```python
"""
OpenAgno Service Manager — Gateway como servicio en segundo plano.
El agente puede solicitar reload sin matarse a sí mismo.

Uso:
  python service_manager.py start
  python service_manager.py stop
  python service_manager.py restart
  python service_manager.py status
"""
import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
PID_FILE = OPENAGNO_ROOT / "openagno.pid"
LOG_FILE = OPENAGNO_ROOT / "gateway.log"
HEALTH_URL = f"http://127.0.0.1:{PORT}/docs"
HEALTH_INTERVAL = 30
RESTART_DELAY = 3


class GatewayDaemon:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self._stop_event = threading.Event()

    def start_gateway(self) -> None:
        if self.process and self.process.poll() is None:
            print(f"[daemon] Gateway ya corriendo (PID {self.process.pid})")
            return
        log_fd = open(LOG_FILE, "a")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "gateway:app",
             "--host", HOST, "--port", str(PORT), "--workers", "1",
             "--log-level", "info"],
            cwd=str(OPENAGNO_ROOT),
            stdout=log_fd, stderr=subprocess.STDOUT,
            env={**os.environ, "OPENAGNO_ROOT": str(OPENAGNO_ROOT)},
        )
        PID_FILE.write_text(str(self.process.pid))
        print(f"[daemon] Gateway arrancado (PID {self.process.pid})")

    def stop_gateway(self, timeout: int = 10) -> None:
        if not self.process or self.process.poll() is not None:
            return
        pid = self.process.pid
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if PID_FILE.exists():
            PID_FILE.unlink()
        print(f"[daemon] Gateway detenido (PID {pid})")

    def restart_gateway(self) -> None:
        self.stop_gateway()
        time.sleep(RESTART_DELAY)
        self.start_gateway()

    def health_check(self) -> bool:
        try:
            import urllib.request
            return urllib.request.urlopen(HEALTH_URL, timeout=5).status == 200
        except Exception:
            return False

    def monitor_loop(self) -> None:
        """Monitorea health + señal de reload."""
        signal_file = OPENAGNO_ROOT / ".reload_requested"
        while not self._stop_event.is_set():
            # Gateway murió → reiniciar
            if self.process and self.process.poll() is not None:
                print(f"[daemon] Gateway murió (exit={self.process.returncode}). Reiniciando...")
                time.sleep(RESTART_DELAY)
                self.start_gateway()
            # Señal de reload del agente
            if signal_file.exists():
                print("[daemon] Señal de reload detectada.")
                signal_file.unlink()
                self.restart_gateway()
            self._stop_event.wait(HEALTH_INTERVAL)

    def run(self) -> None:
        self.start_gateway()
        monitor = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor.start()

        def _shutdown(signum, frame):
            self._stop_event.set()
            self.stop_gateway()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
        except KeyboardInterrupt:
            _shutdown(signal.SIGINT, None)


def main():
    if len(sys.argv) < 2:
        print("Uso: python service_manager.py [start|stop|restart|status]")
        sys.exit(1)

    daemon = GatewayDaemon()
    cmd = sys.argv[1]

    match cmd:
        case "start":
            daemon.run()
        case "stop":
            if PID_FILE.exists():
                os.kill(int(PID_FILE.read_text().strip()), signal.SIGTERM)
            else:
                print("[daemon] No hay PID file")
        case "restart":
            daemon.restart_gateway()
        case "status":
            pid = PID_FILE.read_text().strip() if PID_FILE.exists() else "N/A"
            print(f"PID: {pid} | Health: {'OK' if daemon.health_check() else 'FAIL'}")


if __name__ == "__main__":
    main()
```

---

### 6.2 — `loader.py` — Soporte Bedrock (DOS clases)

```python
def build_model(model_config: dict[str, Any]) -> Any:
    """Construye el modelo según la configuración.

    Proveedores verificados contra docs.agno.com:
    - google:            from agno.models.google import Gemini
    - openai:            from agno.models.openai import OpenAIChat
    - anthropic:         from agno.models.anthropic import Claude
    - aws_bedrock:       from agno.models.aws import AwsBedrock  (Mistral, Nova)
    - aws_bedrock_claude: from agno.models.aws import Claude      (Anthropic via Bedrock)
    """
    provider = model_config.get("provider", "google")
    model_id = model_config.get("id", "gemini-2.0-flash")
    aws_region = model_config.get("aws_region", os.getenv("AWS_REGION", "us-east-1"))

    match provider:
        case "google":
            from agno.models.google import Gemini
            return Gemini(id=model_id)

        case "openai":
            from agno.models.openai import OpenAIChat
            return OpenAIChat(id=model_id)

        case "anthropic":
            from agno.models.anthropic import Claude
            return Claude(id=model_id)

        case "aws_bedrock":
            # Modelos genéricos: Mistral, Amazon Nova, etc.
            from agno.models.aws import AwsBedrock
            return AwsBedrock(
                id=model_id,
                aws_region=aws_region,
            )

        case "aws_bedrock_claude":
            # Claude optimizado para Bedrock
            # Docs: https://docs.agno.com/models/providers/cloud/aws-claude/overview
            from agno.models.aws import Claude as BedrockClaude
            return BedrockClaude(
                id=model_id,
                aws_region=aws_region,
            )

        case _:
            raise ValueError(f"Proveedor no soportado: {provider}")
```

**Configuración en `workspace/config.yaml`:**

```yaml
# Claude Sonnet via Bedrock (recomendado para Anthropic sin API key directa)
model:
  provider: "aws_bedrock_claude"
  id: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  aws_region: "us-east-1"

# Amazon Nova Pro
# model:
#   provider: "aws_bedrock"
#   id: "amazon.nova-pro-v1:0"
#   aws_region: "us-east-1"

# Anthropic directo (con ANTHROPIC_API_KEY)
# model:
#   provider: "anthropic"
#   id: "claude-sonnet-4-20250514"
```

---

### 6.3 — `gateway.py` — Scheduler nativo + Background Hooks + Reload

**Cambios sobre el gateway F5 existente:**

```python
import inspect
from datetime import datetime

# ... (imports existentes) ...

# === Scheduler nativo (verificado: docs.agno.com/agent-os/scheduler/overview) ===
# AgentOS(scheduler=True, scheduler_poll_interval=15) habilita:
#   POST /schedules          — crear schedule
#   GET /schedules           — listar
#   PATCH /schedules/{id}    — actualizar
#   DELETE /schedules/{id}   — eliminar
#   POST /schedules/{id}/enable  — habilitar
#   POST /schedules/{id}/disable — deshabilitar
#   POST /schedules/{id}/trigger — ejecutar ahora
#   GET /schedules/{id}/runs     — historial

os_config = config.get("agentos", {})
scheduler_config = config.get("scheduler", {})

# Construir kwargs del scheduler
_scheduler_kwargs = {}
_agent_os_params = inspect.signature(AgentOS).parameters

if scheduler_config.get("enabled", False) and "scheduler" in _agent_os_params:
    _scheduler_kwargs["scheduler"] = True
    poll = scheduler_config.get("poll_interval", 15)
    if "scheduler_poll_interval" in _agent_os_params:
        _scheduler_kwargs["scheduler_poll_interval"] = poll
    logger.info(f"Scheduler habilitado (poll={poll}s)")

# Background Hooks (verificado: docs.agno.com/agent-os/background-tasks/overview)
_hooks_kwargs = {}
if "run_hooks_in_background" in _agent_os_params:
    _hooks_kwargs["run_hooks_in_background"] = True
    logger.info("Background Hooks habilitados")

agent_os = AgentOS(
    id=os_config.get("id", "agnobot-gateway"),
    name=os_config.get("name", "AgnoBot Platform"),
    agents=all_agents,
    teams=teams if teams else None,
    interfaces=interfaces,
    knowledge=[knowledge] if knowledge else None,
    db=db,
    registry=registry,
    tracing=os_config.get("tracing", True),
    enable_mcp_server=ws["mcp_config"].get("expose", {}).get("enabled", True),
    base_app=base_app,
    on_route_conflict="preserve_base_app",
    **_scheduler_kwargs,
    **_hooks_kwargs,
)

# === Endpoints admin ===
OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))

@base_app.post("/admin/reload")
async def admin_reload():
    """El agente solicita reload. El daemon detecta la señal y reinicia."""
    signal_file = OPENAGNO_ROOT / ".reload_requested"
    signal_file.write_text(datetime.now().isoformat())
    return {"status": "reload_requested"}

@base_app.get("/admin/health")
async def admin_health():
    return {
        "status": "healthy",
        "agents": [a.id for a in all_agents],
        "teams": [t.id for t in teams] if teams else [],
        "channels": config.get("channels", []),
        "model": config.get("model", {}),
        "scheduler": scheduler_config.get("enabled", False),
    }
```

---

### 6.4 — `tools/workspace_tools.py` — Autonomía del Agente

```python
"""
WorkspaceTools — El agente puede auto-configurarse.
CRUD sobre workspace/ con backup automático.
"""
import os
import yaml
import shutil
from pathlib import Path
from datetime import datetime

from agno.tools import Toolkit
from agno.utils.log import logger

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.parent.resolve()))
WORKSPACE_DIR = OPENAGNO_ROOT / "workspace"
BACKUPS_DIR = OPENAGNO_ROOT / "backups"


class WorkspaceTools(Toolkit):
    def __init__(self):
        super().__init__(name="workspace_tools")
        self.register(self.read_workspace_file)
        self.register(self.write_workspace_file)
        self.register(self.list_workspace)
        self.register(self.create_sub_agent)
        self.register(self.update_instructions)
        self.register(self.toggle_tool)
        self.register(self.request_reload)

    def _backup(self, file_path: Path) -> str:
        BACKUPS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = BACKUPS_DIR / f"{file_path.stem}.{ts}.bak{file_path.suffix}"
        if file_path.exists():
            shutil.copy2(file_path, backup_path)
            return f"Backup: {backup_path.name}"
        return "Archivo nuevo, sin backup"

    def read_workspace_file(self, filename: str) -> str:
        """Lee un archivo del workspace. Ej: 'config.yaml', 'instructions.md'."""
        path = WORKSPACE_DIR / filename
        if not path.exists():
            return f"Error: {filename} no existe"
        if not path.resolve().is_relative_to(WORKSPACE_DIR.resolve()):
            return "Error: ruta fuera del workspace"
        return path.read_text(encoding="utf-8")

    def write_workspace_file(self, filename: str, content: str) -> str:
        """Escribe en workspace/. Crea backup automáticamente."""
        path = WORKSPACE_DIR / filename
        if not path.resolve().is_relative_to(WORKSPACE_DIR.resolve()):
            return "Error: ruta fuera del workspace"
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Escrito: {filename}. {backup_msg}. Reload necesario."

    def list_workspace(self) -> str:
        """Lista estructura del workspace."""
        result = []
        for item in sorted(WORKSPACE_DIR.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                result.append(str(item.relative_to(WORKSPACE_DIR)))
        return "\n".join(result) if result else "Workspace vacío"

    def create_sub_agent(
        self, name: str, agent_id: str, role: str,
        tools: list[str], instructions: list[str],
        model_provider: str = "google", model_id: str = "gemini-2.0-flash",
    ) -> str:
        """Crea un sub-agente en workspace/agents/."""
        agent_data = {
            "agent": {
                "name": name, "id": agent_id, "role": role,
                "model": {"provider": model_provider, "id": model_id},
                "tools": tools, "instructions": instructions,
                "config": {"tool_call_limit": 5, "enable_agentic_memory": False, "markdown": True},
            },
            "execution": {"type": "local"},
        }
        filename = f"agents/{agent_id.replace('-', '_')}.yaml"
        path = WORKSPACE_DIR / filename
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(agent_data, f, default_flow_style=False, allow_unicode=True)
        return f"Sub-agente '{name}' creado en {filename}. {backup_msg}. Reload necesario."

    def update_instructions(self, new_instructions: str) -> str:
        """Actualiza workspace/instructions.md."""
        path = WORKSPACE_DIR / "instructions.md"
        backup_msg = self._backup(path)
        path.write_text(new_instructions, encoding="utf-8")
        return f"Instrucciones actualizadas. {backup_msg}. Reload necesario."

    def toggle_tool(self, tool_name: str, enabled: bool) -> str:
        """Activa/desactiva un tool en tools.yaml."""
        path = WORKSPACE_DIR / "tools.yaml"
        if not path.exists():
            return "Error: tools.yaml no existe"
        data = yaml.safe_load(path.read_text()) or {}
        for section in ("builtin", "optional"):
            for tool in data.get(section, []):
                if tool.get("name") == tool_name:
                    backup_msg = self._backup(path)
                    tool["enabled"] = enabled
                    with open(path, "w") as f:
                        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                    return f"Tool '{tool_name}' {'activado' if enabled else 'desactivado'}. {backup_msg}"
        return f"Tool '{tool_name}' no encontrado"

    def request_reload(self) -> str:
        """Solicita reload al daemon (no mata el proceso actual)."""
        signal_file = OPENAGNO_ROOT / ".reload_requested"
        signal_file.write_text(datetime.now().isoformat())
        return "Reload solicitado. El daemon reiniciará el gateway en ~5s."
```

---

### 6.5 — `tools/scheduler_tools.py` — Crons via API REST nativa

**Cambio clave vs plan anterior:** Usa la API REST del scheduler de AgentOS (`POST /schedules`) en vez de escribir YAML.

```python
"""
SchedulerTools — Gestión de crons via API REST nativa de AgentOS.
Docs: https://docs.agno.com/agent-os/scheduler/overview

El scheduler de AgentOS expone:
  POST   /schedules                 — crear
  GET    /schedules                 — listar
  PATCH  /schedules/{id}            — actualizar
  DELETE /schedules/{id}            — eliminar
  POST   /schedules/{id}/enable     — habilitar
  POST   /schedules/{id}/disable    — deshabilitar
  POST   /schedules/{id}/trigger    — ejecutar ahora
  GET    /schedules/{id}/runs       — historial
"""
import os
import json
from typing import Optional
import urllib.request
import urllib.error

from agno.tools import Toolkit
from agno.utils.log import logger

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")


class SchedulerTools(Toolkit):
    """Gestiona crons y recordatorios via la API REST nativa del scheduler."""

    def __init__(self, base_url: str = GATEWAY_URL):
        super().__init__(name="scheduler_tools")
        self.base_url = base_url.rstrip("/")
        self.register(self.list_schedules)
        self.register(self.create_schedule)
        self.register(self.delete_schedule)
        self.register(self.trigger_schedule)

    def _api_call(self, method: str, path: str, data: dict | None = None) -> dict:
        """Llamada a la API REST del scheduler."""
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            url, data=body, method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    def list_schedules(self) -> str:
        """Lista todos los schedules/recordatorios activos."""
        result = self._api_call("GET", "/schedules")
        if "error" in result:
            return f"Error: {result['error']}"
        schedules = result if isinstance(result, list) else result.get("schedules", [])
        if not schedules:
            return "No hay schedules configurados."
        lines = []
        for s in schedules:
            status = "✅" if s.get("enabled", True) else "⏸️"
            lines.append(
                f"- {status} {s.get('name', '?')} | {s.get('cron_expr', '?')} | "
                f"→ {s.get('endpoint', '?')} | ID: {s.get('id', '?')}"
            )
        return "\n".join(lines)

    def create_schedule(
        self,
        name: str,
        cron_expr: str,
        message: str,
        agent_id: str = "agnobot-main",
        timezone: str = "America/Guayaquil",
    ) -> str:
        """Crea un recordatorio/schedule.

        Args:
            name: Nombre descriptivo (ej: "Resumen matutino")
            cron_expr: Expresión cron (ej: "0 9 * * 1-5" = L-V 9am)
            message: Mensaje que el agente procesará
            agent_id: ID del agente que ejecutará la tarea
            timezone: Zona horaria IANA
        """
        data = {
            "name": name,
            "cron_expr": cron_expr,
            "endpoint": f"/agents/{agent_id}/runs",
            "method": "POST",
            "payload": {"message": message},
            "timezone": timezone,
            "max_retries": 2,
            "retry_delay_seconds": 30,
        }
        result = self._api_call("POST", "/schedules", data)
        if "error" in result:
            return f"Error creando schedule: {result['error']}"
        return f"Schedule '{name}' creado ({cron_expr}, tz={timezone}). ID: {result.get('id', '?')}"

    def delete_schedule(self, schedule_id: str) -> str:
        """Elimina un schedule por ID."""
        result = self._api_call("DELETE", f"/schedules/{schedule_id}")
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Schedule {schedule_id} eliminado."

    def trigger_schedule(self, schedule_id: str) -> str:
        """Ejecuta un schedule manualmente ahora."""
        result = self._api_call("POST", f"/schedules/{schedule_id}/trigger")
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Schedule {schedule_id} ejecutado manualmente."
```

---

### 6.6 — `loader.py` — Registrar nuevos tools

```python
# En build_tools(), agregar al match de optional tools:

case "workspace":
    from tools.workspace_tools import WorkspaceTools
    tools.append(WorkspaceTools())
    logger.info("WorkspaceTools activado — auto-configuración habilitada")

case "scheduler_mgmt":
    from tools.scheduler_tools import SchedulerTools
    tools.append(SchedulerTools())
    logger.info("SchedulerTools activado — gestión de crons via API REST")
```

---

### 6.7 — `workspace/tools.yaml` — Nuevos tools

```yaml
optional:
  # ... (existentes: email, tavily, shell, spotify) ...

  - name: workspace
    enabled: true
    description: "Auto-configuración del workspace (CRUD agentes, instrucciones, tools)"

  - name: scheduler_mgmt
    enabled: true
    description: "Gestión de recordatorios y crons via API REST nativa"
```

---

### 6.8 — Onboarding CLI actualizado

```python
# En management/cli.py — PASO 2: Modelo

print("\n🧠 Modelo de IA:")
print("  [1] Gemini 2.0 Flash (Google — multimodal, recomendado)")
print("  [2] Claude Sonnet 4 (Anthropic — directo)")
print("  [3] Claude Sonnet 4 via Bedrock (AWS — sin API key Anthropic)")
print("  [4] Claude Opus 4 via Bedrock (AWS)")
print("  [5] GPT-4.1 (OpenAI)")
print("  [6] Amazon Nova Pro (AWS Bedrock)")
model_choice = input("  Selección [1]: ").strip() or "1"

model_map = {
    "1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
    "2": ("anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY"),
    "3": ("aws_bedrock_claude", "us.anthropic.claude-sonnet-4-20250514-v1:0", "AWS_ACCESS_KEY_ID"),
    "4": ("aws_bedrock_claude", "us.anthropic.claude-opus-4-20250805-v1:0", "AWS_ACCESS_KEY_ID"),
    "5": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
    "6": ("aws_bedrock", "amazon.nova-pro-v1:0", "AWS_ACCESS_KEY_ID"),
}

provider, model_id, key_name = model_map.get(model_choice, model_map["1"])

# Si es AWS, pedir credenciales AWS
aws_vars = {}
if provider.startswith("aws_bedrock"):
    aws_vars["AWS_ACCESS_KEY_ID"] = input("  → AWS Access Key ID: ").strip()
    aws_vars["AWS_SECRET_ACCESS_KEY"] = input("  → AWS Secret Access Key: ").strip()
    aws_vars["AWS_REGION"] = input("  → AWS Region [us-east-1]: ").strip() or "us-east-1"
else:
    api_key = input(f"  → {key_name}: ").strip()
```

---

### 6.9 — `workspace/instructions.md` — Sección autonomía

Agregar al final:

```markdown
## Auto-Configuración (F6)

Tienes herramientas para auto-configurarte:

### WorkspaceTools
- `read_workspace_file` / `write_workspace_file` — CRUD del workspace (backup automático)
- `create_sub_agent` — Crear nuevos sub-agentes desde YAML
- `update_instructions` — Modificar tus propias instrucciones
- `toggle_tool` — Activar/desactivar herramientas
- `request_reload` — Solicitar reinicio al daemon

### SchedulerTools (via API REST nativa AgentOS)
- `list_schedules` — Ver crons activos
- `create_schedule` — Crear recordatorio (ej: cron "0 9 * * 1-5" = L-V 9am)
- `delete_schedule` — Eliminar por ID
- `trigger_schedule` — Ejecutar manualmente

### Reglas
1. Siempre haz backup (automático con WorkspaceTools)
2. Tras cambios en archivos, llama `request_reload`
3. Nunca modifiques `.env` — pide al operador
4. Consulta docs de Agno via MCP si tienes dudas
5. Los schedules se crean vía API REST (no necesitan reload)
```

---

### 6.10 — Archivos de soporte

**`.env.example` — agregar:**
```bash
# === AWS Bedrock (F6) ===
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_REGION=us-east-1
```

**`requirements.txt` — agregar:**
```
# === F6: AWS Bedrock ===
boto3>=1.35
aioboto3>=13.0
```

**`deploy/openagno.service`:**
```ini
[Unit]
Description=OpenAgno AI Agent Platform
After=network.target

[Service]
Type=simple
User=openagno
WorkingDirectory=/opt/openagno
Environment=OPENAGNO_ROOT=/opt/openagno
EnvironmentFile=/opt/openagno/.env
ExecStart=/opt/openagno/.venv/bin/python service_manager.py start
ExecStop=/opt/openagno/.venv/bin/python service_manager.py stop
ExecReload=/opt/openagno/.venv/bin/python service_manager.py restart
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### Checklist Fase 6

| # | Tarea | Prioridad |
|---|-------|-----------|
| 1 | `service_manager.py` — daemon con monitor + signal file | **Alta** |
| 2 | `loader.py` — `build_model()` con `aws_bedrock` + `aws_bedrock_claude` | **Alta** |
| 3 | `tools/workspace_tools.py` — WorkspaceTools completo | **Alta** |
| 4 | `tools/scheduler_tools.py` — via API REST nativa (no YAML) | **Alta** |
| 5 | `gateway.py` — `scheduler=True`, `run_hooks_in_background=True`, `/admin/reload` | **Alta** |
| 6 | `management/cli.py` — opciones Bedrock | Alta |
| 7 | `loader.py` — registrar `workspace` y `scheduler_mgmt` tools | Alta |
| 8 | `workspace/tools.yaml` — declarar nuevos tools | Media |
| 9 | `workspace/instructions.md` — sección auto-configuración | Media |
| 10 | `deploy/openagno.service` — systemd unit | Media |
| 11 | `.env.example` + `requirements.txt` — AWS vars y deps | Baja |
| 12 | Test: Bedrock Claude responde via gateway | **Alta** |
| 13 | Test: Agente crea sub-agente via WorkspaceTools + reload | **Alta** |
| 14 | Test: Agente crea schedule via `POST /schedules` | **Alta** |
| 15 | Test: daemon reinicia tras `.reload_requested` | **Alta** |
| 16 | Test: `service_manager.py start` sobrevive crash | Alta |
| 17 | Test: ShellTools ejecuta sin problemas de permisos | Media |
| 18 | Crear issue Linear DAT-XXX para tracking F6 | Media |

### Notas verificadas

1. **Bedrock Claude:** `from agno.models.aws import Claude` (NO `AwsBedrock` para Anthropic). ID con prefijo region: `us.anthropic.claude-sonnet-4-20250514-v1:0`. Auth vía env vars `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION`.

2. **Scheduler nativo:** `AgentOS(scheduler=True, scheduler_poll_interval=15)`. Expone API REST completa en `/schedules`. También existe `ScheduleManager` programático: `from agno.scheduler import ScheduleManager`. NO necesita escribir YAML + reload.

3. **Background Hooks:** `AgentOS(run_hooks_in_background=True)`. Los hooks post-run no bloquean. Requiere `agno[os]`. Ideal para logging, analytics, auto-evaluación.

4. **Signal file pattern:** `.reload_requested` evita que el agente mate su propio proceso. El daemon lo lee cada 30s.

5. **Linear no es canal Agno.** Es herramienta de project management. Integramos via MCP de Linear o API GraphQL, no como interface de chat.

---

*Verificado contra: docs.agno.com (WhatsApp, Slack, Bedrock, Scheduler, Background Hooks), Linear (DAT-221), MCP Agno.*
*25 de marzo de 2026*
