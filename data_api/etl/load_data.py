"""ETL — charge les données réelles du stage AP-HP dans la base PostgreSQL.

Sources (voir docs/MCD_MLD.md) :
  - Fine-Tuning/data/finetune_train.jsonl        -> patient_fictif, sejour, crh, diagnostic
  - api/data/cim11_termes.csv                    -> code_cim11
  - Recherche_Synonymes_CIM10/synonymes.csv      -> synonyme
  - api/verif_postcoord/data/codes_postcoord_realistes_v2.csv -> code_postcoord
  - api/postcoord_reference/data/axes_par_code.csv -> axe_postcoord

N'utilise que la bibliotheque standard (csv, json) pour la lecture des fichiers,
volontairement, afin de ne pas dependre d'un paquet necessitant une compilation
native (pandas a pose probleme sur certains environnements Windows sans outils
de compilation C++ installes).

Usage :
    set SERENIC_M_DIR=C:\\Users\\mohan\\Desktop\\stage_aphp\\Serenic_M   (Windows, cmd)
    $env:SERENIC_M_DIR="C:\\Users\\mohan\\Desktop\\stage_aphp\\Serenic_M" (PowerShell)
    set DATABASE_URL=postgresql://user:pwd@localhost:5432/cim11
    python -m etl.load_data --limit-referentiel 5000   # --limit-referentiel 0 = tout charger
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.database import engine, SessionLocal, Base  # noqa: E402
from app import models  # noqa: E402

SERENIC_M_DIR = Path(os.getenv("SERENIC_M_DIR", r"C:\Users\mohan\Desktop\stage_aphp\Serenic_M"))

# Un code CIM-11 "racine", optionnellement suivi d'une ou plusieurs extensions de
# post-coordination separees par '&' (voir docs/E5_incident_monitorage.md).
_CODE_PART = r"[A-Z0-9]{2,10}(?:\.[A-Z0-9]+)?"
CODE_RE = rf"{_CODE_PART}(?:&{_CODE_PART})*"
DIAG_RE = re.compile(rf"([^(]+?)\s*\(({CODE_RE})\)")

BATCH_SIZE = 5000


def parse_assistant_reply(reply: str) -> list[dict]:
    """Extrait les couples (libellé, code) depuis une réponse 'DP : ... / DAS : ...'."""
    diags = []
    dp_part, _, das_part = reply.partition("DAS :")
    # Isole le texte apres le marqueur "DP :" (sinon le libelle est prefixe de "DP : ").
    _, _, dp_text = dp_part.partition("DP :")
    dp_text = dp_text or dp_part
    dp_match = DIAG_RE.search(dp_text)
    if dp_match:
        diags.append({"type_diag": "DP", "libelle": dp_match.group(1).strip(), "code": dp_match.group(2).strip()})
    if das_part and "aucun" not in das_part.lower():
        for m in DIAG_RE.finditer(das_part):
            libelle = m.group(1).strip().lstrip(",").strip()
            diags.append({"type_diag": "DAS", "libelle": libelle, "code": m.group(2).strip()})
    return diags


def _read_csv_rows(path: Path, delimiter: str = ","):
    """Lit un CSV volumineux ligne a ligne (pas de chargement complet en memoire)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=delimiter)


def _bulk_insert(conn, table, rows: list[dict]):
    if rows:
        conn.execute(table.insert(), rows)


def load_referentiel_codes(conn, limit: int) -> set:
    path = SERENIC_M_DIR / "api" / "data" / "cim11_termes.csv"
    table = models.CodeCim11.__table__
    seen = set()
    batch = []
    count = 0
    for row in _read_csv_rows(path):
        code = row["code"]
        if code in seen:
            continue
        seen.add(code)
        batch.append({"code": code, "libelle": row["texte"], "type": row.get("type")})
        count += 1
        if len(batch) >= BATCH_SIZE:
            _bulk_insert(conn, table, batch)
            batch = []
        if limit and count >= limit:
            break
    _bulk_insert(conn, table, batch)
    print(f"code_cim11 : {count} lignes chargées")
    return seen


def _load_mapping_cim10_to_cim11() -> dict:
    """Charge la table de correspondance officielle OMS CIM-10 -> CIM-11.

    Le fichier source est 10To11MapToOneCategory.xlsx (mapping OMS, deja
    utilise dans generation_crh/CIM_11_generate_scenarios_final_v2.ipynb pour
    transcoder les CRH d'entrainement). Converti une fois en CSV simple
    (cim10_to_cim11_mapping.csv, colonnes icd10Code/icd11Code) pour eviter une
    dependance a pandas/openpyxl dans ce script (voir docstring du module).
    """
    path = Path(__file__).resolve().parent / "cim10_to_cim11_mapping.csv"
    mapping = {}
    for row in _read_csv_rows(path):
        mapping[row["icd10Code"]] = row["icd11Code"]
    return mapping


