# Integraciones declarativas (`workspace/integrations/`)

Cada subcarpeta es una integracion con:

1. **`integration.yaml`** — manifiesto (versionable en git).
2. **`config.env`** (opcional, no versionar) — claves propias de esa integracion; alternativa: usar solo el `.env` en la raiz del repo.

Al arrancar, el gateway carga los manifiestos, fusiona variables desde `config.env` si existe y **combina** la configuracion con `tools.yaml` y `mcp.yaml` (las integraciones habilitadas activan tools opcionales o servidores MCP).

## Esquema de `integration.yaml`

| Campo | Descripcion |
|-------|-------------|
| `id` | Identificador logico (ej. `tavily`). |
| `enabled` | `true` para aplicar esta integracion. |
| `env_file` | Archivo dentro de la carpeta (ej. `config.env`). Vacio `""` o omitir carga: solo `.env` raiz. |
| `env_files` | Lista de archivos env (alternativa a `env_file`). |
| `optional_tool` | Nombre de tool opcional del loader (ej. `tavily`, `email`, `shell`). |
| `optional_tools` | Lista de nombres o `{name, config}`. |
| `tool_config` | Dict que se fusiona con `config` de `tools.yaml` para esa tool. |
| `mcp` | Un bloque servidor MCP (misma forma que en `mcp.yaml`). |
| `mcp_servers` | Lista de bloques MCP. |

Puedes combinar `optional_tool` y `mcp` en la misma carpeta si la integracion expone ambos.

## Anadir una integracion nueva

```text
workspace/integrations/mi_servicio/
  integration.yaml
  config.env          # opcional
  config.env.example  # plantilla sin secretos (si quieres versionarla)
```

Reinicia el gateway tras cambios.

Ver ejemplo en `tavily/`.
