# OpenAgno — Plan Estratégico Consolidado v1.0

*Fecha: 27 de marzo de 2026*
*Versión actual del código: v1.0.0 (post-Fase 8)*
*Presupuesto AWS: $10,000 USD (créditos Baeza)*

---

## 1. Diagnóstico del Estado Actual

### 1.1 Fases Completadas (F1–F8)

| Fase | Estado | Entregables Clave |
|------|--------|-------------------|
| F1 | ✅ Done | Workspace declarativo, loader.py, gateway.py, PgVector/Supabase, WhatsApp, MCP docs.agno.com |
| F2 | ✅ Done | CLI onboarding wizard, Admin (AgentOSClient) |
| F3 | ✅ Done | Slack, Web, Studio, Sub-agentes YAML, Teams (TeamMode) |
| F4 | ⚠️ Parcial | Remote Execution planificado pero NO implementado (DAT-217 en Backlog) |
| F5 | ✅ Done | Scheduler, auto-ingesta Knowledge, Tavily MCP |
| F6 | ✅ Done | Autonomía operativa: daemon, WorkspaceTools, SchedulerTools, AWS Bedrock, systemd |
| F7 | ✅ Done | Estabilización: bug fixes, auto-consciencia del agente, seguridad (API Key, SQL injection) |
| F8 | ✅ Done* | Model IDs actualizados, workspace genérico, 13 tools opcionales, WhatsApp dual (Cloud API + QR), Studio/Registry, README |

*\*DAT-241 (tests) sigue en Backlog.*

### 1.2 Deuda Técnica y Bugs Activos

| Issue | Tipo | Prioridad | Descripción |
|-------|------|-----------|-------------|
| DAT-250 | Bug | High | Mensajes fantasma WhatsApp — webhook procesa duplicados |
| DAT-251 | Bug | Normal | Claude/Bedrock 400 error `tool_use_id` al cambiar modelo mid-session |
| DAT-241 | Mejora | Medium | Directorio /tests inexistente |
| DAT-217 | Feature | High | Remote Execution — nunca implementado desde F4 |
| — | Deuda | High | `build_mcp_tools()` retorna `dict` en vez de `MCPTools` → stdio MCPs filtrados |
| — | Deuda | Medium | Sin rate limiting en endpoints REST |
| — | Deuda | Medium | DB URL en f-string expuesta en tracebacks |
| — | Deuda | Low | Dependencias sin pinning (builds no reproducibles) |

### 1.3 Capacidades Actuales del Código

