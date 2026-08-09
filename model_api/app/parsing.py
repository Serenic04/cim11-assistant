"""Parsing de la reponse du modele — partage la meme logique que data-api/etl/load_data.py
(format attendu : 'DP : Libelle (CODE)\\nDAS : Libelle (CODE), ...')."""
import re

DIAG_RE = re.compile(r"([^,(]+?)\s*\(([A-Z0-9]{3,10}(?:\.[A-Z0-9]+)?)\)")


def parse_model_reply(reply: str) -> dict:
    dp = None
    das = []
    dp_part, _, das_part = reply.partition("DAS :")

    dp_match = DIAG_RE.search(dp_part)
    if dp_match:
        dp = {"libelle": dp_match.group(1).strip(), "code": dp_match.group(2).strip()}

    if das_part and "aucun" not in das_part.lower():
        for m in DIAG_RE.finditer(das_part):
            das.append({"libelle": m.group(1).strip(), "code": m.group(2).strip()})

    return {"dp": dp, "das": das}
