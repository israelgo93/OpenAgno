# OpenAgno — Validación Fase 1 + Plan de Implementación Fase 2

---

## PARTE 1: VALIDACIÓN COMPLETA DE FASE 1

### Resumen de Validación

| Archivo | Estado | Issues |
|---------|--------|--------|
| `loader.py` | ⚠️ 3 issues | MemoryManager faltante, params no documentados, SearchType import |
| `gateway.py` | ✅ Correcto | Patrón validado contra docs oficiales |
| `routes/knowledge_routes.py` | ⚠️ 2 issues | Endpoints stub, API Knowledge redundante |
| `workspace/config.yaml` | ✅ Correcto | Estructura declarativa válida |
| `workspace/instructions.md` | ✅ Correcto | Formato compatible |
| `workspace/tools.yaml` | ✅ Correcto | Estructura válida |
| `workspace/mcp.yaml` | ✅ Correcto | Patrón MCPTools validado |
| `docker-compose.yml` | ✅ Correcto | pgvector/pgvector:pg17 |
| `requirements.txt` | ⚠️ 1 issue | Falta `rich` (MemoryManager) |
| `.env.example` | ✅ Correcto | Variables completas |

---

### ISSUE 1 (CRÍTICO): MemoryManager faltante

**Archivo:** `loader.py` — función `load_workspace()`

**Problema:** El agente usa `enable_agentic_memory=True` pero NO instancia un `MemoryManager`. Según la documentación oficial de Agno (`agents/usage/agent-with-memory`), `enable_agentic_memory` requiere un `MemoryManager` con modelo y DB.

**Código actual (incorrecto):**
```python
main_agent = Agent(
    ...
    enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
    enable_user_memories=mem_config.get("enable_user_memories", True),  # No documentado
    enable_session_summaries=mem_config.get("enable_session_summaries", True),  # No documentado
    ...
)
```

**Código corregido:**
```python
from agno.memory import MemoryManager

# Construir MemoryManager
memory_manager = MemoryManager(
    model=model,  # Reutiliza el modelo del agente
    db=db,
)

main_agent = Agent(
    ...
    memory_manager=memory_manager,
    enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
    ...
)
```

**Parámetros no documentados a eliminar:**
- `enable_user_memories` — no aparece en la docs oficial de Agno
- `enable_session_summaries` — no aparece en la docs oficial de Agno

Estos parámetros podrían ser ignorados silenciosamente por Agno o causar errores. Se recomienda eliminarlos y depender de `enable_agentic_memory` + `MemoryManager`.

---

### ISSUE 2 (MODERADO): Knowledge Routes redundantes y stub

**Archivo:** `routes/knowledge_routes.py`

**Problemas encontrados:**

1. **Endpoint `/knowledge/list` es un stub** — siempre retorna `{"documents": [], "message": "..."}` sin consultar la DB.

2. **Endpoint `/knowledge/{doc_id}` no elimina nada** — solo logea y retorna éxito.

3. **Redundancia con AgentOS** — AgentOS ya expone endpoints nativos de Knowledge en `/v1/knowledge/{knowledge_id}/content` y `/v1/knowledge/{knowledge_id}/sources` (documentación: `agent-os/knowledge/manage-knowledge`). Los endpoints custom pueden conflictuar.

4. **`knowledge.insert(path=tmp_path)` válido** — confirmado en docs: `knowledge.insert(path="docs/file.pdf")`.

5. **Falta `skip_if_exists`** — la docs recomienda `knowledge.insert(path=..., skip_if_exists=True)` para evitar duplicados.

**Correcciones recomendadas:**

```python
# En upload_document:
knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)

# Para list_documents — usar la API nativa de AgentOS o implementar consulta real
# Para delete_document — implementar eliminación real o delegar a AgentOS
```

---

### ISSUE 3 (MENOR): SearchType import path

**Archivo:** `loader.py`

**Código actual:**
```python
from agno.vectordb.pgvector import PgVector, SearchType
```

**Validación:** La docs quickstart usa `from agno.vectordb.search import SearchType` pero el demo usa `from agno.vectordb.pgvector import PgVector`. Ambas pueden funcionar si PgVector re-exporta SearchType. Sin embargo, para consistencia con la docs más reciente, se recomienda:

```python
from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType
```

---

### ISSUE 4 (MENOR): requirements.txt incompleto

Falta la dependencia `rich` (usada opcionalmente para debug) y posiblemente `agno` necesita la versión con `[memory]` o el MemoryManager está incluido en el paquete base.

**Agregar:**
```
rich
```

---

### Patrones Validados Correctamente

