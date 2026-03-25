"""
Knowledge Routes - Endpoints REST para gestion de la Knowledge Base.
"""
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, create_engine

from agno.knowledge.knowledge import Knowledge
from agno.utils.log import logger


class SearchRequest(BaseModel):
	query: str
	max_results: int = 5


def create_knowledge_router(knowledge: Knowledge) -> APIRouter:
	"""Crea el router de Knowledge con endpoints REST funcionales."""
	router = APIRouter(prefix="/knowledge", tags=["knowledge"])

	@router.post("/upload")
	async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
		"""Recibe un archivo y lo inserta en la Knowledge Base."""
		allowed_extensions = {".pdf", ".txt", ".md", ".csv", ".docx"}
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

	@router.get("/list")
	async def list_documents() -> dict[str, object]:
		"""Lista documentos unicos en la Knowledge Base."""
		try:
			if hasattr(knowledge, "contents_db") and knowledge.contents_db is not None:
				contents_db = knowledge.contents_db
				if hasattr(contents_db, "db_url"):
					engine = create_engine(contents_db.db_url)
					table = getattr(
						contents_db, "knowledge_table", "agnobot_knowledge_contents"
					)
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
		except Exception as e:
			logger.error(f"Error al listar documentos: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	@router.delete("/{doc_name}")
	async def delete_document(doc_name: str) -> dict[str, str]:
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

	@router.post("/search")
	async def search_knowledge(request: SearchRequest) -> dict[str, object]:
		"""Busqueda semantica en la Knowledge Base."""
		try:
			results = knowledge.search(
				query=request.query, num_documents=request.max_results
			)
			documents = []
			for doc in results:
				documents.append({
					"content": doc.content if hasattr(doc, "content") else str(doc),
					"name": doc.name if hasattr(doc, "name") else "unknown",
				})
			return {"results": documents, "count": len(documents)}
		except Exception as e:
			logger.error(f"Error en busqueda: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	return router
