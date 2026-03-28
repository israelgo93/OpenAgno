# OpenAgno — Fase 8: Producción, Tools Expandidos, Studio Completo y WhatsApp Dual

*Fecha: 26 de marzo de 2026*
*Versión objetivo: v1.0.0*

---

## Diagnóstico Pre-Fase 8

### Estado de Fase 7 (v0.8.0): COMPLETADA

Todos los issues DAT-226 a DAT-234 en Done. Fixes: scheduler base_url, fallback 429 retry, mensajes vacíos, auto-consciencia del agente, seguridad (API Key + SQL injection), WhatsApp auth alert, GithubTools, Telegram, validación schedules, deps pineadas.

**Deuda pendiente**: DAT-217 (Remote Execution F4) sigue en Backlog.

### Hallazgo crítico: Model IDs desactualizados

`gemini-2.0-flash` será retirado el 1 de junio de 2026. Google restringió nuevos accesos desde marzo 2026. Migrar a `gemini-2.5-flash` es urgente.

---

## Issues Fase 8 (DAT-235 a DAT-241)

| Issue | Prioridad | Descripción |
|-------|-----------|-------------|
| DAT-235 | Urgent | Actualizar model IDs (gemini-2.5-flash, claude-sonnet-4-6) |
| DAT-236 | High | Workspace por defecto genérico para pruebas desde 0 |
| DAT-237 | High | Agregar más tools y canales según docs Agno |
| DAT-238 | High | Studio con Registry completo + AgentOSClient documentado |
| DAT-239 | Medium | Reestructurar README sin info repetida |
| DAT-240 | High | WhatsApp modo dual: API oficial Meta + vinculación QR |
| DAT-241 | Medium | Crear directorio /tests |

---

## 8.1 — Actualizar Model IDs (DAT-235) — URGENTE

### Archivos a modificar

**`workspace/config.yaml`:**
```yaml
model:
  provider: "google"
  id: "gemini-2.5-flash"  # ERA: gemini-2.0-flash
```

**`workspace/agents/research_agent.yaml`:**
```yaml
agent:
  model:
    provider: "google"
    id: "gemini-2.5-flash"
```

**`loader.py`** — defaults en `build_model()`:
```python
model_id = model_config.get("id", "gemini-2.5-flash")  # ERA: gemini-2.0-flash
```

**`tools/workspace_tools.py`** — default en `create_sub_agent()`:
```python
model_id: str = "gemini-2.5-flash",  # ERA: gemini-2.0-flash
```

**`workspace/self_knowledge.md`** — actualizar mapa:
```markdown
| Provider | Modelos recomendados (marzo 2026) |
|----------|----------------------------------|
| google | gemini-2.5-flash (default), gemini-2.5-pro, gemini-3-flash-preview |
| openai | gpt-4o, gpt-4o-mini, o1, o1-mini |
| anthropic | claude-sonnet-4-6, claude-haiku-3-5 |
| aws_bedrock | us.anthropic.claude-sonnet-4-6-v1:0 |
| groq | llama-3.3-70b-versatile |
```

---

## 8.2 — Workspace por defecto genérico (DAT-236)

Resetear todo a valores genéricos. El workspace debe funcionar con `bash setup.sh` + una API key + DB local.

**`workspace/config.yaml` (default genérico):**
```yaml
agent:
  name: "AgnoBot"
  id: "agnobot-main"
  description: "Asistente IA multimodal con workspace declarativo"

model:
  provider: "google"
  id: "gemini-2.5-flash"

fallback:
  enabled: false

database:
  type: "local"
  tables:
    sessions: "agno_sessions"
    knowledge_contents: "agnobot_knowledge_contents"

vector:
  search_type: "hybrid"
  embedder: "text-embedding-3-small"
  max_results: 5

channels:
  - whatsapp

whatsapp:
  mode: "cloud_api"   # cloud_api | qr_link | dual

memory:
  enable_agentic_memory: true
  num_history_runs: 5

audio:
  auto_transcribe: false
  tts_enabled: false

scheduler:
  enabled: true
  poll_interval: 15
  base_url: "http://127.0.0.1:8000"

agentos:
  id: "agnobot-gateway"
  name: "AgnoBot Platform"
  port: 8000
  tracing: true
  mcp_server: true

studio:
  enabled: true
```

**`workspace/instructions.md` (genérico):**
```markdown
# AgnoBot — Instrucciones

Eres AgnoBot, un asistente IA multimodal construido con Agno Framework.

## Capacidades
- Responder preguntas usando tu conocimiento y herramientas
- Buscar información en la web con DuckDuckGo
- Razonar paso a paso con ReasoningTools
- Consultar la documentación de Agno via MCP
- Auto-configurarte usando WorkspaceTools

## Reglas
- Responde en el idioma del usuario
- Sé conciso pero completo
- Usa markdown cuando mejore la legibilidad
- Si no sabes algo, dilo honestamente
```

