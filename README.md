<p align="center">
  <h1 align="center">OpenAgno</h1>
  <p align="center">
    <strong>Plataforma para construir y operar agentes sobre Agno con workspace declarativo</strong>
  </p>
  <p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://docs.agno.com"><img src="https://img.shields.io/badge/Agno-Framework-6366F1?style=flat-square" alt="Agno"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square" alt="License"></a>
    <a href="https://github.com/israelgo93/OpenAgno"><img src="https://img.shields.io/badge/v1.1.0-Active-brightgreen?style=flat-square" alt="Status"></a>
  </p>
</p>

---

## Que es OpenAgno

OpenAgno ejecuta agentes sobre **Agno** usando un **workspace declarativo** y un runtime FastAPI/AgentOS listo para canales, knowledge base, herramientas y servidores MCP.

Incluye:

- CLI empaquetada `openagno`
- templates de workspace listos para usar
- gateway AgentOS con rutas custom y rutas nativas de Agno
- soporte para WhatsApp Cloud API, QR bridge, Slack, Telegram y Studio
- knowledge base con PgVector
- integraciones declarativas y MCP
- supervisor local con `service_manager.py`

## Quick start

```bash
git clone https://github.com/israelgo93/OpenAgno.git
cd OpenAgno

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

openagno templates list
openagno init --template personal_assistant
openagno validate
openagno start --foreground
```

El runtime queda disponible en `http://127.0.0.1:8000`.

Chequeo rapido:

```bash
curl http://127.0.0.1:8000/admin/health
```

## CLI actual

La CLI principal documentada es:

```bash
openagno <comando>
```

Comandos principales:

| Comando | Uso |
|---------|-----|
| `openagno init` | Onboarding interactivo |
| `openagno init --template <id>` | Copiar un workspace desde template |
| `openagno start` | Arrancar supervisor en background |
| `openagno start --foreground` | Ejecutar `gateway.py` en foreground |
| `openagno stop` | Detener supervisor |
| `openagno restart` | Reiniciar supervisor |
| `openagno status` | Mostrar estado del runtime |
| `openagno logs` | Leer `gateway.log` |
| `openagno validate` | Validar `workspace/` |
| `openagno templates list/show` | Explorar templates |
| `openagno add ...` | Agregar canales o tools |
| `openagno create agent ...` | Crear sub-agentes |
| `openagno deploy ...` | Helpers de despliegue |

Ejemplo:

```bash
openagno templates list
openagno init --template customer_support
openagno add whatsapp --mode dual
openagno add tool tavily
openagno create agent "Billing Agent" --tool wikipedia --instruction "Ayuda con facturacion"
openagno validate
openagno start --foreground
```

### CLI legacy

La CLI historica sigue disponible para algunos flujos interactivos:

```bash
python -m management.cli
python -m management.cli doctor
python -m management.cli chat
```

## Workspace

El runtime se define desde `workspace/`.

| Archivo | Funcion |
|---------|---------|
| `workspace/config.yaml` | Configuracion central: modelo, base de datos, canales, memoria, scheduler |
| `workspace/instructions.md` | Reglas, tono y capacidades del agente |
| `workspace/tools.yaml` | Tools builtin y opcionales |
| `workspace/mcp.yaml` | Servidores MCP externos |
| `workspace/self_knowledge.md` | Auto-consciencia operacional del agente |
| `workspace/knowledge/docs/` | Documentos para ingesta |
| `workspace/knowledge/urls.yaml` | URLs para ingesta |
| `workspace/agents/*.yaml` | Sub-agentes |
| `workspace/agents/teams.yaml` | Teams multi-agente |
| `workspace/schedules.yaml` | Tareas programadas |
| `workspace/integrations/` | Integraciones declarativas con env propio |

La ruta mas estable para operar el proyecto es:

```text
OPENAGNO_ROOT/workspace
```

## Templates incluidos

```bash
openagno templates list
```

Templates empaquetados:

- `personal_assistant`
- `customer_support`
- `research_agent`
- `sales_agent`
- `developer_assistant`

## Modelos y fallback

Providers soportados:

| Provider | Ejemplos | Credenciales |
|----------|----------|--------------|
| `google` | `gemini-2.5-flash`, `gemini-2.5-pro` | `GOOGLE_API_KEY` |
| `openai` | `gpt-4.1`, `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic` | `claude-sonnet-4`, `claude-opus-4` | `ANTHROPIC_API_KEY` |
| `aws_bedrock_claude` | `us.anthropic.claude-sonnet-4-6` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| `aws_bedrock` | `amazon.nova-pro-v1:0` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |

