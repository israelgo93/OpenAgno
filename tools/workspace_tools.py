"""
WorkspaceTools — El agente puede auto-configurarse.
CRUD sobre workspace/ con backup automatico.

Fase 7: Validacion de providers y tools en create_sub_agent.
Fase A.3: multi-tenant safe. La instancia acepta opcionalmente
    workspace_dir, tenant_slug y on_reload para que cada tenant escriba
    dentro de su propio directorio y dispare la invalidacion de cache
    del TenantLoader correspondiente sin tocar al resto de tenants.
"""
import os
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from agno.tools import Toolkit
from agno.utils.log import logger

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.parent.resolve()))
WORKSPACE_DIR = OPENAGNO_ROOT / "workspace"
BACKUPS_DIR = OPENAGNO_ROOT / "backups"

# F7 — 7.4.3: Proveedores de modelo validos
VALID_PROVIDERS = {
    "google", "openai", "anthropic",
    "aws_bedrock_claude", "aws_bedrock",
}

# Modos soportados por agno.team.mode.TeamMode
VALID_TEAM_MODES = {"coordinate", "route", "broadcast", "tasks"}

# Transportes MCP soportados por loader.build_mcp_tools
VALID_MCP_TRANSPORTS = {"streamable-http", "sse", "stdio"}