| Patrón | Archivo | Verificación |
|--------|---------|-------------|
| `PostgresDb(db_url=..., id=..., knowledge_table=...)` | loader.py | ✅ Coincide con docs/demo |
| `Knowledge(vector_db=PgVector(...), contents_db=db)` | loader.py | ✅ Coincide con docs |
| `PgVector(table_name=..., db_url=..., search_type=..., embedder=...)` | loader.py | ✅ Coincide |
| `OpenAIEmbedder(id="text-embedding-3-small")` | loader.py | ✅ Válido |
| `MCPTools(transport="streamable-http", url="...")` | loader.py | ✅ Coincide exacto con docs |
| `AgentOS(..., base_app=app, on_route_conflict="preserve_base_app")` | gateway.py | ✅ Documentado |
| `agent_os.serve(app="gateway:app")` sin `reload=True` | gateway.py | ✅ Requerido con MCP |
| `Registry(name=..., tools=[], models=[...], dbs=[...])` | gateway.py | ✅ Coincide con docs |
| `Whatsapp(agent=main_agent)` | gateway.py | ✅ Patrón oficial |
| Docker `pgvector/pgvector:pg17` puerto `5532:5432` | docker-compose.yml | ✅ Estándar Agno |

---

### Código Corregido: loader.py (diff de cambios)

```python
# === CAMBIO 1: Agregar import de MemoryManager ===
from agno.memory import MemoryManager

# === CAMBIO 2: En load_workspace(), antes de crear main_agent ===
# Construir MemoryManager
memory_manager = MemoryManager(
    model=model,
    db=db,
)

# === CAMBIO 3: En la construcción de main_agent ===
main_agent = Agent(
    name=agent_config.get("name", "AgnoBot"),
    id=agent_config.get("id", "agnobot-main"),
    description=agent_config.get("description", "Asistente personal multimodal"),
    model=model,
    db=db,
    knowledge=knowledge,
    search_knowledge=knowledge is not None,
    tools=tools,
    instructions=instructions,
    memory_manager=memory_manager,                                    # NUEVO
    enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
    # ELIMINADOS: enable_user_memories, enable_session_summaries
    add_history_to_context=True,
    num_history_runs=mem_config.get("num_history_runs", 5),
    add_datetime_to_context=True,
    markdown=True,
)
```

---

## PARTE 2: PLAN DE IMPLEMENTACIÓN — FASE 2

### Objetivo

**CLI de Onboarding que genera el workspace/ completo + módulo Admin programático via AgentOSClient.**

### Entregables

| # | Entregable | Archivo | Descripción |
|---|------------|---------|-------------|
| 1 | CLI Wizard v3 | `management/cli.py` | Genera workspace/ completo con validación |
| 2 | Admin Client | `management/admin.py` | Operaciones admin via AgentOSClient |
| 3 | Validador de Workspace | `management/validator.py` | Valida config antes de arrancar |
| 4 | Package init | `management/__init__.py` | Módulo Python |
| 5 | Correcciones F1 | `loader.py` | MemoryManager + cleanup |
| 6 | Knowledge routes mejoradas | `routes/knowledge_routes.py` | Endpoints funcionales |

---

### Arquitectura Fase 2

```
management/
├── __init__.py           # Exporta funciones principales
├── cli.py                # Wizard interactivo (genera workspace/)
├── admin.py              # Admin via AgentOSClient (sesiones, memorias, knowledge)
└── validator.py          # Validación de workspace antes de arrancar
```

---

### 2.1 — management/__init__.py

```python
"""
Management — CLI de Onboarding y Admin programático para OpenAgno.
"""
from management.validator import validate_workspace

__all__ = ["validate_workspace"]
```

---

### 2.2 — management/validator.py

Valida que el workspace/ tenga la estructura correcta y que las variables de entorno necesarias estén configuradas.

