"""Tests for tenant provisioning API routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
