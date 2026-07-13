import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.agent.tools import search_hcp
from app.database import get_db

router = APIRouter(prefix="/api/hcps", tags=["hcps"])


@router.get("")
def list_hcps(q: str = ""):
    return json.loads(search_hcp.invoke({"query": q}))


@router.post("", response_model=schemas.HCPOut)
def create_hcp(payload: schemas.HCPCreate, db: Session = Depends(get_db)):
    hcp = crud.get_or_create_hcp(db, payload.name)
    if payload.specialty:
        hcp.specialty = payload.specialty
    if payload.institution:
        hcp.institution = payload.institution
    if payload.email:
        hcp.email = payload.email
    if payload.phone:
        hcp.phone = payload.phone
    db.commit()
    db.refresh(hcp)
    return hcp