```python
"""
Validator — Valida el workspace/ antes de arrancar el gateway.

Uso:
    python -m management.validator
    # o desde código:
    from management.validator import validate_workspace
    errors = validate_workspace()
"""
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


def validate_workspace(workspace_dir: Optional[str] = None) -> list[str]:
    """
    Valida la estructura del workspace y las variables de entorno.
    Retorna lista de errores. Lista vacía = workspace válido.
    """
    ws = Path(workspace_dir or os.getenv("AGNOBOT_WORKSPACE", "workspace"))
    errors: list[str] = []

    # --- Archivos requeridos ---
    required_files = [
        ("config.yaml", "Configuración central"),
        ("instructions.md", "Instrucciones del agente"),
        ("tools.yaml", "Configuración de herramientas"),
        ("mcp.yaml", "Configuración MCP"),
    ]
    for filename, desc in required_files:
        if not (ws / filename).exists():
            errors.append(f"Falta {filename} ({desc})")

    if errors:
        return errors  # No continuar si faltan archivos base

    # --- Validar config.yaml ---
    try:
        with open(ws / "config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        errors.append(f"config.yaml tiene YAML inválido: {e}")
        return errors

    # Secciones requeridas
    for section in ("agent", "model", "database"):
        if section not in config:
            errors.append(f"config.yaml: falta sección '{section}'")

    # Validar modelo
    model = config.get("model", {})
    provider = model.get("provider", "")
    key_map = {
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if provider in key_map:
        env_key = key_map[provider]
        if not os.getenv(env_key):
            errors.append(f".env: falta {env_key} (requerido para provider '{provider}')")

    # Validar base de datos
    db_config = config.get("database", {})
    db_type = db_config.get("type", "local")

    if db_type in ("supabase", "local"):
        db_vars = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
        for var in db_vars:
            if not os.getenv(var):
                errors.append(f".env: falta {var} (requerido para database.type='{db_type}')")

    # Validar embeddings (necesarios para PgVector/RAG)
    if db_type != "sqlite":
        if not os.getenv("OPENAI_API_KEY"):
            errors.append(".env: falta OPENAI_API_KEY (requerido para embeddings)")

    # Validar canales
    channels = config.get("channels", [])
    if "whatsapp" in channels:
        wa_vars = [
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_VERIFY_TOKEN",
        ]
        for var in wa_vars:
            if not os.getenv(var):
                errors.append(f".env: falta {var} (requerido para canal WhatsApp)")

    if "slack" in channels:
        if not os.getenv("SLACK_TOKEN"):
            errors.append(".env: falta SLACK_TOKEN (requerido para canal Slack)")

    # --- Validar tools.yaml ---
    try:
        with open(ws / "tools.yaml", "r", encoding="utf-8") as f:
            tools = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        errors.append(f"tools.yaml tiene YAML inválido: {e}")
        return errors

    for tool_def in tools.get("optional", []):
        if not tool_def.get("enabled", False):
            continue
        name = tool_def.get("name", "")
        if name == "tavily" and not os.getenv("TAVILY_API_KEY"):
            errors.append(".env: falta TAVILY_API_KEY (tool Tavily habilitado)")
        if name == "email":
            for var in ("GMAIL_SENDER", "GMAIL_PASSKEY"):
                if not os.getenv(var):
                    errors.append(f".env: falta {var} (tool Email habilitado)")

    # --- Validar directorios ---
    dirs = ["knowledge", "agents"]
    for d in dirs:
        dir_path = ws / d
        if not dir_path.exists():
            errors.append(f"Falta directorio workspace/{d}/")

    return errors


def print_validation(errors: list[str]) -> None:
    """Imprime resultados de validación con formato."""
    if not errors:
        print("\n✅ Workspace válido — listo para arrancar")
        return

    print(f"\n❌ Se encontraron {len(errors)} error(es) en el workspace:\n")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")
    print()
    print("Corrige estos errores antes de ejecutar gateway.py")
    print("Tip: ejecuta 'python -m management.cli' para regenerar el workspace")


if __name__ == "__main__":
    errors = validate_workspace()
    print_validation(errors)
    sys.exit(1 if errors else 0)
```

---

### 2.3 — management/cli.py

Wizard interactivo completo con validación integrada.

