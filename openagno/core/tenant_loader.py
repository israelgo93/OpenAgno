"""Tenant-aware workspace loader with LRU cache.

This module implements the "Fase A" multi-tenancy strategy described in
`OpenAgnoCloud/docs/PLAN_MULTITENANCY_2026-04-21.md`.

Each tenant has its own workspace directory on disk (managed by
`WorkspaceStore`). This loader lazily builds the Agno `Agent` + friends from
that directory and caches the result in an LRU map so subsequent requests
for the same tenant reuse the already-constructed agent.

Design notes:

- The "default" tenant maps to the process-wide workspace loaded by
  `gateway.py` at startup. To avoid duplicate model objects and double DB
  connections, the gateway injects the pre-built bundle through
  `TenantLoader.set_default_bundle`. Subsequent `get_or_load("default")`
  calls return that bundle without reading the disk again.
- The cache is bounded by `max_size`. When it is full, the least recently
  used tenant bundle is evicted. The underlying Agno `db` connection is
  shared (same Postgres URL) so eviction is cheap: we just drop the
  reference and let garbage collection handle it.
- Tests can pass a fake `workspace_store` to exercise the loader without
  touching the filesystem.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

from agno.utils.log import logger

from openagno.core.tenant import DEFAULT_TENANT, normalize_tenant_id
from openagno.core.workspace_store import WorkspaceStore


WorkspaceBundleLoader = Callable[[Path], dict[str, Any]]


class TenantLoader:
	"""LRU-cached loader of per-tenant workspace bundles."""

	def __init__(
		self,
		workspace_store: WorkspaceStore,
		*,
		default_bundle: dict[str, Any] | None = None,
		max_size: int = 32,
		bundle_loader: WorkspaceBundleLoader | None = None,
	):
		if max_size < 1:
			raise ValueError("max_size must be >= 1")
		self._workspace_store = workspace_store
		self._default_bundle = default_bundle
		self._max_size = max_size
		self._bundle_loader = bundle_loader or _default_bundle_loader
		self._cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
		self._lock = threading.RLock()
		self._hits = 0
		self._misses = 0
		self._loads = 0
		self._evictions = 0

	# -- Public API ----------------------------------------------------------

	def set_default_bundle(self, bundle: dict[str, Any] | None) -> None:
		"""Register the pre-built operator workspace as the "default" tenant."""
		self._default_bundle = bundle

	@property
	def default_bundle(self) -> dict[str, Any] | None:
		return self._default_bundle

	def get_or_load(self, slug: str | None) -> dict[str, Any]:
		"""Return the workspace bundle for ``slug`` (loading on first hit)."""
		normalized = normalize_tenant_id(slug)
		if normalized == DEFAULT_TENANT:
			if self._default_bundle is None:
				raise LookupError(
					"default workspace bundle has not been registered; "
					"gateway.py must call TenantLoader.set_default_bundle()"
				)
			with self._lock:
				self._hits += 1
			return self._default_bundle

		with self._lock:
			cached = self._cache.get(normalized)
			if cached is not None:
				self._cache.move_to_end(normalized)
				self._hits += 1
				return cached
			self._misses += 1

		# Heavy work outside the lock: building the Agno graph does I/O and
		# network calls (pgvector, MCP stdio spawns, etc.).
		bundle = self._load_bundle(normalized)

		with self._lock:
			existing = self._cache.get(normalized)
			if existing is not None:
				# Another thread beat us to it. Prefer the cached copy to
				# keep references consistent.
				self._cache.move_to_end(normalized)
				return existing
			self._cache[normalized] = bundle
			self._cache.move_to_end(normalized)
			self._loads += 1
			if len(self._cache) > self._max_size:
				evicted_slug, _evicted_bundle = self._cache.popitem(last=False)
				self._evictions += 1
				logger.info(
					f"TenantLoader evicted '{evicted_slug}' (cache size {len(self._cache)}/{self._max_size})"
				)
		return bundle

	def reload(self, slug: str | None) -> bool:
		"""Drop the cached bundle for ``slug``. Returns True if something was evicted."""
		normalized = normalize_tenant_id(slug)
		if normalized == DEFAULT_TENANT:
			# The default bundle is owned by gateway.py; reload is a no-op.
			return False
		with self._lock:
			return self._cache.pop(normalized, None) is not None

	def reload_all(self) -> int:
		"""Clear every non-default cached bundle. Returns how many were dropped."""
		with self._lock:
			count = len(self._cache)
			self._cache.clear()
			return count

	def stats(self) -> dict[str, Any]:
		with self._lock:
			loaded_tenants = [DEFAULT_TENANT] if self._default_bundle else []
			loaded_tenants.extend(self._cache.keys())
			return {
				"hits": self._hits,
				"misses": self._misses,
				"loads": self._loads,
				"evictions": self._evictions,
				"size": len(self._cache),
				"max_size": self._max_size,
				"default_loaded": self._default_bundle is not None,
				"loaded_tenants": loaded_tenants,
			}

	def get_agent(self, slug: str | None):
		"""Shorthand: returns the tenant's main agent object."""
		bundle = self.get_or_load(slug)
		return bundle["main_agent"]

	# -- Internals -----------------------------------------------------------

	def _load_bundle(self, normalized_slug: str) -> dict[str, Any]:
		workspace_dir = Path(self._workspace_store.workspace_path(normalized_slug))
		if not workspace_dir.exists():
			raise LookupError(
				f"Workspace directory missing for tenant '{normalized_slug}': {workspace_dir}"
			)
		logger.info(f"TenantLoader cargando workspace '{normalized_slug}' desde {workspace_dir}")
		return self._bundle_loader(workspace_dir)


def _default_bundle_loader(workspace_dir: Path) -> dict[str, Any]:
	# Imported lazily to avoid a circular import at module load time.
	from loader import load_workspace_from_dir  # type: ignore

	return load_workspace_from_dir(workspace_dir)
