"""Schémas Pydantic (couche de sérialisation de l'API)."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CodeCim11Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    libelle: str
    type: Optional[str] = None


class SynonymeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_synonyme: int
    synonyme: str
    source: Optional[str] = None


class DiagnosticOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_diagnostic: int
    type_diag: str
    code_cim11: str
    libelle_saisi: Optional[str] = None


class DiagnosticIn(BaseModel):
    type_diag: str
    code_cim11: str
    libelle_saisi: Optional[str] = None


class CrhOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_crh: int
    id_sejour: int
    texte_crh: str
    date_redaction: Optional[datetime] = None
    diagnostics: list[DiagnosticOut] = []


class CrhIn(BaseModel):
    id_sejour: int
    texte_crh: str
    diagnostics: list[DiagnosticIn] = []


class SejourOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_sejour: int
    id_patient: int
    date_entree: Optional[date] = None
    date_sortie: Optional[date] = None
    mode_entree: Optional[str] = None
    mode_sortie: Optional[str] = None
    mode_hospit: Optional[str] = None
    specialite_medicale: Optional[str] = None
