# ruff: noqa: E402
"""
Tests para tools/workspace_tools.py — validacion de provider, tools y
multi-tenancy (workspace_dir + tenant_slug + on_reload).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.workspace_tools import WorkspaceTools, VALID_PROVIDERS


class TestValidProviders:
    """Tests para validacion de providers."""

    def test_valid_providers_set(self):
        expected = {"google", "openai", "anthropic", "aws_bedrock_claude", "aws_bedrock"}
        assert VALID_PROVIDERS == expected

    def test_invalid_provider_rejected(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.create_sub_agent(
            name="Test",
            agent_id="test-agent",
            role="test",
            tools=["duckduckgo"],
            instructions=["test"],
            model_provider="bedrock",  # INVALID
        )
        assert "ERROR" in result
        assert "bedrock" in result

    def test_valid_provider_accepted(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.create_sub_agent(
            name="Test Agent",
            agent_id="test-agent",
            role="test role",
            tools=["duckduckgo"],
            instructions=["Be helpful"],
            model_provider="google",
            model_id="gemini-2.5-flash",
        )
        assert "creado" in result.lower()
        assert "ERROR" not in result


class TestToolValidation:
    """Tests para validacion de tools."""

    def test_invalid_tool_rejected(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.create_sub_agent(
            name="Test",
            agent_id="test-agent",
            role="test",
            tools=["nonexistent_tool"],
            instructions=["test"],
            model_provider="google",
        )
        assert "ERROR" in result
        assert "nonexistent_tool" in result


class TestWorkspaceOps:
    """Tests para operaciones del workspace."""

    def test_list_workspace(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.list_workspace()
        assert "config.yaml" in result
        assert "instructions.md" in result

    def test_read_workspace_file(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.read_workspace_file("config.yaml")
        assert "TestBot" in result

    def test_read_nonexistent_file(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.read_workspace_file("nonexistent.yaml")
        assert "Error" in result

    def test_default_model_id(self):
        """El model_id por defecto debe ser gemini-2.5-flash (DAT-235)."""
        import inspect
        wt = WorkspaceTools()
        sig = inspect.signature(wt.create_sub_agent)
        default = sig.parameters["model_id"].default
        assert default == "gemini-2.5-flash"


class TestMultiTenant:
    """Tests de aislamiento entre workspaces de tenants (Fase A.3)."""

    def test_uses_provided_workspace_dir(self, tmp_path):
        # Dos workspaces independientes con tools.yaml minimo para validar tools.
        ws_a = tmp_path / "tenant-a" / "workspace"
        ws_b = tmp_path / "tenant-b" / "workspace"
        for ws in (ws_a, ws_b):
            ws.mkdir(parents=True)
            (ws / "tools.yaml").write_text(
                "builtin:\n  - {name: duckduckgo, enabled: true}\n"
                "optional: []\ncustom: []\n",
                encoding="utf-8",
            )

        wt_a = WorkspaceTools(workspace_dir=ws_a, tenant_slug="tenant-a")
        wt_b = WorkspaceTools(workspace_dir=ws_b, tenant_slug="tenant-b")

        wt_a.create_sub_agent(
            name="A", agent_id="agent-a", role="r",
            tools=["duckduckgo"], instructions=["x"],
            model_provider="google",
        )
        wt_b.create_sub_agent(
            name="B", agent_id="agent-b", role="r",
            tools=["duckduckgo"], instructions=["y"],
            model_provider="google",
        )

        assert (ws_a / "agents" / "agent_a.yaml").exists()
        assert (ws_b / "agents" / "agent_b.yaml").exists()
        assert not (ws_a / "agents" / "agent_b.yaml").exists()
        assert not (ws_b / "agents" / "agent_a.yaml").exists()

    def test_write_workspace_file_isolated(self, tmp_path):
        ws_a = tmp_path / "tenant-a" / "workspace"
        ws_b = tmp_path / "tenant-b" / "workspace"
        ws_a.mkdir(parents=True)
        ws_b.mkdir(parents=True)

        WorkspaceTools(workspace_dir=ws_a).write_workspace_file("notes.md", "A notes")
        WorkspaceTools(workspace_dir=ws_b).write_workspace_file("notes.md", "B notes")

        assert (ws_a / "notes.md").read_text(encoding="utf-8") == "A notes"
        assert (ws_b / "notes.md").read_text(encoding="utf-8") == "B notes"

    def test_backups_live_per_tenant(self, tmp_path):
        ws = tmp_path / "tenant-x" / "workspace"
        ws.mkdir(parents=True)
        (ws / "instructions.md").write_text("vieja", encoding="utf-8")

        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="tenant-x")
        wt.update_instructions("nuevas")

        backups_dir = tmp_path / "tenant-x" / "backups"
        assert backups_dir.exists()
        backups = list(backups_dir.glob("instructions.*.bak.md"))
        assert len(backups) == 1, f"Se esperaba 1 backup, hay {backups}"

    def test_request_reload_invokes_callback(self, tmp_path):
        ws = tmp_path / "tenant-cb" / "workspace"
        ws.mkdir(parents=True)
        cb = MagicMock()
        wt = WorkspaceTools(
            workspace_dir=ws,
            tenant_slug="tenant-cb",
            on_reload=cb,
        )

        result = wt.request_reload()

        cb.assert_called_once_with("tenant-cb")
        assert "Cache invalidada" in result
        assert "tenant-cb" in result

    def test_legacy_request_reload_writes_signal_file(self, tmp_path):
        """Sin on_reload, conserva el mecanismo historico (.reload_requested)."""
        fake_root = tmp_path / "openagno-root"
        fake_root.mkdir()

        with patch("tools.workspace_tools.OPENAGNO_ROOT", fake_root):
            wt = WorkspaceTools()  # sin kwargs => legacy path
            result = wt.request_reload()

        signal = fake_root / ".reload_requested"
        assert signal.exists()
        assert "Reload solicitado" in result

    def test_tenant_slug_visible_en_mensajes(self, tmp_path):
        ws = tmp_path / "acme" / "workspace"
        ws.mkdir(parents=True)
        (ws / "tools.yaml").write_text(
            "builtin: []\noptional: []\ncustom: []\n", encoding="utf-8"
        )
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="acme")
        msg = wt.write_workspace_file("hello.md", "hi")
        assert "acme" in msg

    def test_path_traversal_bloqueado(self, tmp_path):
        ws = tmp_path / "tenant-safe" / "workspace"
        ws.mkdir(parents=True)
        wt = WorkspaceTools(workspace_dir=ws)
        # Escapar del workspace con "../" debe ser rechazado.
        result = wt.write_workspace_file("../escape.md", "bad")
        assert "Error" in result
        assert not (tmp_path / "tenant-safe" / "escape.md").exists()
