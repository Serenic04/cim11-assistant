"""Application d'aide au codage CIM-11 (bloc 3, E4) — pour un utilisateur métier (médecin/DIM).

L'utilisateur colle le texte d'un compte rendu d'hospitalisation (CRH), l'application
interroge le model_api (prédiction DP/DAS) puis le data_api (libellé officiel du
référentiel, pour vérification) et affiche le résultat.
"""
import os

import requests
import streamlit as st

from app_streamlit.auth import ROLE_AGENT, exiger_connexion

MODEL_API_URL = os.getenv("MODEL_API_URL", "http://localhost:8001")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "dev-only-change-me")
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8000")
DATA_API_KEY = os.getenv("DATA_API_KEY", "dev-only-change-me")

TIMEOUT_S = 30

# Doit rester aligné avec model_api.app.schemas.PredictionRequest (min_length=10) :
# la validation du formulaire est le premier filtre, model_api reste le filet de
# sécurité côté serveur si ce formulaire est contourné (appel direct à l'API).
LONGUEUR_MIN_CRH = 10


def call_model_api(texte_crh: str) -> dict:
    """Appelle model_api /predict. Lève une exception si l'appel échoue (gérée par l'appelant)."""
    resp = requests.post(
        f"{MODEL_API_URL}/predict",
        json={"texte_crh": texte_crh},
        headers={"X-API-Key": MODEL_API_KEY},
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def call_data_api_code(code: str) -> dict | None:
    """Récupère le libellé officiel d'un code CIM-11 depuis data_api (vérification croisée)."""
    try:
        resp = requests.get(
            f"{DATA_API_URL}/codes/{code}",
            headers={"X-API-Key": DATA_API_KEY},
            timeout=TIMEOUT_S,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        return None
    return None


def render_diagnostic(label: str, diag: dict | None):
    if diag is None:
        st.info(f"{label} : aucun diagnostic identifié.")
        return
    st.markdown(f"**{label}** : {diag['libelle']} — `{diag['code']}`")
    ref = call_data_api_code(diag["code"])
    if ref:
        st.caption(f"Référentiel CIM-11 : {ref['libelle']}")
    else:
        st.caption("Code non retrouvé dans le référentiel local (vérification manuelle recommandée).")


def main():
    st.set_page_config(page_title="Assistant de codage CIM-11", page_icon="🩺")
    st.title("Assistant de codage CIM-11")

    # Gestion des droits d'acces (C17) : l'assistant est accessible aux deux profils,
    # la page Monitoring est reservee au profil "responsable" (voir auth.py).
    utilisateur = exiger_connexion(ROLE_AGENT)
    if utilisateur is None:
        return

    st.write(
        "Collez le texte d'un compte rendu d'hospitalisation (CRH). "
        "L'assistant propose un Diagnostic Principal (DP) et des Diagnostics Associés (DAS)."
    )

    # Mesure organisationnelle (RGPD art. 32) : premiere barriere avant la saisie.
    # Elle est completee par une mesure technique cote model_api, ou la journalisation
    # ne conserve aucun contenu de CRH (voir model_api/app/main.py). Defense en profondeur :
    # le filet technique fonctionne meme si cet avertissement n'est pas lu.
    st.warning(
        "**Environnement de démonstration — ne collez pas de compte rendu réel.** "
        "Si vous testez avec un document authentique, retirez au préalable les identifiants "
        "directs : nom, prénom, date de naissance, adresse, numéro de sécurité sociale, "
        "numéro de dossier. Le contenu clinique, lui, doit être conservé : c'est ce que "
        "l'assistant analyse pour proposer un codage."
    )

    texte_crh = st.text_area(
        label="Texte du compte rendu d'hospitalisation (sans identifiants directs)",
        height=300,
        placeholder="Collez ici le CRH à coder...",
        help="Les identifiants directs (nom, date de naissance, numéro de dossier) doivent être "
             "retirés avant la saisie. Aucun contenu de CRH n'est conservé par l'application ni "
             "journalisé par le service de prédiction.",
    )

    texte_saisi = texte_crh.strip()
    texte_trop_court = bool(texte_saisi) and len(texte_saisi) < LONGUEUR_MIN_CRH
    if texte_trop_court:
        st.warning(f"Le compte rendu doit contenir au moins {LONGUEUR_MIN_CRH} caractères.")

    if st.button(
        "Coder ce CRH",
        type="primary",
        disabled=not texte_saisi or texte_trop_court,
    ):
        with st.spinner("Analyse du compte rendu en cours..."):
            try:
                result = call_model_api(texte_crh)
            except requests.RequestException as exc:
                st.error(f"Le service de prédiction est indisponible ({exc}). Réessayez plus tard.")
                return

        st.success(f"Prédiction obtenue en {result['latence_ms']} ms — modèle : {result['modele']}")
        render_diagnostic("Diagnostic Principal (DP)", result.get("dp"))

        das = result.get("das", [])
        if das:
            st.markdown("**Diagnostics Associés (DAS)**")
            for d in das:
                render_diagnostic("DAS", d)
        else:
            st.info("Aucun diagnostic associé identifié.")

        st.caption(
            "Cette proposition est générée automatiquement et doit être validée par un "
            "professionnel du DIM avant intégration au dossier patient."
        )


if __name__ == "__main__":
    main()
