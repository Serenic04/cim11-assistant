# Extraction SQL depuis le SGBD (C2)

`extract_sgbd.py` exécute une requête SQL **brute** (pas d'ORM) contre la base
déjà peuplée par `etl/load_data.py`, via `sqlalchemy.text()`.

## Besoin métier

Identifier les codes CIM-11 « bien documentés » (qui ont à la fois des
synonymes ET des variantes de post-coordination connues), avec un exemple de
CRH réel où le code apparaît en diagnostic principal (DP) — pour prioriser
une revue manuelle du référentiel.

## Requête

```sql
SELECT
    c.code                              AS code_cim11,
    c.libelle                           AS libelle,
    COUNT(DISTINCT s.id_synonyme)       AS nb_synonymes,
    COUNT(DISTINCT p.code_postcoord)    AS nb_postcoord,
    MIN(crh.texte_crh)                  AS exemple_crh
FROM code_cim11 c
JOIN diagnostic d       ON d.code_cim11 = c.code AND d.type_diag = 'DP'
JOIN crh                ON crh.id_crh = d.id_crh
LEFT JOIN synonyme s    ON s.code_cim11 = c.code
LEFT JOIN code_postcoord p ON p.code_racine = c.code
GROUP BY c.code, c.libelle
HAVING COUNT(DISTINCT s.id_synonyme) > 0
   AND COUNT(DISTINCT p.code_postcoord) > 0
ORDER BY nb_postcoord DESC
LIMIT :limit
```

## Choix de sélection / filtrage / jointures

- `JOIN diagnostic ... type_diag = 'DP'` : ne garde que les diagnostics
  principaux (pas les DAS), pour rester sur le cas d'usage prioritaire.
- 2 `LEFT JOIN` (synonyme, code_postcoord) : un code peut légitimement n'avoir
  ni synonyme ni post-coordination chargés — le `LEFT JOIN` + `HAVING` permet
  de les compter sans les exclure prématurément d'un `INNER JOIN`.
- `GROUP BY` + `HAVING` (et non `WHERE`) : le filtre porte sur des agrégats
  (`COUNT`), donc il doit s'appliquer après l'agrégation.
- `LIMIT :limit` (paramétré, défaut 50) : borne le volume restitué côté
  client sans limiter le travail de filtrage/tri, qui reste fait par la base.

## Optimisation

`code_cim11.code` est clé primaire (indexée) : les jointures dessus sont
directes. Le tri (`ORDER BY`) et le filtrage par agrégat (`HAVING`) sont faits
côté base avant la troncature (`LIMIT`), pour éviter de rapatrier plus de
lignes que nécessaire.

## Exécution réelle (résultat vérifié)

```
export DATABASE_URL=sqlite:///./data-api-local.db   # ou une URL PostgreSQL
python -m etl.extraction_sql.extract_sgbd --limit 10
```

Sur la base réelle rechargée depuis les fichiers du stage : 8 codes CIM-11
répondent aux deux critères (synonymes ET post-coordination), le plus
documenté étant `1A40.Z` (28 synonymes, 121 variantes de post-coordination).

Testé par `tests/test_extraction_sql.py` (fixture SQLite en mémoire).
