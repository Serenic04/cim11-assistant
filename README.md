# Assistant de codage CIM-11

Projet fil rouge — certification RNCP 37827 « Développeur.se en Intelligence Artificielle » (Simplon).
Construit à partir du stage AP-HP (codage automatisé CIM-11 de comptes rendus d'hospitalisation).

## Structure

- `data-api/` — API REST (FastAPI) exposant le jeu de données CIM-11 (bloc 1, E1)
- `model-api/` — API REST (FastAPI) encapsulant le modèle fine-tuné Llama-3-8B (bloc 2, E2/E3)
- `app-streamlit/` — application d'aide au codage pour un utilisateur métier (bloc 3, E4/E5)
- `tests/` — tests automatisés (pytest)
- `.github/workflows/` — chaîne d'intégration/livraison continue (C18/C19)
- `docs/` — modélisation des données (Merise), documentation technique

## Origine des données

Toutes les données (CRH, identités patient) sont **synthétiques**, générées via l'API Mistral pendant
le stage — aucune donnée patient réelle n'est utilisée.

