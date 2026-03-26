# OpenAgno — Fase 7: Estabilización, Auto-Consciencia del Agente y Seguridad

*Fecha: 26 de marzo de 2026*
*Versión objetivo: v0.8.0*

---

## Diagnóstico Pre-Fase 7

### Errores Críticos Detectados en `gateway.log`

| # | Error | Causa Raíz | Impacto |
|---|-------|------------|---------|
| 1 | `scheduler_base_url not set, using default http://127.0.0.1:7777` → `All connection attempts failed` | El scheduler de AgentOS usa internamente puerto 7777 para ejecutar schedules pero el gateway corre en 8000. No se configuró `scheduler_base_url`. | **Todos los schedules/recordatorios fallan al ejecutarse.** El cron se dispara, pero nunca llega al agente. |
| 2 | `WARNING Tool 'tavily' no reconocido en senior_dev_agent.yaml` / `Tool 'github' no reconocido` | El agente principal creó un sub-agente via `WorkspaceTools.create_sub_agent()` con tools que no existen en el registro del loader (`tavily`, `github`). El agente no sabe qué tools están disponibles. | Sub-agente cargado sin herramientas. Al intentar analizar un repo, falló con timeout en `tavily_crawl`. |
| 3 | `WARNING Modelo invalido en senior_dev_agent.yaml: Proveedor de modelo no soportado: bedrock` | El agente usó `bedrock` como provider en vez de `aws_bedrock_claude`. No conoce los nombres internos válidos de proveedores. | Sub-agente no se carga → se ignora silenciosamente. |
| 4 | `ERROR Rate limit exceeded: 429` → `Non-retryable model provider error` | El fallback automático detecta el 429 (`WARNING Rate limit exceeded`) pero Agno marca el error como "Non-retryable" antes de que el wrapper pueda hacer swap. El retry/fallback no intercepta a tiempo. | Agente no responde. El usuario recibe silencio. |
| 5 | `ERROR messages: text content blocks must be non-empty` (400) | Mensaje vacío enviado al modelo (probablemente un webhook de WhatsApp con media sin texto, o un audio que no se transcribió). | Error 400, respuesta perdida. |
| 6 | `ERROR Failed to send WhatsApp text message: 401 Unauthorized` / `Session has expired` | Token de WhatsApp Business API expiró. No hay mecanismo de alerta ni renovación. | Gateway sigue recibiendo mensajes pero no puede responder. Sin notificación al operador. |
| 7 | `POST /schedules HTTP/1.1 422 Unprocessable Entity` (múltiples intentos) | El agente intenta crear schedules con formatos de cron inválidos o campos incorrectos. No valida antes de enviar. | Múltiples reintentos fallidos antes de acertar. |

### Hallazgos del Análisis QA (`Analisis_OpenAgno_QA`)

| Severidad | Issue | Estado |
|-----------|-------|--------|
| CRÍTICO | SQL Injection en `knowledge_routes.py` (nombre de tabla dinámico sin whitelist) | Abierto |
| CRÍTICO | Sin autenticación en endpoints REST (`/upload`, `/search`, `/schedules`) | Abierto |
| CRÍTICO | Credenciales Docker por defecto (`ai/ai/ai`) | Abierto |
| ADVERTENCIA | Dependencias sin pinning de versiones | Abierto |
| ADVERTENCIA | Sin rate limiting en endpoints | Abierto |
| ADVERTENCIA | `except HTTPException:` vacío traga errores | Abierto |
| ADVERTENCIA | DB URL con credenciales puede loggearse en tracebacks | Abierto |

### Hallazgos de Slack (`#openagno`)

El canal registra todas las fases F1→v0.7 correctamente documentadas. Puntos relevantes:

- F2 corrigió `MemoryManager` requerido para `enable_agentic_memory` (no documentado originalmente).
- Se eliminaron `enable_user_memories` y `enable_session_summaries` (no documentados en Agno).
- Los mensajes de actualización se envían via Claude/Cursor, confirmando integración activa.
- No hay reportes de pruebas de Slack como canal operativo (solo WhatsApp y Web están validados en producción).

### Hallazgos de Linear (Proyecto OpenAgno)

