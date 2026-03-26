"""
Fixtures para tests de OpenAgno.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

import pytest

# Asegurar que el repo root este en sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def tmp_workspace(tmp_path):
    """Crea un workspace temporal con archivos minimos."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "knowledge").mkdir()
    (ws / "knowledge" / "docs").mkdir()
    (ws / "agents").mkdir()

    # config.yaml minimo
    (ws / "config.yaml").write_text("""
agent:
  name: TestBot
  id: testbot-main
  description: Bot de prueba

model:
  provider: google
  id: gemini-2.5-flash

database:
  type: sqlite

channels:
  - whatsapp

memory:
  enable_agentic_memory: false

scheduler:
  enabled: false

studio:
  enabled: false
""", encoding="utf-8")

    # instructions.md
    (ws / "instructions.md").write_text(
        "# TestBot\nEres un bot de prueba.", encoding="utf-8"
    )

    # tools.yaml
    (ws / "tools.yaml").write_text("""
builtin:
  - name: duckduckgo
    enabled: true
  - name: reasoning
    enabled: true
optional:
  - name: workspace
    enabled: false
  - name: yfinance
    enabled: false
  - name: calculator
    enabled: false
custom: []
""", encoding="utf-8")

    # mcp.yaml
    (ws / "mcp.yaml").write_text("""
servers:
  - name: agno_docs
    enabled: false
    transport: streamable-http
    url: https://docs.agno.com/mcp
expose:
  enabled: false
""", encoding="utf-8")

    # teams.yaml vacio
    (ws / "agents" / "teams.yaml").write_text("""
teams: []
""", encoding="utf-8")

    # knowledge/urls.yaml
    (ws / "knowledge" / "urls.yaml").write_text("urls: []\n", encoding="utf-8")

    return ws


@pytest.fixture
def env_vars():
    """Fixture para configurar variables de entorno temporales."""
    original = os.environ.copy()

    def _set(**kwargs):
        for k, v in kwargs.items():
            os.environ[k] = v

    yield _set

    # Restaurar
    os.environ.clear()
    os.environ.update(original)
