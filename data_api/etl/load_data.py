"""ETL — charge les données réelles du stage AP-HP dans la base PostgreSQL.

Sources (voir docs/MCD_MLD.md) :
  - Fine-Tuning/data/finetune_train.jsonl        -> patient_fictif, sejour, crh, diagnostic
  - api/data/cim11_termes.csv                    -> code_cim11
  - Recherche_Synonymes_CIM10/synonymes.csv      -> synonyme
  - api/verif_postcoord/data/codes_postcoord_realistes_v2.csv -> code_postcoord
  - api/postcoord_reference/data/axes_par_code.csv -> axe_postcoord

Usage :
    set SERENIC_M_DIR=C:\\Users\\mohan\\Desktop\\stage_aphp\\Serenic_M   (Windows, cmd)
    $env:SERENIC_M_DIR="C:\\Users\\mohan\\Desktop\\stage_aphp\\Serenic_M" (PowerShell)
    set DATABASE_URL=postgresql://user:pwd@localhost:5432/cim11
    python -m etl.load_data --limit-referentiel 5000   # --limit-referentiel 0 = tout charger
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.database import engine, SessionLocal, Base  # noqa: E402
from app import models  # noqa: E402

SERENIC_M_DIR = Path(os.getenv("SERENIC_M_DIR", r"C:\Users\mohan\Desktop\stage_aphp\Serenic_M"))

# Un code CIM-11 "racine", optionnellement suivi d'une ou plusieurs extensions de
# post-coordination separees par '&' (voir docs/E5_incident_monitorage.md).
_CODE_PART = r"[A-Z0-9]{2,10}(?:\.[A-Z0-9]+)?"
CODE_RE = rf"{_CODE_PART}(?:&{_CODE_PART})*"
DIAG_RE = re.compile(rf"([^(]+?)\s*\(({CODE_RE})\)")


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
            diags.append({"type_diag": "DAS", "libelle": m.group(1).strip(), "code": m.group(2).strip()})
    return diags


def load_referentiel_codes(db, limit: int):
    path = SERENIC_M_DIR / "api" / "data" / "cim11_termes.csv"
    df = pd.read_csv(path, usecols=["code", "texte", "type"])
    df = df.rename(columns={"texte": "libelle"}).drop_duplicates(subset="code")
    if limit:
        df = df.head(limit)
    df.to_sql("code_cim11", con=db.get_bind(), if_exists="append", index=False, chunksize=5000, method="multi")
    print(f"code_cim11 : {len(df)} lignes chargées")
    return set(df["code"])


def load_synonymes(db, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "Recherche_Synonymes_CIM10" / "synonymes.csv"
    df = pd.read_csv(path, sep=";")
    df = df.rename(columns={"code": "code_cim11"})
    df = df[df["code_cim11"].isin(valid_codes)]
    if limit:
        df = df.head(limit)
    df[["code_cim11", "synonyme", "source"]].to_sql(
        "synonyme", con=db.get_bind(), if_exists="append", index=False, chunksize=5000, method="multi"
    )
    print(f"synonyme : {len(df)} lignes chargées")


def load_postcoord(db, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "api" / "verif_postcoord" / "data" / "codes_postcoord_realistes_v2.csv"
    df = pd.read_csv(path)
    df = df.rename(columns={"code_racine": "code_racine", "libelles_extensions": "libelles_extensions"})
    df = df[df["code_racine"].isin(valid_codes)].drop_duplicates(subset="code_postcoord")
    if limit:
        df = df.head(limit)
    df[["code_postcoord", "code_racine", "libelles_extensions"]].to_sql(
        "code_postcoord", con=db.get_bind(), if_exists="append", index=False, chunksize=5000, method="multi"
    )
    print(f"code_postcoord : {len(df)} lignes chargées")


def load_axes(db, valid_codes: set, limit: int):
    path = SERENIC_M_DIR / "api" / "postcoord_reference" / "data" / "axes_par_code.csv"
    df = pd.read_csv(path)
    df = df.rename(columns={"code": "code_cim11"})
    df = df[df["code_cim11"].isin(valid_codes)]
    if limit:
        df = df.head(limit)
    df[["code_cim11", "axe_nom", "allow_multiple", "taille_axe", "raison_arret"]].to_sql(
        "axe_postcoord", con=db.get_bind(), if_exists="append", index=False, chunksize=5000, method="multi"
    )
    print(f"axe_postcoord : {len(df)} lignes chargées")


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
    db = SessionLocal()
    try:
        valid_codes = load_referentiel_codes(db, args.limit_referentiel)
        load_synonymes(db, valid_codes, args.limit_referentiel)
        load_postcoord(db, valid_codes, args.limit_referentiel)
        load_axes(db, valid_codes, args.limit_referentiel)
        load_crh(db, valid_codes)
    finally:
        db.close()


if __name__ == "__main__":
    main()
