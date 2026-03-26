"""
Tests para security.py — autenticacion API Key.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class TestVerifyApiKey:
    """Tests para verify_api_key."""

    @pytest.mark.asyncio
    async def test_no_key_configured_allows_access(self):
        """Sin API Key configurada, el acceso es libre."""
        # Forzar sin key
        os.environ.pop("OPENAGNO_API_KEY", None)
        # Re-importar para que tome el env actualizado
        import importlib
        import security
        importlib.reload(security)
        # No deberia lanzar excepcion
        await security.verify_api_key(key=None)

    @pytest.mark.asyncio
    async def test_valid_key_allows_access(self):
        """Con la key correcta, acceso permitido."""
        os.environ["OPENAGNO_API_KEY"] = "test_secret_key_123"
        import importlib
        import security
        importlib.reload(security)
        # No deberia lanzar excepcion
        await security.verify_api_key(key="test_secret_key_123")
        os.environ.pop("OPENAGNO_API_KEY", None)

    @pytest.mark.asyncio
    async def test_invalid_key_denied(self):
        """Con key incorrecta, acceso denegado."""
        os.environ["OPENAGNO_API_KEY"] = "correct_key"
        import importlib
        import security
        importlib.reload(security)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await security.verify_api_key(key="wrong_key")
        assert exc_info.value.status_code == 403
        os.environ.pop("OPENAGNO_API_KEY", None)

    @pytest.mark.asyncio
    async def test_missing_key_denied(self):
        """Sin key enviada pero con key configurada, acceso denegado."""
        os.environ["OPENAGNO_API_KEY"] = "configured_key"
        import importlib
        import security
        importlib.reload(security)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await security.verify_api_key(key=None)
        assert exc_info.value.status_code == 403
        os.environ.pop("OPENAGNO_API_KEY", None)
