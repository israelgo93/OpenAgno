"""Helpers to reconcile tenant metadata with workspace files written by the CLI."""

from __future__ import annotations

from openagno.core.tenant import Tenant, TenantStore
from openagno.core.workspace_store import WorkspaceStore


def sync_tenant_workspace_config(
	tenant_store: TenantStore,
	workspace_store: WorkspaceStore,
	identifier: str,
) -> tuple[Tenant | None, bool]:
	"""Sync `Tenant.workspace_config` from `workspaces/<slug>/workspace/config.yaml`.

	The OSS CLI edits tenant workspaces directly on disk. The runtime loader reads
	those files correctly, but the persisted tenant metadata can lag behind until a
	route explicitly updates it. This helper keeps both copies aligned without
	overwriting tenants that do not yet have a workspace config on disk.
	"""
	tenant = tenant_store.get_tenant(identifier)
	if tenant is None:
		return None, False

	config_path = workspace_store.workspace_path(tenant.slug) / "config.yaml"
	if not config_path.exists():
		return tenant, False

	disk_config = workspace_store.read_config(tenant.slug)
	if tenant.workspace_config == disk_config:
		return tenant, False

	updated = tenant_store.update_tenant(tenant.id, workspace_config=disk_config)
	return updated, True


def sync_all_tenant_workspace_configs(
	tenant_store: TenantStore,
	workspace_store: WorkspaceStore,
) -> list[tuple[str, bool]]:
	"""Best-effort reconciliation for every tenant known by the runtime."""
	results: list[tuple[str, bool]] = []
	for tenant in tenant_store.list_tenants():
		updated_tenant, synced = sync_tenant_workspace_config(
			tenant_store,
			workspace_store,
			tenant.id,
		)
		results.append(((updated_tenant or tenant).slug, synced))
	return results
