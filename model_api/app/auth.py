"""Authentification par cle d'API (header X-API-Key) — meme principe que data-api."""
import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("MODEL_API_KEY", "dev-only-change-me")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cle d'API invalide ou manquante (header X-API-Key requis).",
        )
    return key
