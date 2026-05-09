"""Project CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.project import Project
from ..storage import ProjectRow, get_db

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    address: Optional[str] = None
    price: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    description: Optional[str] = None
    template_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    price: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    description: Optional[str] = None
    template_id: Optional[str] = None


@router.post("", response_model=Project)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    row = ProjectRow(
        id=str(uuid.uuid4()),
        name=body.name,
        address=body.address,
        price=body.price,
        beds=body.beds,
        baths=body.baths,
        sqft=body.sqft,
        description=body.description,
        template_id=body.template_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return Project.model_validate(row)


@router.get("", response_model=list[Project])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    rows = db.query(ProjectRow).order_by(ProjectRow.created_at.desc()).all()
    return [Project.model_validate(r) for r in rows]


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    row = db.get(ProjectRow, project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return Project.model_validate(row)


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    row = db.get(ProjectRow, project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return Project.model_validate(row)


@router.delete("/{project_id}", status_code=204, response_class=Response)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    row = db.get(ProjectRow, project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
