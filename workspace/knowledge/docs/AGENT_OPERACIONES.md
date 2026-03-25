# Runbook operativo para AgnoBot (OpenAgno)

Este documento describe la estructura del proyecto, el flujo seguro para cambios y los comandos concretos que puede usar el agente cuando tiene **ShellTools** habilitado (cwd acotado a `OPENAGNO_ROOT`). No incluye secretos: las credenciales viven solo en `.env` (no versionado).

## Variables de entorno necesarias para operar

| Variable | Uso |
|----------|-----|
| `OPENAGNO_ROOT` | Ruta absoluta del clon del repo (raiz donde estan `gateway.py` y `workspace/`). Si falta, el loader usa la raiz del proyecto por defecto al resolver Shell; conviene definirla explicitamente en `.env`. |
| Resto de `.env` | API keys, DB, canales: plantilla en `.env.example` en la raiz del repo (`$OPENAGNO_ROOT/.env.example`). |

## Mapa del repositorio

Todo es relativo a **`OPENAGNO_ROOT`** (directorio que contiene `gateway.py`).

| Ruta | Funcion |
|------|---------|
| `gateway.py` | Punto de entrada AgentOS + FastAPI; lifespan, knowledge, scheduler. |
| `loader.py` | Carga `workspace/` (config, agente principal, sub-agentes, teams, tools, MCP, DB, knowledge). |
| `workspace/config.yaml` | Modelo, DB, canales, agentos, scheduler, knowledge auto-ingesta. |
| `workspace/instructions.md` | Personalidad y reglas del agente principal. |
| `workspace/tools.yaml` | Tools builtin y opcionales (incluye `shell`). |
| `workspace/mcp.yaml` | Servidores MCP externos. |
| `workspace/integrations/<id>/` | Manifiesto `integration.yaml` + `config.env` opcional; el loader fusiona tools/MCP y carga env por integracion. |
| `workspace/agents/*.yaml` | Sub-agentes; `teams.yaml` define equipos. |
| `workspace/knowledge/docs/` | Documentos para RAG (incluye este runbook). |
| `workspace/knowledge/urls.yaml` | URLs para ingesta. |
| `workspace/schedules.yaml` | Referencia de cron (registro operativo via API Agno). |
| `routes/knowledge_routes.py` | Endpoints REST de knowledge montados en el gateway. |
| `management/cli.py` | Wizard de onboarding. |
| `management/validator.py` | Validacion de workspace y env. |
| `management/admin.py` | Cliente admin contra AgentOS. |
| `docs_plan/` | Plan maestro y validaciones por fase. |
| `requirements.txt` | Dependencias Python. |
| `docker-compose.yml` | Postgres local opcional. |

## Que puede personalizar el agente (peticiones del usuario)

- **Si:** archivos bajo `workspace/` (YAML, Markdown), carpeta **`workspace/integrations/<nombre>/`** para nuevas integraciones (ver `workspace/integrations/README.md`), y en coordinacion con el operador `requirements.txt` en la raiz.
- **Con precaucion:** `.env` solo si el operador humano autoriza y aporta valores; nunca escribir secretos en archivos versionados ni pegarlos en chat.
- **No:** borrar `.git` sin confirmacion explicita; ejecutar comandos destructivos fuera de `OPENAGNO_ROOT`; habilitar `shell` en sub-agentes YAML sin decision explicita del proyecto.

### Comportamiento obligatorio ante peticiones de personalizacion

Eres el ejecutor de cambios **declarativos** en este repo: si el usuario pide encender Tavily, otro tool opcional, o cambiar `config.yaml` / `instructions.md`, **debes usar `run_shell_command`** (lista de argumentos; `cwd` ya es la raiz del proyecto) para crear backup si procede, editar archivos y ejecutar el validador. **No** derives la tarea a un "desarrollador externo" por defecto: esa es tu funcion operativa en OpenAgno.

Los cambios en `tools.yaml`, `mcp.yaml`, `workspace/integrations/**/integration.yaml` y `config.yaml` **solo tienen efecto en runtime** despues de **reiniciar** el proceso `gateway.py`. Puedes aplicar los archivos en disco y que el usuario reinicie cuando el lo indique.

### Integraciones y claves

- Cada integracion puede aportar variables con **`config.env`** en su carpeta (no versionado; ver `.gitignore`) o depender del `.env` raiz.
- `env_file: ""` en `integration.yaml` indica que no hay archivo env en la carpeta (solo variables globales).
- El loader carga esos archivos con `override=False` respecto al `.env` principal.

## Flujo obligatorio ante cambios en el workspace o dependencias

1. **Backup** (antes de editar).
2. **Editar** archivos necesarios.
3. **Validar** con el validador.
4. **Reinicio** del proceso del gateway (ver abajo; idealmente por operador o systemd).
5. **Verificar** que `/docs` responde.

## Backup automatico (antes de cambios)

Crear el directorio de backups una vez:

```bash
mkdir -p "${OPENAGNO_ROOT}/backups"
```

**Opcion A — archivo tar comprimido (recomendado):**

