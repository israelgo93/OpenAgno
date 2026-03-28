"""
AgnoBot Gateway - Punto de entrada principal.
Lee el workspace/ y construye el AgentOS completo.

Fase 8: Produccion, Tools Expandidos, Studio Completo y WhatsApp Dual.
"""
import warnings
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")
warnings.filterwarnings("ignore", category=DeprecationWarning)

import inspect
import os
import time
import hmac
import hashlib
from datetime import datetime
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agno.os import AgentOS
from agno.os.interfaces.whatsapp.security import validate_webhook_signature
from agno.registry import Registry
from agno.utils.log import logger

from loader import load_workspace, is_rate_limit_error, NON_AUDIO_PROVIDERS
from management.validator import print_validation, validate_workspace, workspace_warnings
from openagno.core.dedup import MessageDeduplicator
from openagno.core.tenant import TenantStore
from openagno.core.tenant_middleware import TenantMiddleware
from openagno.core.workspace_store import WorkspaceStore
from openagno import __version__

validation_errors = validate_workspace()
if validation_errors:
	print_validation(validation_errors)
	logger.warning(f"Workspace tiene {len(validation_errors)} advertencia(s)")
for _w in workspace_warnings():
	logger.warning(_w)

ws = load_workspace()
config = ws["config"]
db = ws["db"]
main_agent = ws["main_agent"]
fallback_model = ws.get("fallback_model")
sub_agents = ws["sub_agents"]
teams = ws["teams"]
knowledge = ws["knowledge"]
schedules = ws["schedules"]
knowledge_doc_paths = ws["knowledge_doc_paths"]
knowledge_urls = ws["knowledge_urls"]

_wa_cloud_dedup = MessageDeduplicator(ttl=300, max_size=4096)
_wa_qr_dedup = MessageDeduplicator(ttl=120, max_size=4096)
limiter = Limiter(key_func=get_remote_address)

if fallback_model:
	_original_model = main_agent.model
	_using_fallback = False
	_fallback_until: float = 0.0
	FALLBACK_COOLDOWN = int(os.getenv("FALLBACK_COOLDOWN_SECONDS", "60"))

	def _swap_to_fallback() -> None:
		"""Cambia el agente principal al modelo fallback (manual o automatico)."""
		global _using_fallback, _fallback_until
		if not _using_fallback and fallback_model:
			main_agent.model = fallback_model
			_using_fallback = True
			_fallback_until = time.time() + FALLBACK_COOLDOWN
			logger.warning(
				f"FALLBACK activado: {fallback_model.id} "
				f"(cooldown {FALLBACK_COOLDOWN}s)"
			)

	def _swap_to_primary() -> None:
		"""Restaura el modelo principal."""
		global _using_fallback, _fallback_until
		if _using_fallback:
			main_agent.model = _original_model
			_using_fallback = False
			_fallback_until = 0.0
			logger.info(f"Modelo principal restaurado: {_original_model.id}")

	def _maybe_restore_primary() -> None:
		"""Restaura el modelo primario si paso el cooldown."""
		if _using_fallback and time.time() > _fallback_until:
			_swap_to_primary()

	def _on_rate_limit_error(error: Exception) -> None:
		"""Callback para activar fallback automaticamente ante rate-limit."""
		if is_rate_limit_error(error):
			logger.warning(f"Rate-limit detectado: {error}")
			_swap_to_fallback()

	logger.info(
		f"Fallback disponible: {fallback_model.id} "
		f"(cooldown: {FALLBACK_COOLDOWN}s, auto-deteccion: ON)"
	)


# Default: arun sin wrapper (se sobreescribe si hay STT/TTS/Fallback)
_qr_agent_arun = main_agent.arun

# === Wrapper inteligente de arun: STT + TTS + Fallback automatico ===
audio_config = config.get("audio", {})
model_provider = config.get("model", {}).get("provider", "google")
_needs_stt = audio_config.get("auto_transcribe", False) and model_provider in NON_AUDIO_PROVIDERS
_needs_tts = audio_config.get("tts_enabled", False) and model_provider in NON_AUDIO_PROVIDERS

