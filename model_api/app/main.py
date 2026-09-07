"""API REST — encapsule le modele CIM-11 fine-tune pour l'inference (bloc 2, E3, C9/C10/C11).

Endpoints :
- GET  /health   : verification de service
- POST /predict  : prediction DP/DAS a partir d'un texte de CRH
- GET  /metrics  : vecteur de restitution des metriques en temps reel (C11)
"""
import hashlib
import logging
from collections import deque
from statistics import mean

from fastapi import FastAPI, Depends

from .auth import require_api_key
from .predictor import BasePredictor, LlamaCim11Predictor, timed_predict
from .schemas import PredictIn, PredictOut

logger = logging.getLogger("model_api.monitoring")

# RGPD (art. 32) — regle de journalisation : aucun contenu de CRH n'est ecrit dans les
# journaux. Un CRH reel contient des donnees de sante identifiantes (identite, service,
# dates) ; or les journaux sont conserves, recopies et accessibles a plus de personnes
# que le dossier medical lui-meme. On journalise donc uniquement des metadonnees non
# identifiantes : la longueur du texte, et une empreinte SHA-256 tronquee.
#
# L'empreinte est a sens unique (le texte n'est pas reconstituable) mais deterministe :
# deux echecs sur le meme document portent la meme empreinte, ce qui permet de reperer
# une recidive sans savoir de quel patient il s'agit.
#
# Limite assumee : une empreinte reste une donnee *pseudonymisee*, donc une donnee
# personnelle au sens du RGPD (considerant 26) — le risque est fortement reduit, pas
# supprime. Les regles de conservation et d'acces aux journaux restent necessaires.
_EMPREINTE_LONGUEUR = 16


def _empreinte_crh(texte: str) -> str:
    """Empreinte non reversible d'un CRH, pour correler des echecs sans journaliser le contenu."""
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:_EMPREINTE_LONGUEUR]


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
            logger.warning(
                "Prediction sans DP identifie (longueur_crh=%d, empreinte=%s)",
                len(payload.texte_crh),
                _empreinte_crh(payload.texte_crh),
            )
        return result
    except Exception:
        _error_count += 1
        raise
