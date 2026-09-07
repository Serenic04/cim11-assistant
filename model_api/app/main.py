"""API REST — encapsule le modele CIM-11 fine-tune pour l'inference (bloc 2, E3, C9/C10/C11).

Endpoints :
- GET  /health   : verification de service
- POST /predict  : prediction DP/DAS a partir d'un texte de CRH
- GET  /metrics  : vecteur de restitution des metriques en temps reel (C11)
"""
import logging
from collections import deque
from statistics import mean

from fastapi import FastAPI, Depends

from .auth import require_api_key
from .predictor import BasePredictor, LlamaCim11Predictor, timed_predict
from .schemas import PredictIn, PredictOut

logger = logging.getLogger("model_api.monitoring")

app = FastAPI(
    title="CIM-11 Model API",
    description="Encapsule le modele Llama-3-8B fine-tune (adaptateur LoRA) pour le codage CIM-11.",
    version="1.0.0",
)

_predictor_singleton = LlamaCim11Predictor()
_recent_latencies_ms: deque[float] = deque(maxlen=200)
_request_count = 0
_error_count = 0
_anomaly_count = 0  # predictions sans DP identifie (declencheur de l'incident E5)


def get_predictor() -> BasePredictor:
    return _predictor_singleton


@app.get("/health", tags=["monitoring"])
def health():
    return {"status": "ok"}


@app.get("/metrics", tags=["monitoring"])
def metrics():
    """Vecteur de restitution des metriques en temps reel (monitorage du modele, C11)."""
    return {
        "nb_requetes": _request_count,
        "nb_erreurs": _error_count,
        "latence_moyenne_ms": round(mean(_recent_latencies_ms), 1) if _recent_latencies_ms else None,
        "latence_p95_ms": (
            round(sorted(_recent_latencies_ms)[int(len(_recent_latencies_ms) * 0.95) - 1], 1)
            if len(_recent_latencies_ms) >= 5
            else None
        ),
        "fenetre_glissante": len(_recent_latencies_ms),
        "nb_anomalies_dp_manquant": _anomaly_count,
    }


@app.post("/predict", response_model=PredictOut, tags=["prediction"])
def predict(
    payload: PredictIn,
    predictor: BasePredictor = Depends(get_predictor),
    _=Depends(require_api_key),
):
    global _request_count, _error_count, _anomaly_count
    _request_count += 1
    try:
        result = timed_predict(predictor, payload.texte_crh)
        _recent_latencies_ms.append(result["latence_ms"])
        if result.get("dp") is None:
            # Alerte : un CRH non trivial devrait quasi toujours produire un DP.
            # Ce signal permet de detecter une recidive de ce type d'incident
            # en production (l'incident initial a ete detecte via les tests
            # de non-regression, cf. docs/E5_incident_monitorage.md).
            _anomaly_count += 1
            logger.warning("Prediction sans DP identifie (texte_crh tronque=%r)", payload.texte_crh[:80])
        return result
    except Exception:
        _error_count += 1
        raise