**`workspace/tools.yaml` (mínimo + nuevos opcionales):**
```yaml
builtin:
  - name: duckduckgo
    enabled: true
  - name: crawl4ai
    enabled: true
    config:
      max_length: 2000
  - name: reasoning
    enabled: true
    config:
      add_instructions: true

optional:
  - name: workspace
    enabled: true
    description: Auto-configuración del workspace
  - name: scheduler_mgmt
    enabled: true
    description: Gestión de recordatorios y crons
  - name: email
    enabled: false
  - name: tavily
    enabled: false
  - name: github
    enabled: false
  - name: audio
    enabled: false
  - name: shell
    enabled: false
  - name: spotify
    enabled: false
  - name: yfinance
    enabled: false
    description: Datos financieros en tiempo real
  - name: wikipedia
    enabled: false
    description: Búsqueda en Wikipedia
  - name: arxiv
    enabled: false
    description: Papers académicos de arXiv
  - name: calculator
    enabled: false
    description: Calculadora matemática
  - name: file_tools
    enabled: false
    description: Lectura y escritura de archivos
  - name: python_tools
    enabled: false
    description: Ejecución de código Python

custom: []
```

**`workspace/mcp.yaml` (mínimo):**
```yaml
servers:
  - name: agno_docs
    transport: streamable-http
    url: "https://docs.agno.com/mcp"
    enabled: true
  - name: tavily
    transport: streamable-http
    url: "https://mcp.tavily.com/mcp"
    enabled: false
    headers:
      Authorization: "Bearer ${TAVILY_API_KEY}"
  - name: supabase
    transport: stdio
    command: "npx"
    args: ["-y", "@supabase/mcp-server-supabase@latest", "--access-token", "${SUPABASE_ACCESS_TOKEN}"]
    enabled: false
  - name: github
    transport: stdio
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    enabled: false

expose:
  enabled: true
```

**Limpiar**: Eliminar `workspace/knowledge/docs/AGENT_OPERACIONES.md` y cualquier referencia a nombres personalizados.

---

## 8.3 — Agregar más tools y canales (DAT-237)

### Nuevos tools en `loader.py`

Agregar al map de tools opcionales en `build_tools()`:

```python
"yfinance": lambda cfg: _build_yfinance(cfg),
"wikipedia": lambda cfg: _build_wikipedia(cfg),
"arxiv": lambda cfg: _build_arxiv(cfg),
"calculator": lambda cfg: _build_calculator(cfg),
"file_tools": lambda cfg: _build_file_tools(cfg),
"python_tools": lambda cfg: _build_python_tools(cfg),
```

Con sus funciones builder correspondientes importando de:
- `agno.tools.yfinance.YFinanceTools`
- `agno.tools.wikipedia.WikipediaTools`
- `agno.tools.arxiv.ArxivTools`
- `agno.tools.calculator.CalculatorTools`
- `agno.tools.file.FileTools`
- `agno.tools.python.PythonTools`

### Nuevos canales en `gateway.py`

```python
if "ai_sdk" in channels:
    try:
        from agno.os.interfaces.ai_sdk import AISdk
        interfaces.append(AISdk(agent=main_agent))
        logger.info("Canal AI SDK (Vercel) habilitado")
    except ImportError:
        logger.warning("AI SDK no disponible")
```

AG-UI funciona automáticamente via os.agno.com — documentar en README.

### Dependencias en `requirements.txt`

```
yfinance>=0.2.0
wikipedia>=1.4.0
arxiv>=2.0.0
```

---

## 8.4 — Studio con Registry completo + AgentOSClient (DAT-238)

### Registry mejorado en `gateway.py`

```python
# Recopilar TODOS los tools del workspace para Registry
registry_tools = []
for tool in main_agent.tools or []:
    if tool not in registry_tools:
        registry_tools.append(tool)

registry = Registry(
    name=os_config.get("name", "AgnoBot Registry"),
    tools=registry_tools,
    models=all_models,
    dbs=[db],
)
```

### Documentar en README

- Flujo Studio: arrancar gateway → os.agno.com → Add OS → Local → http://localhost:8000
- Ejemplo AgentOSClient con `aget_config()`, `get_agents()`, `run_agent()`, `get_sessions()`, `get_memories()`

---

## 8.5 — WhatsApp modo dual: API Meta + QR (DAT-240)

