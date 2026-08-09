-- Schéma PostgreSQL — Assistant de codage CIM-11
-- Modèle physique dérivé du MCD (voir docs/MCD_MLD.md)

CREATE TABLE patient_fictif (
    id_patient      SERIAL PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    prenom          VARCHAR(100) NOT NULL,
    date_naissance  DATE,
    sexe            CHAR(1) CHECK (sexe IN ('1', '2'))
);

CREATE TABLE sejour (
    id_sejour            SERIAL PRIMARY KEY,
    id_patient           INTEGER NOT NULL REFERENCES patient_fictif(id_patient) ON DELETE CASCADE,
    date_entree           DATE,
    date_sortie           DATE,
    mode_entree           VARCHAR(50),
    mode_sortie           VARCHAR(50),
    mode_hospit           VARCHAR(10),
    specialite_medicale   VARCHAR(100),
    age                   NUMERIC(5,1)
);

CREATE TABLE code_cim11 (
    code     VARCHAR(20) PRIMARY KEY,
    libelle  TEXT NOT NULL,
    type     VARCHAR(20)
);

CREATE TABLE crh (
    id_crh          SERIAL PRIMARY KEY,
    id_sejour       INTEGER NOT NULL REFERENCES sejour(id_sejour) ON DELETE CASCADE,
    texte_crh       TEXT NOT NULL,
    date_redaction  TIMESTAMP DEFAULT now()
);

CREATE TABLE diagnostic (
    id_diagnostic  SERIAL PRIMARY KEY,
    id_crh         INTEGER NOT NULL REFERENCES crh(id_crh) ON DELETE CASCADE,
    type_diag      VARCHAR(3) NOT NULL CHECK (type_diag IN ('DP', 'DAS')),
    code_cim11     VARCHAR(20) NOT NULL REFERENCES code_cim11(code),
    libelle_saisi  TEXT
);

CREATE TABLE synonyme (
    id_synonyme  SERIAL PRIMARY KEY,
    code_cim11   VARCHAR(20) NOT NULL REFERENCES code_cim11(code) ON DELETE CASCADE,
    synonyme     TEXT NOT NULL,
    source       VARCHAR(200)
);

CREATE TABLE code_postcoord (
    code_postcoord      VARCHAR(255) PRIMARY KEY,
    code_racine         VARCHAR(20) NOT NULL REFERENCES code_cim11(code) ON DELETE CASCADE,
    libelles_extensions TEXT
);

CREATE TABLE axe_postcoord (
    id_axe          SERIAL PRIMARY KEY,
    code_cim11      VARCHAR(20) NOT NULL REFERENCES code_cim11(code) ON DELETE CASCADE,
    axe_nom         VARCHAR(100) NOT NULL,
    allow_multiple  VARCHAR(30),
    taille_axe      INTEGER,
    raison_arret    TEXT
);

CREATE INDEX idx_diagnostic_crh ON diagnostic(id_crh);
CREATE INDEX idx_diagnostic_code ON diagnostic(code_cim11);
CREATE INDEX idx_synonyme_code ON synonyme(code_cim11);
CREATE INDEX idx_postcoord_racine ON code_postcoord(code_racine);
CREATE INDEX idx_axe_code ON axe_postcoord(code_cim11);
CREATE INDEX idx_sejour_patient ON sejour(id_patient);
CREATE INDEX idx_crh_sejour ON crh(id_sejour);
