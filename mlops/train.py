"""Etape 2 de la chaine MLOps (C13) — entrainement LoRA du modele de codage CIM-11.

Ce script reproduit, sous forme executable et versionnee, la configuration
d'entrainement effectivement utilisee pour produire l'adaptateur livre dans
Fine-Tuning/llama3_codage_cim11/ (cf. rapport R2, section 5). Les hyperparametres
ci-dessous sont ceux lus dans les artefacts reels du modele :

  - adapter_config.json  : r=16, lora_alpha=32, lora_dropout=0.05,
                           target_modules=["q_proj","v_proj"], base Meta-Llama-3-8B-Instruct
  - trainer_state.json   : 3 epochs, 3 099 pas d'optimisation, perte finale 0,29,
                           precision token moyenne 91,75 % (dernier log, pas 3090)

Historique honnete : l'adaptateur actuellement livre a ete produit pendant le projet
depuis un notebook Google Colab (GPU gratuit), et non par ce script. Ce module existe
pour rendre l'etape d'entrainement reproductible et integrable a la chaine
d'integration continue — il constitue l'etape declenchable du job train-model
(voir .github/workflows/ci.yml et docs/MLOPS.md).

Contrainte materielle : un GPU est indispensable (quantification 4 bits + 8 milliards
de parametres). Sans GPU disponible, le script s'arrete immediatement avec un message
explicite plutot que de tenter un entrainement qui echouerait apres plusieurs minutes.

Usage :
    python -m mlops.train --dataset <chemin>/finetune_train.jsonl \\
                          --sortie Fine-Tuning/llama3_codage_cim11
"""
import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

# Hyperparametres — alignes sur les artefacts reels (voir docstring).
BASE_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "v_proj"]
EPOCHS = 3
BATCH_SIZE = 1
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4


def verifier_gpu() -> None:
    """Arret immediat et explicite si aucun GPU n'est disponible."""
    try:
        import torch
    except ImportError:
        raise SystemExit(
            "ERREUR : PyTorch n'est pas installe. L'entrainement necessite un environnement GPU "
            "complet (voir docs/MLOPS.md, section « Executer l'entrainement »)."
        )
    if not torch.cuda.is_available():
        raise SystemExit(
            "ERREUR : aucun GPU detecte. L'entrainement LoRA de Llama-3-8B en 4 bits exige un GPU "
            "(environ 3 h sur un GPU unique). Les runners GitHub heberges standards n'en ont pas : "
            "declencher le job train-model sur un runner auto-heberge equipe, ou executer ce script "
            "en local sur une machine GPU."
        )
    print(f"GPU detecte : {torch.cuda.get_device_name(0)}")


def construire_arguments(sortie: Path):
    """Construit la configuration d'entrainement (isolee pour etre testable sans GPU)."""
    from peft import LoraConfig
    from transformers import BitsAndBytesConfig
    import torch

    quantification = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    lora = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    return quantification, lora


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sortie", type=Path, default=RACINE / "Fine-Tuning" / "llama3_codage_cim11")
    args = parser.parse_args()

    # L'etape 1 (validation des donnees) est un prerequis : on la rejoue ici pour que
    # le script reste sur par lui-meme, meme lance hors de la chaine.
    from mlops.validate_dataset import valider

    erreurs = valider(args.dataset, min_exemples=100)
    if erreurs:
        print(f"ENTRAINEMENT ANNULE : jeu de donnees invalide ({len(erreurs)} erreur(s))")
        for e in erreurs[:10]:
            print("  -", e)
        return 1

    verifier_gpu()

    from datasets import load_dataset
    from peft import get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    quantification, lora = construire_arguments(args.sortie)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    tokenizer.pad_token = tokenizer.eos_token
    modele = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, quantization_config=quantification, device_map="auto"
    )
    modele = get_peft_model(prepare_model_for_kbit_training(modele), lora)
    modele.print_trainable_parameters()

    donnees = load_dataset("json", data_files=str(args.dataset), split="train")

    entraineur = SFTTrainer(
        model=modele,
        train_dataset=donnees,
        processing_class=tokenizer,
        args=SFTConfig(
            output_dir=str(args.sortie),
            num_train_epochs=EPOCHS,
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            learning_rate=LEARNING_RATE,
            logging_steps=10,
            save_strategy="epoch",
            bf16=True,
        ),
    )
    entraineur.train()
    entraineur.save_model(str(args.sortie))
    tokenizer.save_pretrained(str(args.sortie))
    print(f"Adaptateur LoRA enregistre dans {args.sortie}")
    print("Etape suivante de la chaine : python -m mlops.validate_model")
    return 0


if __name__ == "__main__":
    sys.exit(main())