### Contexto

La cuenta WhatsApp Business ya está verificada y funciona con la API oficial de Meta (Cloud API). Se quiere AGREGAR la opción de vincular via QR para tener flexibilidad.

### Arquitectura modo dual

```
┌─────────────────────────────────────────────────────────────┐
│  workspace/config.yaml                                       │
│  whatsapp:                                                   │
│    mode: "dual"  # cloud_api | qr_link | dual                │
│                                                              │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │ Modo 1: Cloud API   │  │ Modo 2: QR Link              │  │
│  │ (ya implementado)   │  │ (NUEVO)                      │  │
│  │                     │  │                              │  │
│  │ agno.os.interfaces  │  │ bridges/whatsapp-qr/         │  │
│  │ .whatsapp.Whatsapp  │  │ ├── index.js (Baileys)       │  │
│  │                     │  │ ├── package.json              │  │
│  │ Meta Business API   │  │ └── Dockerfile                │  │
│  │ Token temporal      │  │                              │  │
│  │ Webhook público     │  │ Linked Devices protocol      │  │
│  │                     │  │ Sesión persistente            │  │
│  └────────┬────────────┘  │ QR en /whatsapp-qr/code      │  │
│           │               └──────────┬───────────────────┘  │
│           │                          │                       │
│           └──────────┬───────────────┘                       │
│                      │                                       │
│              ┌───────▼──────────┐                            │
│              │  gateway.py      │                            │
│              │  AgentOS :8000   │                            │
│              │  Procesa mensajes│                            │
│              │  de ambas fuentes│                            │
│              └──────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### Configuración en `config.yaml`

```yaml
whatsapp:
  mode: "cloud_api"   # cloud_api | qr_link | dual

  # Modo cloud_api — API oficial Meta (ya implementado)
  # Requiere: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN
  cloud_api:
    webhook_path: "/whatsapp/webhook"

  # Modo qr_link — Vinculación via QR (sin cuenta Business)
  # Requiere: servicio Baileys corriendo como sidecar
  qr_link:
    bridge_url: "http://localhost:3001"
    session_dir: "./whatsapp_session"
    auto_reconnect: true
```

### Servicio Baileys bridge (`bridges/whatsapp-qr/`)

**`bridges/whatsapp-qr/package.json`:**
```json
{
  "name": "openagno-whatsapp-bridge",
  "version": "1.0.0",
  "description": "WhatsApp QR bridge para OpenAgno via Baileys",
  "main": "index.js",
  "dependencies": {
    "@whiskeysockets/baileys": "^6.7.0",
    "express": "^4.18.0",
    "qrcode": "^1.5.0",
    "pino": "^8.0.0"
  }
}
```

**`bridges/whatsapp-qr/index.js` (estructura):**
```javascript
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const express = require('express');
const QRCode = require('qrcode');

const app = express();
app.use(express.json());

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:8000';
const SESSION_DIR = process.env.SESSION_DIR || './session';
const PORT = process.env.BRIDGE_PORT || 3001;

let sock = null;
let currentQR = null;
let connectionStatus = 'disconnected';

async function connectWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            currentQR = qr;
            connectionStatus = 'waiting_qr';
            console.log('QR code generado — escanear desde WhatsApp');
        }
        if (connection === 'open') {
            currentQR = null;
            connectionStatus = 'connected';
            console.log('WhatsApp conectado via QR');
        }
        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            connectionStatus = 'disconnected';
            if (shouldReconnect) {
                console.log('Reconectando...');
                connectWhatsApp();
            }
        }
    });

    // Reenviar mensajes entrantes al gateway de OpenAgno
    sock.ev.on('messages.upsert', async ({ messages }) => {
        for (const msg of messages) {
            if (msg.key.fromMe) continue;

            const from = msg.key.remoteJid.replace('@s.whatsapp.net', '');
            const text = msg.message?.conversation
                || msg.message?.extendedTextMessage?.text
                || '';

            if (!text) continue;

            try {
                // Enviar al gateway como si fuera un webhook de Meta
                await fetch(`${GATEWAY_URL}/whatsapp-qr/incoming`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        from: from,
                        text: text,
                        message_id: msg.key.id,
                        timestamp: msg.messageTimestamp,
                    }),
                });
            } catch (err) {
                console.error('Error reenviando al gateway:', err.message);
            }
        }
    });
}

// Endpoints del bridge
app.get('/status', (req, res) => {
    res.json({ status: connectionStatus, has_qr: !!currentQR });
});

