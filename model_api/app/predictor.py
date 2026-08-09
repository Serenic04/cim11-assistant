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

SYSTEM_PROMPT = (
    "Tu es un médecin DIM (département d'information médicale) expert en codage CIM-11.\n"
    "On te fournit le texte d'un compte rendu d'hospitalisation (CRH) rédigé en français.\n"
    "Ta tâche est d'identifier :\n"
    "- Le Diagnostic Principal (DP) : le diagnostic qui a motivé l'hospitalisation\n"
    "- Les Diagnostics Associés (DAS) : les autres diagnostics documentés et traités\n\n"
    "Réponds UNIQUEMENT dans ce format exact, sans aucun autre texte :\n"
    "DP : <Libellé complet du diagnostic> (<code CIM-11>)\n"
    "DAS : <Libellé> (<code>), <Libellé> (<code>), ...\n\n"
    "Si aucun DAS n'est identifié, écris : DAS : aucun"
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
        self._tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, token=os.getenv("HF_TOKEN"))
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
        user_content = (
            "Voici le compte rendu d'hospitalisation à coder en CIM-11 :\n\n---\n" + texte_crh
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        inputs = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(self._model.device)

        import torch
        with torch.no_grad():
            output = self._model.generate(
                inputs, max_new_tokens=400, do_sample=False, temperature=None, top_p=None
            )
        reply = self._tokenizer.decode(output[0][inputs.shape[-1]:], skip_special_tokens=True)
        return parse_model_reply(reply)


def timed_predict(predictor: BasePredictor, texte_crh: str) -> dict:
    start = time.perf_counter()
    result = predictor.predict(texte_crh)
    latence_ms = (time.perf_counter() - start) * 1000
    result["latence_ms"] = round(latence_ms, 1)
    result["modele"] = f"{BASE_MODEL} + LoRA (llama3_codage_cim11)"
    return result
