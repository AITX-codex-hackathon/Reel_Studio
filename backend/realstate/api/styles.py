"""Style catalog API — browse the 100 cinematic shot styles."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..data.style_catalog import CATEGORY_ORDER, STYLE_BY_ID, STYLES
from ..models.style import VideoStyle

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("", response_model=list[VideoStyle])
def list_styles(category: Optional[str] = Query(None)) -> list[VideoStyle]:
    if category:
        return [s for s in STYLES if s.category == category]
    return STYLES


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    return CATEGORY_ORDER


@router.get("/{style_id}", response_model=VideoStyle)
def get_style(style_id: str) -> VideoStyle:
    s = STYLE_BY_ID.get(style_id)
    if not s:
        raise HTTPException(404, f"Style {style_id} not found")
    return s
