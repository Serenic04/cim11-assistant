"""Tests du dashboard de monitorage (E5) — requests mocke, pas d'appel reseau reel."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest

PAGE_PATH = str(Path(__file__).resolve().parents[1] / "app_streamlit" / "pages" / "1_Monitoring.py")


def _connecte(at, role="responsable", identifiant="resp1"):
    """La page Monitoring est un espace protege : seul le profil responsable y accede."""
    at.session_state["utilisateur"] = {"identifiant": identifiant, "role": role}
    return at


def _fake_response(json_body, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


def test_dashboard_loads_without_error():
    at = _connecte(AppTest.from_file(PAGE_PATH))
    at.run(timeout=15)
    assert not at.exception


@patch("requests.get")
def test_dashboard_shows_services_down_when_unreachable(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("service indisponible")
    at = _connecte(AppTest.from_file(PAGE_PATH))
    at.run(timeout=15)
    assert not at.exception
    assert len(at.error) == 2  # data_api et model_api tous deux indisponibles


@patch("requests.get")
def test_dashboard_shows_metrics_when_services_up(mock_get):
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/health"):
            return _fake_response({"status": "ok"})
        if url.endswith("/metrics"):
            return _fake_response(
                {
                    "nb_requetes": 12,
                    "nb_erreurs": 0,
                    "latence_moyenne_ms": 123.4,
                    "latence_p95_ms": 200.0,
                    "fenetre_glissante": 12,
                    "nb_anomalies_dp_manquant": 0,
                }
            )
        raise AssertionError(f"URL inattendue: {url}")

    mock_get.side_effect = fake_get

    at = _connecte(AppTest.from_file(PAGE_PATH))
    at.run(timeout=15)

    assert not at.exception
    assert len(at.success) == 2  # data_api + model_api disponibles
    values = {m.label: m.value for m in at.metric}
    assert values["Requêtes totales"] == "12"
    assert values["Latence moyenne"] == "123.4 ms"
    assert values["Anomalies DP manquant"] == "0"


@patch("requests.get")
def test_dashboard_flags_dp_missing_anomaly(mock_get):
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/health"):
            return _fake_response({"status": "ok"})
        if url.endswith("/metrics"):
            return _fake_response(
                {
                    "nb_requetes": 5,
                    "nb_erreurs": 0,
                    "latence_moyenne_ms": 90.0,
                    "latence_p95_ms": 150.0,
                    "fenetre_glissante": 5,
                    "nb_anomalies_dp_manquant": 2,
                }
            )
        raise AssertionError(f"URL inattendue: {url}")

    mock_get.side_effect = fake_get

    at = _connecte(AppTest.from_file(PAGE_PATH))
    at.run(timeout=15)

    assert not at.exception
    assert len(at.warning) >= 1
    assert any("2 prédiction" in w.value for w in at.warning)


# --- Gestion des droits d'acces (C17) ---------------------------------------

def test_agent_ne_peut_pas_acceder_au_monitorage():
    """Un agent connecte doit se voir refuser cet espace reserve au responsable."""
    at = _connecte(AppTest.from_file(PAGE_PATH), role="agent", identifiant="agent1")
    at.run(timeout=15)
    assert not at.exception
    assert any("Accès refusé" in e.value for e in at.error)


def test_visiteur_non_connecte_voit_le_formulaire_de_connexion():
    at = AppTest.from_file(PAGE_PATH)
    at.run(timeout=15)
    assert not at.exception
    assert any("Connexion" in h.value for h in at.subheader)
