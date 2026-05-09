"""Template browsing + creation from natural language."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agents.openai_client import OpenAIUnavailable
from ..agents.prompt_translator import PromptTranslator
from ..models.template import Template
from ..storage.filesystem import TemplateLoader

router = APIRouter(prefix="/templates", tags=["templates"])

_loader = TemplateLoader()


@router.get("", response_model=list[Template])
def list_templates() -> list[Template]:
    return _loader.list()


@router.get("/{template_id}", response_model=Template)
def get_template(template_id: str) -> Template:
    t = _loader.get(template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


class FromPromptBody(BaseModel):
    brief: str
    name: Optional[str] = None
    save: bool = False


@router.post("/from-prompt", response_model=Template)
async def from_prompt(body: FromPromptBody) -> Template:
    try:
        translator = PromptTranslator()
        template = await translator.translate(brief=body.brief, name=body.name)
    except OpenAIUnavailable as e:
        raise HTTPException(503, f"Prompt translation requires OPENAI_API_KEY: {e}")
    except Exception as e:
        raise HTTPException(500, f"Translation failed: {e}")

    if body.save:
        _loader.save(template)
    return template
