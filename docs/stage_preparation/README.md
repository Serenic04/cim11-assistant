# Scripts de préparation des données — stage AP-HP

Ces notebooks ont été réalisés pendant le stage AP-HP (projet `Serenic_M`), **en amont** de ce projet de
certification. Ils produisent les fichiers de données réels consommés par `data_api/etl/load_data.py`
(épreuve E1) et par le fine-tuning du modèle (épreuve E3, détaillé dans le rapport R2). Ils sont inclus
ici tels quels (non modifiés depuis le stage), pour traçabilité — c'est le code réel derrière les
chiffres présentés dans les rapports et diaporamas de soutenance.

Ils nécessitent un environnement Google Colab (montage Google Drive) et ne sont pas exécutables tels
quels hors de cet environnement.

## `verif_postcoord_mistral_v2.ipynb`

Génère et valide les codes CIM-11 post-coordonnés. Pour chaque code racine, demande à l'API Mistral de
proposer jusqu'à 100 combinaisons post-coordonnées cliniquement réalistes (plafond nécessaire : certains
codes racines ont plusieurs milliards de combinaisons théoriques, voir `Comptage_PostCoordination_CIM11.ipynb`).

Inclut une **validation anti-hallucination** : chaque code renvoyé par Mistral est vérifié contre les
référentiels réels de codes racines et d'extensions ; tout code inventé (ex. `XA13Z`, absent du
référentiel OMS) est rejeté et journalisé dans `codes_hallucines_v2.csv`.

Produit `codes_postcoord_realistes_v2.csv` (570 132 lignes), consommé par `load_postcoord()`.

## `Construction_Dictionnaire_Synonymes_CIM10.ipynb`

Fusionne plusieurs sources de synonymes médicaux (dictionnaire AP-HP « Hector », Orphanet, CépiDc,
inclusions officielles CIM-10) en un seul fichier `synonymes.csv`, indexé par codes **CIM-10** (la
classification utilisée par ces sources d'origine).

Consommé par `load_synonymes()`, après traduction CIM-10 → CIM-11 via
`data_api/etl/cim10_to_cim11_mapping.csv`.

## `CIM_11_generate_scenarios_final_v2.ipynb`

Transcode les diagnostics annotés en CIM-10 vers la CIM-11, via la table de correspondance officielle
de l'OMS (`10To11MapToOneCategory.xlsx`), pour produire les CRH d'entraînement du modèle
(`Fine-Tuning/data/finetune_train.jsonl`). C'est la même table de correspondance qui a été réutilisée
pour corriger le chargement des synonymes (voir ci-dessus).

## `Comptage_PostCoordination_CIM11.ipynb`

Calcule, pour chaque code racine, le nombre de combinaisons de post-coordination théoriquement possibles
(jusqu'à 12 809 008 742 399 pour le code `PB91.1`, qui a 7 axes). C'est ce calcul qui justifie le
plafonnement à 100 combinaisons réalistes par code appliqué dans `verif_postcoord_mistral_v2.ipynb`.
