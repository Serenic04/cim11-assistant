"""Test de la requete SQL d'extraction depuis le SGBD (C2 - etl/extraction_sql/extract_sgbd.py).

Utilise une base SQLite en memoire peuplee via les memes modeles SQLAlchemy
que l'API (pas de Postgres necessaire en CI) pour verifier que la requete SQL
brute (JOIN + GROUP BY + HAVING) renvoie bien le resultat attendu.
"""
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data_api"))

from app.database import Base  # noqa: E402
from app import models  # noqa: E402
from etl.extraction_sql.extract_sgbd import EXTRACTION_SQL  # noqa: E402


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return engine, Session()


def test_extraction_sgbd_ne_retient_que_les_codes_avec_synonyme_et_postcoord():
    engine, db = _build_session()

    # Code A : synonyme + postcoord + diagnostic DP -> doit apparaitre
    code_a = models.CodeCim11(code="1A00", libelle="Cholera", type="racine")
    # Code B : diagnostic DP mais AUCUN synonyme ni postcoord -> ne doit pas apparaitre
    code_b = models.CodeCim11(code="2B00", libelle="Autre pathologie", type="racine")
    db.add_all([code_a, code_b])
    db.flush()

    db.add(models.Synonyme(code_cim11="1A00", synonyme="Choléra", source="test"))
    db.add(models.CodePostcoord(code_postcoord="1A00&XA1234", code_racine="1A00", libelles_extensions="ext"))

    patient = models.PatientFictif(nom="Test", prenom="Test", sexe="9")
    sejour = models.Sejour(patient=patient, specialite_medicale="Test")
    crh_a = models.Crh(sejour=sejour, texte_crh="CRH mentionnant le choléra")
    crh_a.diagnostics.append(models.Diagnostic(type_diag="DP", code_cim11="1A00", libelle_saisi="Choléra"))

    sejour_b = models.Sejour(patient=patient, specialite_medicale="Test")
    crh_b = models.Crh(sejour=sejour_b, texte_crh="CRH sans synonyme/postcoord")
    crh_b.diagnostics.append(models.Diagnostic(type_diag="DP", code_cim11="2B00", libelle_saisi="Autre"))

    db.add_all([crh_a, crh_b])
    db.commit()

    with engine.connect() as conn:
        rows = conn.execute(text(EXTRACTION_SQL), {"limit": 10}).mappings().all()

    codes = [r["code_cim11"] for r in rows]
    assert "1A00" in codes
    assert "2B00" not in codes

    row_a = next(r for r in rows if r["code_cim11"] == "1A00")
    assert row_a["nb_synonymes"] == 1
    assert row_a["nb_postcoord"] == 1
    assert "choléra" in row_a["exemple_crh"].lower()
