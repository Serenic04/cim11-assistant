from pydantic import BaseModel, Field


class PredictIn(BaseModel):
    texte_crh: str = Field(..., min_length=10, max_length=20000, description="Texte du CRH a coder")


class DiagnosticPred(BaseModel):
    libelle: str
    code: str


class PredictOut(BaseModel):
    dp: DiagnosticPred | None
    das: list[DiagnosticPred] = []
    latence_ms: float
    modele: str