def load_synonymes(conn, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "Recherche_Synonymes_CIM10" / "synonymes.csv"
    table = models.Synonyme.__table__
    mapping_10_11 = _load_mapping_cim10_to_cim11()
    batch = []
    count = 0
    n_non_mappes = 0
    for row in _read_csv_rows(path, delimiter=";"):
        # Les codes du fichier synonymes sont en CIM-10 (dictionnaire du stage) ;
        # on les traduit en CIM-11 avant de verifier le referentiel.
        code_cim11 = mapping_10_11.get(row["code"])
        if code_cim11 is None or code_cim11 not in valid_codes:
            n_non_mappes += 1
            continue
        batch.append({"code_cim11": code_cim11, "synonyme": row["synonyme"], "source": row.get("source")})
        count += 1
        if len(batch) >= BATCH_SIZE:
            _bulk_insert(conn, table, batch)
            batch = []
        if limit and count >= limit:
            break
    _bulk_insert(conn, table, batch)
    print(f"synonyme : {count} lignes chargées ({n_non_mappes} codes CIM-10 non traduits ou hors référentiel)")


def load_postcoord(conn, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "api" / "verif_postcoord" / "data" / "codes_postcoord_realistes_v2.csv"
    table = models.CodePostcoord.__table__
    seen = set()
    batch = []
    count = 0
    for row in _read_csv_rows(path):
        if row["code_racine"] not in valid_codes:
            continue
        cp = row["code_postcoord"]
        if cp in seen:
            continue
        seen.add(cp)
        batch.append(
            {
                "code_postcoord": cp,
                "code_racine": row["code_racine"],
                "libelles_extensions": row.get("libelles_extensions"),
            }
        )
        count += 1
        if len(batch) >= BATCH_SIZE:
            _bulk_insert(conn, table, batch)
            batch = []
        if limit and count >= limit:
            break
    _bulk_insert(conn, table, batch)
    print(f"code_postcoord : {count} lignes chargées")


def load_axes(conn, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "api" / "postcoord_reference" / "data" / "axes_par_code.csv"
    table = models.AxePostcoord.__table__
    batch = []
    count = 0
    for row in _read_csv_rows(path):
        if row["code"] not in valid_codes:
            continue
        batch.append(
            {
                "code_cim11": row["code"],
                "axe_nom": row["axe_nom"],
                "allow_multiple": row.get("allow_multiple"),
                "taille_axe": int(row["taille_axe"]) if row.get("taille_axe") else None,
                "raison_arret": row.get("raison_arret") or None,
            }
        )
        count += 1
        if len(batch) >= BATCH_SIZE:
            _bulk_insert(conn, table, batch)
            batch = []
        if limit and count >= limit:
            break
    _bulk_insert(conn, table, batch)
    print(f"axe_postcoord : {count} lignes chargées")


def load_crh(db, valid_codes: set):
    path = SERENIC_M_DIR / "Fine-Tuning" / "data" / "finetune_train.jsonl"
    n_crh, n_diag, n_skipped = 0, 0, 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            obj = json.loads(line)
            user_msg = next(m["content"] for m in obj["messages"] if m["role"] == "user")
            reply = next(m["content"] for m in obj["messages"] if m["role"] == "assistant")
            diags = parse_assistant_reply(reply)

            patient = models.PatientFictif(nom=f"Fictif{i}", prenom="Synthetique", sexe="9")
            sejour = models.Sejour(patient=patient, specialite_medicale="Non renseigne")
            crh = models.Crh(sejour=sejour, texte_crh=user_msg)
            for d in diags:
                if d["code"] not in valid_codes:
                    n_skipped += 1
                    continue
                crh.diagnostics.append(
                    models.Diagnostic(type_diag=d["type_diag"], code_cim11=d["code"], libelle_saisi=d["libelle"])
                )
                n_diag += 1
            db.add(crh)
            n_crh += 1
    db.commit()
    print(f"crh : {n_crh} CRH, {n_diag} diagnostics charges ({n_skipped} codes hors referentiel ignores)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-referentiel", type=int, default=20000, help="0 = charger tout le referentiel")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        valid_codes = load_referentiel_codes(conn, args.limit_referentiel)
        load_synonymes(conn, valid_codes, args.limit_referentiel)
        load_postcoord(conn, valid_codes, args.limit_referentiel)
        load_axes(conn, valid_codes, args.limit_referentiel)

    db = SessionLocal()
    try:
        load_crh(db, valid_codes)
    finally:
        db.close()


if __name__ == "__main__":
    main()
