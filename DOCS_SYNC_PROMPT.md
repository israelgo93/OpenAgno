# Docs sync prompt for AI agents

Pega este prompt en cualquier IDE con capacidades de agente (Claude Code,
Cursor, Windsurf, GitHub Copilot Workspace, etc.) corriendo sobre el repo
`OpenAgno`. El agente debe usar la ventana de contexto completa antes de
proponer cambios.

> Si tu IDE tiene skills/slash-commands, marca esta tarea con la skill
> `openagno` y la `mintlify` para que surgan de forma automatica.

---

## Prompt

Tu objetivo es dejar la documentacion Mintlify del repositorio OpenAgno
(carpeta `docs/` y su espejo en `docs/es/`) perfectamente alineada con el
codigo que hoy vive en `main`. No alucines capacidades, no asumas features
que no existen, no reintroduzcas referencias a productos externos.

Opera en dos pases: **verificar** el codigo base y **actualizar** la
documentacion.

### Pase 1. Verificar el codigo base

Antes de tocar cualquier `.mdx`:

1. Lee `AGENTS.md` en la raiz. Es el contrato con agentes y la fuente de
   verdad sobre baseline de version, Python, Agno, Node y Baileys.
2. Lee `.agents/skills/openagno/SKILL.md` y `.agents/skills/openagno-channels/SKILL.md`.
3. Mapea todos los endpoints HTTP reales. Para cada endpoint revisa
   codigo, no solo docs, y anota el path, metodo, shape del body y headers
   obligatorios:
   - `gateway.py` (rutas `/admin/*`, wiring de canales, mount del router
     multi-tenant de WhatsApp Cloud API)
   - `routes/tenant_routes.py` (`/tenants/*`)
   - `routes/knowledge_routes.py` (`/knowledge/*`)
   - `openagno/channels/whatsapp_cloud.py` (`/whatsapp-cloud/{tenant_id}/webhook`)
   - el bloque `_setup_whatsapp_qr_routes` en `gateway.py`
     (`/whatsapp-qr/*`)
4. Lista las variables de entorno reales consumidas por el runtime
   (`os.getenv`, `requireServerEnv`, `.env.example`).
5. Lista los comandos reales de la CLI iterando sobre
   `openagno/commands/`.
6. Lista los templates disponibles en `openagno/templates/`.
7. Revisa `pyproject.toml` para anotar version actual, Agno floor y
   extras declarados (`dev`, `protocols`, etc.).
8. Revisa `bridges/whatsapp-qr/package.json` para anotar la version
   exacta de `@whiskeysockets/baileys` en uso.
9. Revisa `tests/` para detectar contratos cubiertos y features que los
   tests ya validan (buen indicador de madurez real).
10. Abre `docs/changelog.mdx` y confirma que la entrada mas reciente
    refleja los ultimos commits de `main` (usa `git log --oneline -20`).

Produce un reporte intermedio con: version detectada, baseline Python,
baseline Agno, baseline Node (si aplica), lista completa de endpoints
activos, lista de env vars, lista de templates y lista de skills.

### Pase 2. Actualizar la documentacion

Abre `docs/docs.json` primero para entender el arbol de navegacion. Luego
procesa cada pagina `.mdx` bajo `docs/` y su espejo en `docs/es/` usando
este criterio:

- **Versiones y baselines**: actualiza cualquier mencion de una version
  anterior a la detectada, de Python anterior a `>=3.10`, o de Agno
  anterior al floor real.
- **Endpoints**: si encuentras un endpoint en la documentacion que no
  existe en el codigo, elimalo o marcalo como `deprecated` con un
  link al codigo que lo reemplaza. Si existe un endpoint en el codigo
  que no esta documentado, agregalo a la pagina correspondiente.
- **Variables de entorno**: compara la lista de env vars del codigo con
  la de `docs/security.mdx` y `docs/deployment.mdx`. Reporta cualquier
  discrepancia.
- **CLI**: compara la lista de subcomandos en `docs/cli.mdx` con los
  modulos de `openagno/commands/`.
- **Canales**: confirma que la matriz en `docs/channels.mdx` tiene solo
  los canales soportados hoy y con la activacion correcta.