| Issue | Estado | Relevancia F7 |
|-------|--------|---------------|
| DAT-217 | **Backlog** | Plan F4 (Remote Agents + MCP Avanzado) nunca se implementó. Remote Execution pendiente. |
| DAT-224 | Done | Fix fallback 429 marcado como resuelto, pero el log posterior muestra que **sigue fallando** (el wrapper intercepta pero Agno lanza `Non-retryable` antes del retry). |
| DAT-225 | Done | TTS funcional tras fix, confirmado en log. |
| DAT-190→223 | Done | F1-F6 + AudioTools completados. |

**Hallazgo clave**: DAT-217 confirma que **Remote Execution** (Fase 4) quedó incompleta. El loader tiene código stub para `execution.type: remote` pero nunca se validó con `RemoteAgent`.

### Hallazgos del README y Repositorio

- Badge muestra v0.7.0 correctamente.
- **No hay directorio `/tests`** — sin cobertura de tests automatizados.
- **No hay `.dockerignore`** — riesgo de incluir `.env` en imágenes Docker.
- **No documenta modelo de seguridad** — quién puede llamar qué endpoint.
- Las dependencias en `requirements.txt` no están pineadas (builds no reproducibles).

### Hallazgos de Agno Framework (Releases Marzo 2026)

Funcionalidades nuevas de Agno que OpenAgno **no está aprovechando**:

| Feature Agno | Import / Uso | Impacto para OpenAgno |
|--------------|-------------|----------------------|
| **GithubTools** | `from agno.tools.github import GithubTools` (req: `PyGithub` + `GITHUB_TOKEN`) | **El agente intentó usar `github` como tool pero no existe en el loader.** GithubTools es builtin de Agno y debería registrarse. |
| **Telegram Interface** | `from agno.os.interfaces.telegram import Telegram` | Nuevo canal disponible. Bajo esfuerzo, alto impacto. |
| **PgVector `similarity_threshold`** | Parámetro en PgVector search | Reduce ruido en búsquedas RAG. |
| **MCPTools race condition fix** | Actualizar `agno[os]` | Fix para llamadas MCP paralelas que creaban sesiones duplicadas (posible causa de timeouts en `tavily_crawl`). |
| **Slack `user_id` fix** | Actualizar `agno[os]` | Bug fix que impedía propagar `user_id` en Slack interface. |
| **AWS Bedrock credential refresh** | Actualizar `agno[os]` | Fix para refrescar credenciales AWS en cada request (evita expiración de tokens temporales). |
| **Session Search Tool** | `search_past_sessions` + `read_past_session` | Agentes pueden buscar sesiones anteriores. |
| **Approval System** | Decorador `@approval` | Para acciones sensibles que requieren confirmación del operador. |

### Problema Central: Falta de Auto-Consciencia del Agente

El agente principal puede auto-configurarse (WorkspaceTools) pero **no tiene conocimiento de**:

1. **Qué tools existen** en el ecosistema (solo sabe los que tiene cargados).
2. **Qué proveedores de modelo son válidos** y su sintaxis exacta.
3. **Cómo estructurar un sub-agente válido** con tools, modelo y MCP correctos.
4. **Qué MCPs puede integrar** y cómo configurarlos.
5. **Su propia arquitectura**: no sabe que al crear un sub-agente debe heredar ciertos tools base o configurar MCP específicos.

---

## Objetivo Fase 7

**Estabilizar la plataforma**, corregir los errores operativos detectados, dotar al agente de **auto-consciencia arquitectónica**, e implementar las correcciones de seguridad críticas del QA.

---

## 7.1 — Fix: Scheduler `base_url`

**Problema**: El scheduler interno usa `http://127.0.0.1:7777` por defecto para ejecutar los endpoints de los schedules, pero el gateway corre en `:8000`.

**Solución en `gateway.py`**:

```python
# Antes de construir AgentOS, configurar scheduler_base_url
if "scheduler_base_url" in _agent_os_params:
    _scheduler_kwargs["scheduler_base_url"] = f"http://127.0.0.1:{PORT}"
    logger.info(f"Scheduler base_url: http://127.0.0.1:{PORT}")
```

**Solución alternativa via config.yaml**:

