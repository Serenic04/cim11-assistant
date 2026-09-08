"""Etape 3 de la chaine MLOps (C12/C13) — validation du modele avant livraison.

Cette etape joue le role de "garde-fou qualite" : elle s'execute apres l'entrainement
et avant le packaging, et fait echouer la chaine si le modele produit ne remplit pas
les conditions minimales. C'est ce qui evite de livrer en production un adaptateur
degrade sans que personne ne s'en apercoive.

Deux familles de controles :

  A. Integrite de l'artefact entraine (Fine-Tuning/llama3_codage_cim11/) —
     l'adaptateur LoRA doit etre configure comme prevu : modele de base attendu,
     modules cibles, rang et alpha. Un adaptateur entraine sur un autre modele de
     base serait silencieusement inutilisable en inference.
     Les poids binaires eux-memes (adapter_model.safetensors, ~13 Mo) sont exclus
     du depot : leur absence est signalee, pas bloquante (cf. controler_artefact).

  B. Non-regression des performances mesurees (Fine-Tuning/resultats_comparaison.json) —
     le modele fine-tune doit rester au-dessus des seuils definis ET rester meilleur
     que le modele de base. Ces seuils sont volontairement fixes en dessous des
     performances mesurees, pour laisser une marge de variation normale tout en
     bloquant une degradation reelle.

Usage :
    python -m mlops.validate_model

Code de sortie 0 si le modele est validé, 1 sinon (bloque la livraison).
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ADAPTATEUR = RACINE / "Fine-Tuning" / "llama3_codage_cim11"
RESULTATS = RACINE / "Fine-Tuning" / "resultats_comparaison.json"

# Configuration attendue de l'adaptateur (cf. R2 §5 — parametrage du service).
BASE_ATTENDUE = "meta-llama/Meta-Llama-3-8B-Instruct"
MODULES_ATTENDUS = {"q_proj", "v_proj"}
RANG_ATTENDU = 16
ALPHA_ATTENDU = 32

# Seuils de non-regression, en lecture souple (code racine) — mesures : F1 0,737 / EM 0,667.
SEUIL_F1_SOUPLE = 0.70
SEUIL_EXACT_MATCH_SOUPLE = 0.60

# Taille minimale plausible pour les poids : l'adaptateur livre pese environ 13 Mo.
# Un fichier de quelques octets traduit une copie interrompue ou un artefact tronque.
TAILLE_MIN_POIDS_OCTETS = 1024


def controler_artefact() -> list[str]:
    """Controle la coherence de l'adaptateur LoRA livre.

    Les poids binaires (adapter_model.safetensors, ~13 Mo) sont deliberement tenus
    hors du depot, comme tout artefact volumineux : ils sont exclus par .gitignore et
    recuperes separement. Un environnement d'integration continue, qui part d'un clone
    neuf, ne peut donc pas controler leur presence — l'exiger produirait un echec
    systematique sans rapport avec la qualite du modele. Leur absence est signalee par
    un avertissement, et le controle de leur presence releve de l'etape de packaging,
    la ou l'artefact complet est assemble.

    Restent bloquants, parce qu'ils portent sur des fichiers versionnes donc
    verifiables partout :
      - la coherence de adapter_config.json — modele de base, modules cibles, rang,
        alpha : un adaptateur entraine sur une autre base serait inutilisable ;
      - l'integrite des poids lorsqu'ils sont presents — un fichier vide ou tronque
        est un artefact inutilisable et doit faire echouer la chaine.
    """
    erreurs: list[str] = []
    config = ADAPTATEUR / "adapter_config.json"
    poids = ADAPTATEUR / "adapter_model.safetensors"

    if not config.exists():
        return [f"adapter_config.json introuvable dans {ADAPTATEUR}"]

    if not poids.exists():
        print(f"  AVERTISSEMENT : {poids.name} absent — artefact binaire hors depot "
              "(.gitignore). Seule la configuration de l'adaptateur est controlee ici.")
    elif poids.stat().st_size < TAILLE_MIN_POIDS_OCTETS:
        erreurs.append(f"{poids.name} present mais vide ou tronque "
                       f"({poids.stat().st_size} octets) : artefact inutilisable")

    cfg = json.loads(config.read_text(encoding="utf-8"))
    if cfg.get("base_model_name_or_path") != BASE_ATTENDUE:
        erreurs.append(f"modele de base inattendu : {cfg.get('base_model_name_or_path')!r} (attendu {BASE_ATTENDUE!r})")
    modules = set(cfg.get("target_modules") or [])
    if modules != MODULES_ATTENDUS:
        erreurs.append(f"modules cibles LoRA inattendus : {sorted(modules)} (attendu {sorted(MODULES_ATTENDUS)})")
    if cfg.get("r") != RANG_ATTENDU:
        erreurs.append(f"rang LoRA inattendu : {cfg.get('r')} (attendu {RANG_ATTENDU})")
    if cfg.get("lora_alpha") != ALPHA_ATTENDU:
        erreurs.append(f"alpha LoRA inattendu : {cfg.get('lora_alpha')} (attendu {ALPHA_ATTENDU})")
    return erreurs


def controler_performances() -> list[str]:
    if not RESULTATS.exists():
        return [f"resultats d'evaluation introuvables : {RESULTATS}"]

    donnees = json.loads(RESULTATS.read_text(encoding="utf-8"))
    bloc = next(iter(donnees.values()))
    base = bloc["base"]["souple"]
    finetune = bloc["finetuned"]["souple"]

    erreurs: list[str] = []
    if finetune["f1"] < SEUIL_F1_SOUPLE:
        erreurs.append(f"F1 souple {finetune['f1']} < seuil {SEUIL_F1_SOUPLE}")
    if finetune["exact_match"] < SEUIL_EXACT_MATCH_SOUPLE:
        erreurs.append(f"exact match souple {finetune['exact_match']} < seuil {SEUIL_EXACT_MATCH_SOUPLE}")
    if finetune["f1"] <= base["f1"]:
        erreurs.append(f"le fine-tuning n'apporte rien : F1 {finetune['f1']} <= base {base['f1']}")

    print(f"  F1 souple          : {base['f1']} (base) -> {finetune['f1']} (fine-tune), seuil {SEUIL_F1_SOUPLE}")
    print(f"  Exact match souple : {base['exact_match']} (base) -> {finetune['exact_match']} (fine-tune), "
          f"seuil {SEUIL_EXACT_MATCH_SOUPLE}")
    print(f"  Jeu d'evaluation   : {bloc['n_sejours_eval']} sejours, {bloc['n_lignes_eval']} diagnostics")
    return erreurs


def main() -> int:
    print("A. Integrite de l'adaptateur entraine")
    erreurs = controler_artefact()
    if not erreurs:
        print("  adaptateur LoRA conforme (base, modules cibles, rang, alpha)")

    print("B. Non-regression des performances mesurees")
    erreurs += controler_performances()

    if erreurs:
        print(f"\nVALIDATION DU MODELE : ECHEC ({len(erreurs)} erreur(s))")
        for e in erreurs:
            print("  -", e)
        return 1

    print("\nVALIDATION DU MODELE : OK — artefact conforme et performances au-dessus des seuils.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