app.get('/qr', async (req, res) => {
    if (!currentQR) {
        return res.json({ status: connectionStatus, qr: null });
    }
    const qrDataUrl = await QRCode.toDataURL(currentQR);
    res.json({ status: 'waiting_qr', qr: qrDataUrl });
});

app.post('/send', async (req, res) => {
    const { to, text } = req.body;
    if (!sock || connectionStatus !== 'connected') {
        return res.status(503).json({ error: 'WhatsApp no conectado' });
    }
    try {
        await sock.sendMessage(`${to}@s.whatsapp.net`, { text });
        res.json({ status: 'sent' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`WhatsApp QR Bridge en puerto ${PORT}`);
    connectWhatsApp();
});
```

### Integración en `gateway.py`

```python
# === WhatsApp modo dual ===
wa_config = config.get("whatsapp", {})
wa_mode = wa_config.get("mode", "cloud_api")

if "whatsapp" in channels:
    # Modo 1: Cloud API (oficial Meta) — siempre disponible
    if wa_mode in ("cloud_api", "dual"):
        from agno.os.interfaces.whatsapp import Whatsapp
        interfaces.append(Whatsapp(agent=main_agent))
        logger.info("WhatsApp Cloud API habilitado (API oficial Meta)")

    # Modo 2: QR Link (via Baileys bridge)
    if wa_mode in ("qr_link", "dual"):
        bridge_url = wa_config.get("qr_link", {}).get("bridge_url", "http://localhost:3001")
        _setup_whatsapp_qr_routes(base_app, main_agent, bridge_url)
        logger.info(f"WhatsApp QR Link habilitado (bridge: {bridge_url})")


def _setup_whatsapp_qr_routes(app: FastAPI, agent: Agent, bridge_url: str):
    """Monta rutas para WhatsApp QR bridge."""
    import httpx

    @app.get("/whatsapp-qr/status")
    async def wa_qr_status():
        """Estado de la conexión QR."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{bridge_url}/status")
                return resp.json()
        except Exception as e:
            return {"status": "bridge_unreachable", "error": str(e)}

    @app.get("/whatsapp-qr/code")
    async def wa_qr_code():
        """Obtener QR code para escanear."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{bridge_url}/qr")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    @app.post("/whatsapp-qr/incoming")
    async def wa_qr_incoming(request: dict):
        """Recibe mensajes del bridge y los procesa con el agente."""
        from_number = request.get("from", "")
        text = request.get("text", "")

        if not text:
            return {"status": "ignored", "reason": "empty message"}

        try:
            response = await agent.arun(
                message=text,
                user_id=from_number,
                session_id=from_number,
            )
            # Enviar respuesta de vuelta via bridge
            response_text = response.content if hasattr(response, 'content') else str(response)
            async with httpx.AsyncClient() as client:
                await client.post(f"{bridge_url}/send", json={
                    "to": from_number,
                    "text": response_text,
                })
            return {"status": "responded"}
        except Exception as e:
            logger.error(f"Error procesando mensaje QR: {e}")
            return {"status": "error", "error": str(e)}
```

### Docker Compose

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    # ... existente ...

  gateway:
    build: .
    command: python gateway.py
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
    # ...

  # NUEVO — WhatsApp QR Bridge (opcional, solo si mode=qr_link o dual)
  whatsapp-bridge:
    build: ./bridges/whatsapp-qr
    ports:
      - "3001:3001"
    environment:
      - GATEWAY_URL=http://gateway:8000
      - SESSION_DIR=/data/session
      - BRIDGE_PORT=3001
    volumes:
      - whatsapp_session:/data/session
    depends_on:
      - gateway
    profiles:
      - qr  # Solo se levanta con: docker compose --profile qr up

volumes:
  pgdata:
  whatsapp_session:
```

### CLI actualizado (`management/cli.py`)

```python
# En la sección de canales del wizard
if "whatsapp" in channels:
    wa_mode = _prompt_choice("Modo de WhatsApp?", {
        "1": "Cloud API (API oficial de Meta — requiere cuenta Business verificada)",
        "2": "QR Link (vincular dispositivo escaneando QR — sin cuenta Business)",
        "3": "Dual (ambos modos simultáneamente)",
    }, default="1")
    wa_config = {"cloud_api": "cloud_api", "qr_link": "qr_link", "dual": "dual"}
    config["whatsapp"] = {"mode": {"1": "cloud_api", "2": "qr_link", "3": "dual"}[wa_mode]}
```

---

## 8.6 — Reestructurar README (DAT-239)

### Estructura propuesta

1. Header — badges v1.0.0
2. Qué es OpenAgno — 3-4 líneas
3. Quick Start — 5 pasos
4. Arquitectura — diagrama actualizado con WhatsApp dual
5. Workspace — config.yaml, instructions.md, tools.yaml, mcp.yaml
6. Canales — WhatsApp (Cloud API + QR), Slack, Telegram, Web
7. Tools disponibles — tabla completa con builtins + opcionales
8. Studio — os.agno.com + AgentOSClient
9. API Endpoints — tabla limpia sin repetir
10. Seguridad — API Key, .env, Docker
11. Desarrollo — tests, Docker, deploy systemd
12. Documentación — links Agno
13. Licencia

---

## 8.7 — Tests básicos (DAT-241)

```
tests/
├── __init__.py
├── conftest.py              # Fixtures: workspace temporal
├── test_loader.py           # load_yaml, build_model, build_tools, build_db_url
├── test_validator.py        # validate_workspace con configs válidas/inválidas
├── test_security.py         # verify_api_key con/sin key
└── test_workspace_tools.py  # Validación de provider y tools
```

---

## Checklist Fase 8

| # | Tarea | Issue | Prioridad | Tipo |
|---|-------|-------|-----------|------|
| 1 | Actualizar model IDs (gemini-2.5-flash) | DAT-235 | Urgent | Bug fix |
| 2 | Workspace genérico por defecto | DAT-236 | High | Mejora |
| 3 | Agregar tools: YFinance, Wikipedia, Arxiv, Calculator, File, Python | DAT-237 | High | Feature |
| 4 | Agregar canales: AI SDK, documentar AG-UI | DAT-237 | High | Feature |
| 5 | WhatsApp modo dual: Cloud API + QR Link (Baileys bridge) | DAT-240 | High | Feature |
| 6 | Crear bridges/whatsapp-qr/ con Baileys sidecar | DAT-240 | High | Feature |
| 7 | Rutas /whatsapp-qr/* en gateway.py | DAT-240 | High | Feature |
| 8 | CLI pregunta modo WhatsApp (cloud_api/qr_link/dual) | DAT-240 | High | Feature |
| 9 | Registry con todos los tools del workspace | DAT-238 | High | Feature |
| 10 | Documentar AgentOSClient y Studio | DAT-238 | High | Docs |
| 11 | Reestructurar README | DAT-239 | Medium | Docs |
| 12 | Crear /tests con pytest | DAT-241 | Medium | Calidad |
| 13 | Actualizar self_knowledge.md con nuevos tools/modelos | DAT-236 | High | Mejora |
| 14 | Docker compose con profile qr para bridge | DAT-240 | High | Infra |

---

## Orden de Implementación

1. **DAT-235** — Actualizar model IDs (URGENTE)
2. **DAT-236** — Workspace genérico por defecto
3. **DAT-237** — Agregar tools y canales
4. **DAT-238** — Studio Registry + AgentOSClient
5. **DAT-240** — WhatsApp modo dual (Cloud API + QR bridge)
6. **DAT-239** — Reestructurar README
7. **DAT-241** — Tests básicos

---

## Archivos Afectados

| Archivo | Cambios |
|---------|---------|
| `workspace/config.yaml` | Model IDs, defaults genéricos, sección whatsapp.mode |
| `workspace/instructions.md` | Contenido genérico |
| `workspace/tools.yaml` | Nuevos tools opcionales |
| `workspace/mcp.yaml` | Defaults mínimos |
| `workspace/self_knowledge.md` | Modelos y tools actualizados |
| `loader.py` | Nuevos tools, defaults actualizados |
| `gateway.py` | Registry mejorado, canales nuevos, rutas WhatsApp QR |
| `tools/workspace_tools.py` | Defaults actualizados |
| `management/cli.py` | Wizard modelos + modo WhatsApp |
| `management/validator.py` | Validar nuevos tools + modo WhatsApp |
| `README.md` | Reescritura completa |
| `requirements.txt` | Nuevas dependencias (yfinance, wikipedia, arxiv, httpx) |
| `requirements-dev.txt` | NUEVO — pytest |
| `tests/*` | NUEVO — directorio completo |
| `bridges/whatsapp-qr/*` | NUEVO — servicio Baileys bridge |
| `bridges/whatsapp-qr/Dockerfile` | NUEVO — imagen Node.js |
| `docker-compose.yml` | Servicio whatsapp-bridge con profile qr |
| `.env.example` | Template actualizado con BRIDGE_PORT, SESSION_DIR |

---

*Verificado contra: Linear DAT-190→241, gateway.log, docs.agno.com, Google Gemini model lifecycle, Agno GitHub repo, Baileys @whiskeysockets, Whapi.cloud*
*26 de marzo de 2026*
