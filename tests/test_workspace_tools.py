# ruff: noqa: E402
"""
Tests para tools/workspace_tools.py — validacion de provider, tools y
multi-tenancy (workspace_dir + tenant_slug + on_reload).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml


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

    def test_create_sub_agent_hereda_modelo_del_workspace(self, tmp_workspace):
        wt = WorkspaceTools(workspace_dir=tmp_workspace)
        result = wt.create_sub_agent(
            name="Heredado",
            agent_id="inherit-agent",
            role="test",
            tools=["duckduckgo"],
            instructions=["usa el modelo principal"],
        )
        assert "ERROR" not in result
        data = yaml.safe_load((tmp_workspace / "agents" / "inherit_agent.yaml").read_text())
        assert data["agent"]["model"] == {
            "provider": "google",
            "id": "gemini-2.5-flash",
        }


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


# =============================================================================
# Fase A.4 — Self-personalization avanzada
# =============================================================================


def _ws_with_tools(tmp_path: Path, *, name: str = "ws") -> Path:
    """Crea un workspace minimo con tools.yaml valido para los tests A.4."""
    ws = tmp_path / name / "workspace"
    ws.mkdir(parents=True)
    (ws / "tools.yaml").write_text(
        "builtin:\n"
        "  - {name: duckduckgo, enabled: true}\n"
        "  - {name: reasoning, enabled: true}\n"
        "optional:\n"
        "  - {name: shell, enabled: false}\n"
        "custom: []\n",
        encoding="utf-8",
    )
    return ws


class TestSubAgentManagement:
    def test_list_sub_agents_empty(self, tmp_path):
        ws = _ws_with_tools(tmp_path)
        wt = WorkspaceTools(workspace_dir=ws)
        assert wt.list_sub_agents() == "No hay sub-agentes configurados."

    def test_list_sub_agents_muestra_info(self, tmp_path):
        ws = _ws_with_tools(tmp_path)
        wt = WorkspaceTools(workspace_dir=ws)
        wt.create_sub_agent(
            name="Research", agent_id="research-1", role="buscar",
            tools=["duckduckgo"], instructions=["Investiga"],
        )
        out = wt.list_sub_agents()
        assert "research-1" in out
        assert "duckduckgo" in out
        assert "google" in out  # default provider

    def test_list_sub_agents_inventory_incluye_disabled(self, tmp_path):
        ws = _ws_with_tools(tmp_path)
        wt = WorkspaceTools(workspace_dir=ws)
        wt.create_sub_agent(
            name="Research", agent_id="research-1", role="buscar",
            tools=["duckduckgo"], instructions=["Investiga"],
        )
        wt.disable_sub_agent("research-1")
        inventory = wt.list_sub_agents_inventory()
        assert inventory == [
            {
                "id": "research-1",
                "name": "Research",
                "role": "buscar",
                "model": {"provider": "google", "id": "gemini-2.5-flash"},
                "tools": ["duckduckgo"],
                "enabled": False,
                "file": "agents/research_1.yaml.disabled",
                "valid": True,
            }
        ]

    def test_disable_sub_agent_rename(self, tmp_path):
        ws = _ws_with_tools(tmp_path)
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="acme")
        wt.create_sub_agent(
            name="X", agent_id="x-agent", role="x",
            tools=[], instructions=["i"],
        )
        assert (ws / "agents" / "x_agent.yaml").exists()
        msg = wt.disable_sub_agent("x-agent")
        assert "deshabilitado" in msg
        assert "acme" in msg
        assert not (ws / "agents" / "x_agent.yaml").exists()
        assert (ws / "agents" / "x_agent.yaml.disabled").exists()

    def test_disable_sub_agent_no_existe(self, tmp_path):
        ws = _ws_with_tools(tmp_path)
        wt = WorkspaceTools(workspace_dir=ws)
        assert "ERROR" in wt.disable_sub_agent("ghost")

    def test_create_sub_agent_usa_modelo_actual_si_workspace_no_es_google(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="bedrock-subagent")
        (ws / "config.yaml").write_text(
            "model:\n"
            "  provider: aws_bedrock_claude\n"
            "  id: us.anthropic.claude-sonnet-4-6\n",
            encoding="utf-8",
        )
        wt = WorkspaceTools(workspace_dir=ws)
        wt.create_sub_agent(
            name="Research", agent_id="research-bedrock", role="investigar",
            tools=["duckduckgo"], instructions=["Investiga"],
        )
        data = yaml.safe_load((ws / "agents" / "research_bedrock.yaml").read_text())
        assert data["agent"]["model"] == {
            "provider": "aws_bedrock_claude",
            "id": "us.anthropic.claude-sonnet-4-6",
        }

    def test_delete_sub_agent_backup(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="del")
        wt = WorkspaceTools(workspace_dir=ws)
        wt.create_sub_agent(
            name="Y", agent_id="y-agent", role="y",
            tools=[], instructions=["i"],
        )
        target = ws / "agents" / "y_agent.yaml"
        assert target.exists()
        msg = wt.delete_sub_agent("y-agent")
        assert "eliminado" in msg
        assert not target.exists()
        backups = list((tmp_path / "del" / "backups").glob("y_agent.*.bak.yaml"))
        assert len(backups) == 1

    def test_delete_sub_agent_deshabilitado(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="del-disabled")
        wt = WorkspaceTools(workspace_dir=ws)
        wt.create_sub_agent(
            name="Z", agent_id="z-agent", role="z",
            tools=[], instructions=["i"],
        )
        wt.disable_sub_agent("z-agent")
        target = ws / "agents" / "z_agent.yaml.disabled"
        assert target.exists()
        msg = wt.delete_sub_agent("z-agent")
        assert "eliminado" in msg
        assert not target.exists()


class TestTeamManagement:
    def _prep(self, tmp_path, slug="team-ws"):
        ws = _ws_with_tools(tmp_path, name=slug)
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug=slug)
        # Dos sub-agentes para armar un team
        wt.create_sub_agent(
            name="A", agent_id="agent-a", role="a", tools=[], instructions=["i"],
        )
        wt.create_sub_agent(
            name="B", agent_id="agent-b", role="b", tools=[], instructions=["i"],
        )
        return ws, wt

    def test_create_team_ok(self, tmp_path):
        ws, wt = self._prep(tmp_path)
        msg = wt.create_team(
            team_id="t1",
            name="Team One",
            mode="coordinate",
            members=["agent-a", "agent-b"],
            instructions=["colabora"],
        )
        assert "creado" in msg
        data = yaml.safe_load((ws / "agents" / "teams.yaml").read_text())
        assert any(t.get("id") == "t1" for t in data["teams"])
        assert next(t for t in data["teams"] if t.get("id") == "t1")["enabled"] is True

    def test_list_teams_empty(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="teams-empty")
        wt = WorkspaceTools(workspace_dir=ws)
        assert wt.list_teams() == "No hay teams configurados."

    def test_list_teams_muestra_info(self, tmp_path):
        _, wt = self._prep(tmp_path, slug="teams-list")
        wt.create_team(
            team_id="t-list",
            name="Team List",
            mode="coordinate",
            members=["agent-a", "agent-b"],
        )
        out = wt.list_teams()
        assert "t-list" in out
        assert "Team List" in out
        assert "agent-a,agent-b" in out

    def test_disable_y_delete_team(self, tmp_path):
        ws, wt = self._prep(tmp_path, slug="team-disable-delete")
        wt.create_team(
            team_id="t-disable",
            name="Disable Me",
            mode="coordinate",
            members=["agent-a", "agent-b"],
        )
        msg = wt.disable_team("t-disable")
        assert "deshabilitado" in msg
        inventory = wt.list_teams_inventory()
        assert inventory[0]["enabled"] is False

        msg = wt.delete_team("t-disable")
        assert "eliminado" in msg
        data = yaml.safe_load((ws / "agents" / "teams.yaml").read_text())
        assert data["teams"] == []

    def test_create_team_hereda_modelo_actual(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="team-bedrock")
        (ws / "config.yaml").write_text(
            "model:\n"
            "  provider: aws_bedrock_claude\n"
            "  id: us.anthropic.claude-sonnet-4-6\n",
            encoding="utf-8",
        )
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="team-bedrock")
        wt.create_sub_agent(
            name="A", agent_id="agent-a", role="a", tools=[], instructions=["i"],
        )
        wt.create_sub_agent(
            name="B", agent_id="agent-b", role="b", tools=[], instructions=["i"],
        )
        msg = wt.create_team(
            team_id="bedrock-team",
            name="Bedrock Team",
            mode="coordinate",
            members=["agent-a", "agent-b"],
        )
        assert "ERROR" not in msg
        data = yaml.safe_load((ws / "agents" / "teams.yaml").read_text())
        team = next(t for t in data["teams"] if t["id"] == "bedrock-team")
        assert team["model"] == {
            "provider": "aws_bedrock_claude",
            "id": "us.anthropic.claude-sonnet-4-6",
        }

    def test_create_team_requiere_model_id_si_provider_no_coincide(self, tmp_path):
        _, wt = self._prep(tmp_path, slug="team-requires-model-id")
        msg = wt.create_team(
            team_id="t-provider-only",
            name="Provider Only",
            mode="coordinate",
            members=["agent-a", "agent-b"],
            model_provider="openai",
        )
        assert "ERROR" in msg
        assert "model_id requerido" in msg

    def test_create_team_rechaza_modo_invalido(self, tmp_path):
        _, wt = self._prep(tmp_path)
        msg = wt.create_team(
            team_id="t2", name="T", mode="solo",
            members=["agent-a", "agent-b"],
        )
        assert "ERROR" in msg
        assert "solo" in msg

    def test_create_team_requires_two_members(self, tmp_path):
        _, wt = self._prep(tmp_path)
        msg = wt.create_team(
            team_id="t3", name="T", mode="coordinate",
            members=["agent-a"],
        )
        assert "ERROR" in msg
        assert "2 miembros" in msg

    def test_create_team_rechaza_miembros_desconocidos(self, tmp_path):
        _, wt = self._prep(tmp_path)
        msg = wt.create_team(
            team_id="t4", name="T", mode="coordinate",
            members=["agent-a", "ghost"],
        )
        assert "ERROR" in msg
        assert "ghost" in msg

    def test_create_team_upsert(self, tmp_path):
        ws, wt = self._prep(tmp_path)
        wt.create_team(
            team_id="t5", name="Primero", mode="coordinate",
            members=["agent-a", "agent-b"],
        )
        wt.create_team(
            team_id="t5", name="Segundo", mode="route",
            members=["agent-a", "agent-b"],
        )
        data = yaml.safe_load((ws / "agents" / "teams.yaml").read_text())
        entries = [t for t in data["teams"] if t.get("id") == "t5"]
        assert len(entries) == 1
        assert entries[0]["name"] == "Segundo"
        assert entries[0]["mode"] == "route"


class TestMcpManagement:
    def test_add_streamable_http(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-a")
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="mcp-a")
        msg = wt.add_mcp_server(
            name="agno_docs",
            transport="streamable-http",
            url="https://docs.agno.com/mcp",
        )
        assert "anadido" in msg
        data = yaml.safe_load((ws / "mcp.yaml").read_text())
        entry = next(s for s in data["servers"] if s["name"] == "agno_docs")
        assert entry["transport"] == "streamable-http"
        assert entry["enabled"] is True
        assert entry["url"] == "https://docs.agno.com/mcp"

    def test_add_stdio(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-b")
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.add_mcp_server(
            name="supabase",
            transport="stdio",
            command="npx",
            args=["-y", "@supabase/mcp-server-supabase"],
            env={"SUPABASE_ACCESS_TOKEN": "xxx"},
        )
        assert "anadido" in msg
        data = yaml.safe_load((ws / "mcp.yaml").read_text())
        entry = next(s for s in data["servers"] if s["name"] == "supabase")
        assert entry["transport"] == "stdio"
        assert entry["command"] == "npx"
        assert entry["args"] == ["-y", "@supabase/mcp-server-supabase"]
        assert entry["env"]["SUPABASE_ACCESS_TOKEN"] == "xxx"

    def test_add_rechaza_transport_invalido(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-c")
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.add_mcp_server(name="x", transport="grpc", url="http://x")
        assert "ERROR" in msg
        assert "grpc" in msg

    def test_http_requiere_url(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-d")
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.add_mcp_server(name="x", transport="streamable-http")
        assert "ERROR" in msg
        assert "url" in msg

    def test_stdio_requiere_command(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-e")
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.add_mcp_server(name="x", transport="stdio")
        assert "ERROR" in msg
        assert "command" in msg

    def test_upsert_por_nombre(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-f")
        wt = WorkspaceTools(workspace_dir=ws)
        wt.add_mcp_server(name="agno", transport="streamable-http", url="https://a")
        wt.add_mcp_server(name="agno", transport="streamable-http", url="https://b")
        data = yaml.safe_load((ws / "mcp.yaml").read_text())
        matches = [s for s in data["servers"] if s["name"] == "agno"]
        assert len(matches) == 1
        assert matches[0]["url"] == "https://b"

    def test_disable_server(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-g")
        wt = WorkspaceTools(workspace_dir=ws)
        wt.add_mcp_server(name="agno", transport="streamable-http", url="https://a")
        msg = wt.disable_mcp_server("agno")
        assert "deshabilitado" in msg
        data = yaml.safe_load((ws / "mcp.yaml").read_text())
        entry = next(s for s in data["servers"] if s["name"] == "agno")
        assert entry["enabled"] is False

    def test_disable_server_no_existe(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="mcp-h")
        wt = WorkspaceTools(workspace_dir=ws)
        # Sin mcp.yaml aun
        assert "no existe" in wt.disable_mcp_server("x")
        # Crear uno y pedir disable de otro nombre
        wt.add_mcp_server(name="agno", transport="streamable-http", url="https://a")
        assert "no encontrado" in wt.disable_mcp_server("otro")


class TestSetModel:
    def test_set_model_ok(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="sm-a")
        (ws / "config.yaml").write_text(
            "agent:\n  name: A\nmodel:\n  provider: google\n  id: gemini-2.5-flash\n",
            encoding="utf-8",
        )
        wt = WorkspaceTools(workspace_dir=ws, tenant_slug="sm-a")
        msg = wt.set_model("openai", "gpt-4o-mini")
        assert "openai/gpt-4o-mini" in msg
        data = yaml.safe_load((ws / "config.yaml").read_text())
        assert data["model"]["provider"] == "openai"
        assert data["model"]["id"] == "gpt-4o-mini"
        # Mantiene agent
        assert data["agent"]["name"] == "A"

    def test_set_model_provider_invalido(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="sm-b")
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.set_model("bedrock", "x")
        assert "ERROR" in msg
        assert "bedrock" in msg

    def test_set_model_con_credenciales_warning(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="sm-c")
        (ws / "config.yaml").write_text(
            "model:\n  provider: google\n  id: gemini-2.5-flash\n",
            encoding="utf-8",
        )
        wt = WorkspaceTools(workspace_dir=ws)
        msg = wt.set_model("openai", "gpt-4o", api_key="sk-secret")
        assert "ADVERTENCIA" in msg
        data = yaml.safe_load((ws / "config.yaml").read_text())
        assert data["model"]["api_key"] == "sk-secret"

    def test_set_model_crea_config_si_no_existe(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="sm-d")
        wt = WorkspaceTools(workspace_dir=ws)
        assert not (ws / "config.yaml").exists()
        msg = wt.set_model("openai", "gpt-4o-mini")
        assert "ERROR" not in msg
        data = yaml.safe_load((ws / "config.yaml").read_text())
        assert data["model"]["id"] == "gpt-4o-mini"


class TestEnableDisableTool:
    def test_enable_y_disable(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="td")
        wt = WorkspaceTools(workspace_dir=ws)
        assert "activado" in wt.enable_tool("shell")
        data = yaml.safe_load((ws / "tools.yaml").read_text())
        shell = next(t for t in data["optional"] if t["name"] == "shell")
        assert shell["enabled"] is True

        assert "desactivado" in wt.disable_tool("shell")
        data = yaml.safe_load((ws / "tools.yaml").read_text())
        shell = next(t for t in data["optional"] if t["name"] == "shell")
        assert shell["enabled"] is False

    def test_enable_tool_inexistente(self, tmp_path):
        ws = _ws_with_tools(tmp_path, name="td2")
        wt = WorkspaceTools(workspace_dir=ws)
        assert "no encontrado" in wt.enable_tool("ghost")
