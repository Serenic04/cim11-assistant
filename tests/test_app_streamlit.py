"""Test de fumee de l'application Streamlit (E4) — requests mocke, pas d'appel reseau reel."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "app_streamlit" / "app.py")


def _fake_response(json_body, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


def test_app_loads_without_error():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception


def test_predict_button_disabled_when_empty():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert at.button[0].disabled is True


@patch("app_streamlit.app.requests.get")
@patch("app_streamlit.app.requests.post")
def test_predict_flow(mock_post, mock_get):
    mock_post.return_value = _fake_response(
        {
            "dp": {"libelle": "Fracture du col du femur", "code": "NC72.2Z"},
            "das": [],
            "latence_ms": 42.0,
            "modele": "fake-model",
        }
    )
    mock_get.return_value = _fake_response({"code": "NC72.2Z", "libelle": "Fracture du col du femur, sans precision"})

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.text_area[0].input("Patient admis pour fracture du col du femur.").run()
    at.button[0].click().run()

    assert not at.exception
    assert any("Fracture du col du femur" in md.value for md in at.markdown)
