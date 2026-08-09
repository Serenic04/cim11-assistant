"""Non-regression E5 pour le parseur utilise par l'ETL (data_api/etl/load_data.py) —
meme incident, meme correction, que model_api/app/parsing.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data_api"))

from etl.load_data import parse_assistant_reply


def test_etl_parses_libelle_with_comma_and_postcoordinated_code():
    reply = (
        "DP : Syphilis tardive symptomatique, sans précision (1A62.2&XA6GV0)\n"
        "DAS : Dénutrition, sans précision (5B7Z)"
    )
    diags = parse_assistant_reply(reply)
    assert diags[0] == {
        "type_diag": "DP",
        "libelle": "Syphilis tardive symptomatique, sans précision",
        "code": "1A62.2&XA6GV0",
    }
    assert diags[1]["code"] == "5B7Z"
