"""Convert a pro editor's natural-language brief into a valid Template YAML.

Example brief:
    "30-second reel for a luxury condo. Open with a 4-second slow zoom on the
    exterior. Cut to the foyer at 4s with a push-in. Music starts at 4s. Show
    kitchen highlights between 8 and 16s. End on a sunset shot of the backyard
    with the price overlaid."

We round-trip through the LLM with a strict JSON schema, then validate against
the Template Pydantic model. If validation fails, we retry once with the error
fed back as a correction.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import yaml
from pydantic import ValidationError

from .openai_client import OpenAIClient, OpenAIUnavailable
from .vlm_factory import get_vlm_client
from ..models.template import Template

log = logging.getLogger(__name__)


_SYSTEM = """You are a senior video editor who converts natural-language briefs from human editors into structured YAML reel templates for a real estate video pipeline.

You output ONLY a single JSON object that matches this schema (no prose, no fences):

{
  "template_id": str (kebab-case),
  "name": str,
  "description": str,
  "target_duration_sec": float,
  "aspect_ratio": "9:16" | "1:1" | "16:9",
  "pacing_mode": "free" | "beat" | "downbeat" | "bar",
  "global_color_grade": "warm_cinematic" | "cool_modern" | "warm_lifestyle" | "punchy_vivid" | "muted_film" | null,
  "draft_resolution_p": 540,
  "final_resolution_p": 1080,
  "draft_crf": 28,
  "final_crf": 20,
  "shot_slots": [
    {
      "slot_id": str (kebab-case),
      "description": str,
      "room_type": "exterior" | "foyer" | "kitchen" | "living_room" | "bedroom" | "bathroom" | "dining" | "backyard" | "view" | "amenity" | "lifestyle" | "detail",
      "duration_sec": float (>0),
      "motion": "slow_zoom_in" | "slow_zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down" | "push_in" | "pull_out" | "static" | "generative",
      "motion_strength": float (0..1),
      "transition_in": "cut" | "dissolve" | "slide_left" | "slide_right" | "whip_pan" | "fade",
      "color_grade": str | null,
      "text_overlay_id": str | null,
      "must_fill": bool,
      "fallback_to_generated": bool,
      "generation_prompt": str | null
    }
  ],
  "audio_cues": [
    {
      "track_query": str,
      "kind": "music" | "voiceover" | "sfx",
      "start_time_sec": float,
      "end_time_sec": float | null,
      "volume_db": float,
      "fade_in_sec": float,
      "fade_out_sec": float
    }
  ],
  "text_overlays": [
    {
      "overlay_id": str,
      "text_template": str,
      "position": "top_left" | "top_right" | "bottom_left" | "bottom_right" | "center",
      "font_family": str,
      "font_size_px": int,
      "color_hex": "#RRGGBB",
      "background_hex": "#RRGGBB" | "#RRGGBBAA" | null,
      "duration_sec": float | null,
      "fade_in_sec": float,
      "fade_out_sec": float
    }
  ]
}

Rules:
- Sum of shot durations should approximately equal target_duration_sec.
- The editor's exact timing requests ("at 4s", "from 8s to 16s") MUST be honored — back-solve durations from those anchors.
- If editor mentions "music starts at 4s", set the music audio_cue start_time_sec to 4.0.
- Default volume_db: -3 for music, 0 for voiceover. Default fades: 1s in, 2s out.
- Use sensible defaults for anything not specified.
- text_overlay_id on a shot must reference an overlay defined in text_overlays."""

_USER = """Brief from the editor:

\"\"\"
{brief}
\"\"\"

Property name (use as the template name if appropriate): {name}
"""


class PromptTranslator:
    def __init__(self, claude: Optional[ClaudeClient] = None):
        self.claude = claude or ClaudeClient()

    async def translate(self, brief: str, name: Optional[str] = None) -> Template:
        if not self.llm.enabled:
            raise OpenAIUnavailable("Cannot translate prompts without OPENAI_API_KEY")

        text = await self.llm.message(
            system=_SYSTEM,
            user=_USER.format(brief=brief, name=name or "Custom Template"),
            max_tokens=3500,
        )
        data = _extract_json(text)

        try:
            return Template(**data)
        except ValidationError as ve:
            # One retry with the error attached
            log.info("Retrying translate with validation feedback")
            corrected = await self.llm.message(
                system=_SYSTEM,
                user=_USER.format(brief=brief, name=name or "Custom Template")
                + f"\n\nYour previous response failed validation:\n{ve}\n\nFix it and respond with the corrected JSON.",
                max_tokens=3500,
            )
            data = _extract_json(corrected)
            return Template(**data)

    def to_yaml(self, template: Template) -> str:
        """Serialize a Template back to YAML for saving to disk."""
        return yaml.safe_dump(
            template.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text
    # Find outermost braces
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(raw[start : end + 1])
