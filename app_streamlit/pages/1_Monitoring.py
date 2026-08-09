"""Dashboard de monitorage applicatif (bloc 3, E5) — vue operationnelle pour l'equipe DIM/ops.

Interroge GET /health et GET /metrics de model_api et data_api en temps reel et affiche :
- disponibilite des deux services,
- volumetrie et latence des predictions (model_api),
- indicateur d'anomalie "DP manquant" (cf. docs/E5_incident_monitorage.md),
- historique de la latence moyenne sur les dernieres actualisations (memoire de session).
"""
import os
import time
from datetime import datetime

import requests
import streamlit as st

MODEL_API_URL = os.getenv("MODEL_API_URL", "http://localhost:8001")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "dev-only-change-me")
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8000")

TIMEOUT_S = 5

st.set_page_config(page_title="Monitorage — CIM-11 Assistant", page_icon="📊", layout="wide")
st.title("📊 Monitorage applicatif")
st.caption(
    "Dispositif de monitorage decrit dans docs/E5_incident_monitorage.md — "
    "sante des services + metriques de prediction en temps reel."
)


def get_json(url: str, headers: dict | None = None) -> tuple[dict | None, str | None]:
    try:
        resp = requests.get(url, headers=headers or {}, timeout=TIMEOUT_S)
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


# --- Etat des services -------------------------------------------------
col1, col2 = st.columns(2)

for col, name, url in [(col1, "data_api", DATA_API_URL), (col2, "model_api", MODEL_API_URL)]:
    with col:
        data, err = get_json(f"{url}/health")
        if data and data.get("status") == "ok":
            st.success(f"**{name}** — disponible ({url})")
        else:
            st.error(f"**{name}** — indisponible ({err or 'reponse inattendue'})")

st.divider()

# --- Metriques model_api -------------------------------------------------
st.subheader("model_api — métriques de prédiction")

metrics, err = get_json(f"{MODEL_API_URL}/metrics", headers={"X-API-Key": MODEL_API_KEY})

if metrics is None:
    st.warning(f"Métriques indisponibles : {err}")
else:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Requêtes totales", metrics["nb_requetes"])
    m2.metric("Erreurs", metrics["nb_erreurs"])
    m3.metric(
        "Latence moyenne",
        f"{metrics['latence_moyenne_ms']} ms" if metrics["latence_moyenne_ms"] is not None else "—",
    )
    m4.metric(
        "Latence p95",
        f"{metrics['latence_p95_ms']} ms" if metrics["latence_p95_ms"] is not None else "—",
    )
    anomalies = metrics["nb_anomalies_dp_manquant"]
    m5.metric("Anomalies DP manquant", anomalies, delta=None if anomalies == 0 else "⚠️ à investiguer")

    if anomalies > 0:
        st.warning(
            f"{anomalies} prédiction(s) sans Diagnostic Principal identifié — "
            "signal d'alerte décrit dans docs/E5_incident_monitorage.md. "
            "À investiguer si le taux dépasse quelques cas isolés."
        )

    st.caption(f"Fenêtre glissante : {metrics['fenetre_glissante']} dernières prédictions.")

    # Historique de latence moyenne en mémoire de session (pas de persistance disque)
    if "historique_latence" not in st.session_state:
        st.session_state.historique_latence = []

    if metrics["latence_moyenne_ms"] is not None:
        st.session_state.historique_latence.append(
            {"heure": datetime.now().strftime("%H:%M:%S"), "latence_ms": metrics["latence_moyenne_ms"]}
        )
        st.session_state.historique_latence = st.session_state.historique_latence[-50:]

    if len(st.session_state.historique_latence) >= 2:
        st.line_chart(
            {h["heure"]: h["latence_ms"] for h in st.session_state.historique_latence},
            y_label="Latence moyenne (ms)",
        )
    else:
        st.caption(
            "Historique de latence : pas encore assez de points sur cette session "
            "(actualisez la page après quelques prédictions)."
        )

st.divider()
auto_refresh = st.checkbox("Actualisation automatique (5 s)", value=False)
if st.button("Actualiser maintenant") or auto_refresh:
    if auto_refresh:
        time.sleep(5)
    st.rerun()