- **WhatsApp Cloud API**: `docs/whatsapp-cloud-api.mdx` debe describir
  los dos modos (single-tenant y multi-tenant) consistentes con lo que
  hace `openagno/channels/whatsapp_cloud.py`. La descripcion del
  cifrado AES-256-GCM debe coincidir con la implementacion real
  (`_decrypt` en ese archivo).
- **Idioma ingles y espanol**: cualquier cambio en una pagina `.mdx` en
  la raiz se espeja en `docs/es/` (si existe). Si no existe el espejo,
  creala cuando tenga sentido para la navegacion en espanol. Preserva
  el tono de cada version (no traduzcas palabra por palabra, respeta el
  estilo).
- **Referencias legacy**: revisa por menciones a:
  - Productos externos al repo (cualquier servicio comercial, dominio
    propietario, repositorio hermano). Reemplaza por terminos neutros
    ("an external control plane", "a SaaS built on top of this
    runtime") porque este es un proyecto open source autocontenido.
  - `mint.json` (obsoleto, debe ser `docs.json`).
  - `ai_sdk` (no soportado).
  - `WORKSPACE_DIR` global (el loader moderno acepta una ruta
    explicita).
  - Versiones viejas del bridge de WhatsApp (`baileys@6.x`) cuando el
    repo ya esta en `7.x`.
- **Changelog**: agrega una entrada `Unreleased` (o actualiza la
  existente) listando todo cambio de contrato relativo al tag anterior.

### Reglas de estilo Mintlify

Aplica lo que dice `.agents/skills/mintlify/SKILL.md`:

- Frontmatter con `title` y `description` en cada pagina.
- Voz en segunda persona, activa, directa.
- Evitar lenguaje de marketing ("powerful", "seamless", "robust").
- Evitar frases de relleno ("it's important to note", "in order to").
- Code blocks con etiqueta de lenguaje.
- Links internos root-relative sin extension.
- Componentes Mintlify nativos en vez de JSX custom cuando exista
  equivalente.

### Validacion antes de cerrar

1. `cd docs && npm run validate`
2. `cd docs && npm run broken-links`
3. Para cada pagina tocada: confirma que aparece en `docs.json` en el
   grupo correcto y con el espejo correcto en `languages.es`.
4. Genera un commit con mensaje `docs: sync con codigo en main` o
   similar, explicando las paginas actualizadas y las referencias
   legacy eliminadas.

### Entregables finales

- El diff de los archivos `.mdx` actualizados.
- La tabla comparativa del Pase 1 (codigo vs docs) dentro del cuerpo
  del PR, para que el revisor pueda verificar rapido.
- Una lista explicita de que NO tocaste y por que (por ejemplo, paginas
  que ya estaban alineadas).

### Que NO hacer

- No introduzcas capacidades que no existen en el codigo.
- No reintroduzcas referencias a productos externos eliminadas a
  proposito.
- No cambies `docs.json` mas alla de lo necesario para acomodar las
  paginas nuevas o renombradas.
- No reescribas paginas enteras si solo una seccion esta desactualizada.
- No toques los `.md` del root del repo (`README.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md`, `AGENTS.md`) a menos que el
  usuario lo pida explicitamente; el objetivo de esta tarea es la
  carpeta `docs/`.

---

## Ejecucion corta (una sola pregunta)

Si tu agente solo te permite una pregunta corta, usa esta:

> Verifica primero el codigo base de OpenAgno (gateway, routes, channels,
> CLI, pyproject.toml, .env.example, bridges/whatsapp-qr/package.json y
> tests). Luego actualiza la documentacion Mintlify en `docs/` (ingles)
> y `docs/es/` (espanol) para que refleje exactamente lo que hay en
> `main`: versiones, endpoints, variables de entorno, canales, comandos
> CLI y templates. Elimina referencias legacy a productos externos,
> `ai_sdk`, `mint.json` o versiones viejas de dependencias. Valida con
> `npm run validate` y `npm run broken-links`. Abre un PR con el diff
> y una tabla comparativa codigo vs docs.
