"""Authentification simple par clé d'API (header X-API-Key).

Conforme à l'attendu de la grille d'évaluation : « l'API restreint l'accès
avec un moyen d'authentification ». En production, la clé est lue depuis une
variable d'environnement (jamais commitée).
"""
import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("DATA_API_KEY", "dev-only-change-me")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé d'API invalide ou manquante (header X-API-Key requis).",
        )
    return key