**Lo que ya funciona:**
- Workspace declarativo completo (config.yaml, instructions.md, tools.yaml, mcp.yaml, agents/*.yaml)
- Multi-modelo (Gemini 2.5, Claude via Bedrock, GPT-4o, Groq)
- Multi-canal (WhatsApp Cloud API + QR, Slack, Telegram, Web)
- RAG con PgVector (SearchType.hybrid + OpenAIEmbedder)
- Memoria agentic persistente en PostgreSQL
- Sub-agentes dinámicos desde YAML
- Teams multi-agente con TeamMode
- Auto-configuración del agente (WorkspaceTools: CRUD workspace, crear sub-agentes, toggle tools)
- Scheduler con crons via API REST
- CLI wizard de onboarding
- Seguridad básica (API Key, SQL injection whitelist)
- Studio (os.agno.com) con Registry
- systemd para producción

**Lo que NO existe aún:**
- Multi-tenancy (aislamiento por usuario/organización)
- Autenticación de usuarios (registro, login, dashboard)
- Sistema de templates de agentes
- Ejecución en sandbox (contenedores aislados)
- Remote Execution distribuido
- Tests automatizados
- Billing/suscripciones
- CLI como producto empaquetado (pip install openagno)

### 1.4 Evaluación de los 4 PDFs Estratégicos

| PDF | Foco | ¿Realista? | Prioridad para MVP |
|-----|------|-----------|---------------------|
| Strategy v1 | Arquitectura, diferenciación vs OpenClaw, sandbox, SaaS | ✅ Sí, pero sandbox requiere infra significativa | Alta |
| Strategy v2 | CLI unificado (`openagno start/stop/restart`) | ✅ Sí, alcanzable en 1-2 sprints | Alta |
| Strategy v3 | CLI nivel producto, cross-platform, templates, wizard | ✅ Sí con Typer + pip | Alta |
| Strategy v4 | SaaS completo, monetización $3.99, serverless Lambda | ⚠️ Parcial — Lambda no es compatible con AgentOS (necesita persistencia). ECS Fargate sí | Media-Alta |

**Conclusión:** Las 4 estrategias son complementarias y viables, pero Lambda como runtime principal es incompatible con AgentOS (que requiere FastAPI + WebSocket + estado). La arquitectura correcta para SaaS es **ECS Fargate** (que Agno ya soporta con template oficial).

---

## 2. Arquitectura Objetivo: OpenAgno SaaS

### 2.1 Modelo de Despliegue

```
                    ┌─────────────────────────────────────┐
                    │          CONTROL PLANE (Web)         │
                    │  ┌─────────┐ ┌──────┐ ┌──────────┐  │
                    │  │Dashboard│ │Auth  │ │Templates │  │
                    │  │(Next.js)│ │(Supa)│ │(Registry)│  │
                    │  └────┬────┘ └──┬───┘ └────┬─────┘  │
                    │       └─────────┼──────────┘        │
                    │            API Gateway               │
                    └────────────┬────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │      DATA PLANE (Per-Tenant)        │
                    │  ┌──────────────────────────────┐   │
                    │  │  ECS Fargate Task (AgentOS)   │   │
                    │  │  ┌────────┐ ┌──────────────┐ │   │
                    │  │  │ Agent  │ │ Sub-Agents   │ │   │
                    │  │  │(loader)│ │ (workspace/) │ │   │
                    │  │  └────────┘ └──────────────┘ │   │
                    │  └──────────────────────────────┘   │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │  RDS PostgreSQL + PgVector    │   │
                    │  │  (shared DB, schema isolation) │  │
                    │  └──────────────────────────────┘   │
                    └─────────────────────────────────────┘
```

### 2.2 Estrategia de Multi-Tenancy

**Opción elegida: Schema-per-tenant en DB compartida**

- Una sola instancia RDS PostgreSQL (costo mínimo)
- Cada tenant tiene su propio schema (`tenant_{id}`)
- Las tablas de sesiones, memorias, knowledge y vectores se crean por tenant
- `db_url` incluye `options=-c search_path=tenant_{id}` o se setea al crear la conexión
- Compatible con `PostgresDb` de Agno (el `table_name` se prefija con el tenant)

**Razón:** Con $10K de créditos, una RDS compartida (db.t3.medium ~$30/mes) soporta ~100 tenants iniciales sin problemas. Escalar a RDS por tenant solo cuando sea necesario.

### 2.3 Modelo de Ejecución por Tenant

**Fase MVP (shared compute):**
- Un solo servicio ECS Fargate corre múltiples AgentOS
- Routing por `tenant_id` en headers
- Workspaces almacenados en S3 (no en filesystem local)
- Costo estimado: $50-100/mes en Fargate

**Fase Scale (isolated compute):**
- Un ECS Task por tenant activo (cold start ~30s)
- Auto-scaling a 0 cuando inactivo (ahorro)
- Workspace se monta desde S3 al arrancar

---

## 3. Plan de Implementación: 4 Fases hacia MVP SaaS

### Fase 9: Estabilización + CLI Producto (2 semanas)

**Objetivo:** Cerrar toda deuda técnica, crear CLI empaquetable, tests.

#### 9.1 — Resolver Bugs Activos

| Archivo | Cambio |
|---------|--------|
| `gateway.py` | Fix DAT-250: deduplicar mensajes WhatsApp con cache de `message_id` (TTL 60s) |
| `loader.py` | Fix DAT-251: sanitizar historial de sesión al cambiar modelo (limpiar `tool_use_id` incompatibles) |
| `loader.py` | Fix MCP stdio: `build_mcp_tools()` debe retornar `MCPTools` instance, no dict |

```python
# Fix DAT-250 — Deduplicación WhatsApp
import time
_processed_messages = {}  # {message_id: timestamp}

@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: dict):
    msg_id = request.get("message_id", "")
    now = time.time()
    # Limpiar cache viejo
    _processed_messages = {k: v for k, v in _processed_messages.items() if now - v < 60}
    if msg_id in _processed_messages:
        return {"status": "duplicate_ignored"}
    _processed_messages[msg_id] = now
    # ... procesar normalmente
```

#### 9.2 — CLI como Producto (`openagno`)

Migrar `management/cli.py` a CLI distribuible con Typer:

```
openagno/
├── __init__.py
├── __main__.py          # python -m openagno
├── cli.py               # Typer app principal
├── commands/
│   ├── init.py          # openagno init (wizard)
│   ├── start.py         # openagno start [--daemon]
│   ├── stop.py          # openagno stop
│   ├── restart.py       # openagno restart
│   ├── status.py        # openagno status
│   ├── logs.py          # openagno logs [--follow]
│   ├── create.py        # openagno create agent <name>
│   ├── add.py           # openagno add whatsapp|slack|telegram
│   ├── validate.py      # openagno validate
│   └── deploy.py        # openagno deploy aws|docker|local
├── templates/           # Templates de workspace pre-configurados
│   ├── personal_assistant/
│   ├── customer_support/
│   ├── research_agent/
│   └── sales_agent/
└── core/
    ├── loader.py        # Refactored desde loader.py actual
    ├── gateway.py       # Refactored
    └── service_manager.py
```

**Comandos principales:**

```bash
# Instalación
pip install openagno

# Crear proyecto nuevo
openagno init                          # Wizard interactivo
openagno init --template sales_agent   # Desde template

# Operaciones
openagno start                         # Arrancar gateway
openagno start --daemon                # Como servicio background
openagno stop                          # Detener
openagno status                        # Estado del servicio
openagno logs --follow                 # Logs en tiempo real

# Configuración
openagno create agent research         # Crear sub-agente
openagno add whatsapp                  # Agregar canal
openagno add tool yfinance             # Agregar tool
openagno validate                      # Validar workspace

# Deploy
openagno deploy docker                 # Docker compose local
openagno deploy aws                    # AWS ECS Fargate
```

**`pyproject.toml`:**

```toml
[project]
name = "openagno"
version = "1.0.0"
description = "Build autonomous AI agents with declarative YAML configuration"
requires-python = ">=3.10"
dependencies = [
    "agno[os,scheduler]>=0.5.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "psycopg[binary]>=3.0",
    "openai>=1.0",
]

[project.scripts]
openagno = "openagno.cli:app"

[project.optional-dependencies]
aws = ["boto3>=1.35", "agno-infra"]
all = ["anthropic", "boto3>=1.35", "crawl4ai", "tavily-python", "yfinance"]
```

#### 9.3 — Tests Básicos

```
tests/
├── conftest.py              # Fixtures: workspace temporal, DB mock
├── test_loader.py           # load_yaml, build_model, build_tools, build_db_url
├── test_validator.py        # validate_workspace con configs válidas/inválidas
├── test_security.py         # verify_api_key
├── test_workspace_tools.py  # CRUD workspace, validación provider/tools
├── test_cli_commands.py     # Smoke tests de comandos CLI
└── test_dedup.py            # Deduplicación WhatsApp
```

#### 9.4 — Pinear Dependencias

```bash
# Generar lockfile
pip freeze > requirements.lock
# O mejor, migrar a uv/poetry
uv init && uv add agno[os,scheduler] typer rich psycopg[binary]
```

**Issues Linear para Fase 9:**

| Issue | Prioridad | Descripción |
|-------|-----------|-------------|
| DAT-252 | Urgent | Fix DAT-250: dedup WhatsApp messages |
| DAT-253 | High | Fix DAT-251: sanitizar historial cross-model |
| DAT-254 | High | Fix MCP stdio: build_mcp_tools retorna MCPTools |
| DAT-255 | High | CLI como paquete pip (Typer + pyproject.toml) |
| DAT-256 | High | Sistema de templates de workspace |
| DAT-257 | Medium | Tests básicos (pytest) |
| DAT-258 | Medium | Pinear dependencias (uv o lockfile) |
| DAT-259 | Medium | Rate limiting con slowapi |

---

### Fase 10: Templates + Multi-Tenancy Base (2 semanas)

**Objetivo:** Sistema de templates funcional, aislamiento por tenant, workspace en S3.

#### 10.1 — Sistema de Templates

Cada template es un directorio con workspace pre-configurado:

```yaml
# templates/registry.yaml
templates:
  - id: personal_assistant
    name: "Asistente Personal"
    description: "Agente multimodal con búsqueda web, calendario y recordatorios"
    category: personal
    tools: [duckduckgo, reasoning, scheduler_mgmt, crawl4ai]
    channels: [whatsapp]
    model_default: gemini-2.5-flash

  - id: customer_support
    name: "Soporte al Cliente"
    description: "Agente con RAG para atención al cliente 24/7"
    category: business
    tools: [duckduckgo, reasoning, crawl4ai]
    channels: [whatsapp, slack]
    model_default: gemini-2.5-flash
    knowledge: true  # Incluye RAG

  - id: research_agent
    name: "Investigador IA"
    description: "Agente especializado en investigación con múltiples fuentes"
    category: developer
    tools: [duckduckgo, tavily, crawl4ai, arxiv, wikipedia, reasoning]
    channels: [slack]
    model_default: gemini-2.5-pro

  - id: sales_agent
    name: "Agente de Ventas"
    description: "Agente para prospección y seguimiento comercial"
    category: business
    tools: [duckduckgo, email, yfinance, reasoning]
    channels: [whatsapp, slack]
    model_default: gemini-2.5-flash

  - id: developer_assistant
    name: "Asistente para Desarrolladores"
    description: "Agente con GitHub, Shell y Python tools"
    category: developer
    tools: [duckduckgo, github, shell, python_tools, file_tools, reasoning]
    channels: [slack]
    model_default: gemini-2.5-flash
```

**CLI de templates:**

```bash
# Listar templates disponibles
openagno templates list

# Crear desde template
openagno init --template customer_support

# Ver detalles de un template
openagno templates info research_agent
```

#### 10.2 — Multi-Tenancy: Schema Isolation

```python
# tenancy/manager.py
from sqlalchemy import text
from agno.db.postgres import PostgresDb

class TenantManager:
    def __init__(self, base_db_url: str):
        self.base_db_url = base_db_url

    async def create_tenant(self, tenant_id: str) -> dict:
        """Crea schema y tablas para un nuevo tenant."""
        schema = f"tenant_{tenant_id}"
        async with self.engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            # Las tablas se crean automáticamente por Agno al primer uso
        return {"tenant_id": tenant_id, "schema": schema}

    def get_tenant_db(self, tenant_id: str) -> PostgresDb:
        """Retorna PostgresDb configurada para el tenant."""
        schema = f"tenant_{tenant_id}"
        return PostgresDb(
            db_url=self.base_db_url,
            id=f"{tenant_id}_db",
            schema=schema,
            knowledge_table=f"{schema}.knowledge_contents",
        )

    def get_tenant_knowledge(self, tenant_id: str) -> Knowledge:
        """Retorna Knowledge con vectores aislados por tenant."""
        schema = f"tenant_{tenant_id}"
        return Knowledge(
            vector_db=PgVector(
                table_name=f"{schema}.knowledge_vectors",
                db_url=self.base_db_url,
                search_type=SearchType.hybrid,
                embedder=OpenAIEmbedder(id="text-embedding-3-small"),
            ),
            contents_db=self.get_tenant_db(tenant_id),
            max_results=5,
        )
```

#### 10.3 — Workspace en S3

```python
# storage/s3_workspace.py
import boto3
import yaml
import os
from pathlib import Path

class S3WorkspaceManager:
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket

    def upload_workspace(self, tenant_id: str, local_path: str):
        """Sube workspace local a S3."""
        prefix = f"workspaces/{tenant_id}/"
        for root, dirs, files in os.walk(local_path):
            for f in files:
                local_file = os.path.join(root, f)
                s3_key = prefix + os.path.relpath(local_file, local_path)
                self.s3.upload_file(local_file, self.bucket, s3_key)

    def download_workspace(self, tenant_id: str, local_path: str):
        """Descarga workspace de S3 a path local."""
        prefix = f"workspaces/{tenant_id}/"
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                rel_path = obj["Key"][len(prefix):]
                local_file = os.path.join(local_path, rel_path)
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                self.s3.download_file(self.bucket, obj["Key"], local_file)

    def create_from_template(self, tenant_id: str, template_id: str):
        """Crea workspace para tenant desde template."""
        # Copiar template a tenant en S3
        src_prefix = f"templates/{template_id}/"
        dst_prefix = f"workspaces/{tenant_id}/"
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=src_prefix):
            for obj in page.get("Contents", []):
                src_key = obj["Key"]
                dst_key = dst_prefix + src_key[len(src_prefix):]
                self.s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                    Key=dst_key,
                )
```

**Issues Linear para Fase 10:**

| Issue | Prioridad | Descripción |
|-------|-----------|-------------|
| DAT-260 | High | Template registry + 5 templates iniciales |
| DAT-261 | High | TenantManager con schema isolation |
| DAT-262 | High | S3WorkspaceManager (upload/download/create from template) |
| DAT-263 | High | Gateway multi-tenant: routing por header X-Tenant-ID |
| DAT-264 | Medium | CLI: `openagno templates list/info` |

---

### Fase 11: Control Plane + Auth + Dashboard (3 semanas)

**Objetivo:** Dashboard web para usuarios, autenticación con Supabase Auth, deploy one-click.

#### 11.1 — Autenticación (Supabase Auth)

Aprovechamos Supabase (ya integrado para DB) para Auth:

```sql
-- Tabla de tenants en schema public
CREATE TABLE public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    name TEXT NOT NULL,
    template_id TEXT,
    status TEXT DEFAULT 'active',  -- active, paused, deleted
    plan TEXT DEFAULT 'free',      -- free, basic, pro
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: cada usuario solo ve sus tenants
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own tenants"
    ON public.tenants FOR ALL
    USING (user_id = auth.uid());

-- API keys por tenant
CREATE TABLE public.tenant_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES public.tenants(id),
    key_hash TEXT NOT NULL,  -- bcrypt hash
    name TEXT DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT now()
);
```

#### 11.2 — Dashboard Web (Next.js + Supabase)

```
dashboard/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  # Overview
│   │   ├── agents/
│   │   │   ├── page.tsx              # Lista de agentes
│   │   │   ├── new/page.tsx          # Crear agente (seleccionar template)
│   │   │   └── [id]/
│   │   │       ├── page.tsx          # Config del agente
│   │   │       ├── knowledge/page.tsx # Upload docs
│   │   │       ├── channels/page.tsx  # Configurar WhatsApp/Slack
│   │   │       └── logs/page.tsx     # Ver logs
│   │   ├── templates/page.tsx        # Catálogo de templates
│   │   ├── billing/page.tsx          # Plan y uso
│   │   └── settings/page.tsx         # Cuenta
│   └── api/
│       ├── agents/route.ts           # CRUD agentes
│       ├── deploy/route.ts           # Deploy/provision
│       └── webhook/stripe/route.ts   # Billing webhooks
├── components/
├── lib/
│   ├── supabase.ts
│   └── api.ts
└── package.json
```

**Flujo de usuario:**

```
Registro → Verificar email → Elegir template → Configurar (nombre, canales, API keys) → Deploy → Agente activo
```

#### 11.3 — API de Provisioning

```python
# api/provisioning.py
from fastapi import APIRouter, Depends
from tenancy.manager import TenantManager
from storage.s3_workspace import S3WorkspaceManager

router = APIRouter(prefix="/api/v1")

@router.post("/agents")
async def create_agent(
    request: CreateAgentRequest,
    user: User = Depends(get_current_user),
):
    """Crear un nuevo agente desde template."""
    # 1. Crear tenant en DB
    tenant = await tenant_manager.create_tenant(request.tenant_id)

    # 2. Crear workspace desde template en S3
    workspace_manager.create_from_template(
        tenant_id=request.tenant_id,
        template_id=request.template_id,
    )

    # 3. Personalizar workspace
    await customize_workspace(
        tenant_id=request.tenant_id,
        name=request.agent_name,
        instructions=request.instructions,
        model=request.model,
        channels=request.channels,
    )

    # 4. Provision ECS task (o agregar a pool compartido)
    if request.plan == "pro":
        await provision_dedicated_task(tenant)
    else:
        await add_to_shared_pool(tenant)

    return {"status": "active", "tenant_id": request.tenant_id}
```

**Issues Linear para Fase 11:**

| Issue | Prioridad | Descripción |
|-------|-----------|-------------|
| DAT-265 | High | Supabase Auth: tablas tenants + tenant_api_keys + RLS |
| DAT-266 | High | Dashboard Next.js: registro, login, lista agentes |
| DAT-267 | High | Flujo crear agente: seleccionar template → configurar → deploy |
| DAT-268 | High | API provisioning: create/start/stop/delete agent |
| DAT-269 | High | Página de configuración del agente (editar instructions, tools, channels) |
| DAT-270 | Medium | Página de knowledge upload (drag-and-drop PDFs) |
| DAT-271 | Medium | Página de logs del agente |

---

### Fase 12: Deploy AWS + Billing + Launch (2 semanas)

**Objetivo:** Infraestructura AWS con ECS Fargate, billing con Stripe, lanzamiento público.

#### 12.1 — Infraestructura AWS

Usando el template oficial de Agno (`agent-infra-aws`):

```python
# infra/settings.py
from agno_infra import InfraSettings

infra_settings = InfraSettings(
    aws_region="us-east-1",
    # ECS Fargate
    ecs_cpu=512,           # 0.5 vCPU ($15/mes)
    ecs_memory=1024,       # 1 GB
    ecs_desired_count=1,   # 1 task inicialmente
    ecs_max_count=4,       # Auto-scale hasta 4
    # RDS PostgreSQL
    rds_instance_class="db.t3.micro",  # $15/mes
    rds_allocated_storage=20,           # 20 GB
    rds_engine_version="16",
    # ALB
    enable_https=True,
    domain="api.openagno.com",
    # S3 para workspaces
    s3_bucket="openagno-workspaces",
)
```

**Costos estimados mensuales (MVP):**

| Servicio | Config | Costo/mes |
|----------|--------|-----------|
| ECS Fargate | 0.5 vCPU, 1 GB, 1 task | ~$15 |
| RDS PostgreSQL | db.t3.micro, 20 GB | ~$15 |
| ALB | 1 load balancer | ~$20 |
| S3 | Workspaces + templates | ~$2 |
| CloudWatch | Logs + métricas | ~$5 |
| Route 53 | DNS | ~$1 |
| ACM | SSL (gratis) | $0 |
| Supabase | Auth (free tier) | $0 |
| **Total** | | **~$58/mes** |

**Con $10,000 de créditos: ~172 meses de operación MVP** (más que suficiente para validar el producto).

#### 12.2 — Billing con Stripe

```yaml
# Planes
plans:
  free:
    price: 0
    agents: 1
    messages: 100/día
    channels: [whatsapp_qr]   # Solo QR (sin costo Meta)
    knowledge: 5 docs
    model: gemini-2.5-flash

  basic:
    price: 3.99/mes
    agents: 3
    messages: 1000/día
    channels: [whatsapp, slack]
    knowledge: 50 docs
    models: [gemini-2.5-flash, gemini-2.5-pro]

  pro:
    price: 14.99/mes
    agents: 10
    messages: unlimited
    channels: [whatsapp, slack, telegram, web]
    knowledge: unlimited
    models: all
    dedicated_compute: true   # ECS task dedicado
    sub_agents: true
    teams: true
```

#### 12.3 — Docker Compose Producción

```yaml
# docker-compose.prod.yml
services:
  gateway:
    image: ${ECR_REPO}/openagno-gateway:latest
    environment:
      - TENANT_MODE=multi
      - S3_WORKSPACE_BUCKET=openagno-workspaces
      - DATABASE_URL=${RDS_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    ports:
      - "8000:8000"
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 1024M

  dashboard:
    image: ${ECR_REPO}/openagno-dashboard:latest
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_SUPABASE_URL=${SUPABASE_URL}
      - NEXT_PUBLIC_SUPABASE_KEY=${SUPABASE_KEY}
      - API_URL=http://gateway:8000

  whatsapp-bridge:
    image: ${ECR_REPO}/openagno-wa-bridge:latest
    ports:
      - "3001:3001"
    volumes:
      - wa_sessions:/data/session
    profiles:
      - qr

volumes:
  wa_sessions:
```

**Issues Linear para Fase 12:**

| Issue | Prioridad | Descripción |
|-------|-----------|-------------|
| DAT-272 | Urgent | Infra AWS: ECS Fargate + RDS + ALB + S3 |
| DAT-273 | High | Stripe: 3 planes (free, basic, pro) + webhooks |
| DAT-274 | High | Docker compose producción multi-servicio |
| DAT-275 | High | CI/CD: GitHub Actions → ECR → ECS deploy |
| DAT-276 | High | Landing page (openagno.com) |
| DAT-277 | Medium | Monitoreo: CloudWatch logs + alarms |
| DAT-278 | Medium | Documentación usuario (docs.openagno.com) |

---

## 4. Resumen de Compatibilidad con Agno

| Requisito | Agno Support | Verificación |
|-----------|-------------|--------------|
| ECS Fargate deploy | ✅ Template oficial `agent-infra-aws` | docs.agno.com/deploy/templates/aws |
| Multi-agent por instancia | ✅ `AgentOS(agents=[...])` | Ya implementado |
| PostgreSQL persistence | ✅ `PostgresDb` + `PgVector` | Ya implementado |
| Multi-channel | ✅ WhatsApp, Slack, Telegram interfaces | Ya implementado |
| Schema isolation | ✅ `db_url` configurable por instancia | Compatible |
| MCP Server | ✅ `enable_mcp_server=True` | Ya implementado |
| Scheduler | ✅ `scheduler=True` + REST API | Ya implementado |
| Teams | ✅ `TeamMode` (coordinate, route, etc.) | Ya implementado |
| Studio | ✅ `Registry` + os.agno.com | Ya implementado |

**Ningún cambio propuesto rompe la compatibilidad con Agno.** Todo se construye sobre las APIs existentes.

---

## 5. Cronograma y Prioridades

```
Semana 1-2:  Fase 9 — Estabilización + CLI Producto
Semana 3-4:  Fase 10 — Templates + Multi-Tenancy
Semana 5-7:  Fase 11 — Dashboard + Auth + Provisioning
Semana 8-9:  Fase 12 — AWS Deploy + Billing + Launch
```

**Total: ~9 semanas hasta MVP SaaS listo para venta**

### Priorización de Funcionalidades

```
MUST HAVE (MVP)                  SHOULD HAVE (v1.1)              NICE TO HAVE (v2.0)
─────────────────                ──────────────────              ───────────────────
• CLI pip install                • Remote Execution              • Marketplace de templates
• 5 templates iniciales          • Sandbox ejecución             • White-label
• Multi-tenancy DB               • AG-UI (chat web)              • API pública
• Auth Supabase                  • Más templates                 • Mobile app
• Dashboard básico               • Analytics por agente          • Custom LLM hosting
• WhatsApp + Slack               • Telegram channel              • A2A Protocol
• Deploy AWS ECS                 • WebSocket streaming           • Enterprise SSO
• Stripe billing                 • Rate limiting avanzado        • GPU instances
• 3 planes de precio             • Backup automático             • Edge deployment
```

---

## 6. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Créditos AWS se agotan antes de revenue | Alto | MVP cuesta ~$58/mes → créditos duran 172 meses |
| Agno cambia API breaking | Alto | Pinear versión en pyproject.toml, monitorear releases |
| WhatsApp Cloud API requiere verificación Business | Medio | Modo QR (Baileys) como alternativa para free tier |
| Costos de LLM por usuario | Alto | Rate limits por plan, modelos baratos por defecto (Gemini Flash) |
| Competencia (OpenClaw, etc.) | Medio | Diferenciación: multi-agente, templates, self-config |
| Seguridad multi-tenant | Alto | Schema isolation + RLS + API keys por tenant |

---

## 7. Métricas de Éxito del MVP

| Métrica | Target (3 meses post-launch) |
|---------|------------------------------|
| Usuarios registrados | 100+ |
| Agentes activos | 50+ |
| Usuarios pagos (basic+pro) | 10+ |
| Revenue mensual | $100+ MRR |
| Uptime | 99.5%+ |
| Tiempo de onboarding | < 5 minutos |
| Templates usados | 5+ |

---

*Documento generado el 27 de marzo de 2026.*
*Fuentes: Linear (DAT-190→251), gateway.log, docs.agno.com, Strategy PDFs v1-v4, Agno deploy templates, análisis QA.*
*Compatible con: Agno Framework, AgentOS, PostgresDb, PgVector, Supabase.*
