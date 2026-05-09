"""Filesystem layout + template loader."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

from ..models.template import Template

log = logging.getLogger(__name__)


class ProjectFiles:
    """Layout under storage_data/{project_id}/.

      uploads/         original user images
      generated/       Nano Banana outputs
      renders/         draft.mp4, final.mp4
      scratch/         intermediate files (audio cuts etc.)
      storyboard.json  most recent storyboard (also in DB)
    """

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or os.getenv("STORAGE_ROOT", "./storage_data"))
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        d = self.root / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def uploads_dir(self, project_id: str) -> Path:
        d = self.project_dir(project_id) / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def generated_dir(self, project_id: str) -> Path:
        d = self.project_dir(project_id) / "generated"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def renders_dir(self, project_id: str) -> Path:
        d = self.project_dir(project_id) / "renders"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def scratch_dir(self, project_id: str) -> Path:
        d = self.project_dir(project_id) / "scratch"
        d.mkdir(parents=True, exist_ok=True)
        return d


class TemplateLoader:
    """Load YAML templates from the bundled templates directory."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            # __file__ is .../realstate/storage/filesystem.py — go up to package root
            templates_dir = Path(__file__).resolve().parent.parent / "templates"
        self.templates_dir = templates_dir

    def list(self) -> list[Template]:
        out: list[Template] = []
        if not self.templates_dir.exists():
            log.warning("Templates dir %s missing", self.templates_dir)
            return out
        for path in sorted(self.templates_dir.glob("*.yaml")):
            try:
                out.append(self._load_one(path))
            except Exception as e:
                log.exception("Failed loading template %s: %s", path, e)
        return out

    def get(self, template_id: str) -> Optional[Template]:
        for t in self.list():
            if t.template_id == template_id:
                return t
        return None

    def _load_one(self, path: Path) -> Template:
        with open(path) as f:
            data = yaml.safe_load(f)
        return Template(**data)

    def save(self, template: Template) -> Path:
        """Persist a template to disk (e.g. one created via PromptTranslator)."""
        path = self.templates_dir / f"{template.template_id}.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(
                template.model_dump(mode="json"),
                f,
                sort_keys=False,
                allow_unicode=True,
                width=100,
            )
        return path