```python
"""
CLI de Onboarding v3 — Genera el workspace/ completo.

Ejecutar:
    python -m management.cli

Genera:
    workspace/config.yaml
    workspace/instructions.md
    workspace/tools.yaml
    workspace/mcp.yaml
    workspace/knowledge/urls.yaml
    workspace/agents/teams.yaml
    .env
"""
import os
import sys
import yaml
from pathlib import Path

from management.validator import validate_workspace, print_validation


def _write_yaml(path: Path, data: dict) -> None:
    """Escribe un dict como YAML con formato legible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _prompt(text: str, default: str = "") -> str:
    """Input con valor por defecto."""
    suffix = f" [{default}]" if default else ""
    value = input(f"  {text}{suffix}: ").strip()
    return value or default


def _prompt_choice(text: str, options: dict[str, str], default: str = "1") -> str:
    """Input de selección numérica."""
    print(f"\n{text}")
    for key, label in options.items():
        print(f"  [{key}] {label}")
    return input(f"  Selección [{default}]: ").strip() or default


def _prompt_yn(text: str, default: bool = False) -> bool:
    """Input sí/no."""
    suffix = "[s/N]" if not default else "[S/n]"
    value = input(f"  {text} {suffix}: ").strip().lower()
    if not value:
        return default
    return value in ("s", "si", "sí", "y", "yes")


def run_onboarding() -> None:
    """Wizard interactivo que genera el workspace/ con toda la configuración."""
    workspace_dir = Path("workspace")

    print()
    print("═" * 50)
    print("  🤖 OpenAgno — Setup Wizard v3")
    print("  Generador de Workspace Parametrizable")
    print("═" * 50)

    # ── PASO 1: Identidad ──
    print("\n📋 PASO 1: Identidad del agente")
    agent_name = _prompt("Nombre del agente", "AgnoBot")
    agent_desc = _prompt("Descripción breve", "Asistente personal multimodal")

    choice = _prompt_choice("¿Instrucciones del agente?", {
        "1": "Usar instrucciones por defecto",
        "2": "Escribir instrucciones personalizadas",
    })
    custom_instructions = None
    if choice == "2":
        print("  Escribe las instrucciones (línea vacía para terminar):")
        lines = []
        while True:
            line = input("  > ")
            if not line:
                break
            lines.append(line)
        custom_instructions = "\n".join(lines)

    # ── PASO 2: Modelo ──
    model_options = {
        "1": "Gemini 2.0 Flash (Google — multimodal, recomendado)",
        "2": "Claude Sonnet 4 (Anthropic)",
        "3": "GPT-4.1 (OpenAI)",
        "4": "GPT-5-mini (OpenAI)",
    }
    model_choice = _prompt_choice("🧠 PASO 2: Modelo de IA", model_options)

    model_map = {
        "1": ("google", "gemini-2.0-flash", "GOOGLE_API_KEY"),
        "2": ("anthropic", "claude-sonnet-4-0", "ANTHROPIC_API_KEY"),
        "3": ("openai", "gpt-4.1", "OPENAI_API_KEY"),
        "4": ("openai", "gpt-5-mini", "OPENAI_API_KEY"),
    }
    provider, model_id, key_name = model_map.get(model_choice, model_map["1"])
    api_key = _prompt(f"→ {key_name}")

    # ── PASO 3: Base de datos ──
    db_options = {
        "1": "Supabase (PostgreSQL managed — recomendado)",
        "2": "PostgreSQL local (Docker)",
        "3": "SQLite (solo desarrollo, sin RAG)",
    }
    db_choice = _prompt_choice("💾 PASO 3: Base de datos", db_options)
    db_type = {"1": "supabase", "2": "local", "3": "sqlite"}.get(db_choice, "supabase")

    db_vars: dict[str, str] = {}
    if db_type == "supabase":
        print("\n  Configuración Supabase (Session Pooler):")
        db_vars["DB_HOST"] = _prompt("DB Host")
        db_vars["DB_PORT"] = _prompt("DB Port", "5432")
        db_vars["DB_USER"] = _prompt("DB User")
        db_vars["DB_PASSWORD"] = _prompt("DB Password")
        db_vars["DB_NAME"] = _prompt("DB Name", "postgres")
        db_vars["DB_SSLMODE"] = "require"
    elif db_type == "local":
        db_vars = {
            "DB_HOST": "localhost",
            "DB_PORT": "5532",
            "DB_USER": "ai",
            "DB_PASSWORD": "ai",
            "DB_NAME": "ai",
            "DB_SSLMODE": "prefer",
        }
        print("\n  ℹ️  Ejecuta: docker compose up -d db")

    # ── PASO 4: Canales ──
    channel_options = {
        "1": "WhatsApp",
        "2": "Slack",
        "3": "WhatsApp + Slack",
    }
    channel_choice = _prompt_choice("📡 PASO 4: Canales (Web siempre disponible)", channel_options)
    channels = {
        "1": ["whatsapp"], "2": ["slack"], "3": ["whatsapp", "slack"],
    }.get(channel_choice, ["whatsapp"])

    whatsapp_vars: dict[str, str] = {}
    if "whatsapp" in channels:
        print("\n  📱 Configuración WhatsApp (Meta Business API):")
        whatsapp_vars["WHATSAPP_ACCESS_TOKEN"] = _prompt("Access Token")
        whatsapp_vars["WHATSAPP_PHONE_NUMBER_ID"] = _prompt("Phone Number ID")
        whatsapp_vars["WHATSAPP_VERIFY_TOKEN"] = _prompt("Verify Token")
        whatsapp_vars["WHATSAPP_WEBHOOK_URL"] = _prompt("Webhook URL")

    slack_vars: dict[str, str] = {}
    if "slack" in channels:
        print("\n  💬 Configuración Slack:")
        slack_vars["SLACK_TOKEN"] = _prompt("Bot Token")

    # ── PASO 5: Tools ──
    print("\n🔧 PASO 5: Herramientas adicionales")
    email_enabled = _prompt_yn("¿Activar Gmail?")
    tavily_enabled = _prompt_yn("¿Activar Tavily (búsqueda web avanzada)?")

    email_vars: dict[str, str] = {}
    if email_enabled:
        email_vars["GMAIL_SENDER"] = _prompt("Email remitente")
        email_vars["GMAIL_PASSKEY"] = _prompt("App password")
        email_vars["GMAIL_RECEIVER"] = _prompt("Email receptor default")

    tavily_key = ""
    if tavily_enabled:
        tavily_key = _prompt("TAVILY_API_KEY")

    # ── PASO 6: Embeddings ──
    openai_key = ""
    if db_type != "sqlite":
        print("\n🔢 PASO 6: Embeddings (requerido para RAG)")
        if key_name == "OPENAI_API_KEY":
            openai_key = api_key
            print(f"  ✅ Reutilizando {key_name} para embeddings")
        else:
            openai_key = _prompt("OPENAI_API_KEY (para text-embedding-3-small)")

    # ══════════════════════════════════
    # GENERAR WORKSPACE
    # ══════════════════════════════════
    print("\n⏳ Generando workspace...")

    # Crear directorios
    for d in ["", "knowledge/docs", "agents"]:
        (workspace_dir / d).mkdir(parents=True, exist_ok=True)

    # --- config.yaml ---
    config = {
        "agent": {
            "name": agent_name,
            "id": "agnobot-main",
            "description": agent_desc,
        },
        "model": {"provider": provider, "id": model_id},
        "database": {
            "type": db_type,
            "knowledge_table": "agnobot_knowledge_contents",
            "vector_table": "agnobot_knowledge_vectors",
        },
        "vector": {
            "search_type": "hybrid",
            "embedder": "text-embedding-3-small",
            "max_results": 5,
        },
        "channels": channels,
        "memory": {
            "enable_agentic_memory": True,
            "num_history_runs": 5,
        },
        "agentos": {
            "id": "agnobot-gateway",
            "name": f"{agent_name} Platform",
            "port": 8000,
            "tracing": True,
            "enable_mcp_server": True,
        },
        "studio": {"enabled": db_type != "sqlite"},
    }
    _write_yaml(workspace_dir / "config.yaml", config)

    # --- instructions.md ---
    instructions_content = custom_instructions or f"""# Instrucciones de {agent_name}

Eres **{agent_name}**, un asistente personal multimodal autónomo.

## Personalidad
- Amable, eficiente y proactivo
- Respondes en el idioma del usuario
- Usas formato Markdown cuando es apropiado

## Capacidades
- Puedes analizar imágenes, videos y audios enviados
- Buscas en la web cuando necesitas información actualizada
- Usas la base de conocimiento para responder sobre documentos cargados
- Recuerdas información importante del usuario entre sesiones
- Puedes consultar la documentación de Agno para resolver dudas técnicas

## Reglas
- Si no estás seguro de algo, búscalo antes de responder
- Siempre cita tus fuentes cuando uses información de la web
- Si el usuario carga documentos, confírmaselo y ofrece analizarlos
"""
    (workspace_dir / "instructions.md").write_text(instructions_content, encoding="utf-8")

    # --- tools.yaml ---
    tools = {
        "builtin": [
            {"name": "duckduckgo", "enabled": True, "config": {}},
            {"name": "crawl4ai", "enabled": True, "config": {"max_length": 2000}},
            {"name": "reasoning", "enabled": True, "config": {"add_instructions": True}},
        ],
        "optional": [
            {
                "name": "email",
                "enabled": email_enabled,
                "config": {
                    "sender_email": "${GMAIL_SENDER}",
                    "sender_name": agent_name,
                    "sender_passkey": "${GMAIL_PASSKEY}",
                    "receiver_email": "${GMAIL_RECEIVER}",
                },
            },
            {"name": "tavily", "enabled": tavily_enabled},
            {"name": "spotify", "enabled": False},
            {"name": "shell", "enabled": False},
        ],
        "custom": [],
    }
    _write_yaml(workspace_dir / "tools.yaml", tools)

    # --- mcp.yaml ---
    mcp = {
        "servers": [
            {
                "name": "agno_docs",
                "enabled": True,
                "transport": "streamable-http",
                "url": "https://docs.agno.com/mcp",
            },
        ],
        "expose": {"enabled": True},
    }
    _write_yaml(workspace_dir / "mcp.yaml", mcp)

    # --- agents/teams.yaml ---
    _write_yaml(workspace_dir / "agents" / "teams.yaml", {"teams": []})

    # --- schedules.yaml ---
    _write_yaml(workspace_dir / "schedules.yaml", {"schedules": []})

    # --- knowledge/urls.yaml ---
    _write_yaml(workspace_dir / "knowledge" / "urls.yaml", {"urls": []})

    # --- .env ---
    env_lines = [
        "# ═══════════════════════════════════",
        f"# {agent_name} — Variables de Entorno",
        "# ═══════════════════════════════════",
        "",
        "# === API Keys ===",
        f"{key_name}={api_key}",
    ]
    if openai_key and key_name != "OPENAI_API_KEY":
        env_lines.append(f"OPENAI_API_KEY={openai_key}")
    if tavily_key:
        env_lines.append(f"TAVILY_API_KEY={tavily_key}")

    if db_vars:
        env_lines.extend(["", "# === Base de datos ==="])
        for k, v in db_vars.items():
            env_lines.append(f"{k}={v}")

    if whatsapp_vars:
        env_lines.extend(["", "# === WhatsApp ==="])
        for k, v in whatsapp_vars.items():
            env_lines.append(f"{k}={v}")

    if slack_vars:
        env_lines.extend(["", "# === Slack ==="])
        for k, v in slack_vars.items():
            env_lines.append(f"{k}={v}")

    if email_vars:
        env_lines.extend(["", "# === Gmail ==="])
        for k, v in email_vars.items():
            env_lines.append(f"{k}={v}")

    env_lines.extend([
        "",
        "# === Seguridad ===",
        "# OS_SECURITY_KEY=genera_con_openssl_rand_hex_32",
        "",
        "# === Entorno ===",
        "APP_ENV=development",
    ])

    Path(".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # ── Validar workspace generado ──
    print("\n🔍 Validando workspace generado...")
    errors = validate_workspace(str(workspace_dir))

    # ── Resumen ──
    print()
    print("═" * 50)
    if not errors:
        print("  ✅ Workspace generado y validado exitosamente!")
    else:
        print("  ⚠️  Workspace generado con advertencias")
    print("═" * 50)
    print(f"  📁 workspace/config.yaml    — Configuración central")
    print(f"  📝 workspace/instructions.md — Personalidad")
    print(f"  🔧 workspace/tools.yaml     — Herramientas")
    print(f"  🔌 workspace/mcp.yaml       — Servidores MCP")
    print(f"  📚 workspace/knowledge/     — Documentos RAG")
    print(f"  🤖 workspace/agents/        — Sub-agentes")
    print(f"  🔐 .env                     — Secretos")

    if errors:
        print()
        for e in errors:
            print(f"  ⚠️  {e}")

    print()
    if db_type == "local":
        print("  📦 Paso 1: docker compose up -d db")
    step = "2" if db_type == "local" else "1"
    print(f"  🚀 Paso {step}: python gateway.py")
    print(f"  🌐 Web UI: os.agno.com → Add OS → Local → http://localhost:8000")

    if "whatsapp" in channels:
        url = whatsapp_vars.get("WHATSAPP_WEBHOOK_URL", "tu-url")
        print(f"  📱 WhatsApp: Configura webhook en Meta → {url}")

    print("═" * 50)
    print()


if __name__ == "__main__":
    run_onboarding()
```

