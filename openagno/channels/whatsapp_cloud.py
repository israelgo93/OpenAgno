"""WhatsApp Cloud API multi-tenant router para el gateway.

Cada tenant expone su propio webhook en `/whatsapp-cloud/<tenant_id>/webhook`
con credenciales cifradas (AES-256-GCM) almacenadas en la tabla
`public.whatsapp_cloud_channels` de Supabase.

Decisiones:

- Usamos el UUID de `tenants.id` en el path (no el slug) porque la columna
  `webhook_path` en la migracion SQL esta definida como generated column a
  partir de ese UUID y es lo que mostramos al operador para pegar en Meta.
- El slug del runtime (`tenants.runtime_slug`) lo resolvemos con JOIN para
  invocar el TenantLoader del OSS, que opera sobre slugs de workspace.
- La clave maestra AES-256-GCM vive en la env var `CHANNEL_SECRETS_KEY`
  (32 bytes en base64). Debe ser identica en este runtime y en cualquier
  sistema externo que escriba las filas cifradas en Supabase.
- Reutilizamos la `DATABASE_URL` que ya construye el gateway para el bundle
  por defecto (misma conexion a Supabase que usa TenantStore).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
from agno.utils.log import logger
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response

from openagno.core.tenant import DEFAULT_TENANT, normalize_tenant_id


GRAPH_API_HOST = "https://graph.facebook.com"
CHANNEL_SECRETS_KEY_ENV = "CHANNEL_SECRETS_KEY"


@dataclass(frozen=True)
class WhatsAppCloudConfig:
	"""Credenciales descifradas + slug de runtime para un tenant."""

	tenant_id: str  # UUID del Cloud (tabla tenants)
	runtime_slug: str  # slug del workspace OSS
	phone_number_id: str
	waba_id: str | None
	graph_api_version: str
	access_token: str
	verify_token: str
	app_secret: str | None


class ConfigNotFoundError(LookupError):
	"""No hay credenciales Cloud API guardadas para ese tenant_id."""


def _load_key() -> bytes:
	raw = os.getenv(CHANNEL_SECRETS_KEY_ENV, "").strip()
	if not raw:
		raise RuntimeError(
			f"{CHANNEL_SECRETS_KEY_ENV} no esta definido en el entorno; "
			"se requiere la misma clave base64 que usa el sistema externo que escribe las filas cifradas."
		)
	decoded = base64.b64decode(raw)
	if len(decoded) != 32:
		raise RuntimeError(
			f"{CHANNEL_SECRETS_KEY_ENV} debe decodificar a 32 bytes (AES-256); "
			f"recibidos {len(decoded)}."
		)
	return decoded


def _decrypt(cipher_b64: str, nonce_b64: str) -> str:
	"""Descifra un secreto almacenado como cipher+nonce en base64.

	El `cipher` incluye el auth tag en los ultimos 16 bytes (convencion
	de Node `crypto.createCipheriv('aes-256-gcm')` y compatible con
	`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
	"""
	key = _load_key()
	nonce = base64.b64decode(nonce_b64)
	ct_with_tag = base64.b64decode(cipher_b64)
	aesgcm = AESGCM(key)
	plaintext = aesgcm.decrypt(nonce, ct_with_tag, associated_data=None)
	return plaintext.decode("utf-8")


def _dsn_from_env() -> str:
	"""Construye un DSN postgres compatible con psycopg usando las vars del gateway."""
	# Preferencia: DATABASE_URL explicita (si el operador la definio).
	url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
	if url:
		return url
	host = os.getenv("DB_HOST")
	port = os.getenv("DB_PORT", "5432")
	user = os.getenv("DB_USER")
	password = os.getenv("DB_PASSWORD")
	name = os.getenv("DB_NAME", "postgres")
	sslmode = os.getenv("DB_SSLMODE", "require")
	if not (host and user and password):
		raise RuntimeError("Falta configuracion de DB (DB_HOST/DB_USER/DB_PASSWORD) para WhatsApp Cloud API")
	return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"


def load_cloud_config(tenant_id: str) -> WhatsAppCloudConfig:
	"""Carga y descifra la config Cloud API para un `tenants.id` UUID."""
	dsn = _dsn_from_env()
	query = """
		SELECT
			w.tenant_id::text,
			w.phone_number_id,
			w.waba_id,
			w.graph_api_version,
			w.access_token_cipher, w.access_token_nonce,
			w.verify_token_cipher, w.verify_token_nonce,
			w.app_secret_cipher, w.app_secret_nonce,
			t.runtime_slug
		FROM public.whatsapp_cloud_channels w
		JOIN public.tenants t ON t.id = w.tenant_id
		WHERE w.tenant_id = %s
		LIMIT 1
	"""
	with psycopg.connect(dsn, connect_timeout=5) as conn:
		with conn.cursor() as cur:
			cur.execute(query, (tenant_id,))
			row = cur.fetchone()
	if row is None:
		raise ConfigNotFoundError(f"whatsapp_cloud_channels: no hay config para tenant_id={tenant_id}")

	(
		tenant_id_s,
		phone_number_id,
		waba_id,
		graph_api_version,
		access_token_cipher,
		access_token_nonce,
		verify_token_cipher,
		verify_token_nonce,
		app_secret_cipher,
		app_secret_nonce,
		runtime_slug,
	) = row

	access_token = _decrypt(access_token_cipher, access_token_nonce)
	verify_token = _decrypt(verify_token_cipher, verify_token_nonce)
	app_secret: str | None = None
	if app_secret_cipher and app_secret_nonce:
		app_secret = _decrypt(app_secret_cipher, app_secret_nonce)

	return WhatsAppCloudConfig(
		tenant_id=tenant_id_s,
		runtime_slug=runtime_slug or DEFAULT_TENANT,
		phone_number_id=phone_number_id,
		waba_id=waba_id,
		graph_api_version=graph_api_version or "v21.0",
		access_token=access_token,
		verify_token=verify_token,
		app_secret=app_secret,
	)


def _touch_column(tenant_id: str, column: str, error: str | None = None) -> None:
	"""Actualiza timestamp de auditoria (verified_at, last_event_at, last_send_at).

	`column` se hardcodea desde call sites; nunca viene de input de usuario.
	"""
	assert column in ("verified_at", "last_event_at", "last_send_at"), column
	dsn = _dsn_from_env()
	if error:
		sql = f"UPDATE public.whatsapp_cloud_channels SET {column} = now(), last_error = %s WHERE tenant_id = %s"
		params: tuple[Any, ...] = (error[:500], tenant_id)
	else:
		sql = f"UPDATE public.whatsapp_cloud_channels SET {column} = now(), last_error = NULL WHERE tenant_id = %s"
		params = (tenant_id,)
	try:
		with psycopg.connect(dsn, connect_timeout=5) as conn:
			with conn.cursor() as cur:
				cur.execute(sql, params)
	except Exception as exc:  # noqa: BLE001 - no queremos que un update de telemetria tire el webhook
		logger.warning(f"whatsapp-cloud: no pude actualizar {column} para {tenant_id}: {exc}")


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
	"""Valida el header X-Hub-Signature-256 que Meta envia al webhook."""
	if not signature_header:
		return False
	expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected.lower(), signature_header.lower().strip())


async def send_text(cfg: WhatsAppCloudConfig, to: str, text: str) -> dict[str, Any]:
	"""Envia un mensaje de texto via Graph API y devuelve el JSON de Meta."""
	url = f"{GRAPH_API_HOST}/{cfg.graph_api_version}/{cfg.phone_number_id}/messages"
	payload = {
		"messaging_product": "whatsapp",
		"to": to,
		"type": "text",
		"text": {"body": text},
	}
	async with httpx.AsyncClient(timeout=20) as client:
		resp = await client.post(
			url,
			json=payload,
			headers={
				"Authorization": f"Bearer {cfg.access_token}",
				"Content-Type": "application/json",
			},
		)
	if resp.status_code >= 400:
		raise RuntimeError(f"graph_api_{resp.status_code}: {resp.text[:300]}")
	return resp.json()


def _extract_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
	"""Extrae mensajes 'text' del payload estandar de Meta.

	Ignora statuses (delivered/read), reactions y otros tipos no conversacionales.
	Retorna una lista de dicts con keys: from, text, id.
	"""
	entries = payload.get("entry") or []
	result: list[dict[str, Any]] = []
	for entry in entries:
		changes = entry.get("changes") or []
		for change in changes:
			value = change.get("value") or {}
			messages = value.get("messages") or []
			for msg in messages:
				if msg.get("type") != "text":
					continue
				text = (msg.get("text") or {}).get("body") or ""
				if not text:
					continue
				result.append(
					{
						"id": msg.get("id", ""),
						"from": msg.get("from", ""),
						"text": text,
					}
				)
	return result


def create_router(*, get_tenant_loader: Any) -> APIRouter:
	"""Construye el router `/whatsapp-cloud/*` inyectando el TenantLoader.

	`get_tenant_loader` es un callable `() -> TenantLoader` para no acoplarnos
	al estado de FastAPI en el momento de import.
	"""
	router = APIRouter()

	@router.get("/whatsapp-cloud/{tenant_id}/webhook")
	async def verify_webhook(
		tenant_id: str,
		mode: str = Query(..., alias="hub.mode"),
		verify_token: str = Query(..., alias="hub.verify_token"),
		challenge: str = Query(..., alias="hub.challenge"),
	):
		if mode != "subscribe":
			raise HTTPException(status_code=403, detail="invalid_hub_mode")
		try:
			cfg = load_cloud_config(tenant_id)
		except ConfigNotFoundError:
			raise HTTPException(status_code=404, detail="tenant_not_configured")
		if not hmac.compare_digest(cfg.verify_token, verify_token):
			raise HTTPException(status_code=403, detail="invalid_verify_token")
		_touch_column(tenant_id, "verified_at")
		# Meta espera el challenge como texto plano (numerico).
		return Response(content=challenge, media_type="text/plain")

	@router.post("/whatsapp-cloud/{tenant_id}/webhook")
	async def receive_webhook(tenant_id: str, request: Request):
		try:
			cfg = load_cloud_config(tenant_id)
		except ConfigNotFoundError:
			raise HTTPException(status_code=404, detail="tenant_not_configured")

		body = await request.body()
		if cfg.app_secret:
			signature = request.headers.get("x-hub-signature-256")
			if not verify_signature(cfg.app_secret, body, signature):
				_touch_column(tenant_id, "last_event_at", error="invalid_signature")
				raise HTTPException(status_code=401, detail="invalid_signature")

		try:
			payload = json.loads(body or b"{}")
		except json.JSONDecodeError:
			raise HTTPException(status_code=400, detail="invalid_json")

		if payload.get("object") != "whatsapp_business_account":
			# Meta envia el webhook generico compartido; ignoramos otros objetos.
			_touch_column(tenant_id, "last_event_at")
			return {"status": "ignored_non_wa"}

		messages = _extract_messages(payload)
		if not messages:
			_touch_column(tenant_id, "last_event_at")
			return {"status": "no_messages"}

		tenant_loader = get_tenant_loader()
		runtime_slug = normalize_tenant_id(cfg.runtime_slug)

		try:
			bundle = tenant_loader.get_or_load(runtime_slug)
		except LookupError as exc:
			logger.error(f"[{runtime_slug}] whatsapp-cloud: no se pudo cargar workspace: {exc}")
			_touch_column(tenant_id, "last_event_at", error=f"workspace_missing:{exc}")
			raise HTTPException(status_code=500, detail="tenant_workspace_missing")

		agent = bundle["main_agent"]
		responses_sent = 0
		last_send_error: str | None = None

		for message in messages:
			from_jid = message["from"]
			text = message["text"]
			logger.info(
				f"[{runtime_slug}] whatsapp-cloud: mensaje de {from_jid}: {text[:80]}"
			)
			try:
				result = await asyncio.to_thread(
					agent.run, text, user_id=from_jid, stream=False
				)
				reply_text = (getattr(result, "content", None) or str(result) or "").strip()
			except Exception as exc:  # noqa: BLE001
				logger.error(f"[{runtime_slug}] whatsapp-cloud: agente fallo: {exc}")
				last_send_error = f"agent_error:{exc}"
				continue
			if not reply_text:
				continue
			try:
				await send_text(cfg, from_jid, reply_text)
				responses_sent += 1
				_touch_column(tenant_id, "last_send_at")
			except Exception as exc:  # noqa: BLE001
				logger.error(
					f"[{runtime_slug}] whatsapp-cloud: send_text fallo a {from_jid}: {exc}"
				)
				last_send_error = f"send_failed:{exc}"

		_touch_column(tenant_id, "last_event_at", error=last_send_error)
		return {
			"status": "ok",
			"received": len(messages),
			"sent": responses_sent,
			"last_error": last_send_error,
		}

	return router


def mount_on(app: FastAPI) -> None:
	"""Monta el router en el FastAPI app del gateway usando `app.state.tenant_loader`."""
	router = create_router(get_tenant_loader=lambda: app.state.tenant_loader)
	app.include_router(router)
	logger.info("WhatsApp Cloud API multi-tenant montado en /whatsapp-cloud/{tenant_id}/webhook")