El fallback es un bloque **top-level** en `config.yaml` y se activa automaticamente ante rate limit.

## Canales

### WhatsApp Cloud API

Variables tipicas:

```bash
WHATSAPP_ACCESS_TOKEN=tu_token
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
WHATSAPP_VERIFY_TOKEN=tu_verify_token
WHATSAPP_APP_SECRET=tu_app_secret
```

Rutas relevantes:

- `GET /whatsapp/webhook`
- `POST /whatsapp/webhook`

Comportamiento actual:

- valida firma con `WHATSAPP_APP_SECRET`
- deduplica por `message_id` solo despues de validar firma
- filtra payloads mixtos sin bloquear mensajes nuevos

Para desarrollo local solamente:

```bash
WHATSAPP_SKIP_SIGNATURE_VALIDATION=true
```

### WhatsApp QR

```yaml
whatsapp:
  mode: qr_link
  qr_link:
    bridge_url: http://localhost:3001
```

```bash
cd bridges/whatsapp-qr
npm install
node index.js
```

Rutas del gateway:

- `/whatsapp-qr/status`
- `/whatsapp-qr/code`
- `/whatsapp-qr/code/json`
- `/whatsapp-qr/incoming`

### Otros canales

- Slack: `channels: [slack]`
- Telegram: `channels: [telegram]`
- Web/Studio: siempre disponible con el gateway
- AI SDK y A2A: opcionales segun instalacion de Agno

## API

### Rutas custom de OpenAgno

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/admin/health` | Estado del runtime |
| `POST` | `/admin/reload` | Solicitar reload al supervisor |
| `POST` | `/admin/fallback/activate` | Activar fallback manualmente |
| `POST` | `/admin/fallback/restore` | Restaurar modelo principal |
| `POST` | `/knowledge/upload` | Subir documento |
| `POST` | `/knowledge/ingest-urls` | Ingestar URLs |
| `GET` | `/knowledge/list` | Listar documentos |
| `DELETE` | `/knowledge/{doc_name}` | Eliminar documento |
| `POST` | `/knowledge/search` | Busqueda semantica |
| `GET` | `/whatsapp-qr/status` | Estado del bridge QR |
| `GET` | `/whatsapp-qr/code` | QR HTML |
| `GET` | `/whatsapp-qr/code/json` | QR JSON |
| `POST` | `/whatsapp-qr/incoming` | Entrada del bridge QR |
| `GET` | `/whatsapp/webhook` | Verificacion webhook Meta |
| `POST` | `/whatsapp/webhook` | Webhook WhatsApp Cloud API |

### Rutas nativas de AgentOS

El runtime tambien expone rutas de AgentOS como:

- `/agents`
- `/teams`
- `/sessions`
- `/memories`
- `/schedules`
- `/registry`
- `/config`
- `/health`
- `/docs`
- `/openapi.json`

## Seguridad

### API key

Las rutas custom de knowledge pueden protegerse con:

```bash
OPENAGNO_API_KEY=tu_key_generada
```

Si esta variable existe, debes enviar:

```bash
X-API-Key: tu_key_generada
```

### Admin

Las rutas `/admin/*` tienen rate limiting, pero no pasan por `X-API-Key` en el codigo actual. Si las expones, protégelas con red privada o reverse proxy.

### Knowledge

Las rutas custom de knowledge usan una whitelist de tablas permitidas y `knowledge.search` ya opera con `max_results`.

## Runtime y procesos

### Foreground

```bash
openagno start --foreground
```

### Supervisor local

```bash
openagno start
openagno status
openagno logs --follow
openagno stop
```

Tambien puedes usar:

```bash
python service_manager.py start
python service_manager.py stop
python service_manager.py restart
python service_manager.py status
```

`gateway.log` se genera cuando corres con supervisor.

## Despliegue

### systemd

```bash
sudo bash deploy/install-service.sh
sudo systemctl start openagno
sudo systemctl status openagno
journalctl -u openagno -f
```

### Docker Compose

```bash
docker compose up -d db
docker compose up -d
docker compose --profile qr up -d
```

## Documentacion

La documentacion del proyecto vive en `docs/` y usa Mintlify.

Vista previa local:

```bash
cd docs
npm install
npm run dev
```

Chequeo de enlaces:

```bash
cd docs
npm run broken-links
```

## Referencias

- [docs.agno.com](https://docs.agno.com)
- [Mintlify](https://mintlify.com/docs)
- [docs.json schema](https://www.mintlify.com/docs.json)

## Licencia

Este proyecto esta licenciado bajo [Apache License 2.0](LICENSE).
