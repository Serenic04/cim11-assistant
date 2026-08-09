"""Parsing de la reponse du modele — partage la meme logique que data_api/etl/load_data.py
(format attendu : 'DP : Libelle (CODE)\\nDAS : Libelle (CODE), ...').

Historique : voir docs/E5_incident_monitorage.md — le motif de code a ete etendu pour
couvrir les codes CIM-11 post-coordonnes (ex. '1A62.2&XA6GV0'), initialement non
reconnus et donc silencieusement ignores (incident E5).
"""
import re

# Un code CIM-11 "racine", optionnellement suivi d'une ou plusieurs extensions de
# post-coordination separees par '&' (ex. '1A62.2&XA6GV0&XA3KX0').
_CODE_PART = r"[A-Z0-9]{2,10}(?:\.[A-Z0-9]+)?"
CODE_RE = rf"{_CODE_PART}(?:&{_CODE_PART})*"
DIAG_RE = re.compile(rf"([^(]+?)\s*\(({CODE_RE})\)")


def parse_model_reply(reply: str) -> dict:
    dp = None
    das = []
    dp_part, _, das_part = reply.partition("DAS :")
    # Isole le texte apres le marqueur "DP :" pour ne pas capturer le label lui-meme
    # (sinon le libelle du DP se retrouve prefixe de "DP : ", cf. docs/E5_incident_monitorage.md).
    _, _, dp_text = dp_part.partition("DP :")
    dp_text = dp_text or dp_part

    dp_match = DIAG_RE.search(dp_text)
    if dp_match:
        dp = {"libelle": dp_match.group(1).strip(), "code": dp_match.group(2).strip()}

    if das_part and "aucun" not in das_part.lower():
        for m in DIAG_RE.finditer(das_part):
            # Le separateur ", " entre deux items DAS peut se retrouver colle au
            # libelle suivant (le motif autorise desormais la virgule pour capturer
            # les libelles du type "..., sans precision") : on le retire explicitement.
            libelle = m.group(1).strip().lstrip(",").strip()
            das.append({"libelle": libelle, "code": m.group(2).strip()})

    return {"dp": dp, "das": das}
