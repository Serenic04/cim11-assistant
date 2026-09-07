"""Extraction SQL depuis le systeme de gestion de base de donnees (C2 - RNCP 37827).

Contexte
--------
La base cible est celle deja peuplee par etl/load_data.py (PostgreSQL en
production, SQLite en local/CI - voir app/database.py). Ce script n'utilise PAS
l'ORM (SQLAlchemy select()/Query) : il ecrit et execute des requetes SQL brutes
(via sqlalchemy.text) pour repondre a un besoin metier reel du projet :

    "Pour chaque code CIM-11 du referentiel qui possede a la fois des
    synonymes ET des variantes de post-coordination connues, extraire son
    libelle, le nombre de synonymes, le nombre de combinaisons
    post-coordonnees, et un CRH reel ou ce code apparait comme diagnostic
    principal (DP), afin de constituer un jeu de "codes bien documentes"
    prioritaires pour le controle qualite manuel du referentiel."

Choix de la requete
--------------------
- 2 LEFT JOIN (synonyme, code_postcoord) + 1 JOIN (diagnostic -> crh) sur
  code_cim11, agreges par GROUP BY code_cim11.code.
- Filtre HAVING nb_synonymes > 0 AND nb_postcoord > 0 : ne garde que les codes
  "bien documentes" (le referentiel complet a 34 663 codes distincts, la
  plupart sans synonyme charge - voir docs/MCD_MLD.md).
- Filtre WHERE diagnostic.type_diag = 'DP' : on ne veut que les diagnostics
  principaux, pas les diagnostics associes (DAS), pour rester sur le cas
  d'usage prioritaire.
- ORDER BY nb_postcoord DESC : priorise les codes les plus complexes
  (les plus susceptibles de contenir une erreur de post-coordination).
- LIMIT parametrable (defaut 50) : evite de charger un resultat inutilement
  volumineux en memoire cote client - la requete elle-meme fait tout le
  filtrage/tri cote base, seule la restitution finale est bornee.

Optimisation
------------
code_cim11.code est cle primaire (donc indexee) : les JOIN dessus sont directs.
Le filtrage HAVING est applique APRES l'agregation (necessaire, car il porte
sur des fonctions d'agregation COUNT()) mais AVANT le tri et la limite, ce qui
minimise le volume trie.

Usage
-----
    export DATABASE_URL=postgresql://user:pwd@localhost:5432/cim11   # ou sqlite:///./data-api-local.db
    python -m etl.extraction_sql.extract_sgbd --limit 50 --out extraction_codes_documentes.csv
"""
import argparse
import csv
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

EXTRACTION_SQL = """
SELECT
    c.code                              AS code_cim11,
    c.libelle                           AS libelle,
    COUNT(DISTINCT s.id_synonyme)       AS nb_synonymes,
    COUNT(DISTINCT p.code_postcoord)    AS nb_postcoord,
    MIN(crh.texte_crh)                  AS exemple_crh
FROM code_cim11 c
JOIN diagnostic d       ON d.code_cim11 = c.code AND d.type_diag = 'DP'
JOIN crh                ON crh.id_crh = d.id_crh
LEFT JOIN synonyme s    ON s.code_cim11 = c.code
LEFT JOIN code_postcoord p ON p.code_racine = c.code
GROUP BY c.code, c.libelle
HAVING COUNT(DISTINCT s.id_synonyme) > 0
   AND COUNT(DISTINCT p.code_postcoord) > 0
ORDER BY nb_postcoord DESC
LIMIT :limit
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default="extraction_codes_documentes.csv")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "sqlite:///./data-api-local.db")
    engine = create_engine(database_url)

    with engine.connect() as conn:
        result = conn.execute(text(EXTRACTION_SQL), {"limit": args.limit})
        rows = result.mappings().all()

    out_path = Path(args.out)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code_cim11", "libelle", "nb_synonymes", "nb_postcoord", "exemple_crh"])
        for row in rows:
            writer.writerow([row["code_cim11"], row["libelle"], row["nb_synonymes"], row["nb_postcoord"], row["exemple_crh"]])

    print(f"{len(rows)} lignes extraites -> {out_path}")
    if rows:
        print("Aperçu de la 1re ligne :", dict(rows[0]))
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
