"""Tenant provisioning and tenant-aware agent execution routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from openagno.core.tenant import TenantStore, build_tenant_knowledge_filters, scope_identity
from openagno.core.workspace_store import WorkspaceStore
from security import verify_api_key


class TenantCreateRequest(BaseModel):
	name: str
	slug: str | None = None
	plan: str = "free"
	template: str = "personal_assistant"
	workspace_config: dict[str, Any] = Field(default_factory=dict)
	max_agents: int = 1
	max_messages_per_day: int = 100


class TenantUpdateRequest(BaseModel):
	name: str | None = None
	slug: str | None = None
	plan: str | None = None
	active: bool | None = None
	workspace_config: dict[str, Any] | None = None
	max_agents: int | None = None
	max_messages_per_day: int | None = None


class TenantRunRequest(BaseModel):
	message: str
	user_id: str | None = None
	session_id: str | None = None
	knowledge_filters: dict[str, Any] = Field(default_factory=dict)
	metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceConfigRequest(BaseModel):
	config: dict[str, Any]


def _extract_response_content(response: Any) -> str | None:
	if response is None:
		return None
	content = getattr(response, "content", None)
	if content is not None:
		return str(content)
	return None


def create_tenant_router(
	tenant_store: TenantStore,
	workspace_store: WorkspaceStore,
	agents_by_id: dict[str, Any],
) -> APIRouter:
	router = APIRouter(prefix="/tenants", tags=["tenants"], dependencies=[Depends(verify_api_key)])

	@router.get("/")
	async def list_tenants(active_only: bool = False) -> dict[str, Any]:
		tenants = tenant_store.list_tenants(active_only=active_only)
		return {"tenants": [tenant.to_dict() for tenant in tenants], "count": len(tenants)}

	@router.post("/")
	async def create_tenant(payload: TenantCreateRequest) -> dict[str, Any]:
		try:
			tenant = tenant_store.create_tenant(
				name=payload.name,
				slug=payload.slug,
				plan=payload.plan,
				workspace_config=payload.workspace_config,
				max_agents=payload.max_agents,
				max_messages_per_day=payload.max_messages_per_day,
			)
		except ValueError as exc:
			raise HTTPException(status_code=409, detail=str(exc)) from exc

		workspace_path = workspace_store.provision(
			tenant.slug,
			template=payload.template,
			workspace_config=payload.workspace_config,
		)
		return {
			"tenant": tenant.to_dict(),
			"workspace_path": str(workspace_path),
			"workspace_backend": workspace_store.backend,
		}

	@router.get("/{tenant_id}")
	async def get_tenant(tenant_id: str) -> dict[str, Any]:
		tenant = tenant_store.get_tenant(tenant_id)
		if tenant is None:
			raise HTTPException(status_code=404, detail="Tenant not found")
		return {"tenant": tenant.to_dict()}

	@router.patch("/{tenant_id}")
	async def update_tenant(tenant_id: str, payload: TenantUpdateRequest) -> dict[str, Any]:
		try:
			tenant = tenant_store.update_tenant(tenant_id, **payload.model_dump(exclude_none=True))
		except KeyError as exc:
			raise HTTPException(status_code=404, detail="Tenant not found") from exc
		except ValueError as exc:
			raise HTTPException(status_code=409, detail=str(exc)) from exc

		if payload.workspace_config:
			workspace_store.write_config(tenant.slug, payload.workspace_config)
		return {"tenant": tenant.to_dict()}

	@router.delete("/{tenant_id}")
	async def deactivate_tenant(tenant_id: str) -> dict[str, Any]:
		try:
			tenant = tenant_store.deactivate_tenant(tenant_id)
		except KeyError as exc:
			raise HTTPException(status_code=404, detail="Tenant not found") from exc
		return {"tenant": tenant.to_dict(), "status": "deactivated"}

	@router.get("/{tenant_id}/workspace")
	async def get_workspace_config(tenant_id: str) -> dict[str, Any]:
		tenant = tenant_store.get_tenant(tenant_id)
		if tenant is None:
			raise HTTPException(status_code=404, detail="Tenant not found")
		return {
			"tenant": tenant.to_dict(),
			"backend": workspace_store.backend,
			"path": str(workspace_store.workspace_path(tenant.slug)),
			"config": workspace_store.read_config(tenant.slug),
		}

	@router.put("/{tenant_id}/workspace")
	async def update_workspace_config(tenant_id: str, payload: WorkspaceConfigRequest) -> dict[str, Any]:
		tenant = tenant_store.get_tenant(tenant_id)
		if tenant is None:
			raise HTTPException(status_code=404, detail="Tenant not found")
		config = workspace_store.write_config(tenant.slug, payload.config)
		tenant = tenant_store.update_tenant(tenant.id, workspace_config=config)
		return {"tenant": tenant.to_dict(), "config": config}

	@router.post("/{tenant_id}/agents/{agent_id}/runs")
	async def run_agent_for_tenant(tenant_id: str, agent_id: str, payload: TenantRunRequest) -> dict[str, Any]:
		tenant = tenant_store.get_tenant(tenant_id)
		if tenant is None:
			raise HTTPException(status_code=404, detail="Tenant not found")
		if not tenant.active:
			raise HTTPException(status_code=409, detail="Tenant is inactive")

		agent = agents_by_id.get(agent_id)
		if agent is None:
			raise HTTPException(status_code=404, detail="Agent not found")

		knowledge_filters = payload.knowledge_filters.copy()
		knowledge_filters.update(build_tenant_knowledge_filters(tenant.slug) or {})
		metadata = payload.metadata.copy()
		metadata.setdefault("tenant_id", tenant.id)
		metadata.setdefault("tenant_slug", tenant.slug)

		response = await agent.arun(
			payload.message,
			user_id=scope_identity(tenant.slug, payload.user_id, fallback="user"),
			session_id=scope_identity(tenant.slug, payload.session_id, fallback="session"),
			knowledge_filters=knowledge_filters,
			metadata=metadata,
		)
		return {
			"tenant": tenant.to_dict(),
			"agent_id": agent_id,
			"content": _extract_response_content(response),
			"knowledge_filters": knowledge_filters,
		}

	return router
