"""Tests for IDE MCP config exports."""

import json
from pathlib import Path


def test_ide_config_json_files_are_valid():
	root = Path(__file__).resolve().parent.parent / "ide-configs"
	for name in ("cursor-mcp.json", "vscode-mcp.json", "windsurf-mcp.json"):
		payload = json.loads((root / name).read_text(encoding="utf-8"))
		assert "mcpServers" in payload
		assert "openagno-docs" in payload["mcpServers"]


def test_claude_code_setup_script_targets_openagno_docs():
	script = (
		Path(__file__).resolve().parent.parent / "ide-configs" / "claude-code-setup.sh"
	).read_text(encoding="utf-8")
	assert "claude mcp add-json" in script
	assert "https://docs.openagno.com/mcp" in script
