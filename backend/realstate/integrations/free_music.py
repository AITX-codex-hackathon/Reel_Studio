"""Free To Use music browsing, caching, and beat-grid preparation.

This module folds the useful EasyBeatSync music workflow into the app backend:
track browsing stays server-side and inserted tracks are cached per project by
stable track id.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

DEFAULT_API_BASE = "https://api.freetouse.com/v3"
USER_AGENT = "EstateReelMaker/0.1 EasyBeatSync"

PREFERRED_MUSIC_TERMS = {
    "acoustic",
    "ambient",
    "beautiful",
    "calm",
    "cinematic",
    "commercial",
    "corporate",
    "documentary",
    "dramatic",
    "dreamy",
    "elegant",
    "emotional",
    "gentle",
    "hopeful",
    "inspirational",
    "luxury",
    "motivational",
    "orchestral",
    "piano",
    "positive",
    "relaxing",
    "smooth",
    "soft",
    "soothing",
    "uplifting",
    "warm",
}


class FreeMusicError(RuntimeError):
    """Raised when the Free To Use API, download, or beat analysis fails."""


@dataclass
class FreeMusicTrack:
    id: str
    title: str
    artist: str
    duration_sec: Optional[float]
    genre: Optional[str]
    tags: list[str]
    thumbnail_url: Optional[str]
    preview_url: Optional[str]
    score: int
    raw: dict[str, Any]


@dataclass
class PreparedTrack:
    source: str
    api_base: str
    track_id: str
    title: str
    artist: str
    duration_sec: Optional[float]
    audio_path: Path
    metadata_path: Path
    timestamps_path: Path
    cuts_dir: Optional[Path]
    manifest_path: Path
    tempo: float
    beat_count: int
    beat_timestamps_ms: list[int]
    attribution: str
    raw: dict[str, Any]

    def manifest(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "apiBase": self.api_base,
            "trackId": self.track_id,
            "title": self.title,
            "artist": self.artist,
            "durationSec": self.duration_sec,
            "audioPath": self.audio_path.name,
            "metadataPath": self.metadata_path.name,
            "timestampsPath": self.timestamps_path.name,
            "cutsDir": self.cuts_dir.name if self.cuts_dir else None,
            "timestampUnit": "ms",
            "timestampFormat": "yaml:type1",
            "cutFormat": "wav",
            "tempo": self.tempo,
            "beatCount": self.beat_count,
            "beatTimestampsMs": self.beat_timestamps_ms,
            "attribution": self.attribution,
        }


class FreeMusicClient:
    def __init__(self, api_base: str = DEFAULT_API_BASE):
        self.api_base = api_base.rstrip("/")

    def list_tracks(
        self,
        *,
        query: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        order: str = "release_date",
        sort: str = "desc",
    ) -> list[FreeMusicTrack]:
        limit = max(1, min(limit, 50))
        fetch_limit = max(limit * 4, 40)
        path = "/music/tracks/search" if query else "/music/tracks/all"
        params: dict[str, Any] = {
            "limit": fetch_limit,
            "offset": max(0, offset),
            "order": order,
            "sort": sort,
        }
        if query:
            params["query"] = query

        payload = self._request_json(path, params)
        tracks = [_normalize_track(item) for item in _payload_tracks(payload)]
        visible = tracks
        visible.sort(key=lambda track: track.score, reverse=True)
        return visible[:limit]

    def get_track(self, track_id: str) -> dict[str, Any]:
        payload = self._request_json(f"/music/tracks/{track_id}")
        track = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(track, dict):
            raise FreeMusicError(f"Track {track_id} was not returned by the Free To Use API.")
        return track

    def prepare_track(
        self,
        *,
        track_id: str,
        output_dir: Path,
        make_cuts: bool = True,
        include_tail: bool = False,
        hop_length: int = 512,
    ) -> PreparedTrack:
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = output_dir / "manifest.json"
        audio_path = output_dir / "track.mp3"
        metadata_path = output_dir / "metadata.json"
        timestamps_path = output_dir / "beats.yaml"
        cuts_dir = output_dir / "cuts" if make_cuts else None

        if manifest_path.exists() and audio_path.exists() and timestamps_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            beat_timestamps = load_timestamps(timestamps_path)
            if make_cuts and cuts_dir and not any(cuts_dir.glob("*.wav")):
                cut_audio(audio_path, timestamps_path, cuts_dir, include_tail=include_tail)
            return PreparedTrack(
                source="free-to-use",
                api_base=self.api_base,
                track_id=track_id,
                title=str(manifest.get("title") or raw.get("title") or "Untitled"),
                artist=str(manifest.get("artist") or track_artists(raw)),
                duration_sec=_optional_float(manifest.get("durationSec") or raw.get("duration")),
                audio_path=audio_path,
                metadata_path=metadata_path,
                timestamps_path=timestamps_path,
                cuts_dir=cuts_dir if cuts_dir and cuts_dir.exists() else None,
                manifest_path=manifest_path,
                tempo=float(manifest.get("tempo") or 0.0),
                beat_count=int(manifest.get("beatCount") or len(beat_timestamps)),
                beat_timestamps_ms=beat_timestamps,
                attribution=str(manifest.get("attribution") or attribution_for(raw)),
                raw=raw,
            )

        track = self.get_track(track_id)
        files = track.get("files") if isinstance(track.get("files"), dict) else {}
        mp3_url = files.get("mp3")
        if not mp3_url:
            raise FreeMusicError(f"Track {track_id} does not include an MP3 file URL.")

        download_url(mp3_url, audio_path)
        metadata_path.write_text(json.dumps(track, indent=2), encoding="utf-8")

        tempo, beat_timestamps = detect_beats(audio_path, hop_length=hop_length)
        write_timestamps(beat_timestamps, timestamps_path)

        written_cuts: list[Path] = []
        if make_cuts and cuts_dir:
            written_cuts = cut_audio(audio_path, timestamps_path, cuts_dir, include_tail=include_tail)

        prepared = PreparedTrack(
            source="free-to-use",
            api_base=self.api_base,
            track_id=track_id,
            title=str(track.get("title") or "Untitled"),
            artist=track_artists(track),
            duration_sec=_optional_float(track.get("duration")),
            audio_path=audio_path,
            metadata_path=metadata_path,
            timestamps_path=timestamps_path,
            cuts_dir=cuts_dir if written_cuts else None,
            manifest_path=manifest_path,
            tempo=tempo,
            beat_count=len(beat_timestamps),
            beat_timestamps_ms=beat_timestamps,
            attribution=attribution_for(track),
            raw=track,
        )
        manifest_path.write_text(json.dumps(prepared.manifest(), indent=2), encoding="utf-8")
        return prepared

    def _request_json(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        try:
            with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(f"{self.api_base}{path}", params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as error:
            raise FreeMusicError(f"Free To Use request failed: {error}") from error
        except ValueError as error:
            raise FreeMusicError("Free To Use returned invalid JSON.") from error

        if isinstance(payload, dict) and payload.get("ok") is False:
            raise FreeMusicError(str(payload.get("error") or "Free To Use request failed."))
        return payload


def download_url(url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream("GET", url, timeout=120.0, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            with open(output_path, "wb") as file:
                for chunk in response.iter_bytes(1024 * 1024):
                    if chunk:
                        file.write(chunk)
    except httpx.HTTPError as error:
        raise FreeMusicError(f"Track download failed: {error}") from error
    return output_path


def detect_beats(audio_path: Path, hop_length: int = 512) -> tuple[float, list[int]]:
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as error:
        raise FreeMusicError(f"Missing audio dependency: {error.name}") from error

    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        if y.size == 0:
            raise FreeMusicError(f"Audio file is empty: {audio_path}")
        tempo, beat_times = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, units="time")
    except FreeMusicError:
        raise
    except Exception as error:
        raise FreeMusicError(f"Beat detection failed: {error}") from error

    tempo_value = float(np.asarray(tempo).reshape(-1)[0])
    beat_ms = sorted({int(round(time * 1000)) for time in beat_times if time > 0})
    if not beat_ms:
        raise FreeMusicError("No beats detected.")
    return tempo_value, beat_ms


def write_timestamps(beat_ms: list[int], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        yaml.safe_dump({"type1": beat_ms}, file, sort_keys=False)


def load_timestamps(path: Path) -> list[int]:
    with open(path, encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    timestamps = data.get("type1")
    if not isinstance(timestamps, list):
        raise FreeMusicError(f"{path} does not contain a type1 timestamp list.")
    return sorted(int(round(float(value))) for value in timestamps if float(value) > 0)


def cut_audio(
    audio_path: Path,
    timestamps_path: Path,
    output_dir: Path,
    *,
    include_tail: bool = False,
) -> list[Path]:
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
        import soundfile as sf  # type: ignore
    except ImportError as error:
        raise FreeMusicError(f"Missing audio dependency: {error.name}") from error

    audio, sr = librosa.load(audio_path, sr=None, mono=False)
    if audio.ndim > 1:
        audio = np.asarray(audio).T

    total_samples = len(audio)
    total_ms = int(round(total_samples * 1000 / sr))
    timestamps = [value for value in load_timestamps(timestamps_path) if value < total_ms]
    boundaries = [0] + timestamps
    if include_tail:
        boundaries.append(total_ms)

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, (start_ms, end_ms) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if end_ms <= start_ms:
            continue
        start_sample = round(start_ms * sr / 1000)
        end_sample = round(end_ms * sr / 1000)
        output_path = output_dir / f"beat_{index:04d}_{start_ms:09d}-{end_ms:09d}ms.wav"
        sf.write(output_path, audio[start_sample:end_sample], sr)
        written.append(output_path)
    return written


def is_track_allowed(track: dict[str, Any]) -> bool:
    return True


def track_score(track: dict[str, Any]) -> int:
    text = _track_search_text(track)
    score = sum(3 for term in PREFERRED_MUSIC_TERMS if term in text)
    duration = _optional_float(track.get("duration"))
    if duration and 25 <= duration <= 120:
        score += 2
    return score


def track_artists(track: dict[str, Any]) -> str:
    names: list[str] = []
    for item in track.get("artists") or []:
        if isinstance(item, list) and len(item) > 1 and isinstance(item[1], dict):
            names.append(str(item[1].get("name") or ""))
        elif isinstance(item, dict):
            names.append(str(item.get("name") or ""))
    return ", ".join(name for name in names if name) or "Unknown Artist"


def track_tags(track: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in track.get("tags_categories") or track.get("categories") or track.get("tags") or []:
        if isinstance(item, list) and len(item) > 1:
            value = item[1]
            labels.append(str(value.get("name") or "") if isinstance(value, dict) else str(value))
        elif isinstance(item, dict):
            labels.append(str(item.get("name") or ""))
        elif isinstance(item, str):
            labels.append(item)
    return [label for label in labels if label]


def attribution_for(track: dict[str, Any]) -> str:
    return f"{track_artists(track)} - {track.get('title', 'Untitled')} | Free To Use: freetouse.com/music"


def _normalize_track(track: dict[str, Any]) -> FreeMusicTrack:
    thumbs = track.get("thumbnails") or {}
    files = track.get("files") if isinstance(track.get("files"), dict) else {}
    return FreeMusicTrack(
        id=str(track.get("id") or ""),
        title=str(track.get("title") or "Untitled"),
        artist=track_artists(track),
        duration_sec=_optional_float(track.get("duration")),
        genre=str(track.get("genre")) if track.get("genre") else None,
        tags=track_tags(track),
        thumbnail_url=_first_url(thumbs),
        preview_url=files.get("mp3") if isinstance(files.get("mp3"), str) else None,
        score=track_score(track),
        raw=track,
    )


def _payload_tracks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("data", payload)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict) and item.get("id")]


def _first_url(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for item in value.values():
            found = _first_url(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _first_url(item)
            if found:
                return found
    return None


def _track_search_text(track: dict[str, Any]) -> str:
    parts = [
        str(track.get("title") or ""),
        str(track.get("genre") or ""),
        " ".join(track_tags(track)),
        track_artists(track),
    ]
    return _normalize_text(" ".join(parts))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ")).lower()


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
