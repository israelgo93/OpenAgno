"""Tenant detection middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from openagno.core.tenant import normalize_tenant_id


class TenantMiddleware(BaseHTTPMiddleware):
	"""Attach a normalized tenant identifier to each request."""

	async def dispatch(self, request: Request, call_next):
		tenant_id = (
			request.headers.get("X-Tenant-ID")
			or request.query_params.get("tenant_id")
			or request.path_params.get("tenant_id")
			or "default"
		)
		request.state.tenant_id = normalize_tenant_id(tenant_id)
		return await call_next(request)