```bash
TS=$(date +%Y%m%d-%H%M%S)
tar -czf "${OPENAGNO_ROOT}/backups/openagno-ws-${TS}.tar.gz" \
  -C "${OPENAGNO_ROOT}" \
  workspace gateway.py loader.py routes management requirements.txt docker-compose.yml
```

**Opcion B — copia con sufijo `.bak` (rapida, sin comprimir):**

```bash
TS=$(date +%Y%m%d-%H%M%S)
cp -a "${OPENAGNO_ROOT}/workspace" "${OPENAGNO_ROOT}/backups/workspace.${TS}.bak"
cp -a "${OPENAGNO_ROOT}/gateway.py" "${OPENAGNO_ROOT}/backups/gateway.py.${TS}.bak"
cp -a "${OPENAGNO_ROOT}/loader.py" "${OPENAGNO_ROOT}/backups/loader.py.${TS}.bak"
```

No incluyas en backup rutina `.venv/` ni secretos innecesarios; `.env` no esta en git pero si lo copias, protege el archivo.

ShellTools de Agno ejecuta comandos como **lista de argumentos** (no shell interactivo). Ejemplo equivalente al tar usando `run_shell_command`:

- Prefiere que el operador ejecute los bloques anteriores en una terminal; si usas tool shell, construye `args` como lista, por ejemplo: `["bash", "-lc", "TS=$(date +%Y%m%d-%H%M%S); mkdir -p backups && tar -czf ..."]` solo si la politica del despliegue lo permite.

## Validacion

Desde la raiz del repo, con la misma venv que usa el gateway:

```bash
cd "${OPENAGNO_ROOT}"
. .venv/bin/activate
python -m management.validator
```

Salida sin errores: listo para arrancar o reiniciar.

## Dependencias (si el usuario pide nuevas librerias)

```bash
cd "${OPENAGNO_ROOT}"
. .venv/bin/activate
pip install -r requirements.txt
```

Si se añadio una dependencia nueva al archivo `requirements.txt`, ejecutar `pip install` tras el backup.

## Reinicio del gateway

**Advertencia:** si reinicias el proceso **desde dentro de la misma conversacion** que atiende Studio (matando el worker que ejecuta tu peticion), la respuesta HTTP puede cortarse. Preferible:

- **Operador humano** ejecuta reinicio en SSH, o
- **systemd:** `sudo systemctl restart openagno` (solo si existe unidad con ese nombre), o
- Tras responder al usuario, en otra sesion: detener y levantar en background.

**Patron manual tipico (puerto 8000):**

```bash
fuser -k 8000/tcp 2>/dev/null || true
cd "${OPENAGNO_ROOT}"
. .venv/bin/activate
nohup python gateway.py >> "${OPENAGNO_ROOT}/gateway.log" 2>&1 &
```

Puerto por variable de entorno:

```bash
export PORT=8000
```

## Verificacion rapida

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
```

Esperado: `200`. La raiz `/` redirige a `/docs` (307).

## Admin AgentOS

```bash
cd "${OPENAGNO_ROOT}"
. .venv/bin/activate
python -m management.admin status --url http://127.0.0.1:8000
```

(Ajusta la URL si el gateway escucha en otra interfaz o detras de proxy.)

## Seguridad y ShellTools

- `ShellTools` ejecuta subprocess con `cwd=base_dir` acotado al proyecto; sigue siendo **riesgo alto** (comandos destructivos, exfiltracion si hay permisos amplios).
- No ampliar `cwd` fuera del repo sin aprobacion.
- Tras cambios en `tools.yaml` o `config.yaml`, hace falta **reiniciar** el gateway para cargar la nueva configuracion.

## Ejemplo: activar Tavily (recomendado via integracion)

**Preferido:** edita `workspace/integrations/tavily/integration.yaml` y pon `enabled: true`. Opcional: `env_file: config.env` y crea ese archivo con `TAVILY_API_KEY=` (valor lo pone el operador fuera del chat).

Backup rapido: `cp workspace/integrations/tavily/integration.yaml workspace/integrations/tavily/integration.yaml.bak.$(date +%Y%m%d%H%M%S)`

Alternativa legacy: activar `tavily` solo en `workspace/tools.yaml` (mismo efecto tras fusion, pero la carpeta `integrations/` es el patron para nuevas integraciones).

1. Clave `TAVILY_API_KEY` en `.env` raiz o en `workspace/integrations/tavily/config.env`.
2. `python -m management.validator` (venv activa).
3. **Reiniciar gateway**.

## Ejemplo legacy: solo `workspace/tools.yaml`

Si debes togglear sin carpeta de integracion, usa un script `python3 -c` que ponga `enabled: true` en el bloque opcional `name: tavily` de `tools.yaml` (ver version anterior de este runbook en git si la necesitas).

## Referencia rapida de fases (docs_plan)

Plan maestro: `docs_plan/plan_agno_agent_platform.md`. Las fases recientes cubren scheduler, knowledge, remote agents y MCP avanzado; la personalizacion declarativa es principalmente via `workspace/`.
