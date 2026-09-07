# Extraction depuis un système big data — Apache Spark (C2)

`extract_bigdata_spark.py` traite `codes_postcoord_realistes_v2.csv` (fichier
le plus volumineux du projet, 570 132 lignes de données réelles — voir
`docs/MCD_MLD.md`) avec **Apache Spark** (Spark SQL), plutôt qu'avec pandas,
pour répondre au critère C2 : « requêtes d'extraction depuis un système big
data ».

Spark tourne ici en local (`local[*]`), faute de cluster Hadoop/YARN
disponible pour ce projet — le moteur de requêtage (Spark SQL / DataFrame
API) reste le même qu'en cluster, seul le gestionnaire de ressources change.
C'est un mode d'exécution standard et documenté de Spark.

## Besoin métier

Repérer les codes CIM-11 « racines » qui ont le plus de combinaisons de
post-coordination réalistes générées et validées (anti-hallucination) — des
candidats prioritaires pour une revue manuelle plus poussée du référentiel
(voir `docs/stage_preparation/README.md`).

## Requête

```sql
SELECT code_racine, COUNT(*) AS nb_combinaisons_realistes
FROM postcoord
GROUP BY code_racine
ORDER BY nb_combinaisons_realistes DESC
LIMIT 20
```

## Optimisation

- Schéma explicite (`StructType`) à la lecture plutôt que `inferSchema=True` :
  évite un premier passage de scan complet du fichier rien que pour deviner
  les types.
- `spark.sql.shuffle.partitions` réduit à 8 (valeur par défaut : 200, pensée
  pour un vrai cluster) : évite de créer des centaines de petites tâches
  inutiles pour un `GROUP BY` sur un fichier de cette taille en local.

## Exécution réelle (résultat vérifié)

```
python extract_bigdata_spark.py --csv <chemin>/codes_postcoord_realistes_v2.csv --top 10
```

570 132 lignes lues. Code racine le plus représenté : `DD95` (501
combinaisons de post-coordination réalistes générées pour ce seul code).
