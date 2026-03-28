"""Smoke tests para la CLI empaquetada `openagno`."""

from pathlib import Path

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
    assert (tmp_path / "workspace" / "config.yaml").exists()