---

### 2.4 — management/admin.py

Admin programático via `AgentOSClient`. Permite gestionar sesiones, memorias, knowledge y ejecutar el agente desde código o CLI.

```python
"""
Admin — Gestión programática via AgentOSClient.

Uso como CLI:
    python -m management.admin status
    python -m management.admin sessions --user +593991234567
    python -m management.admin memories --user +593991234567
    python -m management.admin run --agent agnobot-main --message "Hola"
    python -m management.admin knowledge-search --query "documento"

Uso como módulo:
    from management.admin import AdminClient
    admin = AdminClient("http://localhost:8000")
    await admin.status()
"""
import asyncio
import argparse
import sys
from typing import Optional

from agno.client import AgentOSClient
from agno.run.agent import RunContentEvent, RunCompletedEvent


class AdminClient:
    """Wrapper de AgentOSClient con operaciones de administración."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = AgentOSClient(base_url=base_url)

    async def status(self) -> dict:
        """Obtiene configuración y estado del AgentOS."""
        config = await self.client.aget_config()
        return {
            "name": config.name or config.os_id,
            "agents": [a.id for a in (config.agents or [])],
            "teams": [t.id for t in (config.teams or [])],
            "workflows": [w.id for w in (config.workflows or [])],
        }

    async def list_sessions(self, user_id: str) -> list[dict]:
        """Lista sesiones de un usuario."""
        sessions = await self.client.get_sessions(user_id=user_id)
        return [
            {
                "session_id": s.session_id,
                "name": s.session_name or "Sin nombre",
            }
            for s in sessions.data
        ]

    async def get_session_detail(self, session_id: str) -> list[dict]:
        """Obtiene los runs de una sesión."""
        runs = await self.client.get_session_runs(session_id=session_id)
        return [
            {
                "run_id": r.run_id,
                "content": (r.content[:100] + "...") if r.content and len(str(r.content)) > 100 else r.content,
            }
            for r in runs
        ]

    async def delete_session(self, session_id: str) -> None:
        """Elimina una sesión."""
        await self.client.delete_session(session_id)

    async def list_memories(self, user_id: str) -> list[dict]:
        """Lista memorias de un usuario."""
        memories = await self.client.list_memories(user_id=user_id)
        return [
            {
                "memory_id": m.memory_id,
                "memory": m.memory,
                "topics": getattr(m, "topics", []),
            }
            for m in memories.data
        ]

    async def create_memory(
        self,
        user_id: str,
        memory: str,
        topics: Optional[list[str]] = None,
    ) -> dict:
        """Crea una memoria para un usuario."""
        result = await self.client.create_memory(
            memory=memory,
            user_id=user_id,
            topics=topics or [],
        )
        return {
            "memory_id": result.memory_id,
            "memory": result.memory,
        }

    async def delete_memory(self, memory_id: str, user_id: str) -> None:
        """Elimina una memoria."""
        await self.client.delete_memory(memory_id, user_id=user_id)

    async def run_agent(
        self,
        agent_id: str,
        message: str,
        user_id: str = "admin",
        session_id: Optional[str] = None,
    ) -> str:
        """Ejecuta el agente y retorna la respuesta completa."""
        result = await self.client.run_agent(
            agent_id=agent_id,
            message=message,
            user_id=user_id,
            session_id=session_id,
        )
        return result.content or ""

    async def run_agent_stream(
        self,
        agent_id: str,
        message: str,
        user_id: str = "admin",
        session_id: Optional[str] = None,
    ) -> str:
        """Ejecuta el agente con streaming."""
        full_response = []
        async for event in self.client.run_agent_stream(
            agent_id=agent_id,
            message=message,
            user_id=user_id,
            session_id=session_id,
        ):
            if isinstance(event, RunContentEvent):
                print(event.content, end="", flush=True)
                full_response.append(event.content)
            elif isinstance(event, RunCompletedEvent):
                print()
        return "".join(full_response)

    async def search_knowledge(self, query: str, limit: int = 5) -> list[dict]:
        """Busca en la Knowledge Base via AgentOS API."""
        results = await self.client.search_knowledge(query=query, limit=limit)
        return [
            {
                "content": str(r.content)[:200] if hasattr(r, "content") else str(r)[:200],
                "score": getattr(r, "score", None),
            }
            for r in results.data
        ]


# ═══════════════════════════════════
# CLI
# ═══════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="admin",
        description="OpenAgno — Herramienta de administración",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="URL del AgentOS (default: http://localhost:8000)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Estado del AgentOS")

    # sessions
    p_sessions = sub.add_parser("sessions", help="Listar sesiones")
    p_sessions.add_argument("--user", required=True, help="User ID")

    # session-detail
    p_detail = sub.add_parser("session-detail", help="Detalle de una sesión")
    p_detail.add_argument("--session-id", required=True)

    # delete-session
    p_del_sess = sub.add_parser("delete-session", help="Eliminar sesión")
    p_del_sess.add_argument("--session-id", required=True)

    # memories
    p_mem = sub.add_parser("memories", help="Listar memorias")
    p_mem.add_argument("--user", required=True)

    # create-memory
    p_cmem = sub.add_parser("create-memory", help="Crear memoria")
    p_cmem.add_argument("--user", required=True)
    p_cmem.add_argument("--memory", required=True)
    p_cmem.add_argument("--topics", nargs="*", default=[])

    # delete-memory
    p_dmem = sub.add_parser("delete-memory", help="Eliminar memoria")
    p_dmem.add_argument("--memory-id", required=True)
    p_dmem.add_argument("--user", required=True)

    # run
    p_run = sub.add_parser("run", help="Ejecutar agente")
    p_run.add_argument("--agent", default="agnobot-main")
    p_run.add_argument("--message", required=True)
    p_run.add_argument("--user", default="admin")
    p_run.add_argument("--stream", action="store_true")

    # knowledge-search
    p_ks = sub.add_parser("knowledge-search", help="Buscar en Knowledge Base")
    p_ks.add_argument("--query", required=True)
    p_ks.add_argument("--limit", type=int, default=5)

    return parser


async def _run_cli(args: argparse.Namespace) -> None:
    admin = AdminClient(base_url=args.url)

    match args.command:
        case "status":
            info = await admin.status()
            print(f"\n🤖 {info['name']}")
            print(f"   Agentes: {', '.join(info['agents']) or 'ninguno'}")
            print(f"   Teams:   {', '.join(info['teams']) or 'ninguno'}")

        case "sessions":
            sessions = await admin.list_sessions(args.user)
            print(f"\n📋 Sesiones de {args.user} ({len(sessions)}):")
            for s in sessions:
                print(f"  • {s['session_id']}: {s['name']}")

        case "session-detail":
            runs = await admin.get_session_detail(args.session_id)
            print(f"\n📝 Runs en sesión ({len(runs)}):")
            for r in runs:
                print(f"  • {r['run_id']}: {r['content']}")

        case "delete-session":
            await admin.delete_session(args.session_id)
            print(f"✅ Sesión {args.session_id} eliminada")

        case "memories":
            memories = await admin.list_memories(args.user)
            print(f"\n🧠 Memorias de {args.user} ({len(memories)}):")
            for m in memories:
                topics = ", ".join(m["topics"]) if m["topics"] else "sin topics"
                print(f"  • [{topics}] {m['memory']}")

        case "create-memory":
            result = await admin.create_memory(args.user, args.memory, args.topics)
            print(f"✅ Memoria creada: {result['memory_id']}")

        case "delete-memory":
            await admin.delete_memory(args.memory_id, args.user)
            print(f"✅ Memoria {args.memory_id} eliminada")

        case "run":
            print(f"\n🤖 Ejecutando {args.agent}...\n")
            if args.stream:
                await admin.run_agent_stream(args.agent, args.message, args.user)
            else:
                response = await admin.run_agent(args.agent, args.message, args.user)
                print(response)

        case "knowledge-search":
            results = await admin.search_knowledge(args.query, args.limit)
            print(f"\n🔍 Resultados para '{args.query}' ({len(results)}):")
            for i, r in enumerate(results, 1):
                score = f" (score: {r['score']:.3f})" if r["score"] else ""
                print(f"  {i}.{score} {r['content']}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(_run_cli(args))
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

### 2.5 — Correcciones a loader.py

Cambios exactos a aplicar sobre el `loader.py` actual:

```python
# ═══ CAMBIO 1: Nuevo import (agregar después de los imports existentes) ═══
from agno.memory import MemoryManager

