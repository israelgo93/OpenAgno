"""Tests for tenant provisioning API routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from openagno.core.tenant import TenantStore
from openagno.core.workspace_store import WorkspaceStore
from routes.tenant_routes import create_tenant_router


class _Response:
	def __init__(self, content: str):
		self.content = content


class _FakeAgent:
	def __init__(self):
		self.calls = []

	async def arun(self, message: str, **kwargs):
		self.calls.append({"message": message, **kwargs})
		return _Response("tenant ok")


class _RuntimeObject:
	def __init__(self, object_id: str):
		self.id = object_id


class _FakeTenantLoader:
	def __init__(self, workspace_store: WorkspaceStore):
		self.workspace_store = workspace_store
		self.reload_calls: list[str] = []

	def reload(self, tenant_slug: str) -> bool:
		self.reload_calls.append(tenant_slug)
		return True

	def get_or_load(self, tenant_slug: str):
		import yaml

		workspace = self.workspace_store.workspace_path(tenant_slug)
		config = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8")) or {}
		main_id = config.get("agent", {}).get("id", "agnobot-main")
		sub_agents = []
		for path in sorted((workspace / "agents").glob("*.yaml")):
			if path.name == "teams.yaml":
				continue
			data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
			agent_id = data.get("agent", {}).get("id")
			if agent_id:
				sub_agents.append(_RuntimeObject(agent_id))

		teams = []
		teams_path = workspace / "agents" / "teams.yaml"
		if teams_path.exists():
			data = yaml.safe_load(teams_path.read_text(encoding="utf-8")) or {}
			for entry in data.get("teams", []):
				if isinstance(entry, dict) and entry.get("enabled", True) is not False:
					team_id = entry.get("id")
					if team_id:
						teams.append(_RuntimeObject(team_id))

		return {
			"config": config,
			"main_agent": _RuntimeObject(main_id),
			"sub_agents": sub_agents,
			"teams": teams,
		}


def test_create_tenant_and_run_agent(tmp_path: Path):
	store = TenantStore(f"sqlite:///{tmp_path / 'tenant-api.db'}")
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")
	agent = _FakeAgent()

	app = FastAPI()
	app.include_router(
		create_tenant_router(
			store,
			workspace_store,
			{"agnobot-main": agent},
		)
	)
	client = TestClient(app)

	create_response = client.post(
		"/tenants/",
		json={
			"name": "Acme Corp",
			"template": "personal_assistant",
			"workspace_config": {"agent": {"name": "Tenant Bot"}},
		},
	)
	assert create_response.status_code == 200
	tenant = create_response.json()["tenant"]
	assert tenant["slug"] == "acme-corp"
	assert Path(create_response.json()["workspace_path"]).exists()

	run_response = client.post(
		f"/tenants/{tenant['slug']}/agents/agnobot-main/runs",
		json={"message": "hello tenant", "user_id": "alice"},
	)
	assert run_response.status_code == 200
	assert run_response.json()["content"] == "tenant ok"
	assert agent.calls[0]["knowledge_filters"] == {"linked_to": "acme-corp"}
	assert agent.calls[0]["user_id"] == "acme-corp:alice"


def test_collection_routes_support_trailing_and_non_trailing_slash(tmp_path: Path):
	store = TenantStore(f"sqlite:///{tmp_path / 'tenant-collection-routes.db'}")
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")

	app = FastAPI()
	app.include_router(create_tenant_router(store, workspace_store, {}))
	client = TestClient(app)

	create_without_slash = client.post("/tenants", json={"name": "No Slash Org"})
	assert create_without_slash.status_code == 200
	assert create_without_slash.json()["tenant"]["slug"] == "no-slash-org"

	create_with_slash = client.post("/tenants/", json={"name": "Slash Org"})
	assert create_with_slash.status_code == 200
	assert create_with_slash.json()["tenant"]["slug"] == "slash-org"

	list_without_slash = client.get("/tenants")
	assert list_without_slash.status_code == 200
	assert list_without_slash.json()["count"] == 2

	list_with_slash = client.get("/tenants/")
	assert list_with_slash.status_code == 200
	assert list_with_slash.json()["count"] == 2


def test_update_workspace_config(tmp_path: Path):
	store = TenantStore(f"sqlite:///{tmp_path / 'tenant-config.db'}")
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")

	app = FastAPI()
	app.include_router(create_tenant_router(store, workspace_store, {}))
	client = TestClient(app)

	create_response = client.post("/tenants/", json={"name": "Beta Org"})
	tenant = create_response.json()["tenant"]

	update_response = client.put(
		f"/tenants/{tenant['slug']}/workspace",
		json={"config": {"scheduler": {"enabled": False}}},
	)
	assert update_response.status_code == 200
	assert update_response.json()["config"]["scheduler"]["enabled"] is False


def test_reload_syncs_workspace_config_written_via_cli(tmp_path: Path):
	store = TenantStore(f"sqlite:///{tmp_path / 'tenant-reload-sync.db'}")
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")

	app = FastAPI()
	app.include_router(create_tenant_router(store, workspace_store, {}))
	client = TestClient(app)

	create_response = client.post(
		"/tenants/",
		json={
			"name": "Gamma Org",
			"workspace_config": {"model": {"provider": "openai", "id": "gpt-5-mini"}},
		},
	)
	assert create_response.status_code == 200
	tenant = create_response.json()["tenant"]

	# Simula el flujo CLI: el YAML del workspace cambia en disco sin pasar por
	# update_workspace_config del runtime.
	workspace_store.write_config(
		tenant["slug"],
		{"model": {"provider": "aws_bedrock_claude", "id": "us.anthropic.claude-sonnet-4-6"}},
	)

	reload_response = client.post(f"/tenants/{tenant['slug']}/reload")
	assert reload_response.status_code == 200
	assert reload_response.json()["tenant"]["workspace_config"]["model"] == {
		"provider": "aws_bedrock_claude",
		"id": "us.anthropic.claude-sonnet-4-6",
	}

	workspace_response = client.get(f"/tenants/{tenant['slug']}/workspace")
	assert workspace_response.status_code == 200
	assert workspace_response.json()["tenant"]["workspace_config"]["model"] == {
		"provider": "aws_bedrock_claude",
		"id": "us.anthropic.claude-sonnet-4-6",
	}


def test_workspace_inventory_actions_reflect_created_runtime_after_reload(tmp_path: Path):
	store = TenantStore(f"sqlite:///{tmp_path / 'tenant-inventory.db'}")
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")
	tenant_loader = _FakeTenantLoader(workspace_store)

	app = FastAPI()
	app.include_router(
		create_tenant_router(
			store,
			workspace_store,
			{},
			tenant_loader=tenant_loader,
		)
	)
	client = TestClient(app)

	create_response = client.post(
		"/tenants/",
		json={
			"name": "Inventory Org",
			"workspace_config": {
				"agent": {"name": "Inventory Bot", "id": "inventory-main"},
			},
		},
	)
	assert create_response.status_code == 200
	tenant = create_response.json()["tenant"]

	sub_agent_response = client.post(
		f"/tenants/{tenant['slug']}/workspace/sub-agents",
		json={
			"name": "Sales Agent",
			"agent_id": "sales-agent",
			"role": "ventas",
			"tools": [],
			"instructions": ["Ayuda con ventas."],
		},
	)
	assert sub_agent_response.status_code == 200

	team_response = client.post(
		f"/tenants/{tenant['slug']}/workspace/teams",
		json={
			"team_id": "sales-team",
			"name": "Sales Team",
			"mode": "coordinate",
			"members": ["inventory-main", "sales-agent"],
		},
	)
	assert team_response.status_code == 200

	reload_response = client.post(f"/tenants/{tenant['slug']}/reload")
	assert reload_response.status_code == 200
	assert tenant_loader.reload_calls == [tenant["slug"]]

	inventory_response = client.get(f"/tenants/{tenant['slug']}/workspace/inventory")
	assert inventory_response.status_code == 200
	inventory = inventory_response.json()["inventory"]

	assert inventory["tenant_slug"] == tenant["slug"]
	assert inventory["main_agent"]["id"] == "inventory-main"
	assert [
		{
			"id": entry["id"],
			"enabled": entry["enabled"],
			"runtime_loaded": entry["runtime_loaded"],
		}
		for entry in inventory["sub_agents"]
	] == [{"id": "sales-agent", "enabled": True, "runtime_loaded": True}]
	assert [
		{
			"id": entry["id"],
			"enabled": entry["enabled"],
			"runtime_loaded": entry["runtime_loaded"],
			"members": entry["members"],
		}
		for entry in inventory["teams"]
	] == [
		{
			"id": "sales-team",
			"enabled": True,
			"runtime_loaded": True,
			"members": ["inventory-main", "sales-agent"],
		}
	]


def test_collection_routes_fail_fast_when_storage_is_unavailable(tmp_path: Path):
	workspace_store = WorkspaceStore(base_dir=tmp_path / "tenant-workspaces")

	class _BrokenStore:
		def list_tenants(self, *, active_only: bool = False):
			raise OperationalError("select 1", {}, RuntimeError("db unavailable"))

	app = FastAPI()
	app.include_router(create_tenant_router(_BrokenStore(), workspace_store, {}))
	client = TestClient(app)

	response = client.get("/tenants")
	assert response.status_code == 503
	assert response.json()["detail"] == "Tenant storage unavailable"
