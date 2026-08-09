# Modélisation des données — Assistant de codage CIM-11

Base sur les fichiers réels du stage (`Serenic_M`) : `finetune_train.jsonl` (CRH synthétiques + DP/DAS),
`cim11_termes.csv` (référentiel CIM-11), `synonymes.csv`, `codes_postcoord_realistes_v2.csv`, `axes_par_code.csv`.

## MCD (entités / associations)

```
PATIENT_FICTIF (id_patient, nom, prenom, date_naissance, sexe)
   1,N ── concerne ── SEJOUR
SEJOUR (id_sejour, date_entree, date_sortie, mode_entree, mode_sortie, mode_hospit,
        specialite_medicale, age)
   1,N ── documenté par ── CRH
CRH (id_crh, texte_crh, date_redaction)
   1,N ── contient ── DIAGNOSTIC
DIAGNOSTIC (id_diagnostic, type[DP|DAS], libelle_diagnostic)
   N,1 ── codé par ── CODE_CIM11
CODE_CIM11 (code, libelle, type)
   1,N ── possède ── SYNONYME
SYNONYME (id_synonyme, synonyme, source)
   1,N ── se décline en ── CODE_POSTCOORD (réflexif sur CODE_CIM11 via code_racine)
CODE_POSTCOORD (code_postcoord, libelles_extensions)
   1,N ── contraint par ── AXE_POSTCOORD
AXE_POSTCOORD (id_axe, axe_nom, allow_multiple, taille_axe, raison_arret)
```

## RGPD

`PATIENT_FICTIF` ne contient que des identités synthétiques générées par l'API Mistral pendant le stage
(aucune donnée patient réelle). Le champ est conservé tel quel pour illustrer la démarche
d'anonymisation dans le rapport E1 (C4), mais en conditions réelles ce module appliquerait un
pseudonymat (hash de l'identifiant + séparation stricte identité / données de santé).

## MLD (schéma relationnel — voir db/schema.sql)

- `patient_fictif(id_patient PK, nom, prenom, date_naissance, sexe)`
- `sejour(id_sejour PK, id_patient FK, date_entree, date_sortie, mode_entree, mode_sortie, mode_hospit, specialite_medicale, age)`
- `crh(id_crh PK, id_sejour FK, texte_crh, date_redaction)`
- `code_cim11(code PK, libelle, type)`
- `diagnostic(id_diagnostic PK, id_crh FK, type_diag, code_cim11 FK)`
- `synonyme(id_synonyme PK, code_cim11 FK, synonyme, source)`
- `code_postcoord(code_postcoord PK, code_racine FK -> code_cim11, libelles_extensions)`
- `axe_postcoord(id_axe PK, code_cim11 FK, axe_nom, allow_multiple, taille_axe, raison_arret)`

## Limitation connue — synonymes

`synonymes.csv` (dossier `Recherche_Synonymes_CIM10`) indexe les synonymes par **code
CIM-10**, pas par code CIM-11 : le chargement dans `synonyme` (FK vers `code_cim11`)
ne trouve donc aucune correspondance directe (0 ligne chargée en l'état). Une table de
correspondance CIM-10 → CIM-11 existe déjà dans le stage
(`Dictionnaire/CIM11/mapping/10To11MapToOneCategory.xlsx`) et permettrait de la
raccorder ; non traité ici, hors périmètre de la certification (aucune compétence ne
porte spécifiquement sur les synonymes).

## Volumétrie réelle observée (référence pour le dimensionnement)

| Table source | Fichier stage | Lignes |
|---|---|---|
| code_cim11 | `cim11_termes.csv` | 119 537 |
| synonyme | `synonymes.csv` | 220 891 |
| code_postcoord | `codes_postcoord_realistes_v2.csv` | 570 133 |
| axe_postcoord | `axes_par_code.csv` | 21 679 |
| crh + diagnostic | `finetune_train.jsonl` | 150 CRH annotés |
