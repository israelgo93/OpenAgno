# OpenAgno

OpenAgno es una plataforma para construir y operar agentes sobre **Agno** usando un **workspace declarativo**. El proyecto empaqueta una CLI (`openagno`), un runtime AgentOS/FastAPI, templates listos para usar, canales, knowledge con PgVector y soporte MCP.

## Estado actual

OpenAgno hoy sí incluye:

- CLI empaquetada `openagno`
- workspace declarativo en `workspace/`
- runtime AgentOS con rutas operativas y knowledge
- templates empaquetados
- canales: WhatsApp, Slack y Telegram
- protocolos opcionales: AG-UI y A2A
- knowledge vectorial con PostgreSQL/Supabase + PgVector
- tests automatizados
- documentación en Mintlify

OpenAgno hoy no incluye todavía:

- multi-tenancy productiva
- autenticación/dashboard SaaS
- remote execution o sandbox aislado
- billing
- despliegue AWS automatizado desde la CLI

## Instalación

OpenAgno **todavía no se distribuye públicamente vía PyPI**. La ruta recomendada es instalarlo desde el repositorio.

Requisitos mínimos:

- Python 3.10+
- Python 3.11+ recomendado
- PostgreSQL con `pgvector` si quieres knowledge vectorial
- Node.js 18+ solo si usarás el bridge WhatsApp QR o Mintlify local

Instalación recomendada:

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si vas a desarrollar, preparar builds o usar protocolos avanzados:

```bash
pip install -e '.[dev,protocols]'
```

## Inicio rápido

```bash
openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground
```

Health check:

```bash
curl http://127.0.0.1:8000/admin/health
```

## Flujo recomendado

1. Crea un workspace desde un template.
2. Completa `.env` con tu modelo, base de datos y canales.
3. Valida con `openagno validate`.
4. Arranca con `openagno start --foreground` para desarrollo o `openagno start` para supervisor local.
5. Conecta canales y clientes sobre el runtime ya levantado.

## Comandos principales

```bash
openagno init --template <id>
openagno templates list
openagno templates show <id>
openagno validate
openagno start --foreground
openagno start
openagno status
openagno logs --follow
openagno stop
openagno restart
openagno create agent "<nombre>"
openagno add whatsapp --mode cloud_api
openagno add slack
openagno add telegram
openagno add agui
openagno add a2a
openagno add tool tavily
openagno deploy docker
```

`openagno deploy aws` todavía no automatiza despliegue; hoy funciona como guía y no como provisionador.

## Estructura actual del repo

```text
OpenAgno/
  openagno/            # CLI, helpers y templates empaquetados
  workspace/           # Configuración declarativa del agente
  gateway.py           # Runtime AgentOS/FastAPI
  loader.py            # Construcción de agentes, DB, knowledge y MCP
  routes/              # Rutas REST custom
  tools/               # Tools locales del runtime
  tests/               # Suite de regresión
  docs/                # Sitio Mintlify
  bridges/whatsapp-qr/ # Bridge opcional para QR
  deploy/              # Assets de despliegue y systemd
```

## Workspace

Los archivos importantes están en `workspace/`:

- `config.yaml`: modelo, DB, canales, scheduler y runtime
- `instructions.md`: comportamiento principal del agente
- `tools.yaml`: builtin y optional tools
- `mcp.yaml`: servidores MCP
- `self_knowledge.md`: contexto operacional del agente
- `knowledge/urls.yaml`: URLs a ingerir
- `agents/*.yaml`: sub-agentes
- `agents/teams.yaml`: teams
- `schedules.yaml`: cron jobs
- `integrations/`: integraciones declarativas

## Canales y protocolos

Canales soportados por el runtime actual:

- `whatsapp`
- `slack`
- `telegram`
- `agui`

Protocolos adicionales:

- `a2a.enabled: true`

Notas:

- Slack y Telegram ya están incluidos en las dependencias base del proyecto.
- `agui` y `a2a` requieren instalar el extra `.[protocols]`.
- El canal `ai_sdk` no forma parte del runtime compatible actual de Agno y no debe usarse.

## MCP y docs públicas

La documentación de OpenAgno ya expone:

- MCP remoto: `https://docs.openagno.com/mcp`
- índice AI: `https://docs.openagno.com/llms.txt`

## Release prep para maintainers

La publicación pública sigue pendiente, pero puedes validar el empaquetado localmente:

```bash
python -m build
```

## Documentación

La documentación vive en `docs/`.

Preview local:

```bash
cd docs
npm install
npm run dev
```

Chequeo de links:

```bash
cd docs
npm run broken-links
```

## Licencia

Apache 2.0.
