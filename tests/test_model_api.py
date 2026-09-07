"""Tests de l'API modele — un FakePredictor remplace Llama-3 (pas de GPU/telechargement en CI)."""
import os
import sys
from pathlib import Path

os.environ["MODEL_API_KEY"] = "test-key"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from model_api.app.main import app, get_predictor
from model_api.app.predictor import BasePredictor

HEADERS = {"X-API-Key": "test-key"}


class FakePredictor(BasePredictor):
    def predict(self, texte_crh: str) -> dict:
        return {
            "dp": {"libelle": "Fracture du col du femur, sans precision", "code": "NC72.2Z"},
            "das": [{"libelle": "Denutrition, sans precision", "code": "5B7Z"}],
        }


@pytest.fixture()
def client():
    app.dependency_overrides[get_predictor] = lambda: FakePredictor()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").status_code == 200


def test_auth_required(client):
    r = client.post("/predict", json={"texte_crh": "x" * 20})
    assert r.status_code == 401


def test_predict(client):
    r = client.post("/predict", json={"texte_crh": "Patient admis pour fracture du col du femur."}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["dp"]["code"] == "NC72.2Z"
    assert len(body["das"]) == 1
    assert body["latence_ms"] >= 0


def test_predict_input_too_short(client):
    r = client.post("/predict", json={"texte_crh": "court"}, headers=HEADERS)
    assert r.status_code == 422


def test_metrics_after_prediction(client):
    client.post("/predict", json={"texte_crh": "Patient admis pour fracture du col du femur."}, headers=HEADERS)
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["nb_requetes"] >= 1
    assert body["latence_moyenne_ms"] is not None


def test_metrics_tracks_anomaly_when_dp_missing(client):
    """Non-regression E5 : une prediction sans DP doit incrementer nb_anomalies_dp_manquant."""
    before = client.get("/metrics").json()["nb_anomalies_dp_manquant"]

    class NoDpPredictor:
        def predict(self, texte_crh: str) -> dict:
            return {"dp": None, "das": []}

    from model_api.app.main import app, get_predictor

    app.dependency_overrides[get_predictor] = lambda: NoDpPredictor()
    client.post("/predict", json={"texte_crh": "Patient admis pour observation."}, headers=HEADERS)

    after = client.get("/metrics").json()["nb_anomalies_dp_manquant"]
    assert after == before + 1


class FakePredictorSansDP(BasePredictor):
    """Simule le cas d'anomalie : aucun diagnostic principal identifie."""

    def predict(self, texte_crh: str) -> dict:
        return {"dp": None, "das": []}


def test_journalisation_ne_contient_aucun_contenu_de_crh(caplog):
    """RGPD (art. 32) : l'alerte d'anomalie ne doit journaliser aucun extrait du CRH.

    Un CRH reel contient des donnees de sante identifiantes ; seules des metadonnees
    non identifiantes (longueur, empreinte non reversible) sont autorisees.
    """
    app.dependency_overrides[get_predictor] = lambda: FakePredictorSansDP()
    texte_sensible = "MARTIN Jeanne, nee le 12/03/1954 - CHU de Lille - Cardiologie - douleur thoracique"
    try:
        with TestClient(app) as c, caplog.at_level("WARNING", logger="model_api.monitoring"):
            r = c.post("/predict", json={"texte_crh": texte_sensible}, headers=HEADERS)
            assert r.status_code == 200
    finally:
        app.dependency_overrides.clear()

    journaux = "\n".join(rec.getMessage() for rec in caplog.records)
    assert journaux, "l'anomalie DP manquant doit produire une alerte journalisee"
    # Aucun fragment du CRH ne doit apparaitre dans les journaux.
    for fragment in ("MARTIN", "Jeanne", "12/03/1954", "Lille", "thoracique"):
        assert fragment not in journaux, f"fuite de donnee personnelle dans les journaux : {fragment}"
    # Les metadonnees non identifiantes, elles, doivent bien etre presentes.
    assert f"longueur_crh={len(texte_sensible)}" in journaux
    assert "empreinte=" in journaux
