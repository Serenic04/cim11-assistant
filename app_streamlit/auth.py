"""Gestion des droits d'acces a l'application (C17).

Deux roles, correspondant aux deux profils identifies dans l'analyse du besoin :

  - agent      : agent du DIM. Acces a l'assistant de codage uniquement.
  - responsable : responsable du DIM / exploitation. Acces a l'assistant ET a la page
                  de monitorage, qui expose des indicateurs d'exploitation (volumetrie,
                  latence, taux d'anomalie) n'ayant pas a etre visibles de tous.

C'est la traduction du critere « la gestion des droits d'acces a l'application ou a
certains espaces de l'application est developpee » : l'espace protege ici est la page
Monitoring.

Mecanisme. Les identifiants sont fournis par variables d'environnement, jamais ecrits
dans le code ni dans le depot, et le mot de passe n'est jamais compare en clair : seule
son empreinte SHA-256 est manipulee, et la comparaison utilise compare_digest, qui
s'execute en temps constant pour ne pas laisser fuir d'information par la duree de la
comparaison.

Limite assumee. Ce dispositif est volontairement simple : il demontre le controle
d'acces et la separation des espaces, mais un deploiement reel s'appuierait sur
l'annuaire de l'etablissement (SSO / LDAP hospitalier) plutot que sur des comptes
locaux, avec journalisation nominative des acces — exigence qui accompagne de toute
facon l'hebergement HDS (cf. R2).

Configuration (voir .env.example) :
    APP_UTILISATEURS="agent1:motdepasse:agent,resp1:motdepasse:responsable"
"""
import hashlib
import os
from hmac import compare_digest

import streamlit as st

ROLE_AGENT = "agent"
ROLE_RESPONSABLE = "responsable"
ROLES_CONNUS = (ROLE_AGENT, ROLE_RESPONSABLE)

# Comptes de demonstration, utilises uniquement si APP_UTILISATEURS n'est pas defini.
COMPTES_DEMO = "agent:demo-agent:agent,responsable:demo-resp:responsable"


def _empreinte(valeur: str) -> str:
    return hashlib.sha256(valeur.encode("utf-8")).hexdigest()


def charger_comptes() -> dict[str, dict[str, str]]:
    """Lit les comptes depuis l'environnement et n'en conserve que l'empreinte du mot de passe."""
    brut = os.getenv("APP_UTILISATEURS", COMPTES_DEMO)
    comptes: dict[str, dict[str, str]] = {}
    for entree in brut.split(","):
        champs = entree.strip().split(":")
        if len(champs) != 3:
            continue
        identifiant, motdepasse, role = (c.strip() for c in champs)
        if not identifiant or not motdepasse or role not in ROLES_CONNUS:
            continue
        comptes[identifiant] = {"empreinte": _empreinte(motdepasse), "role": role}
    return comptes


def verifier(identifiant: str, motdepasse: str) -> str | None:
    """Retourne le role si les identifiants sont valides, None sinon."""
    compte = charger_comptes().get(identifiant.strip())
    if compte is None:
        # Empreinte calculee malgre tout : le temps de reponse ne doit pas reveler
        # si l'identifiant existe ou non.
        _empreinte(motdepasse)
        return None
    if compare_digest(compte["empreinte"], _empreinte(motdepasse)):
        return compte["role"]
    return None


def utilisateur_courant() -> dict | None:
    return st.session_state.get("utilisateur")


def formulaire_connexion() -> None:
    """Affiche le formulaire de connexion. Retourne apres avoir renseigne la session."""
    st.subheader("Connexion")
    st.caption("L'accès est réservé aux agents du département d'information médicale.")
    with st.form("connexion"):
        identifiant = st.text_input("Identifiant", key="champ_identifiant")
        motdepasse = st.text_input("Mot de passe", type="password", key="champ_motdepasse")
        valider = st.form_submit_button("Se connecter", type="primary")
    if valider:
        role = verifier(identifiant, motdepasse)
        if role is None:
            # Message volontairement generique : ne pas indiquer lequel des deux est faux.
            st.error("Identifiant ou mot de passe incorrect.")
        else:
            st.session_state["utilisateur"] = {"identifiant": identifiant.strip(), "role": role}
            st.rerun()


def exiger_connexion(role_minimum: str = ROLE_AGENT) -> dict | None:
    """Garde d'acces a placer en tete de chaque page.

    Retourne l'utilisateur connecte si l'acces est autorise ; sinon affiche le
    formulaire ou le refus, et retourne None (la page doit alors s'interrompre).
    """
    utilisateur = utilisateur_courant()
    if utilisateur is None:
        formulaire_connexion()
        return None

    if role_minimum == ROLE_RESPONSABLE and utilisateur["role"] != ROLE_RESPONSABLE:
        st.error(
            "Accès refusé — cet espace est réservé au profil « responsable ». "
            "Les indicateurs d'exploitation ne sont pas accessibles au profil « agent »."
        )
        barre_laterale(utilisateur)
        return None

    barre_laterale(utilisateur)
    return utilisateur


def barre_laterale(utilisateur: dict) -> None:
    """Rappelle qui est connecte et avec quel role, et propose la deconnexion."""
    with st.sidebar:
        st.markdown(f"**Connecté :** {utilisateur['identifiant']}")
        st.caption(f"Profil : {utilisateur['role']}")
        if st.button("Se déconnecter"):
            st.session_state.pop("utilisateur", None)
            st.rerun()
