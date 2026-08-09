"""API REST — mise à disposition du jeu de données CIM-11 (bloc 1, E1, C5).

Endpoints :
- GET  /health                         : vérification de service (utilisé par le monitorage, E5)
- GET  /codes                          : liste paginée du référentiel CIM-11
- GET  /codes/{code}                   : détail d'un code (+ synonymes, + post-coordination)
- GET  /crh                            : liste paginée des CRH (avec leurs diagnostics)
- GET  /crh/{id_crh}                   : détail d'un CRH
- POST /crh                            : création d'un CRH annoté (alimentation du jeu de données)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from . import models, schemas
from .database import engine, get_db, Base
from .auth import require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables si elles n'existent pas encore (utile en dev/CI avec SQLite).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="CIM-11 Data API",
    description="Mise à disposition du jeu de données (CRH, référentiel CIM-11, post-coordination).",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["monitoring"])
def health():
    return {"status": "ok"}


@app.get("/codes", response_model=list[schemas.CodeCim11Out], tags=["referentiel"])
def list_codes(
    q: str | None = Query(default=None, description="Filtre plein texte sur le libellé"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    stmt = select(models.CodeCim11)
    if q:
        stmt = stmt.where(models.CodeCim11.libelle.ilike(f"%{q}%"))
    stmt = stmt.offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()


@app.get("/codes/{code}", tags=["referentiel"])
def get_code(code: str, db: Session = Depends(get_db), _=Depends(require_api_key)):
    obj = db.get(models.CodeCim11, code)
    if obj is None:
        raise HTTPException(status_code=404, detail="Code CIM-11 inconnu")
    return {
        "code": obj.code,
        "libelle": obj.libelle,
        "type": obj.type,
        "synonymes": [schemas.SynonymeOut.model_validate(s) for s in obj.synonymes],
        "postcoordination": [p.code_postcoord for p in obj.postcoords],
    }


@app.get("/crh", response_model=list[schemas.CrhOut], tags=["crh"])
def list_crh(
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_api_key),
):
    stmt = (
        select(models.Crh)
        .options(joinedload(models.Crh.diagnostics))
        .offset(offset)
        .limit(limit)
    )
    return db.execute(stmt).unique().scalars().all()


@app.get("/crh/{id_crh}", response_model=schemas.CrhOut, tags=["crh"])
def get_crh(id_crh: int, db: Session = Depends(get_db), _=Depends(require_api_key)):
    obj = db.get(models.Crh, id_crh)
    if obj is None:
        raise HTTPException(status_code=404, detail="CRH introuvable")
    return obj


@app.post("/crh", response_model=schemas.CrhOut, status_code=201, tags=["crh"])
def create_crh(payload: schemas.CrhIn, db: Session = Depends(get_db), _=Depends(require_api_key)):
    sejour = db.get(models.Sejour, payload.id_sejour)
    if sejour is None:
        raise HTTPException(status_code=404, detail="Séjour inconnu — créez le séjour avant le CRH")

    crh = models.Crh(id_sejour=payload.id_sejour, texte_crh=payload.texte_crh)
    for diag in payload.diagnostics:
        code_ref = db.get(models.CodeCim11, diag.code_cim11)
        if code_ref is None:
            raise HTTPException(status_code=404, detail=f"Code CIM-11 inconnu : {diag.code_cim11}")
        crh.diagnostics.append(
            models.Diagnostic(type_diag=diag.type_diag, code_cim11=diag.code_cim11, libelle_saisi=diag.libelle_saisi)
        )
    db.add(crh)
    db.commit()
    db.refresh(crh)
    return crh
