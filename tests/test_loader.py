"""
Tests para loader.py — carga de configuracion y construccion de objetos.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Asegurar import
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loader import (
    load_yaml,
    build_db_url,
    build_tools,
    _resolve_env,
    _resolve_config,
    BUILTIN_TOOL_MAP,
)


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
