# OpenAgno — Auditoría Post Fase 9 y Plan de Cierre

*Fecha: 28 de marzo de 2026*

## Resultado de la validación

La Fase 9 está **mayormente implementada**, pero no estaba cerrada al 100% al momento de esta auditoría.

### Implementado y validado

- CLI empaquetada `openagno`
- templates empaquetados
- tests (`45 passed`)
- deduplicación WhatsApp
- saneamiento de historial cross-model
- soporte MCP `stdio`, `sse` y `streamable-http`
- rate limiting operativo
- lockfile presente (`requirements.lock`)

### Gaps detectados

1. **Fallback roto por configuración inconsistente**
   - `loader.py` solo leía `model.fallback`
   - `workspace/config.yaml` y la documentación usan `fallback` top-level
   - Impacto: el fallback documentado no se activaba realmente

2. **Canales soportados “solo en papel”**
   - Agno 2.5.10 en este entorno expone `whatsapp`, `slack`, `telegram`, `a2a`, `agui`
   - El repo documentaba `ai_sdk`, pero esa interfaz no existe aquí
   - Slack y Telegram no tenían sus dependencias declaradas en la instalación base

3. **Documentación desalineada**
   - README y Mintlify mezclaban la ruta actual con flujos legacy
   - Se documentaban capacidades no cerradas o no compatibles con el runtime actual

4. **Basura local dentro del árbol del repo**
   - `docs/node_modules/`
   - logs, caches y artefactos temporales locales

## Cambios aplicados en esta auditoría

- compatibilidad de `fallback` con bloque top-level y forma legacy
- incorporación de `agui` como canal compatible actual
- comandos `openagno add agui` y `openagno add a2a`
- declaración de dependencias base para Slack y Telegram
- extra opcional `protocols` para `a2a-sdk` y `ag-ui-protocol`
- limpieza y reescritura de README + docs públicas para solo documentar la ruta vigente

## Lo que sigue faltando del plan estratégico consolidado

Estos puntos siguen siendo **roadmap** y no deben presentarse como implementados:

- Remote Execution
- multi-tenancy real
- control plane / auth / dashboard
- billing
- despliegue AWS automatizado
- sandbox de ejecución aislado

## Plan de cierre recomendado

### Bloque 1 — Estabilización final

- regenerar `requirements.lock` con las nuevas dependencias
- validar import real de Slack, Telegram, AG-UI y A2A en entorno limpio
- ejecutar verificación de links de Mintlify

### Bloque 2 — Fase 10 real

- multi-tenancy con aislamiento por schema
- storage de workspaces fuera del filesystem local
- routing por tenant

### Bloque 3 — Fase 11 real

- Supabase Auth
- tablas `tenants` y API keys
- dashboard para gestión de agentes

### Bloque 4 — Fase 12 real

- despliegue AWS automatizado
- billing
- observabilidad

## Nota sobre compatibilidad con Agno

La base actual sigue siendo compatible con Agno 2.5.10.

Confirmado en esta auditoría:

- `PgVector` + `SearchType.hybrid`
- interfaces `whatsapp`, `slack`, `telegram`, `a2a`, `agui`
- protocolo MCP embebido

Descartado para la ruta vigente:

- `ai_sdk` como canal documentado actual
