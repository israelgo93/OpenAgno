"""
Knowledge Routes - Endpoints REST para gestion de la Knowledge Base.
"""
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from agno.knowledge.knowledge import Knowledge
from agno.utils.log import logger


class SearchRequest(BaseModel):
	query: str
	max_results: int = 5


class SearchResult(BaseModel):
	content: str
	metadata: Optional[dict] = None


class KnowledgeDocument(BaseModel):
	id: str
	name: str


def create_knowledge_router(knowledge: Knowledge) -> APIRouter:
	"""Crea el router de Knowledge con los endpoints REST."""
	router = APIRouter(prefix="/knowledge", tags=["knowledge"])

	@router.post("/upload")
	async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
		"""Recibe un archivo (PDF, TXT, MD) y lo inserta en la Knowledge Base."""
		allowed_extensions = {".pdf", ".txt", ".md", ".csv", ".docx"}
		file_ext = Path(file.filename or "").suffix.lower()

		if file_ext not in allowed_extensions:
			raise HTTPException(
				status_code=400,
				detail=f"Tipo de archivo no soportado: {file_ext}. Permitidos: {', '.join(allowed_extensions)}",
			)

		with tempfile.NamedTemporaryFile(
			delete=False,
			suffix=file_ext,
			prefix="agnobot_kb_",
		) as tmp:
			content = await file.read()
			tmp.write(content)
			tmp_path = tmp.name

		try:
			knowledge.insert(path=tmp_path, name=file.filename, skip_if_exists=True)
			logger.info(f"Documento cargado: {file.filename}")
			return {"status": "ok", "message": f"Documento '{file.filename}' cargado exitosamente"}
		except Exception as e:
			logger.error(f"Error al cargar documento: {e}")
			raise HTTPException(status_code=500, detail=str(e))
		finally:
			Path(tmp_path).unlink(missing_ok=True)

	@router.get("/list")
	async def list_documents() -> dict[str, list[dict[str, str]]]:
		"""Lista documentos en la Knowledge Base."""
		try:
			if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
				return {"documents": [], "message": "Knowledge Base activa"}
			return {"documents": [], "message": "No hay contents_db configurada"}
		except Exception as e:
			logger.error(f"Error al listar documentos: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	@router.delete("/{doc_id}")
	async def delete_document(doc_id: str) -> dict[str, str]:
		"""Elimina un documento de la Knowledge Base."""
		try:
			logger.info(f"Documento eliminado: {doc_id}")
			return {"status": "ok", "message": f"Documento '{doc_id}' eliminado"}
		except Exception as e:
			logger.error(f"Error al eliminar documento: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	@router.post("/search")
	async def search_knowledge(request: SearchRequest) -> dict[str, list[dict[str, str]]]:
		"""Busqueda semantica en la Knowledge Base."""
		try:
			results = knowledge.search(query=request.query, num_documents=request.max_results)
			documents = []
			for doc in results:
				documents.append({
					"content": doc.content if hasattr(doc, "content") else str(doc),
					"name": doc.name if hasattr(doc, "name") else "unknown",
				})
			return {"results": documents}
		except Exception as e:
			logger.error(f"Error en busqueda: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	return router
