"""Etape 1 de la chaine MLOps (C12/C13) — validation du jeu de donnees d'entrainement.

Cette etape s'execute AVANT tout entrainement : un jeu de donnees invalide doit faire
echouer la chaine immediatement, plutot que de produire un modele entraine sur des
donnees corrompues (principe du "fail fast" applique aux donnees).

Regles de validation appliquees :
  R1 — chaque ligne est un JSON valide contenant une cle "messages" ;
  R2 — chaque exemple contient exactement les trois roles system / user / assistant ;
  R3 — le message utilisateur (le CRH) n'est pas vide et depasse la longueur minimale
       acceptee par l'API du modele (voir model_api/app/schemas.py) ;
  R4 — la reponse attendue contient un Diagnostic Principal parsable par la meme
       expression reguliere que celle utilisee en production (model_api/app/parsing.py) —
       c'est ce controle qui aurait detecte l'incident documente en E5 ;
  R5 — aucun doublon exact de CRH (un meme compte rendu deux fois biaiserait
       l'apprentissage et fausserait l'evaluation).

Usage :
    python -m mlops.validate_dataset Fine-Tuning/data/sample_finetune_train.jsonl
    python -m mlops.validate_dataset <chemin>/finetune_train.jsonl --min-exemples 100

Code de sortie 0 si le jeu de donnees est valide, 1 sinon (bloque la chaine).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_api.app.parsing import parse_model_reply  # noqa: E402

LONGUEUR_MIN_CRH = 10
ROLES_ATTENDUS = ("system", "user", "assistant")


def valider(chemin: Path, min_exemples: int) -> list[str]:
    """Retourne la liste des erreurs detectees (liste vide = jeu de donnees valide)."""
    erreurs: list[str] = []
    vus: set[str] = set()
    n = 0

    with open(chemin, encoding="utf-8") as f:
        for num, ligne in enumerate(f, start=1):
            ligne = ligne.strip()
            if not ligne:
                continue
            n += 1

            # R1 — JSON valide, structure attendue
            try:
                obj = json.loads(ligne)
            except json.JSONDecodeError as exc:
                erreurs.append(f"ligne {num} : JSON invalide ({exc.msg})")
                continue
            if "messages" not in obj:
                erreurs.append(f"ligne {num} : cle 'messages' absente")
                continue

            # R2 — les trois roles attendus, dans l'ordre
            roles = tuple(m.get("role") for m in obj["messages"])
            if roles != ROLES_ATTENDUS:
                erreurs.append(f"ligne {num} : roles {roles} au lieu de {ROLES_ATTENDUS}")
                continue

            contenus = {m["role"]: m.get("content", "") for m in obj["messages"]}

            # R3 — CRH non vide et assez long pour etre accepte par l'API
            crh = contenus["user"].strip()
            if len(crh) < LONGUEUR_MIN_CRH:
                erreurs.append(f"ligne {num} : CRH trop court ({len(crh)} < {LONGUEUR_MIN_CRH} caracteres)")

            # R4 — la reponse attendue contient un DP parsable en production
            attendu = parse_model_reply(contenus["assistant"])
            if attendu.get("dp") is None:
                erreurs.append(f"ligne {num} : aucun Diagnostic Principal parsable dans la reponse attendue")

            # R5 — pas de doublon exact
            if crh in vus:
                erreurs.append(f"ligne {num} : CRH en doublon exact")
            vus.add(crh)

    if n < min_exemples:
        erreurs.append(f"jeu de donnees trop petit : {n} exemples (< {min_exemples} attendus)")

    print(f"{n} exemples analyses dans {chemin}")
    return erreurs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--min-exemples", type=int, default=10)
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"ERREUR : jeu de donnees introuvable : {args.dataset}")
        return 1

    erreurs = valider(args.dataset, args.min_exemples)
    if erreurs:
        print(f"\nVALIDATION DES DONNEES : ECHEC ({len(erreurs)} erreur(s))")
        for e in erreurs[:20]:
            print("  -", e)
        return 1

    print("VALIDATION DES DONNEES : OK — toutes les regles R1 a R5 sont respectees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
