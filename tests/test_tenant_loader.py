"""Tests for the TenantLoader LRU cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from openagno.core.tenant_loader import TenantLoader
from openagno.core.workspace_store import WorkspaceStore


class _FakeStore:
	"""Minimal WorkspaceStore stub exposing only what TenantLoader needs."""

	def __init__(self, base: Path):
		self.base = base
		self.backend = "local"

	def workspace_path(self, slug: str) -> Path:
		return self.base / slug / "workspace"


def _make_bundle(tag: str) -> dict[str, object]:
	return {"main_agent": f"agent-for-{tag}", "tag": tag, "config": {"model": {"id": tag}}}


def _prepare_workspaces(tmp_path: Path, slugs: list[str]) -> _FakeStore:
	for slug in slugs:
		(tmp_path / slug / "workspace").mkdir(parents=True, exist_ok=True)
	return _FakeStore(tmp_path)


def test_default_bundle_served_without_filesystem(tmp_path: Path):
	store = _FakeStore(tmp_path)
	default = _make_bundle("operator")
	loader = TenantLoader(store, default_bundle=default, max_size=2)
	assert loader.get_or_load("default") is default
	stats = loader.stats()
	assert stats["hits"] == 1
	assert stats["default_loaded"] is True


def test_get_or_load_caches_per_tenant(tmp_path: Path):
	store = _prepare_workspaces(tmp_path, ["tenant-a", "tenant-b"])
	calls: list[Path] = []

	def fake_loader(path: Path) -> dict[str, object]:
		calls.append(path)
		return _make_bundle(path.parent.name)

	loader = TenantLoader(store, max_size=4, bundle_loader=fake_loader)

	first = loader.get_or_load("tenant-a")
	second = loader.get_or_load("tenant-a")
	third = loader.get_or_load("tenant-b")

	assert first is second
	assert first is not third
	assert len(calls) == 2  # solo una llamada por tenant
	stats = loader.stats()
	assert stats["hits"] == 1
	assert stats["misses"] == 2
	assert stats["loads"] == 2
	assert "tenant-a" in stats["loaded_tenants"]
	assert "tenant-b" in stats["loaded_tenants"]


def test_lru_eviction(tmp_path: Path):
	store = _prepare_workspaces(tmp_path, ["a", "b", "c"])
	loader = TenantLoader(
		store,
		max_size=2,
		bundle_loader=lambda p: _make_bundle(p.parent.name),
	)

	loader.get_or_load("a")
	loader.get_or_load("b")
	# Touch "a" so it becomes MRU
	loader.get_or_load("a")
	loader.get_or_load("c")  # debe evict "b"

	stats = loader.stats()
	assert stats["size"] == 2
	assert stats["evictions"] == 1
	assert "b" not in stats["loaded_tenants"]
	assert "a" in stats["loaded_tenants"]
	assert "c" in stats["loaded_tenants"]


def test_reload_drops_tenant(tmp_path: Path):
	store = _prepare_workspaces(tmp_path, ["acme"])
	counter = {"calls": 0}

	def fake_loader(path: Path) -> dict[str, object]:
		counter["calls"] += 1
		return _make_bundle(f"acme-v{counter['calls']}")

	loader = TenantLoader(store, max_size=2, bundle_loader=fake_loader)

	first = loader.get_or_load("acme")
	assert first["tag"] == "acme-v1"

	assert loader.reload("acme") is True
	assert loader.reload("acme") is False  # ya no esta

	second = loader.get_or_load("acme")
	assert second["tag"] == "acme-v2"
	assert second is not first


def test_reload_default_is_noop(tmp_path: Path):
	loader = TenantLoader(_FakeStore(tmp_path), default_bundle=_make_bundle("op"), max_size=2)
	assert loader.reload("default") is False


def test_missing_workspace_raises_lookup_error(tmp_path: Path):
	store = _FakeStore(tmp_path)
	loader = TenantLoader(store, max_size=1)
	with pytest.raises(LookupError):
		loader.get_or_load("ghost")


def test_get_or_load_without_default_bundle_errors(tmp_path: Path):
	loader = TenantLoader(_FakeStore(tmp_path), max_size=1)
	with pytest.raises(LookupError):
		loader.get_or_load("default")


def test_reload_all_clears_cache(tmp_path: Path):
	store = _prepare_workspaces(tmp_path, ["x", "y"])
	loader = TenantLoader(
		store,
		max_size=4,
		bundle_loader=lambda p: _make_bundle(p.parent.name),
	)
	loader.get_or_load("x")
	loader.get_or_load("y")
	assert loader.reload_all() == 2
	assert loader.stats()["size"] == 0


def test_workspace_store_write_config_emits_md_files(tmp_path: Path):
	store = WorkspaceStore(base_dir=tmp_path)
	(tmp_path / "acme" / "workspace").mkdir(parents=True)

	config = store.write_config(
		"acme",
		{
			"agent": {"name": "Acme"},
			"model": {"provider": "openai", "id": "gpt-4.1-mini"},
			"instructions": "Responde siempre en espanol.",
			"self_knowledge": "Soy el agente oficial de Acme.",
		},
	)

	assert config["model"]["id"] == "gpt-4.1-mini"
	assert (tmp_path / "acme" / "workspace" / "instructions.md").read_text(encoding="utf-8") == "Responde siempre en espanol."
	assert (tmp_path / "acme" / "workspace" / "self_knowledge.md").read_text(encoding="utf-8") == "Soy el agente oficial de Acme."


def test_workspace_store_write_config_spills_tools_and_mcp_yaml(tmp_path: Path):
	"""Fix multi-tenant 2026-04-22: tools_yaml y mcp_yaml deben volcarse
	a archivos separados (no quedarse dentro del config.yaml)."""
	import yaml

	store = WorkspaceStore(base_dir=tmp_path)
	(tmp_path / "acme" / "workspace").mkdir(parents=True)

	tools_yaml = {
		"builtin": [{"name": "duckduckgo", "enabled": True}],
		"optional": [{"name": "workspace", "enabled": True}],
		"custom": [],
	}
	mcp_yaml = {
		"servers": [
			{"name": "agno_docs", "transport": "streamable-http", "url": "https://docs.agno.com/mcp", "enabled": True}
		],
		"expose": {"enabled": False},
	}

	config = store.write_config(
		"acme",
		{
			"agent": {"name": "Acme"},
			"model": {"provider": "openai", "id": "gpt-4.1-mini"},
			"tools_yaml": tools_yaml,
			"mcp_yaml": mcp_yaml,
		},
	)

	# Archivos separados creados
	tools_file = tmp_path / "acme" / "workspace" / "tools.yaml"
	mcp_file = tmp_path / "acme" / "workspace" / "mcp.yaml"
	assert tools_file.exists()
	assert mcp_file.exists()
	assert yaml.safe_load(tools_file.read_text()) == tools_yaml
	assert yaml.safe_load(mcp_file.read_text()) == mcp_yaml

	# config.yaml NO debe contener las claves tools_yaml / mcp_yaml
	config_file = tmp_path / "acme" / "workspace" / "config.yaml"
	config_on_disk = yaml.safe_load(config_file.read_text())
	assert "tools_yaml" not in config_on_disk
	assert "mcp_yaml" not in config_on_disk
	# Pero si debe contener el resto
	assert config_on_disk["agent"]["name"] == "Acme"

	# El dict devuelto tambien queda sin las claves "meta"
	assert "tools_yaml" not in config
	assert "mcp_yaml" not in config


def test_workspace_store_tools_yaml_no_escrito_si_vacio(tmp_path: Path):
	"""Si tools_yaml / mcp_yaml no vienen, no se tocan los archivos existentes."""
	store = WorkspaceStore(base_dir=tmp_path)
	ws = tmp_path / "acme" / "workspace"
	ws.mkdir(parents=True)
	(ws / "tools.yaml").write_text("builtin: [{name: pre-existente}]\n", encoding="utf-8")

	store.write_config("acme", {"agent": {"name": "Acme"}})

	# El tools.yaml preexistente no debe haber sido sobrescrito
	assert "pre-existente" in (ws / "tools.yaml").read_text(encoding="utf-8")