```yaml
scheduler:
  enabled: true
  poll_interval: 15
  base_url: "http://127.0.0.1:8000"  # NUEVO — debe coincidir con PORT
```

Y en `gateway.py` pasar:

```python
if scheduler_cfg.get("base_url"):
    _scheduler_kwargs["scheduler_base_url"] = scheduler_cfg["base_url"]
```

---

## 7.2 — Fix: Fallback Automático por Rate-Limit

**Problema**: Agno marca el 429 como `Non-retryable` antes de que el wrapper haga swap. El wrapper `_arun_wrapped` no tiene oportunidad de interceptar.

**Solución**: Interceptar el error **después** de que Agno lo lance, hacer swap, y **reintentar la llamada completa**:

```python
# En gateway.py — wrapper mejorado
async def _arun_wrapped(agent, *args, **kwargs):
    global _using_fallback, _fallback_until

    # Restaurar primario si pasó el cooldown
    if _using_fallback and time.time() > _fallback_until:
        agent.model = _original_model
        _using_fallback = False
        logger.info(f"Modelo primario restaurado: {_original_model.id}")

    try:
        return await _original_arun(agent, *args, **kwargs)
    except Exception as e:
        if _is_rate_limit_error(e) and fallback_model and not _using_fallback:
            agent.model = fallback_model
            _using_fallback = True
            _fallback_until = time.time() + FALLBACK_COOLDOWN
            logger.warning(f"FALLBACK AUTO: 429 → {fallback_model.id}")
            # RETRY con el modelo fallback
            try:
                return await _original_arun(agent, *args, **kwargs)
            except Exception as retry_err:
                logger.error(f"Fallback también falló: {retry_err}")
                raise
        raise

def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(p in msg for p in [
        "429", "rate_limit", "rate limit", "too many",
        "quota", "throttl", "resourceexhausted",
    ])
```

**Clave**: El monkey-patch debe ser sobre `agent.arun` directamente, no sobre un middleware FastAPI que no captura errores del modelo.

---

## 7.3 — Fix: Mensajes Vacíos (Error 400)

**Problema**: Webhooks de WhatsApp con media sin texto, o audios que no se transcriben, generan `text content blocks must be non-empty`.

**Solución en el wrapper pre-run**:

```python
# Antes de llamar al agente, validar contenido
if not message_text or not message_text.strip():
    if audio_objects:
        message_text = "[Audio recibido sin contenido transcribible]"
    elif image_objects:
        message_text = "[Imagen recibida]"
    else:
        logger.warning("Mensaje vacío descartado")
        return  # No procesar mensajes vacíos
```

---

## 7.4 — Auto-Consciencia del Agente (Core de F7)

### 7.4.1 — `workspace/self_knowledge.md` (NUEVO)

Archivo que el agente consulta antes de auto-configurarse. Se carga como parte de sus instrucciones.

```markdown
# Auto-Conocimiento de OpenAgno

## Proveedores de Modelo Válidos

| Provider (config.yaml) | Import Agno | Ejemplo de ID |
|------------------------|-------------|---------------|
| `google` | `agno.models.google.Gemini` | `gemini-2.0-flash` |
| `openai` | `agno.models.openai.OpenAIChat` | `gpt-4.1` |
| `anthropic` | `agno.models.anthropic.Claude` | `claude-sonnet-4-20250514` |
| `aws_bedrock_claude` | `agno.models.aws.Claude` | `us.anthropic.claude-sonnet-4-6` |
| `aws_bedrock` | `agno.models.aws.AwsBedrock` | `amazon.nova-pro-v1:0` |

**NUNCA usar**: `bedrock`, `aws`, `claude`, `gemini` como provider.

## Tools Disponibles en el Loader

| Nombre (tools.yaml) | Clase | Requiere |
|---------------------|-------|----------|
| `duckduckgo` | `DuckDuckGoTools` | Nada (builtin) |
| `crawl4ai` | `Crawl4aiTools` | Nada (builtin) |
| `github` | `GithubTools` | `PyGithub` + `GITHUB_TOKEN` env var |
| `shell` | `ShellTools` | `base_dir` en config |
| `email` | `EmailTools` | `EMAIL_*` env vars |
| `tavily_search` | Via MCP | `TAVILY_API_KEY` |
| `workspace` | `WorkspaceTools` | Nada |
| `scheduler_mgmt` | `SchedulerTools` | `GATEWAY_URL` |
| `audio` | `AudioTools` | `OPENAI_API_KEY` |

**NUNCA usar en sub-agentes**: `tavily`, `web_search`, `search` — no son nombres de tools válidos en el loader.
**OJO**: `github` ahora SÍ es válido (F7). Requiere registrar `GithubTools` en `loader.py`.

## Cómo Crear un Sub-Agente Válido

```yaml
# workspace/agents/ejemplo.yaml
name: "Nombre del Agente"
id: "nombre-agente"  # sin espacios, lowercase
model:
  provider: google  # DEBE ser uno de la tabla de arriba
  id: gemini-2.0-flash
