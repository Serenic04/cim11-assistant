"""Controle avant soutenance : verifie que la demonstration peut se derouler.

A lancer sur le poste de demonstration, avant d'entrer en salle :

    demo_check.bat          (Windows, recommande)
    python demo_check.py    (equivalent, depuis la racine du depot)

Chaque controle affiche [OK], [KO] ou [--] (information, pas bloquant).
Code de sortie 0 si tout est vert, 1 sinon.
"""
import importlib.util
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
BASE = RACINE / "data_api" / "data-api-local.db"
ADAPTATEUR = RACINE / "Fine-Tuning" / "llama3_codage_cim11" / "adapter_config.json"
CAPTURES = RACINE / "docs" / "screenshots"
PORTS = (8000, 8001, 8501)

erreurs = []


def ok(msg):
    print(f"  [OK] {msg}")


def ko(msg, remede=""):
    print(f"  [KO] {msg}")
    if remede:
        print(f"       -> {remede}")
    erreurs.append(msg)


def info(msg):
    print(f"  [--] {msg}")


def titre(t):
    print(f"\n{t}")


def verifier_interpreteur():
    titre("1. Interpreteur Python")
    v = sys.version_info
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    dans_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if dans_venv:
        ok(f"Environnement virtuel actif ({Path(sys.prefix).name})")
    else:
        info("Python systeme (pas d'environnement virtuel actif)")


def verifier_dependances():
    titre("2. Dependances")
    groupes = {
        "data_api": ["fastapi", "uvicorn", "sqlalchemy", "pydantic"],
        "app_streamlit": ["streamlit", "requests"],
        "tests": ["pytest"],
    }
    for nom, modules in groupes.items():
        absents = [m for m in modules if importlib.util.find_spec(m) is None]
        if absents:
            ko(f"{nom} : module(s) manquant(s) : {', '.join(absents)}",
               "lancer demo_setup.bat (connexion internet requise)")
        else:
            ok(f"{nom} : toutes les dependances sont installees")


def verifier_base():
    titre("3. Base de donnees du referentiel")
    if not BASE.exists():
        ko(f"{BASE.name} introuvable dans data_api/",
           "la base ne se recree pas : recopier le dossier depuis le poste d'origine")
        return
    try:
        cx = sqlite3.connect(BASE)
        codes = cx.execute("select count(*) from code_cim11").fetchone()[0]
        postcoord = cx.execute("select count(*) from code_postcoord").fetchone()[0]
        crh = cx.execute("select count(*) from crh").fetchone()[0]
        cx.close()
    except sqlite3.Error as exc:
        ko(f"base illisible : {exc}")
        return
    if codes > 1000 and crh > 0:
        ok(f"base peuplee : {codes} codes, {postcoord} post-coordonnes, {crh} CRH")
    else:
        ko(f"base presente mais vide ou incomplete ({codes} codes, {crh} CRH)",
           "verifier que DATABASE_URL pointe sur data_api/data-api-local.db")


def verifier_modele():
    titre("4. Modele")
    if ADAPTATEUR.exists():
        ok("adaptateur LoRA present (Fine-Tuning/llama3_codage_cim11)")
    else:
        ko("adaptateur LoRA introuvable",
           "sans lui, /predict est impossible meme avec un GPU")
    try:
        import torch
        if torch.cuda.is_available():
            ok(f"GPU disponible : {torch.cuda.get_device_name(0)} — PLAN A possible")
        else:
            info("aucun GPU detecte : /predict indisponible — appliquer le PLAN B")
    except ImportError:
        info("torch non installe : /predict indisponible — appliquer le PLAN B")


def verifier_ports():
    titre("5. Ports reseau")
    for port in PORTS:
        with socket.socket() as s:
            s.settimeout(0.4)
            occupe = s.connect_ex(("127.0.0.1", port)) == 0
        if occupe:
            ko(f"port {port} deja occupe",
               "fermer le service qui l'utilise, ou changer de port au lancement")
        else:
            ok(f"port {port} libre")


def verifier_secours():
    titre("6. Filet de secours")
    if CAPTURES.is_dir() and any(CAPTURES.iterdir()):
        n = sum(1 for _ in CAPTURES.iterdir())
        ok(f"{n} captures disponibles dans docs/screenshots (PLAN B)")
    else:
        info("docs/screenshots vide : aucune capture de secours")


def verifier_tests():
    titre("7. Suite de tests")
    if importlib.util.find_spec("pytest") is None:
        info("pytest absent : controle ignore")
        return
    print("      execution en cours...")
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                         cwd=RACINE, capture_output=True, text=True)
    derniere = [l for l in res.stdout.strip().splitlines() if l.strip()]
    resume = derniere[-1] if derniere else "(pas de sortie)"
    if res.returncode == 0:
        ok(f"tous les tests passent — {resume}")
    else:
        ko(f"des tests echouent — {resume}",
           "ne pas lancer pytest devant le jury tant que ce n'est pas corrige")


def main():
    print("=" * 62)
    print("  Controle avant soutenance — cim11-assistant")
    print("=" * 62)
    os.chdir(RACINE)
    for etape in (verifier_interpreteur, verifier_dependances, verifier_base,
                  verifier_modele, verifier_ports, verifier_secours,
                  verifier_tests):
        etape()

    print("\n" + "=" * 62)
    if erreurs:
        print(f"  {len(erreurs)} point(s) a regler :")
        for e in erreurs:
            print(f"    - {e}")
        print("  Dans le doute, basculer sur le PLAN B :")
        print("  tests automatises + captures deja exportees.")
    else:
        print("  PRET.")
        print("  Lancer dans l'ordre : demo_start_data_api.bat,")
        print("  demo_start_model_api.bat, demo_start_app_streamlit.bat")
    print("=" * 62)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