if _needs_stt or _needs_tts or fallback_model:
	import tempfile
	from agno.media import Audio as AgnoAudio
	from tools.audio_tools import AudioTools

	_audio_tools: AudioTools | None = None
	if _needs_stt or _needs_tts:
		_audio_tools = AudioTools(
			stt_model=audio_config.get("stt_model", "whisper-1"),
			tts_model=audio_config.get("tts_model", "gpt-4o-mini-tts"),
			tts_voice=audio_config.get("tts_voice", "nova"),
			tts_enabled=_needs_tts,
			auto_transcribe=_needs_stt,
		)

	_original_arun = main_agent.arun

	def _transcribe_audio_objects(audio_list: list) -> str:
		"""Transcribe una lista de objetos Audio y retorna el texto combinado."""
		if not _audio_tools:
			return "[Audio no procesable: AudioTools no configurado]"
		transcriptions: list[str] = []
		for audio_obj in audio_list:
			try:
				suffix = ".ogg"
				if hasattr(audio_obj, "mime_type") and audio_obj.mime_type:
					mime_to_ext = {
						"audio/ogg": ".ogg", "audio/mpeg": ".mp3",
						"audio/mp4": ".m4a", "audio/wav": ".wav",
						"audio/amr": ".amr", "audio/aac": ".aac",
					}
					suffix = mime_to_ext.get(audio_obj.mime_type, ".ogg")

				content = getattr(audio_obj, "content", None)
				filepath = getattr(audio_obj, "filepath", None)

				if content:
					tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
					tmp.write(content)
					tmp.close()
					text = _audio_tools.transcribe_audio(tmp.name)
					os.unlink(tmp.name)
				elif filepath:
					text = _audio_tools.transcribe_audio(str(filepath))
				else:
					text = "[Audio recibido pero no se pudo procesar]"

				if text and not text.startswith("Error"):
					transcriptions.append(text)
					logger.info(f"STT transcrito: {len(text)} chars")
				else:
					transcriptions.append("[No se pudo transcribir el audio]")
			except Exception as e:
				logger.error(f"Error transcribiendo audio: {e}")
				transcriptions.append(f"[Error al transcribir audio: {e}]")
		return "\n".join(transcriptions)

	def _attach_tts_to_response(response):
		"""Genera TTS del texto de respuesta y lo adjunta como response_audio."""
		if not _audio_tools or not _needs_tts:
			return response
		try:
			text = getattr(response, "content", None)
			if not text or not isinstance(text, str) or len(text.strip()) < 5:
				return response

			# Limitar texto TTS a 4000 chars para evitar timeout
			tts_text = text[:4000]
			audio_bytes, mime = _audio_tools.generate_tts_bytes(tts_text)
			if audio_bytes:
				response.response_audio = AgnoAudio(
					content=audio_bytes,
					mime_type=mime,
					format="mp3",
				)
				logger.info(f"TTS adjuntado a respuesta: {len(audio_bytes)} bytes")
		except Exception as e:
			logger.error(f"Error adjuntando TTS a respuesta: {e}")
		return response

	async def _arun_wrapped(input="", **kwargs):
		"""Wrapper completo de arun: STT entrada + fallback + TTS salida."""
		# 0. Validar mensajes vacios (F7 — 7.3)
		audio_list = kwargs.get("audio", None) or []
		image_list = kwargs.get("images", None) or []
		message_text = input if isinstance(input, str) else ""

		if not message_text or not message_text.strip():
			if audio_list:
				# Se procesará via STT abajo
				input = "[Audio recibido]"
			elif image_list:
				input = "[Imagen recibida]"
			else:
				logger.warning("Mensaje vacio descartado")
				return None  # No procesar mensajes vacios

		# 1. STT: transcribir audio si el modelo no soporta audio nativo
		if _needs_stt:
			audio_list = kwargs.pop("audio", None) or []
			if audio_list:
				transcription = _transcribe_audio_objects(audio_list)
				prefix = "[Transcripcion de audio del usuario]:\n"
				if isinstance(input, str):
					input = prefix + transcription + ("\n\n" + input if input else "")
				else:
					input = prefix + transcription
				logger.info(f"Audio reemplazado por transcripcion para {model_provider}")

		# 2. Restaurar modelo primario si paso el cooldown
		if fallback_model:
			_maybe_restore_primary()

		# 3. Ejecutar con retry/fallback ante rate-limit (F7 — 7.2 mejorado)
		try:
			response = await _original_arun(input, **kwargs)
		except Exception as exc:
			if fallback_model and is_rate_limit_error(exc):
				logger.warning(f"Rate-limit en modelo primario: {exc}")
				_swap_to_fallback()
				# Reintentar con modelo fallback
				try:
					response = await _original_arun(input, **kwargs)
				except Exception as exc2:
					logger.error(f"Tambien fallo el fallback: {exc2}")
					raise
			elif is_rate_limit_error(exc):
				# Sin fallback configurado, pero es rate-limit
				logger.error(f"Rate-limit sin fallback disponible: {exc}")
				raise
			else:
				# F7 — 7.5: detectar 401 WhatsApp
				_check_wa_auth_error(exc)
				raise

		# 4. TTS: generar audio de la respuesta para enviar por WhatsApp
		if _needs_tts and response:
			response = _attach_tts_to_response(response)

		return response

	main_agent.arun = _arun_wrapped

	features = []
	if _needs_stt:
		features.append(f"STT:{audio_config.get('stt_model', 'whisper-1')}")
	if _needs_tts:
		features.append(f"TTS:{audio_config.get('tts_model', 'gpt-4o-mini-tts')}/{audio_config.get('tts_voice', 'nova')}")
	if fallback_model:
		features.append(f"Fallback:{fallback_model.id}")
	logger.info(f"Agent wrapper activado: [{', '.join(features)}]")