instructions: |
  Instrucciones específicas del agente.
tools:
  - duckduckgo      # DEBE existir en la tabla de tools
  - crawl4ai
```

## MCP Servers Disponibles

| Server | URL | Tipo |
|--------|-----|------|
| Agno Docs | `https://docs.agno.com/mcp` | streamable-http |
| Tavily | Requiere API key | streamable-http |
| Supabase | Requiere `npx` + access token | stdio |

## Reglas de Auto-Configuración

1. Antes de crear un sub-agente, **consultar este archivo** para validar provider y tools.
2. Si necesitas un tool que no existe, **consulta MCP de Agno** (`docs.agno.com/mcp`) para ver si hay un tool builtin o MCP disponible.
3. Los sub-agentes **NO heredan** los tools del agente principal. Debes declararlos explícitamente.
4. Los sub-agentes **NO heredan** MCP servers. Si necesitan acceso a MCP, deben configurarlo en su YAML.
5. Después de crear un sub-agente, siempre llama `request_reload` para que se cargue.
6. Nunca uses nombres inventados de tools. Si no estás seguro, consulta `workspace/tools.yaml`.
```

### 7.4.2 — Inyección en `loader.py`

```python
# En load_workspace(), al construir instrucciones del agente principal
self_knowledge_path = WORKSPACE / "self_knowledge.md"
if self_knowledge_path.exists():
    self_knowledge = self_knowledge_path.read_text(encoding="utf-8")
    instructions.append(self_knowledge)
    logger.info("Self-knowledge cargado para auto-consciencia")
```

### 7.4.3 — Validación en `WorkspaceTools.create_sub_agent()`

```python
# En tools/workspace_tools.py — validar antes de escribir el YAML

VALID_PROVIDERS = {
    "google", "openai", "anthropic",
    "aws_bedrock_claude", "aws_bedrock",
}

VALID_TOOLS = set()  # Se carga dinámicamente desde tools.yaml

def create_sub_agent(self, name: str, agent_id: str, provider: str,
                     model_id: str, instructions: str,
                     tools: list[str] | None = None) -> str:
    # Validar provider
    if provider not in VALID_PROVIDERS:
        return (f"ERROR: Provider '{provider}' no válido. "
                f"Usa uno de: {', '.join(sorted(VALID_PROVIDERS))}")

    # Validar tools
    if tools:
        valid_tools = self._load_valid_tools()
        invalid = [t for t in tools if t not in valid_tools]
        if invalid:
            return (f"ERROR: Tools no válidos: {invalid}. "
                    f"Disponibles: {', '.join(sorted(valid_tools))}")

    # Crear YAML validado
    ...
```

### 7.4.4 — Consulta MCP de Agno para extensión

Agregar a `instructions.md`:

```markdown
## Extensión de Capacidades

Cuando un usuario pida una funcionalidad que no tienes (ej: "busca en GitHub",
"conecta con Notion"), ANTES de inventar un tool:

1. Consulta el MCP de Agno: `search_agno_docs("tools builtin list")`
2. Si existe como tool builtin de Agno → sugiere agregarlo a `tools.yaml`
3. Si existe como MCP server → sugiere agregarlo a `mcp.yaml`
4. Si no existe → informa al usuario que no está disponible y sugiere alternativas