# ═══ CAMBIO 2: En load_workspace(), reemplazar la construcción de main_agent ═══
# ANTES (líneas actuales):
#   main_agent = Agent(
#       ...
#       enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
#       enable_user_memories=mem_config.get("enable_user_memories", True),
#       enable_session_summaries=mem_config.get("enable_session_summaries", True),
#       ...
#   )

# DESPUÉS:
    # Construir MemoryManager para memoria agentic
    memory_manager = None
    if mem_config.get("enable_agentic_memory", True):
        memory_manager = MemoryManager(model=model, db=db)

    main_agent = Agent(
        name=agent_config.get("name", "AgnoBot"),
        id=agent_config.get("id", "agnobot-main"),
        description=agent_config.get("description", "Asistente personal multimodal"),
        model=model,
        db=db,
        knowledge=knowledge,
        search_knowledge=knowledge is not None,
        tools=tools,
        instructions=instructions,
        memory_manager=memory_manager,
        enable_agentic_memory=mem_config.get("enable_agentic_memory", True),
        add_history_to_context=True,
        num_history_runs=mem_config.get("num_history_runs", 5),
        add_datetime_to_context=True,
        markdown=True,
    )
```

---

### 2.6 — Correcciones a routes/knowledge_routes.py

```python
# ═══ CAMBIO en upload_document: agregar skip_if_exists y name ═══
# ANTES:
#   knowledge.insert(path=tmp_path)

