"""Run FFmpeg as a subprocess and stream progress."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import AsyncIterator

from .ffmpeg_builder import FFmpegCommand


@dataclass
class RenderProgress:
    progress: float  # 0.0 .. 1.0
    seconds_done: float
    fps: float
    log_line: str = ""


# ffmpeg with `-stats` writes lines like:
# frame= 425 fps= 23 q=24.0 size=    1024kB time=00:00:14.16 bitrate=...
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_FPS_RE = re.compile(r"fps=\s*(\d+(?:\.\d+)?)")


class Encoder:
    """Subprocess wrapper that yields RenderProgress as ffmpeg runs."""

    async def run(self, cmd: FFmpegCommand) -> AsyncIterator[RenderProgress]:
        """Async generator yielding progress updates. Final yield has progress=1.0."""
        proc = await asyncio.create_subprocess_exec(
            *cmd.args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        last_progress = 0.0
        last_seconds = 0.0
        last_fps = 0.0
        stderr_buf: list[str] = []

        try:
            assert proc.stdout is not None
            while True:
                # ffmpeg emits stats with \r — read in raw chunks then split
                chunk = await proc.stdout.read(512)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                stderr_buf.append(text)
                # Keep buffer bounded
                if len("".join(stderr_buf)) > 8192:
                    stderr_buf = stderr_buf[-4:]

                # Look for the latest time= and fps= in the chunk
                tmatch = list(_TIME_RE.finditer(text))
                fmatch = list(_FPS_RE.finditer(text))
                if tmatch:
                    h, m, s = tmatch[-1].groups()
                    seconds = int(h) * 3600 + int(m) * 60 + float(s)
                    last_seconds = seconds
                if fmatch:
                    last_fps = float(fmatch[-1].group(1))

                if cmd.expected_duration_sec > 0:
                    last_progress = min(1.0, last_seconds / cmd.expected_duration_sec)

                yield RenderProgress(
                    progress=last_progress,
                    seconds_done=last_seconds,
                    fps=last_fps,
                    log_line=text.strip().splitlines()[-1] if text.strip() else "",
                )
        finally:
            await proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg exited with code {proc.returncode}\n"
                f"Last output:\n{''.join(stderr_buf)[-2000:]}"
            )

        yield RenderProgress(progress=1.0, seconds_done=cmd.expected_duration_sec, fps=last_fps)
