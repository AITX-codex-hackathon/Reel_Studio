"""Local stock audio library — scans `audio_library/` for tagged tracks.

A track's tags are encoded in its filename:
    cinematic-slow-warm.mp3      -> tags: cinematic, slow, warm
    upbeat-fast-modern_01.mp3    -> tags: upbeat, fast, modern

Or via a sidecar JSON: `cinematic-slow-warm.mp3.json`:
    {"mood": "cinematic", "tempo": "slow", "tags": ["warm", "piano"], "bpm": 72}

The user can drop royalty-free tracks (Pixabay, Mixkit, etc.) into the folder.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}


@dataclass
class AudioTrack:
    path: Path
    name: str
    mood: Optional[str] = None
    tempo: Optional[str] = None
    tags: tuple[str, ...] = ()
    bpm: Optional[float] = None


class StockAudioLibrary:
    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or os.getenv("AUDIO_LIBRARY_ROOT", "./audio_library"))
        self._cache: Optional[list[AudioTrack]] = None

    def scan(self) -> list[AudioTrack]:
        """Walk the library and build the track list. Cached."""
        if self._cache is not None:
            return self._cache

        tracks: list[AudioTrack] = []
        if not self.root.exists():
            log.info("Audio library %s does not exist", self.root)
            self._cache = []
            return tracks

        for p in sorted(self.root.rglob("*")):
            if p.suffix.lower() not in _AUDIO_EXTS:
                continue

            track = AudioTrack(path=p, name=p.stem)

            # 1) sidecar JSON
            side = p.with_suffix(p.suffix + ".json")
            if side.exists():
                try:
                    data = json.loads(side.read_text())
                    track.mood = data.get("mood")
                    track.tempo = data.get("tempo")
                    track.tags = tuple(data.get("tags", []))
                    track.bpm = data.get("bpm")
                except Exception:
                    pass

            # 2) parse name for tags if no sidecar
            if not track.mood:
                tokens = [t.lower() for t in re.split(r"[-_\s.]+", p.stem) if t]
                if tokens:
                    # cheap heuristic: first token is mood, second is tempo
                    track.mood = tokens[0]
                    if len(tokens) > 1:
                        track.tempo = tokens[1]
                    track.tags = tuple(tokens)

            tracks.append(track)

        log.info("Scanned %d tracks from %s", len(tracks), self.root)
        self._cache = tracks
        return tracks

    def find(self, query: str, seed: int = 42) -> Optional[AudioTrack]:
        """Resolve a track_query string to a track on disk.

        Query forms:
          - "path/to/file.mp3"           → exact relative path under root
          - "mood:cinematic tempo:slow"  → tag query
          - "filename.mp3"               → by name
        """
        query = query.strip()
        if not query:
            return None

        tracks = self.scan()
        if not tracks:
            return None

        # 1) exact path match
        candidate = self.root / query
        if candidate.exists() and candidate.suffix.lower() in _AUDIO_EXTS:
            return AudioTrack(path=candidate, name=candidate.stem)

        # 2) by name
        for t in tracks:
            if t.name.lower() == Path(query).stem.lower():
                return t

        # 3) tag query — score each track
        wants = _parse_tag_query(query)
        if wants:
            scored = []
            for t in tracks:
                score = 0
                if "mood" in wants and t.mood == wants["mood"]:
                    score += 3
                if "tempo" in wants and t.tempo == wants["tempo"]:
                    score += 2
                for tag in wants.get("tags", []):
                    if tag in t.tags:
                        score += 1
                if score > 0:
                    scored.append((score, t))
            if scored:
                scored.sort(key=lambda x: -x[0])
                top = [t for s, t in scored if s == scored[0][0]]
                rng = random.Random(seed)
                return rng.choice(top)

        # 4) random fallback so something always plays
        rng = random.Random(seed)
        return rng.choice(tracks)


def _parse_tag_query(q: str) -> dict:
    """Parse 'mood:cinematic tempo:slow piano' into {mood, tempo, tags}."""
    out: dict = {"tags": []}
    for part in q.split():
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.lower()] = v.lower()
        else:
            out["tags"].append(part.lower())
    return out