# DESPUÉS:
    knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
```

---

### 2.7 — Corrección a workspace/config.yaml (generado por CLI)

Eliminar parámetros no documentados del bloque memory:

```yaml
# ANTES:
memory:
  enable_agentic_memory: true
  enable_user_memories: true       # ← ELIMINAR
  enable_session_summaries: true   # ← ELIMINAR
  num_history_runs: 5

# DESPUÉS:
memory:
  enable_agentic_memory: true
  num_history_runs: 5
```

---

### 2.8 — Integración: Validación al arrancar gateway.py

Agregar validación automática al inicio de `gateway.py`:

```python
# ═══ Agregar al inicio de gateway.py, antes de load_workspace() ═══
from management.validator import validate_workspace, print_validation

errors = validate_workspace()
if errors:
    print_validation(errors)
    # No bloquear arranque, solo advertir
    logger.warning(f"Workspace tiene {len(errors)} advertencia(s)")
```

---

### Checklist Fase 2

| # | Tarea | Estado |
|---|-------|--------|
| 1 | `management/__init__.py` — módulo | ⬜ |
| 2 | `management/validator.py` — validación de workspace | ⬜ |
| 3 | `management/cli.py` — wizard genera workspace/ completo | ⬜ |
| 4 | `management/admin.py` — CLI + módulo con AgentOSClient | ⬜ |
| 5 | Corregir `loader.py` — MemoryManager + eliminar params inválidos | ⬜ |
| 6 | Corregir `routes/knowledge_routes.py` — skip_if_exists | ⬜ |
| 7 | Corregir `workspace/config.yaml` — eliminar params no documentados | ⬜ |
| 8 | Integrar validación en `gateway.py` | ⬜ |
| 9 | Agregar `rich` a `requirements.txt` | ⬜ |
| 10 | Testear: `python -m management.cli` genera workspace válido | ⬜ |
| 11 | Testear: `python -m management.validator` pasa sin errores | ⬜ |
| 12 | Testear: `python -m management.admin status` conecta al gateway | ⬜ |

---

### Comandos de Prueba Fase 2

```bash
# 1. Generar workspace desde cero
python -m management.cli

# 2. Validar workspace
python -m management.validator

# 3. Arrancar gateway (con validación automática)
python gateway.py

# 4. Admin — verificar estado
python -m management.admin status

# 5. Admin — listar sesiones de un usuario
python -m management.admin sessions --user "+593991234567"

# 6. Admin — ver memorias
python -m management.admin memories --user "+593991234567"

# 7. Admin — ejecutar agente directamente
python -m management.admin run --agent agnobot-main --message "Hola, ¿cómo estás?"

# 8. Admin — ejecutar con streaming
python -m management.admin run --agent agnobot-main --message "Busca noticias de IA" --stream

# 9. Admin — buscar en Knowledge Base
python -m management.admin knowledge-search --query "documentación"

# 10. Admin — crear memoria manualmente
python -m management.admin create-memory --user admin --memory "El usuario prefiere respuestas en español" --topics preferencias idioma
```

---

### Dependencias Adicionales Fase 2

No se requieren dependencias nuevas. Todo usa:
- `agno[os]` — incluye `AgentOSClient` y `MemoryManager`
- `pyyaml` — ya instalado
- `python-dotenv` — ya instalado

Opcional:
```
rich    # Para output con formato (no bloqueante)
```
