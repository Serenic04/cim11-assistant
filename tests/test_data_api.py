"""Tests automatises de l'API dataset (C12 / C18) — base SQLite en memoire, echantillon reduit.

Objectif : ces tests s'executent en quelques secondes dans la CI (pas de dependance
a PostgreSQL ni aux fichiers volumineux du stage), conformement a la strategie
"petit echantillon" retenue pour que la chaine d'integration continue reste rapide.
"""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_API_KEY"] = "test-key"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from data_api.app import models  # noqa: E402
from data_api.app.database import Base, get_db
from data_api.app.main import app

HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    code = models.CodeCim11(code="NC72.2Z", libelle="Fracture du col du femur, sans precision", type="title")
    db.add(code)
    db.add(models.Synonyme(code_cim11="NC72.2Z", synonyme="fracture col femoral", source="test"))
    patient = models.PatientFictif(nom="Test", prenom="Patient", sexe="1")
    sejour = models.Sejour(patient=patient, specialite_medicale="ORTHOPEDIE")
    crh = models.Crh(sejour=sejour, texte_crh="CRH de test")
    crh.diagnostics.append(models.Diagnostic(type_diag="DP", code_cim11="NC72.2Z"))
    db.add(crh)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_auth_required(client):
    r = client.get("/codes")
    assert r.status_code == 401


def test_list_codes(client):
    r = client.get("/codes", headers=HEADERS)
    assert r.status_code == 200
    codes = [c["code"] for c in r.json()]
    assert "NC72.2Z" in codes


def test_get_code_detail(client):
    r = client.get("/codes/NC72.2Z", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["libelle"].startswith("Fracture")
    assert len(body["synonymes"]) == 1


def test_get_code_not_found(client):
    r = client.get("/codes/INCONNU", headers=HEADERS)
    assert r.status_code == 404


def test_get_crh_detail(client):
    """Couverture du dernier point de terminaison : GET /crh/{id_crh} (nominal + 404)."""
    r = client.get("/crh/1", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["id_crh"] == 1
    assert body["texte_crh"] == "CRH de test"
    assert body["diagnostics"][0]["code_cim11"] == "NC72.2Z"

    assert client.get("/crh/9999", headers=HEADERS).status_code == 404
    assert client.get("/crh/1").status_code == 401


def test_list_and_create_crh(client):
    r = client.get("/crh", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 1

    payload = {
        "id_sejour": 1,
        "texte_crh": "Nouveau CRH de test",
        "diagnostics": [{"type_diag": "DP", "code_cim11": "NC72.2Z"}],
    }
    r = client.post("/crh", json=payload, headers=HEADERS)
    assert r.status_code == 201
    assert r.json()["texte_crh"] == "Nouveau CRH de test"
