"""Tests de la chaine MLOps (C12/C13) — validation des donnees et validation du modele.

Ces tests verifient que les garde-fous de la chaine font bien echouer un jeu de donnees
corrompu ou un modele non conforme : un garde-fou qui laisse tout passer ne protege rien.
"""
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from mlops.validate_dataset import valider  # noqa: E402
from mlops import validate_model  # noqa: E402

ECHANTILLON = RACINE / "Fine-Tuning" / "data" / "sample_finetune_train.jsonl"


def _exemple(crh="Patient admis pour pneumonie communautaire, evolution favorable.",
             reponse="DP : Pneumonie, sans precision (CA40.Z)\nDAS : Diabete sucre de type 2 (5A11)"):
    return {"messages": [
        {"role": "system", "content": "Tu es un medecin DIM."},
        {"role": "user", "content": crh},
        {"role": "assistant", "content": reponse},
    ]}


def _ecrire(tmp_path, exemples):
    p = tmp_path / "dataset.jsonl"
    p.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in exemples), encoding="utf-8")
    return p


# --- Validation des donnees -------------------------------------------------

def test_echantillon_reel_du_depot_est_valide():
    """Le jeu de donnees versionne doit passer la validation (garde-fou de la CI)."""
    assert ECHANTILLON.exists(), "l'echantillon d'entrainement doit etre versionne"
    assert valider(ECHANTILLON, min_exemples=10) == []


def test_json_malforme_est_rejete(tmp_path):
    p = tmp_path / "dataset.jsonl"
    p.write_text('{"messages": [ceci n\'est pas du JSON}', encoding="utf-8")
    erreurs = valider(p, min_exemples=1)
    assert any("JSON invalide" in e for e in erreurs)


def test_roles_incomplets_sont_rejetes(tmp_path):
    ex = _exemple()
    ex["messages"] = ex["messages"][1:]  # system manquant
    erreurs = valider(_ecrire(tmp_path, [ex]), min_exemples=1)
    assert any("roles" in e for e in erreurs)


def test_crh_trop_court_est_rejete(tmp_path):
    erreurs = valider(_ecrire(tmp_path, [_exemple(crh="court")]), min_exemples=1)
    assert any("trop court" in e for e in erreurs)


def test_reponse_sans_dp_parsable_est_rejetee(tmp_path):
    """Regle R4 — c'est ce controle qui aurait detecte l'incident documente en E5."""
    ex = _exemple(reponse="Le patient presente une pneumonie mais aucun code n'est fourni.")
    erreurs = valider(_ecrire(tmp_path, [ex]), min_exemples=1)
    assert any("Diagnostic Principal parsable" in e for e in erreurs)


def test_doublon_exact_est_rejete(tmp_path):
    erreurs = valider(_ecrire(tmp_path, [_exemple(), _exemple()]), min_exemples=1)
    assert any("doublon" in e for e in erreurs)


def test_jeu_de_donnees_trop_petit_est_rejete(tmp_path):
    erreurs = valider(_ecrire(tmp_path, [_exemple()]), min_exemples=100)
    assert any("trop petit" in e for e in erreurs)


# --- Validation du modele ---------------------------------------------------

def test_adaptateur_livre_est_conforme():
    """L'adaptateur LoRA versionne doit correspondre a la configuration documentee."""
    assert validate_model.controler_artefact() == []


def test_performances_mesurees_passent_les_seuils():
    assert validate_model.controler_performances() == []


def test_seuil_de_non_regression_bloque_un_modele_degrade(monkeypatch, tmp_path):
    """Un modele dont le F1 repasse sous le seuil doit faire echouer la chaine."""
    degrade = {"modele_degrade": {
        "n_sejours_eval": 950, "n_lignes_eval": 2788,
        "base": {"souple": {"f1": 0.5313, "exact_match": 0.3411}},
        "finetuned": {"souple": {"f1": 0.42, "exact_match": 0.30}},
    }}
    faux = tmp_path / "resultats.json"
    faux.write_text(json.dumps(degrade), encoding="utf-8")
    monkeypatch.setattr(validate_model, "RESULTATS", faux)

    erreurs = validate_model.controler_performances()
    assert any("F1 souple" in e for e in erreurs)
    assert any("n'apporte rien" in e for e in erreurs)


def test_adaptateur_entraine_sur_un_autre_modele_de_base_est_rejete(monkeypatch, tmp_path):
    """Un adaptateur LoRA entraine sur une autre base serait inutilisable en inference."""
    faux = tmp_path / "adaptateur"
    faux.mkdir()
    (faux / "adapter_model.safetensors").write_bytes(b"")
    (faux / "adapter_config.json").write_text(json.dumps({
        "base_model_name_or_path": "mistralai/Mistral-7B-v0.1",
        "target_modules": ["q_proj", "v_proj"], "r": 16, "lora_alpha": 32,
    }), encoding="utf-8")
    monkeypatch.setattr(validate_model, "ADAPTATEUR", faux)

    erreurs = validate_model.controler_artefact()
    assert any("modele de base inattendu" in e for e in erreurs)