class WorkspaceTools(Toolkit):
    def __init__(
        self,
        *,
        workspace_dir: Optional[Path] = None,
        tenant_slug: Optional[str] = None,
        on_reload: Optional[Callable[[Optional[str]], None]] = None,
    ):
        """Crea el toolkit sobre un workspace concreto.

        Args:
            workspace_dir: directorio del tenant (ej. workspaces/acme/workspace).
                Si es None usa el WORKSPACE_DIR global (operador/legacy).
            tenant_slug: slug del tenant; se pasa al callback on_reload y aparece
                en los mensajes de retorno para trazabilidad.
            on_reload: callback invocado por request_reload(); tipicamente
                TenantLoader.reload(slug). Si es None se cae al mecanismo
                legacy (.reload_requested) que reinicia el daemon global.
        """
        # El Toolkit se identifica como "self_customization" en Agno para que el
        # LLM no infiera un rol tipo "workspace admin" al ver la lista de tools.
        # El archivo / clase siguen llamandose workspace_tools por compat.
        super().__init__(name="self_customization")
        self._workspace_dir = (workspace_dir or WORKSPACE_DIR).resolve()
        self._tenant_slug = tenant_slug
        self._on_reload = on_reload
        # Los backups viven junto al workspace del tenant para no mezclar
        # historiales entre tenants. Para el operador (legacy) conserva la
        # ubicacion historica OPENAGNO_ROOT/backups.
        if workspace_dir is None:
            self._backups_dir = BACKUPS_DIR
        else:
            self._backups_dir = self._workspace_dir.parent / "backups"

        self.register(self.read_workspace_file)
        self.register(self.write_workspace_file)
        self.register(self.list_workspace)
        self.register(self.create_sub_agent)
        self.register(self.list_sub_agents)
        self.register(self.disable_sub_agent)
        self.register(self.delete_sub_agent)
        self.register(self.create_team)
        self.register(self.list_teams)
        self.register(self.disable_team)
        self.register(self.delete_team)
        self.register(self.update_instructions)
        self.register(self.toggle_tool)
        self.register(self.enable_tool)
        self.register(self.disable_tool)
        self.register(self.add_mcp_server)
        self.register(self.disable_mcp_server)
        self.register(self.set_model)
        self.register(self.request_reload)

    # -- helpers -------------------------------------------------------------

    def _tenant_suffix(self) -> str:
        return f" (tenant={self._tenant_slug})" if self._tenant_slug else ""

    def _backup(self, file_path: Path) -> str:
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self._backups_dir / f"{file_path.stem}.{ts}.bak{file_path.suffix}"
        if file_path.exists():
            shutil.copy2(file_path, backup_path)
            return f"Backup: {backup_path.name}"
        return "Archivo nuevo, sin backup"

    def _load_valid_tools(self) -> set[str]:
        """Carga la lista de tools validos desde tools.yaml."""
        tools_path = self._workspace_dir / "tools.yaml"
        if not tools_path.exists():
            return set()
        try:
            data = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
            valid = set()
            for section in ("builtin", "optional"):
                for tool in data.get(section, []):
                    name = tool.get("name")
                    if name:
                        valid.add(name)
            return valid
        except Exception:
            return set()

    def _is_tool_enabled(self, tool_name: str) -> bool:
        tools_path = self._workspace_dir / "tools.yaml"
        if not tools_path.exists():
            return False
        try:
            data = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
            for section in ("builtin", "optional"):
                for tool in data.get(section, []):
                    if tool.get("name") == tool_name:
                        return tool.get("enabled", True) is not False
        except Exception:
            return False
        return False

    def _current_model_defaults(self) -> tuple[str, str]:
        """Lee provider/id actuales desde config.yaml.

        Si el workspace no declara modelo valido, cae al default historico para
        mantener compatibilidad con workspaces minimos de tests/CLI.
        """
        fallback = ("google", "gemini-2.5-flash")
        config_path = self._workspace_dir / "config.yaml"
        if not config_path.exists():
            return fallback
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return fallback

        model = data.get("model")
        if not isinstance(model, dict):
            return fallback

        provider = model.get("provider")
        model_id = model.get("id")
        if (
            isinstance(provider, str)
            and provider in VALID_PROVIDERS
            and isinstance(model_id, str)
            and model_id.strip()
        ):
            return provider, model_id.strip()
        return fallback

    def _main_agent_id(self) -> str:
        config_path = self._workspace_dir / "config.yaml"
        if not config_path.exists():
            return "agnobot-main"
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return "agnobot-main"
        agent = data.get("agent")
        if isinstance(agent, dict):
            agent_id = agent.get("id")
            if isinstance(agent_id, str) and agent_id.strip():
                return agent_id.strip()
        return "agnobot-main"

    def _resolve_model_selection(
        self,
        model_provider: Optional[str],
        model_id: Optional[str],
    ) -> tuple[str, str] | str:
        """Resuelve el modelo de una nueva entidad desde el workspace actual.

        - Sin argumentos: hereda provider/id del workspace principal.
        - Solo model_id: mantiene el provider actual.
        - Solo model_provider: solo se permite si coincide con el provider
          actual; si no, se exige model_id explicito para evitar mezclas.
        """
        current_provider, current_id = self._current_model_defaults()
        if model_provider is not None and model_provider not in VALID_PROVIDERS:
            return (
                f"ERROR: Provider '{model_provider}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_PROVIDERS))}"
            )
        resolved_provider = model_provider or current_provider

        if model_id:
            resolved_id = model_id
        elif model_provider is None or model_provider == current_provider:
            resolved_id = current_id
        else:
            return (
                "ERROR: model_id requerido cuando model_provider no coincide "
                "con el workspace actual. "
                f"Workspace actual: {current_provider}/{current_id}"
            )

        return resolved_provider, resolved_id

    # -- lectura/escritura generica ------------------------------------------

    def read_workspace_file(self, filename: str) -> str:
        """Lee un archivo del workspace. Ej: 'config.yaml', 'instructions.md'."""
        if filename.startswith("workspace/"):
            filename = filename[10:]
        path = self._workspace_dir / filename
        if not path.exists():
            return f"Error: {filename} no existe"
        if not path.resolve().is_relative_to(self._workspace_dir):
            return "Error: ruta fuera del workspace"
        return path.read_text(encoding="utf-8")

    def write_workspace_file(self, filename: str, content: str) -> str:
        """Escribe en workspace/. Crea backup automaticamente."""
        if filename.startswith("workspace/"):
            filename = filename[10:]
        path = self._workspace_dir / filename
        if not path.resolve().is_relative_to(self._workspace_dir):
            return "Error: ruta fuera del workspace"
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Escrito: {filename}{self._tenant_suffix()}. {backup_msg}. Reload necesario."

    def list_workspace(self) -> str:
        """Lista estructura del workspace."""
        result = []
        for item in sorted(self._workspace_dir.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                result.append(str(item.relative_to(self._workspace_dir)))
        return "\n".join(result) if result else "Workspace vacio"

    # -- sub-agentes ---------------------------------------------------------

    def create_sub_agent(
        self, name: str, agent_id: str, role: str,
        tools: list[str], instructions: list[str],
        model_provider: str | None = None, model_id: str | None = None,
    ) -> str:
        """Crea un sub-agente en workspace/agents/.

        Valida provider y tools antes de crear el YAML (F7). Si no se pasa
        modelo, hereda el provider/id del workspace principal actual.
        """
        resolved_model = self._resolve_model_selection(model_provider, model_id)
        if isinstance(resolved_model, str):
            return resolved_model
        resolved_provider, resolved_id = resolved_model

        # F7 — 7.4.3: Validar provider
        if resolved_provider not in VALID_PROVIDERS:
            return (
                f"ERROR: Provider '{resolved_provider}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_PROVIDERS))}"
            )

        # F7 — 7.4.3: Validar tools
        if tools:
            valid_tools = self._load_valid_tools()
            invalid = [t for t in tools if t not in valid_tools]
            if invalid:
                return (
                    f"ERROR: Tools no validos: {invalid}. "
                    f"Disponibles: {', '.join(sorted(valid_tools))}"
                )

        agent_data = {
            "agent": {
                "name": name, "id": agent_id, "role": role,
                "model": {"provider": resolved_provider, "id": resolved_id},
                "tools": tools, "instructions": instructions,
                "config": {"tool_call_limit": 5, "enable_agentic_memory": False, "markdown": True},
            },
            "execution": {"type": "local"},
        }
        filename = f"agents/{agent_id.replace('-', '_')}.yaml"
        path = self._workspace_dir / filename
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(agent_data, f, default_flow_style=False, allow_unicode=True)
        return f"Sub-agente '{name}' creado en {filename}{self._tenant_suffix()}. {backup_msg}. Reload necesario."

    # -- instrucciones / tools -----------------------------------------------

    def update_instructions(self, new_instructions: str) -> str:
        """Actualiza workspace/instructions.md."""
        path = self._workspace_dir / "instructions.md"
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_instructions, encoding="utf-8")
        return f"Instrucciones actualizadas{self._tenant_suffix()}. {backup_msg}. Reload necesario."

    def toggle_tool(self, tool_name: str, enabled: bool) -> str:
        """Activa/desactiva un tool en tools.yaml."""
        path = self._workspace_dir / "tools.yaml"
        if not path.exists():
            return "Error: tools.yaml no existe"
        data = yaml.safe_load(path.read_text()) or {}
        for section in ("builtin", "optional"):
            for tool in data.get(section, []):
                if tool.get("name") == tool_name:
                    backup_msg = self._backup(path)
                    tool["enabled"] = enabled
                    with open(path, "w") as f:
                        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                    return f"Tool '{tool_name}' {'activado' if enabled else 'desactivado'}{self._tenant_suffix()}. {backup_msg}"
        return f"Tool '{tool_name}' no encontrado"

    # -- gestion de sub-agentes ---------------------------------------------

    def _agents_dir(self) -> Path:
        return self._workspace_dir / "agents"

    def _list_agent_files(self) -> list[Path]:
        agents_dir = self._agents_dir()
        if not agents_dir.exists():
            return []
        return sorted(
            f for f in agents_dir.glob("*.yaml")
            if f.name != "teams.yaml"
        )

    def _list_disabled_agent_files(self) -> list[Path]:
        agents_dir = self._agents_dir()
        if not agents_dir.exists():
            return []
        return sorted(f for f in agents_dir.glob("*.yaml.disabled"))

    def _sub_agent_inventory_entry(self, path: Path, *, enabled: bool) -> dict[str, Any]:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {
                "id": path.stem,
                "name": path.name,
                "role": "",
                "model": {},
                "tools": [],
                "enabled": enabled,
                "file": str(path.relative_to(self._workspace_dir)),
                "valid": False,
            }
        agent = data.get("agent", {})
        model = agent.get("model", {})
        tools = agent.get("tools", [])
        return {
            "id": agent.get("id", path.name.removesuffix(".yaml").removesuffix(".disabled")),
            "name": agent.get("name", "?"),
            "role": agent.get("role", ""),
            "model": model if isinstance(model, dict) else {},
            "tools": tools if isinstance(tools, list) else [],
            "enabled": enabled,
            "file": str(path.relative_to(self._workspace_dir)),
            "valid": isinstance(agent, dict) and bool(agent),
        }

    def list_sub_agents_inventory(self) -> list[dict[str, Any]]:
        """Inventario estructurado de sub-agentes del workspace del tenant."""
        entries = [
            self._sub_agent_inventory_entry(path, enabled=True)
            for path in self._list_agent_files()
        ]
        entries.extend(
            self._sub_agent_inventory_entry(path, enabled=False)
            for path in self._list_disabled_agent_files()
        )
        return sorted(entries, key=lambda entry: str(entry.get("id", "")))

    def list_sub_agents(self) -> str:
        """Lista los sub-agentes configurados en workspace/agents/*.yaml."""
        entries = [entry for entry in self.list_sub_agents_inventory() if entry["enabled"]]
        if not entries:
            return "No hay sub-agentes configurados."
        lines: list[str] = []
        for entry in entries:
            if not entry.get("valid", False):
                lines.append(f"- {entry.get('file', '?')} (YAML invalido)")
                continue
            model = entry.get("model", {})
            tools = entry.get("tools", [])
            lines.append(
                f"- id={entry.get('id', '?')} | name={entry.get('name', '?')} | "
                f"role={entry.get('role', '?')} | "
                f"model={model.get('provider', '?')}/{model.get('id', '?')} | "
                f"tools={','.join(tools) if tools else '-'}"
            )
        return "\n".join(lines)

    def _resolve_agent_file(self, agent_id: str) -> Path | None:
        agents_dir = self._agents_dir()
        if not agents_dir.exists():
            return None
        for f in list(agents_dir.glob("*.yaml")) + list(agents_dir.glob("*.yaml.disabled")):
            if f.name == "teams.yaml":
                continue
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if data.get("agent", {}).get("id") == agent_id:
                return f
        # Fallback: match por nombre de archivo
        candidate = agents_dir / f"{agent_id.replace('-', '_')}.yaml"
        if candidate.exists():
            return candidate
        disabled_candidate = candidate.with_suffix(candidate.suffix + ".disabled")
        return disabled_candidate if disabled_candidate.exists() else None

    def disable_sub_agent(self, agent_id: str) -> str:
        """Soft-disable: renombra agents/<id>.yaml a .yaml.disabled."""
        path = self._resolve_agent_file(agent_id)
        if path is None:
            return f"ERROR: sub-agente '{agent_id}' no encontrado."
        if path.name.endswith(".disabled"):
            return f"ERROR: sub-agente '{agent_id}' ya esta deshabilitado."
        disabled = path.with_suffix(path.suffix + ".disabled")
        path.rename(disabled)
        return (
            f"Sub-agente '{agent_id}' deshabilitado (renombrado a {disabled.name})"
            f"{self._tenant_suffix()}. Reload necesario."
        )

    def delete_sub_agent(self, agent_id: str) -> str:
        """Elimina definitivamente agents/<id>.yaml (con backup previo)."""
        path = self._resolve_agent_file(agent_id)
        if path is None:
            return f"ERROR: sub-agente '{agent_id}' no encontrado."
        backup_msg = self._backup(path)
        path.unlink()
        return (
            f"Sub-agente '{agent_id}' eliminado{self._tenant_suffix()}. "
            f"{backup_msg}. Reload necesario."
        )

    # -- teams ---------------------------------------------------------------

    def create_team(
        self,
        team_id: str,
        name: str,
        mode: str,
        members: list[str],
        instructions: list[str] | None = None,
        model_provider: str | None = None,
        model_id: str | None = None,
    ) -> str:
        """Crea o actualiza un team en workspace/agents/teams.yaml.

        - `mode` debe estar en {coordinate, route, broadcast, tasks}.
        - `members` son IDs de sub-agentes existentes (o 'agnobot-main').
        - Si no se pasa modelo, hereda el provider/id del workspace principal.
        Hace upsert por team_id: si ya existe, reemplaza su definicion.
        """
        if mode not in VALID_TEAM_MODES:
            return (
                f"ERROR: mode '{mode}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_TEAM_MODES))}"
            )
        resolved_model = self._resolve_model_selection(model_provider, model_id)
        if isinstance(resolved_model, str):
            return resolved_model
        resolved_provider, resolved_id = resolved_model

        if resolved_provider not in VALID_PROVIDERS:
            return (
                f"ERROR: Provider '{resolved_provider}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_PROVIDERS))}"
            )
        if not isinstance(members, list) or len(members) < 2:
            return "ERROR: un team requiere al menos 2 miembros."

        # Validar que los miembros existen como sub-agente (o son el main)
        known_ids = {self._main_agent_id()}
        for f in self._list_agent_files():
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                aid = data.get("agent", {}).get("id")
                if aid:
                    known_ids.add(aid)
            except yaml.YAMLError:
                continue

        missing = [m for m in members if m not in known_ids]
        if missing:
            return (
                f"ERROR: miembros no encontrados: {missing}. "
                f"Disponibles: {', '.join(sorted(known_ids))}"
            )

        teams_path = self._workspace_dir / "agents" / "teams.yaml"
        teams_path.parent.mkdir(parents=True, exist_ok=True)

        if teams_path.exists():
            current = yaml.safe_load(teams_path.read_text(encoding="utf-8")) or {}
        else:
            current = {}
        teams_list = current.get("teams", [])
        if not isinstance(teams_list, list):
            teams_list = []

        new_entry = {
            "id": team_id,
            "name": name,
            "enabled": True,
            "mode": mode,
            "members": list(members),
            "model": {"provider": resolved_provider, "id": resolved_id},
            "instructions": list(instructions or []),
        }

        replaced = False
        for idx, existing in enumerate(teams_list):
            if isinstance(existing, dict) and existing.get("id") == team_id:
                teams_list[idx] = new_entry
                replaced = True
                break
        if not replaced:
            teams_list.append(new_entry)

        backup_msg = self._backup(teams_path)
        current["teams"] = teams_list
        with open(teams_path, "w") as f:
            yaml.dump(current, f, default_flow_style=False, allow_unicode=True)
        verb = "actualizado" if replaced else "creado"
        return (
            f"Team '{team_id}' {verb}{self._tenant_suffix()} "
            f"(mode={mode}, miembros={members}). {backup_msg}. Reload necesario."
        )

    def _read_teams_document(self) -> dict[str, Any] | str:
        teams_path = self._workspace_dir / "agents" / "teams.yaml"
        if not teams_path.exists():
            return {"teams": []}

        try:
            return yaml.safe_load(teams_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return "ERROR: teams.yaml invalido."

    def list_teams_inventory(self) -> list[dict[str, Any]]:
        """Inventario estructurado de teams declarados para este workspace."""
        data = self._read_teams_document()
        if isinstance(data, str):
            return []

        teams = data.get("teams", [])
        if not isinstance(teams, list):
            return []

        entries: list[dict[str, Any]] = []
        for entry in teams:
            if not isinstance(entry, dict):
                continue
            model = entry.get("model", {})
            members = entry.get("members", [])
            entries.append({
                "id": entry.get("id", "?"),
                "name": entry.get("name", "?"),
                "mode": entry.get("mode", "?"),
                "members": members if isinstance(members, list) else [],
                "model": model if isinstance(model, dict) else {},
                "enabled": entry.get("enabled", True) is not False,
            })
        return sorted(entries, key=lambda entry: str(entry.get("id", "")))

    def list_teams(self) -> str:
        """Lista los teams declarados en workspace/agents/teams.yaml."""
        data = self._read_teams_document()
        if isinstance(data, str):
            return "ERROR: teams.yaml invalido."

        teams = self.list_teams_inventory()
        if not teams:
            return "No hay teams configurados."

        lines: list[str] = []
        for entry in teams:
            model = entry.get("model", {})
            members = entry.get("members", [])
            lines.append(
                f"- id={entry.get('id', '?')} | name={entry.get('name', '?')} | "
                f"enabled={entry.get('enabled', True)} | "
                f"mode={entry.get('mode', '?')} | "
                f"members={','.join(members) if isinstance(members, list) and members else '-'} | "
                f"model={model.get('provider', '?')}/{model.get('id', '?')}"
            )

        return "\n".join(lines) if lines else "No hay teams configurados."

    def disable_team(self, team_id: str) -> str:
        """Soft-disable: marca enabled=false en agents/teams.yaml."""
        teams_path = self._workspace_dir / "agents" / "teams.yaml"
        data = self._read_teams_document()
        if isinstance(data, str):
            return data
        teams = data.get("teams", [])
        if not isinstance(teams, list):
            return "ERROR: teams.yaml invalido."
        for entry in teams:
            if isinstance(entry, dict) and entry.get("id") == team_id:
                backup_msg = self._backup(teams_path)
                entry["enabled"] = False
                teams_path.parent.mkdir(parents=True, exist_ok=True)
                with open(teams_path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                return (
                    f"Team '{team_id}' deshabilitado{self._tenant_suffix()}. "
                    f"{backup_msg}. Reload necesario."
                )
        return f"ERROR: team '{team_id}' no encontrado."

    def delete_team(self, team_id: str) -> str:
        """Elimina definitivamente un team de agents/teams.yaml (con backup)."""
        teams_path = self._workspace_dir / "agents" / "teams.yaml"
        data = self._read_teams_document()
        if isinstance(data, str):
            return data
        teams = data.get("teams", [])
        if not isinstance(teams, list):
            return "ERROR: teams.yaml invalido."
        next_teams = [
            entry for entry in teams
            if not (isinstance(entry, dict) and entry.get("id") == team_id)
        ]
        if len(next_teams) == len(teams):
            return f"ERROR: team '{team_id}' no encontrado."
        backup_msg = self._backup(teams_path)
        data["teams"] = next_teams
        teams_path.parent.mkdir(parents=True, exist_ok=True)
        with open(teams_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return (
            f"Team '{team_id}' eliminado{self._tenant_suffix()}. "
            f"{backup_msg}. Reload necesario."
        )

    def workspace_inventory(self) -> dict[str, Any]:
        """Inventario estructurado tenant-scoped sin tocar el workspace global."""
        return {
            "tenant_slug": self._tenant_slug,
            "workspace_dir": str(self._workspace_dir),
            "main_agent": {"id": self._main_agent_id()},
            "workspace_tools_enabled": self._is_tool_enabled("workspace"),
            "sub_agents": self.list_sub_agents_inventory(),
            "teams": self.list_teams_inventory(),
        }

    # -- MCP servers ---------------------------------------------------------

    def add_mcp_server(
        self,
        name: str,
        transport: str,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        headers: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> str:
        """Registra un MCP server en workspace/mcp.yaml (upsert por name).

        - transport='streamable-http' o 'sse': requiere `url`.
        - transport='stdio': requiere `command`; `args` opcional.
        """
        if transport not in VALID_MCP_TRANSPORTS:
            return (
                f"ERROR: transport '{transport}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_MCP_TRANSPORTS))}"
            )
        if transport in ("streamable-http", "sse") and not url:
            return f"ERROR: transport '{transport}' requiere 'url'."
        if transport == "stdio" and not command:
            return "ERROR: transport 'stdio' requiere 'command'."

        path = self._workspace_dir / "mcp.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            data = {}
        servers = data.get("servers", [])
        if not isinstance(servers, list):
            servers = []

        entry: dict[str, Any] = {"name": name, "enabled": enabled, "transport": transport}
        if transport in ("streamable-http", "sse"):
            entry["url"] = url
            if headers:
                entry["headers"] = dict(headers)
        else:
            entry["command"] = command
            if args:
                entry["args"] = list(args)
            if env:
                entry["env"] = dict(env)

        replaced = False
        for idx, existing in enumerate(servers):
            if isinstance(existing, dict) and existing.get("name") == name:
                servers[idx] = entry
                replaced = True
                break
        if not replaced:
            servers.append(entry)

        backup_msg = self._backup(path)
        data["servers"] = servers
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        verb = "actualizado" if replaced else "anadido"
        return (
            f"MCP server '{name}' {verb}{self._tenant_suffix()} "
            f"(transport={transport}, enabled={enabled}). {backup_msg}. Reload necesario."
        )

    def disable_mcp_server(self, name: str) -> str:
        """Deshabilita un MCP server existente (enabled=false)."""
        path = self._workspace_dir / "mcp.yaml"
        if not path.exists():
            return "ERROR: mcp.yaml no existe en este workspace."
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        servers = data.get("servers", [])
        for entry in servers:
            if isinstance(entry, dict) and entry.get("name") == name:
                backup_msg = self._backup(path)
                entry["enabled"] = False
                with open(path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                return (
                    f"MCP server '{name}' deshabilitado{self._tenant_suffix()}. "
                    f"{backup_msg}. Reload necesario."
                )
        return f"ERROR: MCP server '{name}' no encontrado."

    # -- modelo principal ----------------------------------------------------

    def set_model(
        self,
        provider: str,
        model_id: str,
        api_key: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_region: str | None = None,
    ) -> str:
        """Cambia el modelo principal en config.yaml::model.

        Si vienen credenciales, se escriben en texto plano dentro del
        config.yaml del tenant. Preferir rotar credenciales via dashboard
        (cifradas en Supabase). Este metodo emite un warning explicito en
        logs + mensaje de retorno cuando se usan credenciales por chat.
        """
        if provider not in VALID_PROVIDERS:
            return (
                f"ERROR: Provider '{provider}' no valido. "
                f"Usa uno de: {', '.join(sorted(VALID_PROVIDERS))}"
            )
        if not model_id or not isinstance(model_id, str):
            return "ERROR: model_id requerido."

        path = self._workspace_dir / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            data = {}

        model_cfg = data.get("model")
        if not isinstance(model_cfg, dict):
            model_cfg = {}
        model_cfg["provider"] = provider
        model_cfg["id"] = model_id

        used_creds = False
        if api_key:
            model_cfg["api_key"] = api_key
            used_creds = True
        if aws_access_key_id:
            model_cfg["aws_access_key_id"] = aws_access_key_id
            used_creds = True
        if aws_secret_access_key:
            model_cfg["aws_secret_access_key"] = aws_secret_access_key
            used_creds = True
        if aws_region:
            model_cfg["aws_region"] = aws_region

        data["model"] = model_cfg
        backup_msg = self._backup(path)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        msg = (
            f"Modelo actualizado a {provider}/{model_id}{self._tenant_suffix()}. "
            f"{backup_msg}. Reload necesario."
        )
        if used_creds:
            warn = (
                " ADVERTENCIA: se escribieron credenciales en config.yaml en "
                "texto plano. Preferir rotar credenciales desde el dashboard."
            )
            logger.warning(
                f"set_model{self._tenant_suffix()} recibio credenciales por chat; "
                "quedan en config.yaml en texto plano."
            )
            msg += warn
        return msg

    # -- atajos enable/disable tool -----------------------------------------

    def enable_tool(self, tool_name: str) -> str:
        """Alias conversacional de toggle_tool(name, True)."""
        return self.toggle_tool(tool_name, True)

    def disable_tool(self, tool_name: str) -> str:
        """Alias conversacional de toggle_tool(name, False)."""
        return self.toggle_tool(tool_name, False)

    # -- reload --------------------------------------------------------------

    def request_reload(self) -> str:
        """Invalida la cache del tenant o (legacy) solicita reload global.

        Si se construyo con `on_reload`, invoca el callback (TenantLoader.reload)
        y la proxima request del tenant reconstruye su workspace en caliente.
        Si no, escribe el archivo-senal `.reload_requested` que el service_manager
        detecta para reiniciar el daemon global (compatibilidad con operador).
        """
        if self._on_reload is not None:
            try:
                self._on_reload(self._tenant_slug)
            except Exception as exc:
                return f"Reload fallo{self._tenant_suffix()}: {exc}"
            return (
                f"Cache invalidada{self._tenant_suffix()}. La proxima "
                "interaccion reconstruira el workspace con los cambios."
            )

        signal_file = OPENAGNO_ROOT / ".reload_requested"
        signal_file.write_text(datetime.now().isoformat())
        return "Reload solicitado. El daemon reiniciara el gateway en ~5s."
