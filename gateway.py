"""
AgnoBot Gateway - Punto de entrada principal.
Lee el workspace/ y construye el AgentOS completo.

Fase 6: Autonomia operativa, Bedrock, Background Hooks, Daemon, Scheduler nativo.
"""
import inspect
import os
import time
from datetime import datetime
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from agno.os import AgentOS
from agno.registry import Registry
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.utils.log import logger

from loader import load_workspace, is_rate_limit_error, NON_AUDIO_PROVIDERS
from management.validator import print_validation, validate_workspace, workspace_warnings

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

		# 3. Ejecutar con retry/fallback ante rate-limit
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
			else:
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


base_app = FastAPI(
	title=config.get("agentos", {}).get("name", "AgnoBot Platform"),
	version="0.6.0",
	lifespan=lifespan,
)
base_app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)



@base_app.get("/")
async def root() -> RedirectResponse:
	"""La raiz no tiene UI de AgentOS; redirige a la documentacion interactiva OpenAPI."""
	return RedirectResponse(url="/docs", status_code=307)


if knowledge:
	from routes.knowledge_routes import create_knowledge_router
	knowledge_router = create_knowledge_router(knowledge)
	base_app.include_router(knowledge_router)

interfaces = []
channels = config.get("channels", ["whatsapp"])

if "whatsapp" in channels:
	from agno.os.interfaces.whatsapp import Whatsapp
	interfaces.append(Whatsapp(agent=main_agent))
	logger.info("Canal WhatsApp habilitado")

if "slack" in channels:
	from agno.os.interfaces.slack import Slack
	interfaces.append(Slack(agent=main_agent))
	logger.info("Canal Slack habilitado")

if config.get("a2a", {}).get("enabled", False):
	try:
		from agno.os.interfaces.a2a import A2A
		interfaces.append(A2A(agent=main_agent))
		logger.info("Protocolo A2A habilitado")
	except ImportError:
		logger.warning("A2A no disponible. Instalar: pip install agno[a2a]")

logger.info("Canal Web disponible via os.agno.com (Control Plane)")

studio_config = config.get("studio", {})
registry = None
if studio_config.get("enabled", True) and not ws["db_url"].startswith("sqlite"):
	all_models = [main_agent.model]
	for sa in sub_agents:
		if sa.model not in all_models:
			all_models.append(sa.model)

	registry = Registry(
		name="AgnoBot Registry",
		tools=[DuckDuckGoTools(), Crawl4aiTools()],
		models=all_models,
		dbs=[db],
	)
	logger.info("Studio Registry configurado")

all_agents = [main_agent] + sub_agents
logger.info(f"Agentes cargados: {[a.id for a in all_agents]}")
if teams:
	logger.info(f"Teams cargados: {[t.id for t in teams]}")
if schedules:
	logger.info(f"Schedules cargados: {[s['name'] for s in schedules]}")

os_config = config.get("agentos", {})
scheduler_cfg = config.get("scheduler", {})

_agent_os_params = inspect.signature(AgentOS.__init__).parameters
_scheduler_kwargs: dict[str, object] = {}
if scheduler_cfg.get("enabled", True) and "scheduler" in _agent_os_params:
	_scheduler_kwargs["scheduler"] = True
	if "scheduler_poll_interval" in _agent_os_params:
		_scheduler_kwargs["scheduler_poll_interval"] = int(
			scheduler_cfg.get("poll_interval", 15)
		)
	logger.info(
		"Scheduler AgentOS habilitado (poll cada %ss)",
		_scheduler_kwargs.get("scheduler_poll_interval", 15),
	)

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

# === Endpoints admin (F6) ===
OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))


@base_app.post("/admin/reload")
async def admin_reload():
	"""El agente solicita reload. El daemon detecta la senal y reinicia."""
	signal_file = OPENAGNO_ROOT / ".reload_requested"
	signal_file.write_text(datetime.now().isoformat())
	return {"status": "reload_requested"}


@base_app.get("/admin/health")
async def admin_health():
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
		"version": "0.7.0",
		"agents": [a.id for a in all_agents],
		"teams": [t.id for t in teams] if teams else [],
		"channels": config.get("channels", []),
		"model": model_info,
		"audio": audio_info if audio_info else None,
		"scheduler": scheduler_cfg.get("enabled", False),
	}


@base_app.post("/admin/fallback/activate")
async def admin_fallback_activate():
	"""Activa manualmente el modelo fallback."""
	if not fallback_model:
		return {"error": "No hay modelo fallback configurado"}
	_swap_to_fallback()
	return {"status": "fallback_active", "model": fallback_model.id}


@base_app.post("/admin/fallback/restore")
async def admin_fallback_restore():
	"""Restaura el modelo principal."""
	if not fallback_model:
		return {"error": "No hay modelo fallback configurado"}
	_swap_to_primary()
	return {"status": "primary_restored", "model": _original_model.id}

app = agent_os.get_app()

if __name__ == "__main__":
	port = int(os.getenv("PORT", os_config.get("port", 8000)))
	agent_os.serve(app="gateway:app", host="0.0.0.0", port=port)
