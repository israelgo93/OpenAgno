# ruff: noqa: E402
"""
Tests para loader.py — carga de configuracion y construccion de objetos.
"""
import sys
from pathlib import Path
from unittest.mock import patch


# Asegurar import
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loader import (
    load_yaml,
    build_db_url,
    build_tools,
    build_mcp_tools,
    build_fallback_model,
    _resolve_env,
    _resolve_config,
    BUILTIN_TOOL_MAP,
    sanitize_history_for_provider,
)
from agno.models.message import Message


class TestResolveEnv:
    """Tests para resolucion de variables de entorno."""

    def test_resolve_simple_var(self, env_vars):
        env_vars(TEST_VAR="hello")
        assert _resolve_env("${TEST_VAR}") == "hello"

    def test_resolve_missing_var(self):
        result = _resolve_env("${NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_resolve_no_vars(self):
        assert _resolve_env("plain text") == "plain text"

    def test_resolve_multiple_vars(self, env_vars):
        env_vars(A="foo", B="bar")
        assert _resolve_env("${A}-${B}") == "foo-bar"


class TestResolveConfig:
    """Tests para resolucion recursiva de config."""

    def test_resolve_nested_dict(self, env_vars):
        env_vars(MY_KEY="value123")
        result = _resolve_config({"key": "${MY_KEY}", "nested": {"inner": "${MY_KEY}"}})
        assert result["key"] == "value123"
        assert result["nested"]["inner"] == "value123"

    def test_non_string_values_preserved(self):
        result = _resolve_config({"num": 42, "flag": True})
        assert result["num"] == 42
        assert result["flag"] is True

    def test_resolve_lists_recursively(self, env_vars):
        env_vars(TOKEN="abc123")
        result = _resolve_config({"args": ["--token", "${TOKEN}"], "nested": [{"value": "${TOKEN}"}]})
        assert result["args"] == ["--token", "abc123"]
        assert result["nested"][0]["value"] == "abc123"


class TestLoadYaml:
    """Tests para load_yaml."""

    def test_load_existing_yaml(self, tmp_workspace):
        with patch("loader.WORKSPACE_DIR", tmp_workspace):
            config = load_yaml("config.yaml")
            assert config["agent"]["name"] == "TestBot"
            assert config["model"]["id"] == "gemini-2.5-flash"

    def test_load_missing_yaml(self, tmp_workspace):
        with patch("loader.WORKSPACE_DIR", tmp_workspace):
            result = load_yaml("nonexistent.yaml")
            assert result == {}


class TestBuildDbUrl:
    """Tests para build_db_url."""

    def test_sqlite(self):
        url = build_db_url({"type": "sqlite"})
        assert url.startswith("sqlite")

    def test_local_postgres(self, env_vars):
        env_vars(
            DB_HOST="localhost",
            DB_PORT="5532",
            DB_USER="ai",
            DB_PASSWORD="ai",
            DB_NAME="ai",
        )
        url = build_db_url({"type": "local"})
        assert "postgresql+psycopg://ai:ai@localhost:5532/ai" in url

    def test_supabase_postgres(self, env_vars):
        env_vars(
            DB_HOST="db.supabase.co",
            DB_PORT="5432",
            DB_USER="postgres",
            DB_PASSWORD="secret",
            DB_NAME="postgres",
        )
        url = build_db_url({"type": "supabase"})
        assert "db.supabase.co" in url
        assert "sslmode=require" in url


class TestBuildTools:
    """Tests para build_tools."""

    def test_builtin_tools(self):
        config = {
            "builtin": [
                {"name": "duckduckgo", "enabled": True, "config": {}},
                {"name": "reasoning", "enabled": True, "config": {"add_instructions": True}},
            ],
            "optional": [],
        }
        tools = build_tools(config)
        assert len(tools) == 2

    def test_disabled_builtin(self):
        config = {
            "builtin": [
                {"name": "duckduckgo", "enabled": False, "config": {}},
            ],
            "optional": [],
        }
        tools = build_tools(config)
        assert len(tools) == 0

    def test_unknown_builtin(self):
        config = {
            "builtin": [
                {"name": "nonexistent_tool", "enabled": True, "config": {}},
            ],
            "optional": [],
        }
        tools = build_tools(config)
        assert len(tools) == 0

    def test_optional_disabled_by_default(self):
        config = {
            "builtin": [],
            "optional": [
                {"name": "email", "config": {}},  # enabled defaults to False
            ],
        }
        tools = build_tools(config)
        assert len(tools) == 0


class TestBuiltinToolMap:
    """Tests para el mapa de tools builtin."""

    def test_known_builtins(self):
        assert "duckduckgo" in BUILTIN_TOOL_MAP
        assert "crawl4ai" in BUILTIN_TOOL_MAP
        assert "reasoning" in BUILTIN_TOOL_MAP

    def test_builtin_factories_callable(self):
        for name, factory in BUILTIN_TOOL_MAP.items():
            assert callable(factory), f"{name} factory no es callable"


class TestBuildMcpTools:
    """Tests para MCPTools declarativos."""

    def test_stdio_uses_command_and_args(self, env_vars):
        env_vars(SUPABASE_ACCESS_TOKEN="token-123")
        tools = build_mcp_tools({
            "servers": [
                {
                    "name": "supabase",
                    "enabled": True,
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@supabase/mcp-server-supabase@latest", "--access-token", "${SUPABASE_ACCESS_TOKEN}"],
                }
            ]
        })
        assert len(tools) == 1
        server_params = tools[0].server_params
        assert server_params.command == "npx"
        assert server_params.args[-1] == "token-123"


class TestBuildFallbackModel:
    """Tests para fallback model config."""

    def test_supports_top_level_fallback_block(self):
        config = {
            "model": {"provider": "google", "id": "gemini-2.5-flash"},
            "fallback": {
                "enabled": True,
                "provider": "openai",
                "id": "gpt-4o-mini",
            },
        }
        with patch("loader._build_single_model", return_value="fallback-model") as mocked:
            result = build_fallback_model(config, model_config=config["model"])
        assert result == "fallback-model"
        # Desde la Fase BYOK, build_fallback_model propaga credenciales heredadas.
        # Cuando el config no las define, se envian como None para que Agno caiga
        # al os.environ (comportamiento del operador).
        mocked.assert_called_once_with(
            "openai",
            "gpt-4o-mini",
            "us-east-1",
            api_key=None,
            aws_access_key_id=None,
            aws_secret_access_key=None,
        )

    def test_supports_legacy_nested_fallback_block(self):
        model_config = {
            "provider": "google",
            "id": "gemini-2.5-flash",
            "fallback": {
                "enabled": True,
                "provider": "anthropic",
                "id": "claude-sonnet-4",
            },
        }
        with patch("loader._build_single_model", return_value="fallback-model") as mocked:
            result = build_fallback_model(model_config)
        assert result == "fallback-model"
        mocked.assert_called_once_with(
            "anthropic",
            "claude-sonnet-4",
            "us-east-1",
            api_key=None,
            aws_access_key_id=None,
            aws_secret_access_key=None,
        )


class TestSanitizeHistory:
    """Tests para saneamiento cross-model."""

    def test_keeps_history_for_non_anthropic_like_provider(self):
        messages = [
            Message(role="assistant", content="ok"),
            Message(role="tool", content="{}", tool_call_id="call-1"),
        ]
        sanitized = sanitize_history_for_provider(messages, "google")
        assert len(sanitized) == 2

    def test_removes_invalid_tool_messages_for_claude(self):
        messages = [
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    {"id": {"bad": "id"}, "function": {"name": "search", "arguments": "{}"}},
                    {"id": "call-2", "function": {"name": "search", "arguments": "{}"}},
                ],
            ),
            Message.model_construct(role="tool", content='{"ok": true}', tool_call_id={"bad": "id"}),
            Message(role="tool", content='{"ok": true}', tool_call_id="call-2"),
        ]
        sanitized = sanitize_history_for_provider(messages, "anthropic")
        assert len(sanitized) == 2
        assert sanitized[0].tool_calls == [
            {"id": "call-2", "function": {"name": "search", "arguments": "{}"}}
        ]
        assert sanitized[1].tool_call_id == "call-2"
