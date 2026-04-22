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
from typing import Callable, Optional

from agno.tools import Toolkit

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.parent.resolve()))
WORKSPACE_DIR = OPENAGNO_ROOT / "workspace"
BACKUPS_DIR = OPENAGNO_ROOT / "backups"

# F7 — 7.4.3: Proveedores de modelo validos
VALID_PROVIDERS = {
    "google", "openai", "anthropic",
    "aws_bedrock_claude", "aws_bedrock",
}


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
        super().__init__(name="workspace_tools")
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
        self.register(self.update_instructions)
        self.register(self.toggle_tool)
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
        model_provider: str = "google", model_id: str = "gemini-2.5-flash",
    ) -> str:
        """Crea un sub-agente en workspace/agents/.

        Valida provider y tools antes de crear el YAML (F7).
        """
        # F7 — 7.4.3: Validar provider
        if model_provider not in VALID_PROVIDERS:
            return (
                f"ERROR: Provider '{model_provider}' no valido. "
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
                "model": {"provider": model_provider, "id": model_id},
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
