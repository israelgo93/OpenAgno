"""Tests for tenant storage and Agno-native tenant helpers."""

from pathlib import Path

from agno.knowledge.knowledge import Knowledge

from openagno.core.tenant import (
	TenantStore,
	build_tenant_knowledge_filters,
	get_tenant_scoped_knowledge,
	scope_identity,
	slugify_tenant,
)


class _FakeVectorDb:
	def exists(self):
		return True

	def create(self):
		return None


def test_slugify_tenant():
	assert slugify_tenant("Acme Corp") == "acme-corp"
	assert slugify_tenant("  ") == "default"


def test_scope_identity_prefixes_tenant():
	assert scope_identity("acme", "demo", fallback="user") == "acme:demo"
	assert scope_identity("Acme Corp", None, fallback="session") == "acme-corp:session"


def test_build_tenant_knowledge_filters_uses_linked_to():
	assert build_tenant_knowledge_filters("acme") == {"linked_to": "acme"}


def test_get_tenant_scoped_knowledge_returns_proxy():
	base = Knowledge(
		name=None,
		vector_db=_FakeVectorDb(),
		contents_db=None,
		max_results=7,
		isolate_vector_search=False,
	)

	scoped = get_tenant_scoped_knowledge(base, "acme")

	assert isinstance(scoped, Knowledge)
	assert scoped is not base
	assert scoped.name == "acme"
	assert scoped.isolate_vector_search is True
	assert scoped.max_results == 7


def test_tenant_store_crud(tmp_path: Path):
	db_url = f"sqlite:///{tmp_path / 'tenants.db'}"
	store = TenantStore(db_url)

	created = store.create_tenant(name="Acme Corp", workspace_config={"model": {"id": "demo"}})
	assert created.slug == "acme-corp"

	fetched = store.get_tenant(created.id)
	assert fetched is not None
	assert fetched.slug == "acme-corp"

	updated = store.update_tenant(created.id, plan="enterprise", max_agents=10)
	assert updated.plan == "enterprise"
	assert updated.max_agents == 10

	tenants = store.list_tenants()
	assert len(tenants) == 1

	deactivated = store.deactivate_tenant(created.id)
	assert deactivated.active is False
