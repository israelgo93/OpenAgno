"""Knowledge routes with optional tenant-aware isolation."""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from agno.knowledge.knowledge import Knowledge
from agno.utils.log import logger
from openagno.core.tenant import get_tenant_scoped_knowledge
from security import verify_api_key


class SearchRequest(BaseModel):
	query: str
	max_results: int = 5


def _tenant_knowledge(knowledge, request: Request):
	tenant_id = getattr(request.state, "tenant_id", None)
	return get_tenant_scoped_knowledge(knowledge, tenant_id)


class UrlEntry(BaseModel):
	url: str
	name: Optional[str] = None


class IngestUrlsRequest(BaseModel):
	urls: list[UrlEntry]


def create_knowledge_router(knowledge: Knowledge, limiter=None) -> APIRouter:
	"""Crea el router de Knowledge con endpoints REST funcionales."""
	router = APIRouter(prefix="/knowledge", tags=["knowledge"])
	limit = limiter.limit if limiter is not None else (lambda _rule: (lambda func: func))

	@router.post("/upload", dependencies=[Depends(verify_api_key)])
	@limit("10/minute")
	async def upload_document(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
		"""Recibe un archivo y lo inserta en la Knowledge Base."""
		allowed_extensions = {".pdf", ".txt", ".md", ".csv", ".docx", ".json"}
		file_ext = Path(file.filename or "").suffix.lower()

		if file_ext not in allowed_extensions:
			raise HTTPException(
				status_code=400,
				detail=(
					f"Tipo no soportado: {file_ext}. "
					f"Permitidos: {', '.join(allowed_extensions)}"
				),
			)

		with tempfile.NamedTemporaryFile(
			delete=False, suffix=file_ext, prefix="agnobot_kb_",
		) as tmp:
			content = await file.read()
			tmp.write(content)
			tmp_path = tmp.name

		try:
			tenant_knowledge = _tenant_knowledge(knowledge, request)
			tenant_knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
			logger.info(f"Documento cargado: {file.filename}")
			return {
				"status": "ok",
				"message": f"Documento '{file.filename}' cargado exitosamente",
				"tenant_id": getattr(request.state, "tenant_id", "default"),
			}
		except Exception as e:
			logger.error(f"Error al cargar documento: {e}")
			raise HTTPException(status_code=500, detail=str(e))
		finally:
			Path(tmp_path).unlink(missing_ok=True)

	@router.post("/ingest-urls", dependencies=[Depends(verify_api_key)])
	@limit("10/minute")
	async def ingest_urls(request: Request, payload: IngestUrlsRequest) -> dict[str, object]:
		"""Ingesta una lista de URLs en la Knowledge Base."""
		results: list[dict[str, str]] = []
		tenant_knowledge = _tenant_knowledge(knowledge, request)
		for entry in payload.urls:
			if not entry.url:
				results.append({"url": "", "status": "error", "detail": "URL vacia"})
				continue
			name = entry.name or entry.url
			try:
				tenant_knowledge.insert(url=entry.url, name=name, skip_if_exists=True)
				results.append({"url": entry.url, "status": "ok", "name": name})
				logger.info(f"URL ingestada: {name}")
			except Exception as e:
				results.append({"url": entry.url, "status": "error", "detail": str(e)})
				logger.warning(f"Error ingestando URL {name}: {e}")

		ok_count = sum(1 for r in results if r["status"] == "ok")
		return {
			"results": results,
			"total": len(results),
			"ok": ok_count,
			"tenant_id": getattr(request.state, "tenant_id", "default"),
		}

	@router.get("/list", dependencies=[Depends(verify_api_key)])
	@limit("30/minute")
	async def list_documents(request: Request) -> dict[str, object]:
		"""Lista documentos unicos en la Knowledge Base."""
		try:
			tenant_knowledge = _tenant_knowledge(knowledge, request)
			if not hasattr(tenant_knowledge, "get_content"):
				return {"documents": [], "count": 0, "message": "Knowledge backend sin listado"}

			contents, total = tenant_knowledge.get_content()
			docs = [
				{
					"id": str(content.id),
					"name": content.name,
					"status": str(getattr(content, "status", "")),
				}
				for content in contents
				if getattr(content, "name", None)
			]
			return {
				"documents": docs,
				"count": len(docs),
				"total": total,
				"tenant_id": getattr(request.state, "tenant_id", "default"),
			}
		except HTTPException:
			raise  # F7 — 7.6.3: SIEMPRE re-raise
		except Exception as e:
			logger.warning(f"Error al listar documentos: {e}")
			return {"documents": [], "count": 0, "message": "Knowledge backend no inicializado"}

	@router.delete("/{doc_name}", dependencies=[Depends(verify_api_key)])
	@limit("10/minute")
	async def delete_document(request: Request, doc_name: str) -> dict[str, str]:
		"""Elimina un documento de la Knowledge Base por nombre."""
		try:
			tenant_knowledge = _tenant_knowledge(knowledge, request)
			contents, _ = tenant_knowledge.get_content()
			matching = [
				content.id for content in contents
				if getattr(content, "id", None) and getattr(content, "name", None) == doc_name
			]
			if not matching:
				raise HTTPException(status_code=404, detail="Documento no encontrado")
			for content_id in matching:
				tenant_knowledge.remove_content_by_id(content_id)
			logger.info(f"Documento eliminado: {doc_name}")
			return {
				"status": "ok",
				"message": f"Documento '{doc_name}' eliminado",
				"tenant_id": getattr(request.state, "tenant_id", "default"),
			}
		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"Error al eliminar documento: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	@router.post("/search", dependencies=[Depends(verify_api_key)])
	@limit("30/minute")
	async def search_knowledge(request: Request, payload: SearchRequest) -> dict[str, object]:
		"""Busqueda semantica en la Knowledge Base."""
		try:
			tenant_knowledge = _tenant_knowledge(knowledge, request)
			results = tenant_knowledge.search(
				query=payload.query, max_results=payload.max_results
			)
			documents = []
			for doc in results:
				documents.append({
					"content": doc.content[:500] if hasattr(doc, "content") and doc.content else str(doc)[:500],
					"name": doc.name if hasattr(doc, "name") else "unknown",
					"score": getattr(doc, "score", None),
				})
			return {
				"query": payload.query,
				"results": documents,
				"count": len(documents),
				"tenant_id": getattr(request.state, "tenant_id", "default"),
			}
		except HTTPException:
			raise  # F7 — 7.6.3: SIEMPRE re-raise
		except Exception as e:
			logger.warning(f"Error en busqueda: {e}")
			return {"query": payload.query, "results": [], "count": 0}

	return router
