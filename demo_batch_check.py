"""Mesure de bout en bout de model_api sur des CRH reels du corpus.

Contrairement a l'evaluation du fine-tuning (menee dans Colab, directement sur le
modele), ce script interroge l'API telle qu'elle est deployee : gabarit de prompt,
parsing de la reponse et exposition HTTP compris. Il verifie donc la chaine complete,
pas seulement le modele.

Deux niveaux de comparaison, identiques a ceux du rapport E2 :
  - strict : le code predit doit etre exactement celui de reference ;
  - souple : on ne compare que le code racine, extensions de post-coordination exclues.

Usage :
    python demo_batch_check.py https://xxxx.trycloudflare.com
    python demo_batch_check.py http://localhost:8001 --nombre 5
"""
import argparse
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent
BASE = RACINE / "data_api" / "data-api-local.db"
CLE_API = "demo-key-portfolio"


def racine_code(code: str) -> str:
    """Code racine : partie precedant les extensions de post-coordination."""
    return (code or "").split("&")[0].strip().upper()


def normaliser(libelle: str) -> str:
    """Minuscules sans accents ni ponctuation, pour comparer des libelles."""
    s = unicodedata.normalize("NFKD", libelle or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def charger_cas(limite: int) -> list[dict]:
    """Un CRH par code de DP distinct.

    Le corpus contient plusieurs comptes rendus pour un meme diagnostic : les prendre
    par ordre de longueur donnerait un echantillon domine par deux ou trois pathologies
    et un taux de reussite non representatif. On ne garde donc qu'un cas par code.
    """
    cx = sqlite3.connect(BASE)
    cx.row_factory = sqlite3.Row
    lignes = cx.execute(
        """
        SELECT c.id_crh, c.texte_crh, d.code_cim11 AS code_dp, r.libelle AS libelle_dp
        FROM crh c
        JOIN diagnostic d ON d.id_crh = c.id_crh AND d.type_diag = 'DP'
        LEFT JOIN code_cim11 r ON r.code = d.code_cim11
        WHERE length(c.texte_crh) BETWEEN 2500 AND 9000
        GROUP BY d.code_cim11
        ORDER BY length(c.texte_crh)
        LIMIT ?
        """,
        (limite,),
    ).fetchall()
    cx.close()
    return [dict(ligne) for ligne in lignes]


def nettoyer(texte: str) -> str:
    """Retire l'enrobage de prompt stocke dans le corpus : l'API ajoute le sien."""
    texte = re.sub(
        r"^.*?compte rendu d'hospitalisation à coder en CIM-11\s*:\s*\n+-*\n?",
        "", texte, flags=re.S)
    texte = re.sub(r"\n-+\n*\s*Propose le codage CIM-11.*$", "", texte, flags=re.S)
    texte = re.sub(r"^Le compte rendu suivant respecte.*?-{10,}\n", "", texte, flags=re.S)
    return texte.strip()


def interroger(url: str, texte: str, delai: int) -> dict | None:
    reponse = requests.post(
        f"{url.rstrip('/')}/predict",
        json={"texte_crh": texte},
        headers={"X-API-Key": CLE_API},
        timeout=delai,
    )
    reponse.raise_for_status()
    return reponse.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL de model_api (tunnel Colab ou localhost)")
    parser.add_argument("--nombre", type=int, default=15)
    parser.add_argument("--delai", type=int, default=300)
    args = parser.parse_args()

    if not BASE.exists():
        print(f"ERREUR : base introuvable ({BASE})")
        return 1

    cas = charger_cas(args.nombre)
    print(f"{len(cas)} CRH du corpus, API : {args.url}\n")
    print(f"{'CRH':>5}  {'attendu':<12} {'predit':<16} {'racine':<8} {'libelle':<7} {'ms':>7}")
    print("-" * 62)

    exacts = souples = libelles = repondus = 0
    bons_cas = []
    debut = time.time()

    for c in cas:
        try:
            res = interroger(args.url, nettoyer(c["texte_crh"]), args.delai)
        except Exception as exc:
            print(f"{c['id_crh']:>5}  {c['code_dp']:<12} ECHEC : {type(exc).__name__}")
            continue

        dp = (res or {}).get("dp")
        if not dp:
            print(f"{c['id_crh']:>5}  {c['code_dp']:<12} {'(aucun DP)':<16}")
            continue

        repondus += 1
        code_attendu, code_predit = c["code_dp"], dp["code"]
        exact = code_predit.strip().upper() == code_attendu.strip().upper()
        souple = racine_code(code_predit) == racine_code(code_attendu)
        meme_libelle = (c["libelle_dp"] or "") and (
            normaliser(dp["libelle"]) == normaliser(c["libelle_dp"])
            or normaliser(c["libelle_dp"]) in normaliser(dp["libelle"]))

        exacts += exact
        souples += souple
        libelles += bool(meme_libelle)
        if exact:
            bons_cas.append(c["id_crh"])

        print(f"{c['id_crh']:>5}  {code_attendu:<12} {code_predit:<16} "
              f"{'oui' if souple else 'non':<8} {'oui' if meme_libelle else 'non':<7} "
              f"{res['latence_ms']:>7.0f}")

    n = len(cas)
    print("-" * 62)
    print(f"\n{n} CRH interroges en {time.time() - debut:.0f} s")
    print(f"  DP identifie            : {repondus}/{n}")
    print(f"  code exact              : {exacts}/{n}")
    print(f"  code racine correct     : {souples}/{n}")
    print(f"  libelle correct         : {libelles}/{n}")
    if bons_cas:
        print(f"\nCas ou le code est exact — a privilegier pour la demonstration : {bons_cas}")
    else:
        print("\nAucun code exact sur cet echantillon : presenter la verification "
              "croisee au referentiel comme le garde-fou, plutot que viser le sans-faute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
