"""Extraction depuis un systeme big data - Apache Spark (C2 - RNCP 37827).

Contexte
--------
Le fichier source `codes_postcoord_realistes_v2.csv` (referentiel des
combinaisons de post-coordination CIM-11, ~570 000 lignes generees pendant le
stage - voir docs/stage_preparation/README.md) est le plus volumineux du
projet. Il est traite ici avec Apache Spark (Spark SQL, moteur de traitement
distribue cite dans le referentiel RNCP au meme titre que Hive/Impala) plutot
qu'avec pandas, pour repondre au critere C2 : "requetes d'extraction depuis
un systeme big data".

Spark tourne ici en local[*] (pas de cluster Hadoop/YARN disponible pour ce
projet), ce qui reste un mode d'execution standard et documente de Spark -
le moteur de requetage (Spark SQL / DataFrame API) est le meme qu'en cluster ;
seul le gestionnaire de ressources change.

Requete d'extraction
---------------------
Besoin : identifier, pour chaque code CIM-11 "racine", le nombre de
combinaisons post-coordonnees realistes qui ont ete generees et validees
(anti-hallucination) pour lui, afin de reperer les codes les plus complexes
(candidats prioritaires pour une revue manuelle plus poussee du referentiel).

    SELECT code_racine, COUNT(*) AS nb_combinaisons_realistes
    FROM postcoord
    GROUP BY code_racine
    ORDER BY nb_combinaisons_realistes DESC
    LIMIT 20

Optimisation
------------
- Lecture en `inferSchema=False` + schema explicite : evite un premier passage
  de scan complet du fichier rien que pour deviner les types (gain de temps
  sur un fichier de cette taille).
- `spark.sql.shuffle.partitions` reduit (defaut 200, beaucoup trop pour un
  fichier de quelques centaines de milliers de lignes en local) : evite de
  creer des centaines de petites taches inutiles pour un GROUP BY qui reste
  local.

Usage
-----
    python extract_bigdata_spark.py --csv /chemin/vers/codes_postcoord_realistes_v2.csv \
                                     --out extraction_bigdata_top_codes.csv
"""
import argparse
import sys

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", required=True, help="Chemin vers codes_postcoord_realistes_v2.csv"
    )
    parser.add_argument("--out", default="extraction_bigdata_top_codes.csv")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    spark = (
        SparkSession.builder.appName("cim11-extraction-postcoord")
        .config("spark.sql.shuffle.partitions", "8")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    schema = StructType([
        StructField("code_racine", StringType(), True),
        StructField("libelle_racine", StringType(), True),
        StructField("code_postcoord", StringType(), True),
        StructField("libelles_extensions", StringType(), True),
    ])

    df = spark.read.csv(args.csv, header=True, schema=schema)
    df.createOrReplaceTempView("postcoord")

    result = spark.sql(
        f"""
        SELECT code_racine, COUNT(*) AS nb_combinaisons_realistes
        FROM postcoord
        GROUP BY code_racine
        ORDER BY nb_combinaisons_realistes DESC
        LIMIT {args.top}
        """
    )

    total = df.count()
    print(f"Lignes lues (big data / Spark) : {total}")
    result.show(args.top, truncate=False)

    result.coalesce(1).toPandas().to_csv(args.out, index=False)
    print(f"Résultat -> {args.out}")

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
