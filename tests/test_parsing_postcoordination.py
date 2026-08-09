"""Non-regression de l'incident E5 (voir docs/E5_incident_monitorage.md) :
les codes CIM-11 post-coordonnes (avec extensions separees par '&') doivent
etre correctement extraits, et non plus silencieusement ignores.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_api.app.parsing import parse_model_reply


def test_simple_code_still_parsed():
    reply = "DP : Fracture du col du fémur, sans précision (NC72.2Z)\nDAS : aucun"
    result = parse_model_reply(reply)
    assert result["dp"] == {"libelle": "Fracture du col du fémur, sans précision", "code": "NC72.2Z"}
    assert result["das"] == []


def test_postcoordinated_code_with_one_extension():
    reply = "DP : Syphilis tardive symptomatique (1A62.2&XA6GV0)\nDAS : aucun"
    result = parse_model_reply(reply)
    assert result["dp"] is not None, "regression E5 : le DP post-coordonne ne doit pas etre perdu"
    assert result["dp"]["code"] == "1A62.2&XA6GV0"


def test_postcoordinated_code_with_multiple_extensions():
    reply = "DP : Chute accidentelle (1A62.2&XA6GV0&XA3KX0)\nDAS : aucun"
    result = parse_model_reply(reply)
    assert result["dp"]["code"] == "1A62.2&XA6GV0&XA3KX0"


def test_libelle_with_internal_comma_fully_captured():
    """Deuxieme regression trouvee en investiguant E5 : un libelle contenant une
    virgule (tres frequent en francais medical, ex. 'sans precision') ne doit pas
    etre tronque."""
    reply = "DP : Fracture du col du fémur, sans précision (NC72.2Z)\nDAS : aucun"
    result = parse_model_reply(reply)
    assert result["dp"]["libelle"] == "Fracture du col du fémur, sans précision"


def test_das_with_postcoordinated_code():
    reply = (
        "DP : Fracture du col du fémur (NC72.2Z)\n"
        "DAS : Syphilis tardive symptomatique (1A62.2&XA6GV0), Dénutrition (5B7Z)"
    )
    result = parse_model_reply(reply)
    assert len(result["das"]) == 2
    assert result["das"][0]["code"] == "1A62.2&XA6GV0"
    assert result["das"][1]["code"] == "5B7Z"


def test_das_list_no_leading_comma_artifact():
    """Regression trouvee en validant l'ETL sur les vraies donnees du stage : le
    separateur ', ' entre deux items DAS ne doit pas se retrouver colle au libelle
    de l'item suivant."""
    reply = (
        "DP : Fracture du col du fémur (NC72.2Z)\n"
        "DAS : Dénutrition, sans précision (5B7Z), Carence en vitamine D, sans précision (5B57.Z), "
        "Candidose des lèvres ou de la muqueuse buccale (1F23.0)"
    )
    result = parse_model_reply(reply)
    libelles = [d["libelle"] for d in result["das"]]
    assert libelles == [
        "Dénutrition, sans précision",
        "Carence en vitamine D, sans précision",
        "Candidose des lèvres ou de la muqueuse buccale",
    ]
    assert all(not lib.startswith(",") for lib in libelles)
