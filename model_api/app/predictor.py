"""Encapsule le modele fine-tune (Llama-3-8B-Instruct + adaptateur LoRA) pour l'inference.

Le modele n'est charge qu'a la premiere requete (lazy loading) afin que l'API demarre
instantanement et que les tests (CI) n'aient pas besoin de charger 8B de parametres :
en test, on injecte un FakePredictor via dependency override (voir tests/test_model_api.py).
"""
import os
import time
from abc import ABC, abstractmethod

from .parsing import parse_model_reply

BASE_MODEL = os.getenv("BASE_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
ADAPTER_PATH = os.getenv("ADAPTER_PATH", "../Fine-Tuning/llama3_codage_cim11")

# Consigne systeme. Elle reproduit celle du protocole d'evaluation du modele
# (Fine-Tuning/Test_checkpoint_3099.ipynb), qui a mesure les performances annoncees
# dans le rapport E2 : F1 souple 0,7370 et exact match souple 0,6671.
#
# Le paragraphe sur la post-coordination est indispensable. Mesure du 08/09/2026 sur
# 5 comptes rendus du corpus, en interrogeant l'API deployee : sans ce paragraphe,
# le modele n'identifie un Diagnostic Principal que dans 1 cas sur 5 ; avec, dans
# 5 cas sur 5. Le jeu d'entrainement, lui, utilisait une consigne plus courte : c'est
# a l'evaluation que la consigne enrichie a ete introduite, et c'est donc elle qui
# doit etre servie en production pour que le comportement corresponde aux mesures.
SYSTEM_PROMPT = (
    "Tu es un médecin DIM (département d'information médicale) expert en codage CIM-11.\n"
    "On te fournit un texte clinique rédigé en français.\n"
    "Ta tâche est d'identifier :\n"
    "- Le Diagnostic Principal (DP) : le diagnostic qui a motivé l'hospitalisation\n"
    "- Les Diagnostics Associés (DAS) : les autres diagnostics documentés et traités\n\n"
    "La CIM-11 utilise la post-coordination : un code racine peut être précisé par une ou\n"
    "plusieurs extensions du chapitre X, reliées par le caractère &.\n"
    "Exemple : 2C6Z&XA3LS6 = tumeur du sein, quadrant interne supérieur.\n"
    "Quand le texte donne une précision de localisation, de latéralité, de sévérité ou de\n"
    "temporalité, exprime-la sous forme d'extension plutôt que de t'en tenir au code racine.\n\n"
    "Réponds UNIQUEMENT dans ce format exact, sans aucun autre texte :\n"
    "DP : <Libellé complet du diagnostic> (<code CIM-11>)\n"
    "DAS : <Libellé> (<code>), <Libellé> (<code>), ...\n\n"
    "Si aucun DAS n'est identifié, écris : DAS : aucun"
)

# Gabarit du message utilisateur. Il doit reproduire EXACTEMENT celui du jeu
# d'entrainement (Fine-Tuning/data/*.jsonl) et du script d'evaluation qui a mesure
# les performances annoncees : meme en-tete, memes delimiteurs '---' ouvrant ET
# fermant, meme consigne finale. Un modele affine sur un gabarit precis se degrade
# fortement si le gabarit d'inference en differe.
GABARIT_UTILISATEUR = (
    "Voici le compte rendu d'hospitalisation à coder en CIM-11 :\n"
    "\n"
    "---\n"
    "{texte}\n"
    "---\n"
    "\n"
    "Propose le codage CIM-11 (DP et DAS)."
)


class BasePredictor(ABC):
    @abstractmethod
    def predict(self, texte_crh: str) -> dict:
        ...


class LlamaCim11Predictor(BasePredictor):
    """Implementation reelle : charge Llama-3-8B-Instruct + l'adaptateur LoRA du stage."""

    def __init__(self):
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        # Le tokenizer est celui sauvegarde AVEC l'adaptateur : il embarque le gabarit
        # de conversation (chat_template.jinja) utilise pendant l'entrainement, et repris
        # tel quel par le script d'evaluation qui a mesure les performances annoncees.
        # Charger celui du modele de base applique un gabarit different et degrade
        # fortement les sorties. On retombe sur le modele de base uniquement si
        # l'adaptateur n'embarque pas de tokenizer.
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)
        except Exception:
            self._tokenizer = AutoTokenizer.from_pretrained(
                BASE_MODEL, token=os.getenv("HF_TOKEN"))
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            quantization_config=bnb_config,
            device_map="auto",
            token=os.getenv("HF_TOKEN"),
        )
        self._model = PeftModel.from_pretrained(base, ADAPTER_PATH)
        self._model.eval()

    def predict(self, texte_crh: str) -> dict:
        self._load()
        user_content = GABARIT_UTILISATEUR.format(texte=texte_crh.strip())
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        import torch

        # La tokenisation reproduit celle du protocole d'evaluation : le gabarit est
        # d'abord rendu en texte, puis tokenise separement. Ce n'est pas un detail de
        # style — cette sequence ajoute un second jeton de debut, et l'inference doit
        # partir du meme prefixe que celui sur lequel les performances ont ete mesurees.
        # Passer par return_tensors="pt" directement changerait ce prefixe, et selon la
        # version de transformers renverrait un BatchEncoding que generate() refuse.
        texte_gabarit = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        entree = self._tokenizer(texte_gabarit, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            output = self._model.generate(
                **entree,
                max_new_tokens=400,
                do_sample=False,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        reply = self._tokenizer.decode(
            output[0][entree["input_ids"].shape[-1]:], skip_special_tokens=True
        )
        return parse_model_reply(reply)


def timed_predict(predictor: BasePredictor, texte_crh: str) -> dict:
    start = time.perf_counter()
    result = predictor.predict(texte_crh)
    latence_ms = (time.perf_counter() - start) * 1000
    result["latence_ms"] = round(latence_ms, 1)
    result["modele"] = f"{BASE_MODEL} + LoRA (llama3_codage_cim11)"
    return result
