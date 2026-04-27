# ruff: noqa: E402
"""
Tests para management/validator.py — validacion del workspace.
"""
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from management.validator import validate_workspace


class TestValidateWorkspace:
    """Tests para validate_workspace."""

    def test_valid_workspace(self, tmp_workspace, env_vars):
        """Un workspace valido con SQLite no deberia tener errores criticos de DB/keys."""
        env_vars(
            WHATSAPP_ACCESS_TOKEN="test",
            WHATSAPP_PHONE_NUMBER_ID="test",
            WHATSAPP_VERIFY_TOKEN="test",
        )
        errors = validate_workspace(str(tmp_workspace))
        # SQLite no requiere DB_HOST, OPENAI_API_KEY, etc.
        assert not any("config.yaml" in e for e in errors)

    def test_missing_model_provider_key_is_not_workspace_error(self, tmp_workspace, env_vars):
        """Las keys de modelo se configuran por CLI/UI/BYOK y no bloquean el workspace base."""
        env_vars(
            WHATSAPP_ACCESS_TOKEN="test",
            WHATSAPP_PHONE_NUMBER_ID="test",
            WHATSAPP_VERIFY_TOKEN="test",
        )
        errors = validate_workspace(str(tmp_workspace))

        assert not any("GOOGLE_API_KEY" in e for e in errors)

    def test_missing_config(self, tmp_path):
        """Un workspace sin config.yaml deberia reportar error."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        errors = validate_workspace(str(ws))
        assert any("config.yaml" in e for e in errors)

    def test_missing_instructions(self, tmp_workspace):
        """Sin instructions.md deberia reportar error."""
        (tmp_workspace / "instructions.md").unlink()
        errors = validate_workspace(str(tmp_workspace))
        assert any("instructions.md" in e for e in errors)

    def test_missing_tools_yaml(self, tmp_workspace):
        """Sin tools.yaml deberia reportar error."""
        (tmp_workspace / "tools.yaml").unlink()
        errors = validate_workspace(str(tmp_workspace))
        assert any("tools.yaml" in e for e in errors)

    def test_missing_mcp_yaml(self, tmp_workspace):
        """Sin mcp.yaml deberia reportar error."""
        (tmp_workspace / "mcp.yaml").unlink()
        errors = validate_workspace(str(tmp_workspace))
        assert any("mcp.yaml" in e for e in errors)

    def test_invalid_yaml(self, tmp_workspace):
        """YAML invalido deberia reportar error."""
        (tmp_workspace / "config.yaml").write_text(
            "invalid: yaml: content:\n  bad", encoding="utf-8"
        )
        errors = validate_workspace(str(tmp_workspace))
        # Deberia tener algun error (puede ser YAML invalido o falta secciones)
        assert len(errors) > 0
