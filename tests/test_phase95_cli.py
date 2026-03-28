from __future__ import annotations

import sys

import management.cli as legacy_cli


def test_process_utils_posix_flags(monkeypatch):
    from openagno.core import process_utils

    monkeypatch.setattr(process_utils, "IS_WINDOWS", False)
    assert process_utils.detached_process_kwargs() == {"start_new_session": True}


def test_process_utils_windows_flags(monkeypatch):
    from openagno.core import process_utils

    monkeypatch.setattr(process_utils, "IS_WINDOWS", True)
    monkeypatch.setattr(process_utils.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(process_utils.subprocess, "CREATE_NO_WINDOW", 0x8000000, raising=False)

    kwargs = process_utils.detached_process_kwargs()
    assert kwargs["creationflags"] == 0x200 | 0x8000000


def test_management_cli_prints_deprecation_notice(monkeypatch, capsys):
    called = {"value": False}

    def fake_run_onboarding():
        called["value"] = True

    monkeypatch.setattr(legacy_cli, "run_onboarding", fake_run_onboarding)
    monkeypatch.setattr(sys, "argv", ["management.cli"])

    legacy_cli.main()

    captured = capsys.readouterr()
    assert "deprecated" in captured.out.lower()
    assert "openagno init" in captured.out
    assert called["value"] is True