# Referencia para QR bridge: DESPUES del wrapper para que audio/images pasen por STT
_qr_agent_arun = main_agent.arun


async def _auto_ingest_knowledge() -> None:
	"""Ingesta automatica de documentos y URLs al arrancar."""
	if not knowledge:
		return

	knowledge_config = config.get("knowledge", {})

	if knowledge_config.get("auto_ingest_docs", True) and knowledge_doc_paths:
		logger.info(f"Auto-ingesta: {len(knowledge_doc_paths)} archivo(s) en knowledge/docs/")
		for doc_path in knowledge_doc_paths:
			try:
				knowledge.insert(
					path=str(doc_path),
					name=doc_path.name,
					skip_if_exists=True,
				)
				logger.info(f"  Ingestado: {doc_path.name}")
			except Exception as e:
				logger.warning(f"  Error ingestando {doc_path.name}: {e}")

	if knowledge_config.get("auto_ingest_urls", True) and knowledge_urls:
		logger.info(f"Auto-ingesta: {len(knowledge_urls)} URL(s) desde urls.yaml")
		for url_entry in knowledge_urls:
			url = url_entry.get("url", "")
			name = url_entry.get("name", url)
			if not url:
				continue
			try:
				knowledge.insert(
					url=url,
					name=name,
					skip_if_exists=True,
				)
				logger.info(f"  Ingestado URL: {name}")
			except Exception as e:
				logger.warning(f"  Error ingestando URL {name}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
	await _auto_ingest_knowledge()
	yield


def _setup_whatsapp_qr_routes(app: FastAPI, agent, bridge_url: str):
	"""Monta rutas para WhatsApp QR bridge (DAT-240)."""
	import httpx

	@app.get("/whatsapp-qr/status")
	async def wa_qr_status():
		"""Estado de la conexión QR."""
		try:
			async with httpx.AsyncClient() as client:
				resp = await client.get(f"{bridge_url}/status")
				return resp.json()
		except Exception as e:
			return {"status": "bridge_unreachable", "error": str(e)}

	@app.get("/whatsapp-qr/code")
	async def wa_qr_code():
		"""Pagina HTML con QR para escanear desde el navegador."""
		from fastapi.responses import HTMLResponse
		try:
			async with httpx.AsyncClient() as client:
				resp = await client.get(f"{bridge_url}/qr")
				data = resp.json()
			status = data.get("status", "unknown")
			qr_data = data.get("qr")
			if status == "connected":
				return HTMLResponse("<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
					"<h2>WhatsApp vinculado</h2><p>El dispositivo ya esta conectado.</p></body></html>")
			if not qr_data:
				return HTMLResponse("<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
					f"<h2>QR no disponible</h2><p>Estado: {status}</p>"
					"<p>Espera unos segundos y recarga la pagina.</p>"
					"<script>setTimeout(()=>location.reload(),5000)</script></body></html>")
			return HTMLResponse(
				"<html><body style='font-family:sans-serif;text-align:center;padding:40px;background:#f5f5f5'>"
				"<h2>OpenAgno - WhatsApp QR</h2>"
				"<p>Escanea desde WhatsApp &gt; Dispositivos vinculados</p>"
				f"<img src='{qr_data}' style='width:300px;height:300px;border:8px solid white;border-radius:12px'/>"
				"<p style='color:#888;margin-top:16px'>El QR se actualiza automaticamente</p>"
				"<script>setTimeout(()=>location.reload(),30000)</script></body></html>"
			)
		except Exception as e:
			return HTMLResponse(f"<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
				f"<h2>Bridge no disponible</h2><p>{e}</p></body></html>", status_code=502)

	@app.get("/whatsapp-qr/code/json")
	async def wa_qr_code_json():
		"""QR como JSON (para integraciones programaticas)."""
		try:
			async with httpx.AsyncClient() as client:
				resp = await client.get(f"{bridge_url}/qr")
				return resp.json()
		except Exception as e:
			return {"error": str(e)}

	@app.post("/whatsapp-qr/incoming")
	async def wa_qr_incoming(request: dict):
		"""Recibe mensajes del bridge y los procesa con el agente (DAT-246)."""
		from agno.media import Audio as AgnoAudio, Image as AgnoImage

		from_jid = request.get("from", "")
		message_id = request.get("message_id", "")
		text = request.get("text", "")
		msg_type = request.get("type", "text")
		mime_type = request.get("mimeType", "")
		media_b64 = request.get("media", "")

		if message_id and _wa_qr_dedup.is_duplicate(message_id):
			logger.info(f"QR Bridge duplicado ignorado: {message_id[:20]}")
			return {"status": "duplicate_ignored"}

		if not text and msg_type == "text":
			return {"status": "ignored", "reason": "empty message"}

		logger.info(f"QR Bridge mensaje de {from_jid}: {text[:80]} (tipo: {msg_type})")

		try:
			# Decodificar media base64 si existe
			media_bytes = None
			if media_b64:
				import base64
				try:
					media_bytes = base64.b64decode(media_b64)
				except Exception as e:
					logger.error(f"Error decodificando media b64: {e}")

			# Construir kwargs validos para Agno Agent.arun
			arun_kwargs: dict = {
				"user_id": from_jid,
				"session_id": from_jid,
			}

			if media_bytes and msg_type == "audio":
				arun_kwargs["audio"] = [AgnoAudio(
					content=media_bytes,
					mime_type=mime_type or "audio/ogg",
				)]
				if not text or text.startswith("["):
					text = "[Audio recibido]"
				logger.info(f"QR Bridge audio preparado: {len(media_bytes)} bytes, mime={mime_type}")

			elif media_bytes and msg_type == "image":
				arun_kwargs["images"] = [AgnoImage(
					content=media_bytes,
					mime_type=mime_type or "image/jpeg",
				)]
				if not text or text.startswith("["):
					text = "Describe o analiza esta imagen"
				logger.info(f"QR Bridge imagen preparada: {len(media_bytes)} bytes, mime={mime_type}")

			elif media_bytes and msg_type in ("document", "video"):
				# Documentos y videos: informar al agente sin adjuntar
				if not text or text.startswith("["):
					text = f"[{msg_type} recibido — tipo: {mime_type}]"
				logger.info(f"QR Bridge {msg_type} recibido pero no procesable como media directa")

			# Usar arun wrapped (con STT/TTS/Fallback) via _qr_agent_arun
			response = await _qr_agent_arun(text, **arun_kwargs)

			# Extraer texto de la respuesta de forma segura
			response_text = None
			if response is not None:
				if hasattr(response, 'content') and response.content is not None:
					response_text = str(response.content)
				elif hasattr(response, 'messages') and response.messages:
					for msg in reversed(response.messages):
						role = getattr(msg, 'role', '')
						content = getattr(msg, 'content', None)
						if role == 'assistant' and content:
							response_text = str(content)
							break

			if not response_text or not response_text.strip() or response_text == "None":
				response_text = "Lo siento, no pude procesar tu mensaje. Intenta de nuevo."
				logger.warning(f"QR Bridge respuesta vacia/None para {from_jid}, enviando fallback")
			else:
				response_text = response_text.strip()

			logger.info(f"QR Bridge respuesta a {from_jid}: {response_text[:80]}")

			async with httpx.AsyncClient(timeout=30) as client:
				send_resp = await client.post(f"{bridge_url}/send", json={
					"to": from_jid,
					"text": response_text,
				})
				logger.info(f"QR Bridge send result: {send_resp.status_code}")
			return {"status": "responded"}
		except Exception as e:
			logger.error(f"Error procesando mensaje QR de {from_jid}: {type(e).__name__}: {e}")
			try:
				async with httpx.AsyncClient(timeout=10) as client:
					await client.post(f"{bridge_url}/send", json={
						"to": from_jid,
						"text": "Ocurrio un error procesando tu mensaje. Intenta de nuevo en unos segundos.",
					})
			except Exception:
				pass
			return {"status": "error", "error": str(e)}


base_app = FastAPI(
	title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
	version=__version__,
	lifespan=lifespan,
)
base_app.state.limiter = limiter
base_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
base_app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
base_app.add_middleware(TenantMiddleware)

# === Middleware: dedup WhatsApp webhooks por message ID ===
# Meta re-entrega webhooks si el servidor estuvo caido o demoro en responder.
# No filtramos mensajes historicos validos; solo replays del mismo message_id.
import json as _json
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

async def _read_http_body(receive: Receive) -> bytes:
	"""Lee el body completo de una request ASGI."""
	chunks: list[bytes] = []
	more_body = True
	while more_body:
		message = await receive()
		if message["type"] != "http.request":
			continue
		chunks.append(message.get("body", b""))
		more_body = message.get("more_body", False)
	return b"".join(chunks)


def _sign_whatsapp_payload(payload: bytes) -> str | None:
	"""Genera firma X-Hub-Signature-256 para un payload si existe app secret."""
	app_secret = os.getenv("WHATSAPP_APP_SECRET")
	if not app_secret:
		return None
	digest = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
	return f"sha256={digest}"


class WhatsAppDedupMiddleware:
	def __init__(self, app: ASGIApp):
		self.app = app

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if (
			scope["type"] != "http"
			or scope["method"] != "POST"
			or "/webhook" not in scope["path"]
			or "whatsapp-qr" in scope["path"]
		):
			await self.app(scope, receive, send)
			return

		body = await _read_http_body(receive)
		try:
			data = _json.loads(body)
			if data.get("object") == "whatsapp_business_account":
				headers = dict(scope.get("headers") or [])
				signature = headers.get(b"x-hub-signature-256", b"").decode()
				try:
					signature_is_valid = validate_webhook_signature(body, signature)
				except HTTPException:
					signature_is_valid = False

				# Nunca deduplicar antes de que el webhook pase validacion.
				# Si la firma es invalida o la configuracion esta incompleta, delegar al router oficial.
				if signature_is_valid:
					all_duplicate = True
					has_messages = False
					body_modified = False
					for entry in data.get("entry", []):
						for change in entry.get("changes", []):
							value = change.get("value", {})
							messages = value.get("messages", [])
							if not messages:
								continue
							has_messages = True
							filtered_messages = []
							for msg in messages:
								msg_id = msg.get("id", "")
								if msg_id and _wa_cloud_dedup.is_duplicate(msg_id):
									logger.info(f"Webhook duplicado ignorado: {msg_id[:20]}")
									body_modified = True
									continue
								all_duplicate = False
								filtered_messages.append(msg)

							if len(filtered_messages) != len(messages):
								value["messages"] = filtered_messages

					if has_messages and all_duplicate:
						response = JSONResponse({"status": "duplicate_ignored"}, status_code=200)
						await response(scope, receive, send)
						return

					if body_modified:
						body = _json.dumps(data).encode("utf-8")
						new_signature = _sign_whatsapp_payload(body)
						if new_signature:
							scope = dict(scope)
							headers = [
								(key, value)
								for key, value in scope.get("headers", [])
								if key != b"x-hub-signature-256"
							]
							headers.append((b"x-hub-signature-256", new_signature.encode()))
							scope["headers"] = headers

		except (ValueError, KeyError):
			pass  # No es JSON valido o estructura inesperada, dejar pasar

		sent = False

		async def replay_receive() -> dict:
			nonlocal sent
			if sent:
				return {"type": "http.request", "body": b"", "more_body": False}
			sent = True
			return {"type": "http.request", "body": body, "more_body": False}

		await self.app(scope, replay_receive, send)

base_app.add_middleware(WhatsAppDedupMiddleware)


@base_app.get("/")
async def root() -> RedirectResponse:
	"""La raiz no tiene UI de AgentOS; redirige a la documentacion interactiva OpenAPI."""
	return RedirectResponse(url="/docs", status_code=307)


if knowledge:
	from routes.knowledge_routes import create_knowledge_router
	knowledge_router = create_knowledge_router(knowledge, limiter=limiter)
	base_app.include_router(knowledge_router)

tenant_store = TenantStore(ws["db_url"])
workspace_store = WorkspaceStore(
	backend=os.getenv("OPENAGNO_WORKSPACE_STORE_BACKEND", "local"),
)
base_app.state.tenant_store = tenant_store
base_app.state.workspace_store = workspace_store

interfaces = []
channels = config.get("channels", ["whatsapp"])

# === WhatsApp modo dual (DAT-240) ===
wa_config = config.get("whatsapp", {})
wa_mode = wa_config.get("mode", "cloud_api")

if "whatsapp" in channels:
	# Modo 1: Cloud API (oficial Meta) — siempre disponible
	if wa_mode in ("cloud_api", "dual"):
		from agno.os.interfaces.whatsapp import Whatsapp
		interfaces.append(Whatsapp(agent=main_agent))
		logger.info("WhatsApp Cloud API habilitado (API oficial Meta)")

	# Modo 2: QR Link (via Baileys bridge)
	if wa_mode in ("qr_link", "dual"):
		bridge_url = wa_config.get("qr_link", {}).get("bridge_url", "http://localhost:3001")
		_setup_whatsapp_qr_routes(base_app, main_agent, bridge_url)
		logger.info(f"WhatsApp QR Link habilitado (bridge: {bridge_url})")

if "slack" in channels:
	from agno.os.interfaces.slack import Slack
	interfaces.append(Slack(agent=main_agent))
	logger.info("Canal Slack habilitado")

if "telegram" in channels:
	try:
		from agno.os.interfaces.telegram import Telegram
		interfaces.append(Telegram(agent=main_agent))
		logger.info("Canal Telegram habilitado")
	except ImportError:
		logger.warning("Telegram no disponible — actualizar agno[os]")

if "agui" in channels:
	try:
		from agno.os.interfaces.agui import AGUI
		interfaces.append(AGUI(agent=main_agent))
		logger.info("Canal AG-UI habilitado")
	except ImportError:
		logger.warning("AG-UI no disponible. Instalar: pip install ag-ui-protocol")

if "ai_sdk" in channels:
	logger.warning("El canal 'ai_sdk' ya no esta soportado en Agno 2.x. Usa 'agui'.")

if config.get("a2a", {}).get("enabled", False):
	try:
		from agno.os.interfaces.a2a import A2A
		interfaces.append(A2A(agent=main_agent))
		logger.info("Protocolo A2A habilitado")
	except ImportError:
		logger.warning("A2A no disponible. Instalar: pip install agno[a2a]")

logger.info("Canal Web disponible via os.agno.com (Control Plane)")

# === Studio Registry con todos los tools del workspace (DAT-238) ===
studio_config = config.get("studio", {})
registry = None
if studio_config.get("enabled", True) and not ws["db_url"].startswith("sqlite"):
	all_models = [main_agent.model]
	for sa in sub_agents:
		if sa.model not in all_models:
			all_models.append(sa.model)

	# Recopilar TODOS los tools del workspace para Registry
	registry_tools = []
	for tool in main_agent.tools or []:
		if tool not in registry_tools:
			registry_tools.append(tool)

	os_config_name = config.get("agentos", {}).get("name", "AgnoBot Registry")
	registry = Registry(
		name=os_config_name,
		tools=registry_tools,
		models=all_models,
		dbs=[db],
	)
	logger.info(f"Studio Registry configurado con {len(registry_tools)} tools")

all_agents = [main_agent] + sub_agents
agents_by_id = {agent.id: agent for agent in all_agents if getattr(agent, "id", None)}
logger.info(f"Agentes cargados: {[a.id for a in all_agents]}")
if teams:
	logger.info(f"Teams cargados: {[t.id for t in teams]}")
if schedules:
	logger.info(f"Schedules cargados: {[s['name'] for s in schedules]}")

from routes.tenant_routes import create_tenant_router
base_app.include_router(create_tenant_router(tenant_store, workspace_store, agents_by_id))

os_config = config.get("agentos", {})
scheduler_cfg = config.get("scheduler", {})
PORT = int(os.getenv("PORT", os_config.get("port", 8000)))

_agent_os_params = inspect.signature(AgentOS.__init__).parameters
_scheduler_kwargs: dict[str, object] = {}
if scheduler_cfg.get("enabled", True) and "scheduler" in _agent_os_params:
	_scheduler_kwargs["scheduler"] = True
	if "scheduler_poll_interval" in _agent_os_params:
		_scheduler_kwargs["scheduler_poll_interval"] = int(
			scheduler_cfg.get("poll_interval", 15)
		)
	# F7 — 7.1: Fix scheduler_base_url para apuntar al puerto correcto
	if "scheduler_base_url" in _agent_os_params:
		_sched_base = scheduler_cfg.get("base_url", f"http://127.0.0.1:{PORT}")
		_scheduler_kwargs["scheduler_base_url"] = _sched_base
		logger.info(f"Scheduler base_url: {_sched_base}")
	_poll = _scheduler_kwargs.get("scheduler_poll_interval", 15)
	logger.info(f"Scheduler AgentOS habilitado (poll cada {_poll}s)")

if schedules:
	if not scheduler_cfg.get("enabled", True):
		logger.info(
			"schedules.yaml: referencia cargada; scheduler.enabled=false, cron de AgentOS desactivado."
		)
	elif "scheduler" not in _agent_os_params:
		logger.warning(
			"schedules.yaml tiene entradas pero AgentOS no expone scheduler; usa agno[os,scheduler]."
		)

# Background Hooks (F6) — hooks post-run no bloquean response
_hooks_kwargs: dict[str, object] = {}
if "run_hooks_in_background" in _agent_os_params:
	_hooks_kwargs["run_hooks_in_background"] = True
	logger.info("Background Hooks habilitados")

agent_os = AgentOS(
	id=os_config.get("id", "agnobot-gateway"),
	name=os_config.get("name", "AgnoBot Platform"),
	agents=all_agents,
	teams=teams if teams else None,
	interfaces=interfaces,
	knowledge=[knowledge] if knowledge else None,
	db=db,
	registry=registry,
	tracing=os_config.get("tracing", True),
	enable_mcp_server=ws["mcp_config"].get("expose", {}).get("enabled", True),
	base_app=base_app,
	on_route_conflict="preserve_base_app",
	**_scheduler_kwargs,
	**_hooks_kwargs,
)

# === F7 — 7.5: Alerta de token WhatsApp expirado ===
_wa_auth_failed = False

def _check_wa_auth_error(error: Exception):
	"""Detecta si un error es por token WhatsApp expirado."""
	global _wa_auth_failed
	error_msg = str(error).lower()
	if ("401" in error_msg or "unauthorized" in error_msg) and (
		"access token" in error_msg or "session" in error_msg or "expired" in error_msg
	):
		if not _wa_auth_failed:
			_wa_auth_failed = True
			logger.critical("TOKEN WHATSAPP EXPIRADO — renovar en Meta Business")


# === Endpoints admin (F6+F7) ===
OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))


