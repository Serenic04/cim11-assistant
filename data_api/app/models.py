"""Modèles SQLAlchemy — reflètent le MLD décrit dans docs/MCD_MLD.md."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class PatientFictif(Base):
    __tablename__ = "patient_fictif"

    id_patient = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    date_naissance = Column(Date)
    sexe = Column(String(1))

    sejours = relationship("Sejour", back_populates="patient", cascade="all, delete-orphan")


class Sejour(Base):
    __tablename__ = "sejour"

    id_sejour = Column(Integer, primary_key=True, index=True)
    id_patient = Column(Integer, ForeignKey("patient_fictif.id_patient", ondelete="CASCADE"), nullable=False)
    date_entree = Column(Date)
    date_sortie = Column(Date)
    mode_entree = Column(String(50))
    mode_sortie = Column(String(50))
    mode_hospit = Column(String(10))
    specialite_medicale = Column(String(100))
    age = Column(Numeric(5, 1))

    patient = relationship("PatientFictif", back_populates="sejours")
    crhs = relationship("Crh", back_populates="sejour", cascade="all, delete-orphan")


class CodeCim11(Base):
    __tablename__ = "code_cim11"

    code = Column(String(20), primary_key=True)
    libelle = Column(Text, nullable=False)
    type = Column(String(20))

    synonymes = relationship("Synonyme", back_populates="code_ref", cascade="all, delete-orphan")
    postcoords = relationship("CodePostcoord", back_populates="racine", cascade="all, delete-orphan")
    axes = relationship("AxePostcoord", back_populates="code_ref", cascade="all, delete-orphan")


class Crh(Base):
    __tablename__ = "crh"

    id_crh = Column(Integer, primary_key=True, index=True)
    id_sejour = Column(Integer, ForeignKey("sejour.id_sejour", ondelete="CASCADE"), nullable=False)
    texte_crh = Column(Text, nullable=False)
    date_redaction = Column(DateTime, server_default=func.now())

    sejour = relationship("Sejour", back_populates="crhs")
    diagnostics = relationship("Diagnostic", back_populates="crh", cascade="all, delete-orphan")


class Diagnostic(Base):
    __tablename__ = "diagnostic"
    __table_args__ = (CheckConstraint("type_diag IN ('DP', 'DAS')", name="ck_type_diag"),)

    id_diagnostic = Column(Integer, primary_key=True, index=True)
    id_crh = Column(Integer, ForeignKey("crh.id_crh", ondelete="CASCADE"), nullable=False)
    type_diag = Column(String(3), nullable=False)
    code_cim11 = Column(String(20), ForeignKey("code_cim11.code"), nullable=False)
    libelle_saisi = Column(Text)

    crh = relationship("Crh", back_populates="diagnostics")
    code_ref = relationship("CodeCim11")


class Synonyme(Base):
    __tablename__ = "synonyme"

    id_synonyme = Column(Integer, primary_key=True, index=True)
    code_cim11 = Column(String(20), ForeignKey("code_cim11.code", ondelete="CASCADE"), nullable=False)
    synonyme = Column(Text, nullable=False)
    source = Column(String(200))

    code_ref = relationship("CodeCim11", back_populates="synonymes")


class CodePostcoord(Base):
    __tablename__ = "code_postcoord"

    code_postcoord = Column(String(255), primary_key=True)
    code_racine = Column(String(20), ForeignKey("code_cim11.code", ondelete="CASCADE"), nullable=False)
    libelles_extensions = Column(Text)

    racine = relationship("CodeCim11", back_populates="postcoords")


class AxePostcoord(Base):
    __tablename__ = "axe_postcoord"

    id_axe = Column(Integer, primary_key=True, index=True)
    code_cim11 = Column(String(20), ForeignKey("code_cim11.code", ondelete="CASCADE"), nullable=False)
    axe_nom = Column(String(100), nullable=False)
    allow_multiple = Column(String(30))
    taille_axe = Column(Integer)
    raison_arret = Column(Text)

    code_ref = relationship("CodeCim11", back_populates="axes")
