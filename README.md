# Assistant de codage CIM-11

Projet fil rouge — certification RNCP 37827 « Développeur.se en Intelligence Artificielle » (Simplon).
Construit à partir du stage AP-HP (codage automatisé CIM-11 de comptes rendus d'hospitalisation).

## Structure

- `data_api/` — API REST (FastAPI) exposant le jeu de données CIM-11 (bloc 1, E1)
- `model_api/` — API REST (FastAPI) encapsulant le modèle Llama-3-8B fine-tuné (bloc 2, E2/E3)
- `app_streamlit/` — application d'aide au codage pour un utilisateur métier (bloc 3, E4/E5)
- `tests/` — tests automatisés (pytest), avec échantillons/mocks pour rester rapides en CI
- `.github/workflows/` — chaîne d'intégration/livraison continue (C18/C19)
- `docs/` — modélisation des données (Merise), documentation technique

## Démarrage rapide

```bash
cp .env.example .env   # puis remplir les valeurs
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate sous Windows
pip install -r data_api/requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

### data_api

```bash
uvicorn data_api.app.main:app --reload --port 8000
```

### model_api

Nécessite un GPU pour un temps de réponse correct (CPU fonctionne mais lentement) et un accès
Hugging Face au modèle gated `meta-llama/Meta-Llama-3-8B-Instruct` (variable `HF_TOKEN`).

```bash
pip install -r model_api/requirements.txt
uvicorn model_api.app.main:app --reload --port 8001
```

### app_streamlit

```bash
pip install -r app_streamlit/requirements.txt
export MODEL_API_URL=http://localhost:8001 DATA_API_URL=http://localhost:8000
streamlit run app_streamlit/app.py
```

## Origine des données

Toutes les données (CRH, identités patient) sont **synthétiques**, générées via l'API Mistral pendant
le stage — aucune donnée patient réelle n'est utilisée.

## Sécurité

Toutes les clés (API Mistral, HF_TOKEN, clés d'API internes) sont lues depuis des variables
d'environnement (voir `.env.example`), jamais codées en dur ni committées.
