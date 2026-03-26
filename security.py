"""
Security — API Key authentication for REST endpoints.

Phase 7: Proteccion de endpoints REST con API Key.
Si OPENAGNO_API_KEY esta configurado, todos los endpoints protegidos
requieren el header X-API-Key. En modo desarrollo (sin key), acceso libre.
"""
import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("OPENAGNO_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str = Security(api_key_header)):
    """Verifica la API Key. Si no hay key configurada, acceso libre (dev)."""
    if not API_KEY:
        return  # Sin API key configurada, acceso libre (dev)
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