NUNCA crees un sub-agente con tools que no hayas verificado primero.
```

---

## 7.5 — Fix: Alerta de Token WhatsApp Expirado

**Problema**: Token expirado → gateway recibe pero no puede responder. Sin notificación.

```python
# En gateway.py — interceptar 401 de WhatsApp
_wa_auth_failed = False

@base_app.middleware("http")
async def whatsapp_auth_monitor(request, call_next):
    global _wa_auth_failed
    response = await call_next(request)
    return response

# En el error handler de WhatsApp (o post-hook):
def _check_wa_auth_error(error_msg: str):
    global _wa_auth_failed
    if "401" in str(error_msg) and "access token" in str(error_msg).lower():
        if not _wa_auth_failed:
            _wa_auth_failed = True
            logger.critical("TOKEN WHATSAPP EXPIRADO — renovar en Meta Business")
            # Opción: enviar alerta via email/slack si está configurado
```

Agregar al endpoint `/admin/health`:

```python
@base_app.get("/admin/health")
async def admin_health():
    return {
        ...
        "whatsapp_auth": "expired" if _wa_auth_failed else "ok",
        "scheduler_base_url": _scheduler_kwargs.get("scheduler_base_url", "NOT SET"),
    }
```

---

## 7.6 — Seguridad (Correcciones QA)

### 7.6.1 — Autenticación API Key en endpoints REST

```python
# security.py (NUEVO)
import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("OPENAGNO_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(key: str = Security(api_key_header)):
    if not API_KEY:
        return  # Sin API key configurada, acceso libre (dev)
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
```

Aplicar a `knowledge_routes.py`:

```python
from security import verify_api_key

@router.post("/upload", dependencies=[Depends(verify_api_key)])
async def upload_document(...):
    ...
```

### 7.6.2 — SQL Injection Fix

```python
# En knowledge_routes.py
ALLOWED_TABLES = {"agnobot_knowledge_contents", "agnobot_knowledge_vectors"}

# En delete_document:
if table not in ALLOWED_TABLES:
    raise HTTPException(400, "Tabla no permitida")
```

### 7.6.3 — HTTPException re-raise

```python
# Corregir en knowledge_routes.py
except HTTPException:
    raise  # SIEMPRE re-raise
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(500, detail=str(e))
```

### 7.6.4 — Docker credentials

```yaml
# docker-compose.yml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme_in_production}
```

---

## 7.7 — Validación de Schedules Pre-Envío

```python
# En tools/scheduler_tools.py — validar cron antes de POST
import re

CRON_REGEX = re.compile(
    r'^(\*|[0-9,\-\/]+)\s+'  # minuto
    r'(\*|[0-9,\-\/]+)\s+'   # hora
    r'(\*|[0-9,\-\/]+)\s+'   # día del mes
    r'(\*|[0-9,\-\/]+)\s+'   # mes
    r'(\*|[0-9,\-\/]+)$'     # día de la semana
)

VALID_TIMEZONES = [
    "America/Guayaquil", "America/New_York", "America/Chicago",
    "America/Denver", "America/Los_Angeles", "America/Bogota",
    "America/Lima", "America/Santiago", "America/Sao_Paulo",
    "Europe/London", "Europe/Madrid", "UTC",
]

def create_schedule(self, name, cron_expr, message, agent_id="agnobot-main",
                    timezone="America/Guayaquil"):
    # Validar cron
    if not CRON_REGEX.match(cron_expr.strip()):
        return f"ERROR: Expresión cron inválida: '{cron_expr}'. Formato: 'min hora día mes díaSemana'"

    # Validar timezone
    if timezone not in VALID_TIMEZONES:
        return f"ERROR: Timezone '{timezone}' no soportado. Usa uno de: {', '.join(VALID_TIMEZONES[:5])}..."

    # Proceder con POST
    ...
```

---

## 7.8 — Mejora de Logs del Sub-Agente

Cuando un sub-agente falla al cargar, el log actual solo dice `WARNING`. Debe ser más explícito:

```python
# En loader.py — build_sub_agents()
except Exception as e:
    logger.error(
        f"Sub-agente '{yaml_file.stem}' NO cargado: {e}\n"
        f"  Provider: {agent_cfg.get('model', {}).get('provider', '?')}\n"
        f"  Tools: {agent_cfg.get('tools', [])}\n"
        f"  Acción: Verificar provider y tools contra workspace/self_knowledge.md"
    )
```

---

## 7.9 — Registrar `GithubTools` en el Loader

**Contexto**: El agente intentó asignar `github` como tool al `senior_dev_agent` pero el loader no lo reconoce. Agno tiene `GithubTools` builtin desde `agno.tools.github`.

**En `loader.py` — `build_tools()`, agregar al match:**

```python
case "github":
    from agno.tools.github import GithubTools
    tools.append(GithubTools())
    logger.info("GithubTools activado — requiere GITHUB_TOKEN")
```

**En `requirements.txt`, agregar:**

```
PyGithub>=2.0
```

**En `.env.example`, agregar:**

```bash
# === GitHub (GithubTools) ===
# GITHUB_TOKEN=ghp_...
```

**En `workspace/tools.yaml`, agregar a `optional`:**

```yaml
- name: github
  enabled: false  # Activar cuando se configure GITHUB_TOKEN
  description: "Acceso a repositorios GitHub (issues, PRs, código)"
```

---

## 7.10 — Canal Telegram

**Contexto**: Agno anadio interfaz Telegram en releases recientes. Telegram es el canal de menor esfuerzo y mayor impacto para ampliar cobertura.

**En `gateway.py`, agregar al bloque de interfaces:**

```python
if "telegram" in channels:
    try:
        from agno.os.interfaces.telegram import Telegram
        interfaces.append(Telegram(agent=main_agent))
        logger.info("Canal Telegram habilitado")
    except ImportError:
        logger.warning("Telegram no disponible — actualizar agno[os]")
```

**En `workspace/config.yaml`:**

```yaml
channels:
  - whatsapp
  - slack
  - telegram  # NUEVO F7
```

**En `.env.example`:**

```bash
# === Telegram ===
# TELEGRAM_TOKEN=bot_token_from_botfather
```

**En `management/cli.py`, agregar Telegram como opción de canal en el wizard.**

---

## 7.11 — Actualizar Dependencias de Agno

Varias correcciones críticas en releases recientes de Agno que impactan directamente a OpenAgno:

```bash
# Actualizar a la última versión
pip install --upgrade "agno[os,scheduler]"
```

Fixes incluidos que resuelven problemas observados en `gateway.log`:

- **MCPTools race condition**: Llamadas MCP paralelas creaban sesiones duplicadas → posible causa de los timeouts en `tavily_crawl` (línea 304-433 del log).
- **Slack `user_id` propagation**: Bug que impedía propagar `user_id` en la interfaz de Slack.
- **AWS Bedrock credential refresh**: Credenciales AWS se refrescan en cada request (evita expiración de tokens temporales STS).

**En `requirements.txt`, pinear versión mínima:**

```
agno[os,scheduler]>=1.5.0  # Incluye fixes MCPTools, Slack, Bedrock
```

---

## Checklist Fase 7

| # | Tarea | Prioridad | Tipo |
|---|-------|-----------|------|
| 1 | Fix `scheduler_base_url` → apuntar a puerto correcto | **Crítica** | Bug fix |
| 2 | Fix fallback 429: interceptar post-error + retry | **Crítica** | Bug fix |
| 3 | Fix mensajes vacíos (400 empty text blocks) | **Crítica** | Bug fix |
| 4 | Crear `workspace/self_knowledge.md` | **Alta** | Feature |
| 5 | Validación en `create_sub_agent()` (provider + tools) | **Alta** | Feature |
| 6 | Inyectar self_knowledge en instrucciones del agente | **Alta** | Feature |
| 7 | Instrucciones de extensión via MCP de Agno | **Alta** | Feature |
| 8 | Registrar `GithubTools` en loader + tools.yaml | **Alta** | Feature |
| 9 | Alerta de token WhatsApp expirado en health + logs | **Alta** | Mejora |
| 10 | API Key auth en endpoints REST (`security.py`) | **Alta** | Seguridad |
| 11 | SQL Injection fix (whitelist de tablas) | **Alta** | Seguridad |
| 12 | Agregar canal Telegram (interface Agno disponible) | **Media** | Feature |
| 13 | Actualizar `agno[os]` (fixes MCPTools, Slack, Bedrock) | **Media** | Mejora |
| 14 | HTTPException re-raise en knowledge_routes | **Media** | Bug fix |
| 15 | Docker credentials con env vars | **Media** | Seguridad |
| 16 | Validación pre-envío de schedules (cron + timezone) | **Media** | Mejora |
| 17 | Logs mejorados para sub-agentes fallidos | **Media** | Mejora |
| 18 | Pinear versiones en `requirements.txt` | **Media** | Mejora |
| 19 | Crear directorio `/tests` con tests básicos | **Media** | Calidad |
| 20 | Agregar `.dockerignore` | **Baja** | Seguridad |
| 21 | Test: schedule se ejecuta y llega al agente | **Alta** | Validación |
| 22 | Test: 429 → swap → retry → respuesta exitosa | **Alta** | Validación |
| 23 | Test: crear sub-agente con provider inválido → error claro | **Alta** | Validación |
| 24 | Test: crear sub-agente con tools inválidos → error claro | **Alta** | Validación |
| 25 | Test: sub-agente con `github` tool se carga correctamente | **Alta** | Validación |
| 26 | Test: mensaje vacío no genera error 400 | **Media** | Validación |
| 27 | Test: `/admin/health` muestra estado WhatsApp y scheduler | **Media** | Validación |
| 28 | Crear issues Linear DAT-226+ para tracking F7 | **Media** | Gestión |

---

## Archivos Afectados

| Archivo | Cambios |
|---------|---------|
| `gateway.py` | scheduler_base_url, fallback retry, WhatsApp auth monitor, mensajes vacíos, Telegram interface |
| `loader.py` | Cargar self_knowledge.md, registrar GithubTools, mejorar logs sub-agentes |
| `tools/workspace_tools.py` | Validación de provider y tools en create_sub_agent |
| `tools/scheduler_tools.py` | Validación cron + timezone pre-envío |
| `routes/knowledge_routes.py` | Whitelist tablas, re-raise HTTPException, API key |
| `workspace/self_knowledge.md` | **NUEVO** — mapa de providers, tools, MCPs, canales, reglas |
| `workspace/instructions.md` | Agregar sección de extensión de capacidades |
| `workspace/tools.yaml` | Agregar `github` a optional tools |
| `workspace/config.yaml` | Agregar `telegram` a channels, `scheduler.base_url` |
| `security.py` | **NUEVO** — middleware de API Key |
| `docker-compose.yml` | Credentials via env vars |
| `.env.example` | `OPENAGNO_API_KEY`, `GITHUB_TOKEN`, `TELEGRAM_TOKEN`, scheduler_base_url |
| `requirements.txt` | Pinear versiones, agregar `PyGithub>=2.0` |
| `.dockerignore` | **NUEVO** — excluir `.env`, `backups/`, `__pycache__/` |

---

## Orden de Implementación

1. **Actualizar `agno[os]`** (fixes MCPTools race condition, Slack, Bedrock)
2. **scheduler_base_url** (fix inmediato, 1 línea)
3. **fallback retry** (fix crítico, gateway.py)
4. **mensajes vacíos** (fix crítico, gateway.py)
5. **self_knowledge.md** + inyección en loader (feature core)
6. **validación create_sub_agent** (feature core)
7. **GithubTools** en loader + tools.yaml (feature)
8. **security.py** + aplicar a routes (seguridad)
9. **SQL injection fix** (seguridad)
10. **WhatsApp auth alert** (mejora operativa)
11. **Telegram** interface (feature, bajo esfuerzo)
12. **validación schedules** (mejora)
13. **Pinear versiones + `.dockerignore`** (calidad)
14. **Tests de validación** (todos los items)
15. **Issues Linear** DAT-226+ para tracking

---

*Verificado contra: gateway.log (1046 líneas), Analisis_OpenAgno_QA, ANALISIS_OPENAGNO_v0_7_vs_OPENCLAW.md, phase5_validation_phase6_plan_CORRECTED.md, phase6_1_plan.md, Slack #openagno (11 mensajes), Linear proyecto OpenAgno (DAT-190→225 + DAT-217 Backlog), docs.agno.com (GithubTools, Telegram interface, releases)*
*26 de marzo de 2026*
