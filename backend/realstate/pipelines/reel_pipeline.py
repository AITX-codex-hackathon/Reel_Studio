"""ReelPipeline — orchestrates: storyboard → audio resolution → ffmpeg render → mp4.

Analogous to LTX-Video's `LTXVideoPipeline.__call__()`. Single-pass.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from ..integrations.elevenlabs import ElevenLabsClient
from ..integrations.stock_audio import StockAudioLibrary
from ..models.render_config import RenderConfig
from ..models.storyboard import Storyboard
from ..models.template import AudioCue
from ..render.encoder import Encoder, RenderProgress
from ..render.ffmpeg_builder import FFmpegBuilder

log = logging.getLogger(__name__)


@dataclass
class RenderResult:
    output_path: Path
    duration_sec: float


class ReelPipeline:
    def __init__(
        self,
        builder: Optional[FFmpegBuilder] = None,
        encoder: Optional[Encoder] = None,
        stock_audio: Optional[StockAudioLibrary] = None,
        elevenlabs: Optional[ElevenLabsClient] = None,
        font_path: Optional[str] = None,
    ):
        self.builder = builder or FFmpegBuilder(font_path=font_path)
        self.encoder = encoder or Encoder()
        self.stock_audio = stock_audio or StockAudioLibrary()
        self.elevenlabs = elevenlabs or ElevenLabsClient()

    async def render(
        self,
        storyboard: Storyboard,
        config: RenderConfig,
        output_path: Path,
        global_color_grade: Optional[str] = None,
        scratch_dir: Optional[Path] = None,
    ) -> AsyncIterator[RenderProgress]:
        """Render the storyboard to `output_path`. Yields progress updates.

        Final progress = 1.0 with output_path written when done.
        """
        scratch = scratch_dir or output_path.parent / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)

        # Resolve audio cues to files on disk (download / generate / look up)
        cue_files = await self._resolve_audio_cues(
            storyboard.audio_cues,
            scratch,
            seed=config.seed,
            total_duration_sec=storyboard.total_duration_sec,
        )

        cmd = self.builder.build(
            storyboard=storyboard,
            config=config,
            output_path=output_path,
            audio_cue_files=cue_files,
            global_color_grade=global_color_grade,
        )

        log.info("Running ffmpeg: %s", " ".join(cmd.args[:4]) + " ... " + cmd.args[-1])
        async for progress in self.encoder.run(cmd):
            yield progress

    async def _resolve_audio_cues(
        self,
        cues: list[AudioCue],
        scratch_dir: Path,
        seed: int,
        total_duration_sec: float,
    ) -> dict[int, str]:
        """For each cue, find or generate the audio file. Returns {cue_index: filepath}."""
        out: dict[int, str] = {}
        for i, cue in enumerate(cues):
            q = cue.track_query.strip()
            file_path: Optional[Path] = None

            if q.startswith("gen:"):
                if cue.kind == "voiceover":
                    file_path = await self.elevenlabs.tts(
                        text=q[4:].strip(),
                        out_path=scratch_dir / f"voice_{i}.mp3",
                    )
                else:
                    file_path = await self.elevenlabs.music(
                        prompt=q[4:].strip(),
                        out_path=scratch_dir / f"music_{i}.mp3",
                        duration_sec=min(total_duration_sec, 60.0),
                    )
            elif q.startswith("file:"):
                candidate = Path(q[5:].strip()).expanduser()
                if candidate.exists() and candidate.is_file():
                    file_path = candidate
                else:
                    log.info("Cue %d file path missing — skipping: %s", i, candidate)
            else:
                track = self.stock_audio.find(q, seed=seed)
                if track:
                    file_path = track.path

            if file_path:
                out[i] = str(file_path)
            else:
                log.info("Cue %d (%s) had no resolvable audio — skipping", i, q[:40])

        return out
