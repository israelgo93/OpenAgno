"""
WorkspaceTools — El agente puede auto-configurarse.
CRUD sobre workspace/ con backup automatico.
"""
import os
import yaml
import shutil
from pathlib import Path
from datetime import datetime

from agno.tools import Toolkit
from agno.utils.log import logger

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.parent.resolve()))
WORKSPACE_DIR = OPENAGNO_ROOT / "workspace"
BACKUPS_DIR = OPENAGNO_ROOT / "backups"


class WorkspaceTools(Toolkit):
    def __init__(self):
        super().__init__(name="workspace_tools")
        self.register(self.read_workspace_file)
        self.register(self.write_workspace_file)
        self.register(self.list_workspace)
        self.register(self.create_sub_agent)
        self.register(self.update_instructions)
        self.register(self.toggle_tool)
        self.register(self.request_reload)

    def _backup(self, file_path: Path) -> str:
        BACKUPS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = BACKUPS_DIR / f"{file_path.stem}.{ts}.bak{file_path.suffix}"
        if file_path.exists():
            shutil.copy2(file_path, backup_path)
            return f"Backup: {backup_path.name}"
        return "Archivo nuevo, sin backup"

    def read_workspace_file(self, filename: str) -> str:
        """Lee un archivo del workspace. Ej: 'config.yaml', 'instructions.md'."""
        path = WORKSPACE_DIR / filename
        if not path.exists():
            return f"Error: {filename} no existe"
        if not path.resolve().is_relative_to(WORKSPACE_DIR.resolve()):
            return "Error: ruta fuera del workspace"
        return path.read_text(encoding="utf-8")

    def write_workspace_file(self, filename: str, content: str) -> str:
        """Escribe en workspace/. Crea backup automaticamente."""
        path = WORKSPACE_DIR / filename
        if not path.resolve().is_relative_to(WORKSPACE_DIR.resolve()):
            return "Error: ruta fuera del workspace"
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Escrito: {filename}. {backup_msg}. Reload necesario."

    def list_workspace(self) -> str:
        """Lista estructura del workspace."""
        result = []
        for item in sorted(WORKSPACE_DIR.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                result.append(str(item.relative_to(WORKSPACE_DIR)))
        return "\n".join(result) if result else "Workspace vacio"

    def create_sub_agent(
        self, name: str, agent_id: str, role: str,
        tools: list[str], instructions: list[str],
        model_provider: str = "google", model_id: str = "gemini-2.0-flash",
    ) -> str:
        """Crea un sub-agente en workspace/agents/."""
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
        path = WORKSPACE_DIR / filename
        backup_msg = self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(agent_data, f, default_flow_style=False, allow_unicode=True)
        return f"Sub-agente '{name}' creado en {filename}. {backup_msg}. Reload necesario."

    def update_instructions(self, new_instructions: str) -> str:
        """Actualiza workspace/instructions.md."""
        path = WORKSPACE_DIR / "instructions.md"
        backup_msg = self._backup(path)
        path.write_text(new_instructions, encoding="utf-8")
        return f"Instrucciones actualizadas. {backup_msg}. Reload necesario."

    def toggle_tool(self, tool_name: str, enabled: bool) -> str:
        """Activa/desactiva un tool en tools.yaml."""
        path = WORKSPACE_DIR / "tools.yaml"
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
                    return f"Tool '{tool_name}' {'activado' if enabled else 'desactivado'}. {backup_msg}"
        return f"Tool '{tool_name}' no encontrado"

    def request_reload(self) -> str:
        """Solicita reload al daemon (no mata el proceso actual)."""
        signal_file = OPENAGNO_ROOT / ".reload_requested"
        signal_file.write_text(datetime.now().isoformat())
        return "Reload solicitado. El daemon reiniciara el gateway en ~5s."
