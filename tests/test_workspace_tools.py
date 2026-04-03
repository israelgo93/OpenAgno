# ruff: noqa: E402
"""
Tests para tools/workspace_tools.py — validacion de provider y tools.
"""
import sys
from pathlib import Path
from unittest.mock import patch


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
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            wt = WorkspaceTools()
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
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            with patch("tools.workspace_tools.OPENAGNO_ROOT", tmp_workspace.parent):
                wt = WorkspaceTools()
                result = wt.create_sub_agent(
                    name="Test Agent",
                    agent_id="test-agent",
                    role="test role",
                    tools=["duckduckgo"],
                    instructions=["Be helpful"],
                    model_provider="google",
                    model_id="gemini-2.5-flash",
                )
                assert "creado" in result.lower() or "ERROR" not in result


class TestToolValidation:
    """Tests para validacion de tools."""

    def test_invalid_tool_rejected(self, tmp_workspace):
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            wt = WorkspaceTools()
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
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            wt = WorkspaceTools()
            result = wt.list_workspace()
            assert "config.yaml" in result
            assert "instructions.md" in result

    def test_read_workspace_file(self, tmp_workspace):
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            wt = WorkspaceTools()
            result = wt.read_workspace_file("config.yaml")
            assert "TestBot" in result

    def test_read_nonexistent_file(self, tmp_workspace):
        with patch("tools.workspace_tools.WORKSPACE_DIR", tmp_workspace):
            wt = WorkspaceTools()
            result = wt.read_workspace_file("nonexistent.yaml")
            assert "Error" in result

    def test_default_model_id(self):
        """El model_id por defecto debe ser gemini-2.5-flash (DAT-235)."""
        import inspect
        wt = WorkspaceTools()
        sig = inspect.signature(wt.create_sub_agent)
        default = sig.parameters["model_id"].default
        assert default == "gemini-2.5-flash"
