"""
Knowledge Routes - Endpoints REST para gestion de la Knowledge Base.

Incluye upload de documentos, ingesta de URLs, listado, busqueda y eliminacion.
Fase 7: API Key auth, SQL injection fix, HTTPException re-raise.
"""
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text, create_engine

from agno.knowledge.knowledge import Knowledge
from agno.utils.log import logger
from security import verify_api_key

# F7 — 7.6.2: Whitelist de tablas permitidas para prevenir SQL Injection
ALLOWED_TABLES = {"agnobot_knowledge_contents", "agnobot_knowledge_vectors"}


class SearchRequest(BaseModel):
	query: str
	max_results: int = 5


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
			knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
			logger.info(f"Documento cargado: {file.filename}")
			return {
				"status": "ok",
				"message": f"Documento '{file.filename}' cargado exitosamente",
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
		for entry in payload.urls:
			if not entry.url:
				results.append({"url": "", "status": "error", "detail": "URL vacia"})
				continue
			name = entry.name or entry.url
			try:
				knowledge.insert(url=entry.url, name=name, skip_if_exists=True)
				results.append({"url": entry.url, "status": "ok", "name": name})
				logger.info(f"URL ingestada: {name}")
			except Exception as e:
				results.append({"url": entry.url, "status": "error", "detail": str(e)})
				logger.warning(f"Error ingestando URL {name}: {e}")

		ok_count = sum(1 for r in results if r["status"] == "ok")
		return {"results": results, "total": len(results), "ok": ok_count}

	@router.get("/list", dependencies=[Depends(verify_api_key)])
	@limit("30/minute")
	async def list_documents(request: Request) -> dict[str, object]:
		"""Lista documentos unicos en la Knowledge Base."""
		try:
			if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
				contents_db = knowledge.contents_db
				if hasattr(contents_db, "db_url"):
					engine = create_engine(contents_db.db_url)
					table = getattr(
						contents_db, "knowledge_table", "agnobot_knowledge_contents"
					)
					if table not in ALLOWED_TABLES:
						raise HTTPException(400, "Tabla no permitida")
					with engine.connect() as conn:
						result = conn.execute(
							text(
								f"SELECT DISTINCT name, id FROM {table} "
								f"WHERE name IS NOT NULL ORDER BY name"
							)
						)
						docs = [
							{"id": str(row[1]), "name": row[0]}
							for row in result
						]
					return {"documents": docs, "count": len(docs)}

			return {"documents": [], "count": 0, "message": "Sin contents_db"}
		except HTTPException:
			raise  # F7 — 7.6.3: SIEMPRE re-raise
		except Exception as e:
			logger.warning(f"Error al listar documentos: {e}")
			return {"documents": [], "count": 0, "message": "Knowledge table no inicializada"}

	@router.delete("/{doc_name}", dependencies=[Depends(verify_api_key)])
	@limit("10/minute")
	async def delete_document(request: Request, doc_name: str) -> dict[str, str]:
		"""Elimina un documento de la Knowledge Base por nombre."""
		try:
			if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
				contents_db = knowledge.contents_db
				if hasattr(contents_db, "db_url"):
					engine = create_engine(contents_db.db_url)
					table = getattr(
						contents_db, "knowledge_table", "agnobot_knowledge_contents"
					)
					vector_table: Optional[str] = None
					if hasattr(knowledge, "vector_db") and knowledge.vector_db is not None:
						vector_table = getattr(
							knowledge.vector_db, "table_name", None
						)

					# F7 — 7.6.2: Validar tablas contra whitelist
					if table not in ALLOWED_TABLES:
						raise HTTPException(400, "Tabla no permitida")
					if vector_table and vector_table not in ALLOWED_TABLES:
						raise HTTPException(400, "Tabla de vectores no permitida")

					with engine.connect() as conn:
						conn.execute(
							text(f"DELETE FROM {table} WHERE name = :name"),
							{"name": doc_name},
						)
						if vector_table:
							conn.execute(
								text(f"DELETE FROM {vector_table} WHERE name = :name"),
								{"name": doc_name},
							)
						conn.commit()

					logger.info(f"Documento eliminado: {doc_name}")
					return {
						"status": "ok",
						"message": f"Documento '{doc_name}' eliminado",
					}

			raise HTTPException(
				status_code=501,
				detail="Eliminacion no soportada sin contents_db",
			)
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
			results = knowledge.search(
				query=payload.query, max_results=payload.max_results
			)
			documents = []
			for doc in results:
				documents.append({
					"content": doc.content[:500] if hasattr(doc, "content") and doc.content else str(doc)[:500],
					"name": doc.name if hasattr(doc, "name") else "unknown",
					"score": getattr(doc, "score", None),
				})
			return {"query": payload.query, "results": documents, "count": len(documents)}
		except HTTPException:
			raise  # F7 — 7.6.3: SIEMPRE re-raise
		except Exception as e:
			logger.warning(f"Error en busqueda: {e}")
			return {"query": payload.query, "results": [], "count": 0}

	return router
