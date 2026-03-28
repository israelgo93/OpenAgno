"""Smoke tests para la CLI empaquetada `openagno`."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from openagno.cli import app


runner = CliRunner()


def test_cli_help_renders():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "openagno" in result.stdout.lower()


def test_templates_list_renders():
    result = runner.invoke(app, ["templates", "list"])
    assert result.exit_code == 0
    assert "personal_assistant" in result.stdout
    assert "developer_assistant" in result.stdout


def test_init_from_template(tmp_path: Path):
    result = runner.invoke(
        app,
        ["init", "--template", "personal_assistant", "--directory", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "Workspace initialized from packaged template." in result.stdout
    assert (tmp_path / "workspace" / "config.yaml").exists()


def test_add_agui_updates_workspace(tmp_path: Path):
    runner.invoke(
        app,
        ["init", "--template", "personal_assistant", "--directory", str(tmp_path)],
    )
    result = runner.invoke(app, ["add", "agui"], env={"OPENAGNO_ROOT": str(tmp_path)})
    assert result.exit_code == 0
    assert "AG-UI channel added." in result.stdout
    config = yaml.safe_load((tmp_path / "workspace" / "config.yaml").read_text())
    assert "agui" in config["channels"]


def test_add_a2a_updates_workspace(tmp_path: Path):
    runner.invoke(
        app,
        ["init", "--template", "personal_assistant", "--directory", str(tmp_path)],
    )
    result = runner.invoke(app, ["add", "a2a"], env={"OPENAGNO_ROOT": str(tmp_path)})
    assert result.exit_code == 0
    assert "A2A protocol enabled." in result.stdout
    config = yaml.safe_load((tmp_path / "workspace" / "config.yaml").read_text())
    assert config["a2a"]["enabled"] is True