@base_app.post("/admin/reload")
@limiter.limit("10/minute")
async def admin_reload(request: Request):
	"""El agente solicita reload. El daemon detecta la senal y reinicia."""
	signal_file = OPENAGNO_ROOT / ".reload_requested"
	signal_file.write_text(datetime.now().isoformat())
	return {"status": "reload_requested"}


@base_app.get("/admin/health")
@limiter.limit("60/minute")
async def admin_health(request: Request):
	model_info = {**config.get("model", {})}
	if fallback_model:
		model_info["fallback_active"] = _using_fallback
		model_info["fallback_id"] = fallback_model.id
		model_info["fallback_cooldown_seconds"] = FALLBACK_COOLDOWN
		if _using_fallback:
			remaining = max(0, int(_fallback_until - time.time()))
			model_info["fallback_restore_in_seconds"] = remaining
	audio_info = config.get("audio", {})
	return {
		"status": "healthy",
		"version": __version__,
		"agents": [a.id for a in all_agents],
		"teams": [t.id for t in teams] if teams else [],
		"channels": config.get("channels", []),
		"model": model_info,
		"audio": audio_info if audio_info else None,
		"scheduler": scheduler_cfg.get("enabled", False),
		"scheduler_base_url": _scheduler_kwargs.get("scheduler_base_url", "NOT SET"),
		"whatsapp_auth": "expired" if _wa_auth_failed else "ok",
		"tenancy": {
			"enabled": True,
			"workspace_backend": workspace_store.backend,
			"tenant_header": "X-Tenant-ID",
		},
	}


@base_app.post("/admin/fallback/activate")
@limiter.limit("10/minute")
async def admin_fallback_activate(request: Request):
	"""Activa manualmente el modelo fallback."""
	if not fallback_model:
		return {"error": "No hay modelo fallback configurado"}
	_swap_to_fallback()
	return {"status": "fallback_active", "model": fallback_model.id}


@base_app.post("/admin/fallback/restore")
@limiter.limit("10/minute")
async def admin_fallback_restore(request: Request):
	"""Restaura el modelo principal."""
	if not fallback_model:
		return {"error": "No hay modelo fallback configurado"}
	_swap_to_primary()
	return {"status": "primary_restored", "model": _original_model.id}

app = agent_os.get_app()

if __name__ == "__main__":
	agent_os.serve(app="gateway:app", host="0.0.0.0", port=PORT, ws="wsproto")
