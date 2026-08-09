# E5 — Monitorage applicatif et résolution d'un incident technique

## 1. Dispositif de monitorage applicatif

- `GET /health` (data_api, model_api) : vérification de disponibilité du service.
- `GET /metrics` (model_api) : vecteur de restitution en temps réel — nombre de requêtes,
  nombre d'erreurs, latence moyenne, latence p95, **nombre d'anomalies "DP manquant"**.
- Journalisation structurée (`logging`) : chaque prédiction sans Diagnostic Principal
  identifié déclenche un `logger.warning(...)`, avec un extrait du CRH concerné pour
  faciliter l'investigation.
- Le compteur `nb_anomalies_dp_manquant` sert de signal d'alerte : sur un corpus de CRH
  réels, un DP est identifié dans la quasi-totalité des cas. Une hausse de ce compteur
  indique un problème (modèle ou parsing) à investiguer.

## 2. Description de l'incident

**Déclenchement** : en écrivant les tests de non-régression pour `model_api/app/parsing.py`
avec des exemples issus des vraies données du stage (`codes_postcoord_realistes_v2.csv`,
qui contient des codes CIM-11 post-coordonnés du type `1A62.2&XA6GV0`), le test
`parse_model_reply("DP : Syphilis tardive symptomatique (1A62.2&XA6GV0)\nDAS : aucun")`
échoue : `result["dp"]` vaut `None`.

**Périmètre impacté** : `model_api` (endpoint `/predict`) et l'ETL `data_api/etl/load_data.py`
utilisent tous deux la même expression régulière `DIAG_RE` pour extraire `(libellé, code)`
de la réponse du modèle. Tout diagnostic dont le code est post-coordonné (extension après
`&`) est silencieusement perdu — ni erreur, ni log, juste une prédiction incomplète.
C'est précisément le type d'anomalie que `nb_anomalies_dp_manquant` est censé détecter.

## 3. Diagnostic

`DIAG_RE` était : `([^,(]+?)\s*\(([A-Z0-9]{3,10}(?:\.[A-Z0-9]+)?)\)`.
La classe de caractères `[A-Z0-9]{3,10}(?:\.[A-Z0-9]+)?` ne reconnaît qu'un code simple
(éventuellement avec un point), pas la syntaxe de post-coordination CIM-11 avec un ou
plusieurs `&EXTENSION` (jusqu'à 16 extensions chaînées observées dans le référentiel réel).
Comme le code entre parenthèses ne correspond plus au motif attendu, la parenthèse
fermante n'est jamais atteinte et le `re.search` échoue entièrement sur ce diagnostic.

En creusant plus loin (écriture d'un cas de test avec un libellé réaliste), un **second
défaut lié** a été trouvé : l'exclusion de la virgule dans `[^,(]+?` tronquait aussi les
libellés contenant une virgule interne (très fréquent en français médical, ex. « Fracture
du col du fémur, **sans précision** ») — seule la partie après la dernière virgule était
capturée.

## 4. Résolution

**Méthodologie** :
1. Reproduction du bug par un test isolé (`tests/test_parsing_postcoordination.py`),
   avant toute correction (TDD).
2. Élargissement du motif de code : `[A-Z0-9]{2,10}(?:\.[A-Z0-9]+)?(?:&[A-Z0-9]{2,10}(?:\.[A-Z0-9]+)?)*`
   pour accepter zéro, une ou plusieurs extensions de post-coordination.
3. Remplacement de l'exclusion de virgule par une exclusion de parenthèse uniquement
   (`[^(]+?`), et isolation explicite du texte après le marqueur `DP :` pour ne pas
   capturer le label lui-même.
4. Application du même correctif dans `model_api/app/parsing.py` **et**
   `data_api/etl/load_data.py` (code dupliqué, corrigé aux deux endroits).
5. Ajout du compteur `nb_anomalies_dp_manquant` exposé par `/metrics`, pour détecter plus
   tôt ce type d'anomalie en conditions réelles.

**Tests en succès** : 21/21 tests passent après correction
(`tests/test_parsing_postcoordination.py`, `tests/test_etl_parsing.py`,
`tests/test_model_api.py::test_metrics_tracks_anomaly_when_dp_missing`), couvrant :
code simple, code post-coordonné à une extension, à extensions multiples, libellé avec
virgule interne, et DAS post-coordonné dans une liste.

## 5. Documentation de l'incident

| | |
|---|---|
| Composants touchés | `model_api/app/parsing.py`, `data_api/etl/load_data.py` |
| Détecté par | Écriture de tests de non-régression à partir de données réelles |
| Impact avant correctif | Perte silencieuse de diagnostics post-coordonnés + troncature de libellés avec virgule |
| Correctif | Élargissement de `DIAG_RE`, isolation du marqueur `DP :`, ajout d'un indicateur de monitorage |
| Non-régression | 5 nouveaux tests dédiés, suite complète 21/21 verte |
