#!/usr/bin/env python3
"""
List Free To Use music, download tracks, detect beat timestamps, and cut audio
on those beat boundaries.

Examples:
  python tools/free_music_beats.py list --limit 10
  python tools/free_music_beats.py search cinematic --limit 10
  python tools/free_music_beats.py prepare TRACK_ID --output-dir ./my_song --cuts
"""
import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


DEFAULT_API_BASE = "https://api.freetouse.com/v3"


def stop(message):
    raise SystemExit(f"Program stopped: {message}")


def slugify(value):
    value = re.sub(r"[^\w\s.-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "track"


def request_json(api_base, path, params=None):
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{api_base.rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"

    request = urllib.request.Request(url, headers={"User-Agent": "EasyBeatSync/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if isinstance(payload, dict) and payload.get("ok") is False:
        stop(payload.get("error") or f"API request failed for {path}")
    return payload


def track_artists(track):
    names = []
    for item in track.get("artists") or []:
        if isinstance(item, list) and len(item) > 1 and isinstance(item[1], dict):
            names.append(item[1].get("name", ""))
        elif isinstance(item, dict):
            names.append(item.get("name", ""))
    return ", ".join(name for name in names if name) or "Unknown Artist"


def track_tags(track):
    labels = []
    for item in track.get("tags_categories") or track.get("categories") or track.get("tags") or []:
        if isinstance(item, list) and len(item) > 1:
            value = item[1]
            labels.append(value.get("name", "") if isinstance(value, dict) else str(value))
        elif isinstance(item, dict):
            labels.append(item.get("name", ""))
        elif isinstance(item, str):
            labels.append(item)
    return ", ".join(label for label in labels if label)


def get_track(api_base, track_id):
    payload = request_json(api_base, f"/music/tracks/{track_id}")
    return payload.get("data", payload)


def list_tracks(args):
    params = {
        "limit": args.limit,
        "offset": args.offset,
        "order": args.order,
        "sort": args.sort,
    }
    path = "/music/tracks/search" if args.query else "/music/tracks/all"
    if args.query:
        params["query"] = args.query

    payload = request_json(args.api_base, path, params)
    tracks = payload.get("data", payload if isinstance(payload, list) else [])
    if args.json:
        print(json.dumps(payload, indent=2))
        return

    for index, track in enumerate(tracks, start=args.offset + 1):
        duration = track.get("duration")
        duration_text = f"{duration:.1f}s" if isinstance(duration, (int, float)) else "unknown"
        print(f"{index:>3}. {track.get('id')}")
        print(f"     {track_artists(track)} - {track.get('title', 'Untitled')} ({duration_text})")
        if track.get("genre"):
            print(f"     genre: {track['genre']}")
        tags = track_tags(track)
        if tags:
            print(f"     tags: {tags}")

    pagination = payload.get("pagination") if isinstance(payload, dict) else None
    if pagination:
        print(f"\nShowing {len(tracks)} of {pagination.get('count', 'unknown')} tracks.")


def download_url(url, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "EasyBeatSync/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, open(output_path, "wb") as file:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            file.write(chunk)
    return output_path


def download_track(args):
    track = get_track(args.api_base, args.track_id)
    files = track.get("files") or {}
    mp3_url = files.get("mp3")
    if not mp3_url:
        stop(f"Track {args.track_id} does not include an MP3 file URL.")

    output_dir = Path(args.output_dir)
    artist = track_artists(track)
    filename = f"{slugify(artist)} - {slugify(track.get('title', args.track_id))}.mp3"
    output_path = output_dir / filename
    download_url(mp3_url, output_path)

    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(track, indent=2), encoding="utf-8")
    print(f"Downloaded: {output_path}")
    print(f"Metadata:   {metadata_path}")
    return output_path, track


def require_audio_libs():
    try:
        import librosa
        import numpy as np
        import soundfile as sf
    except ImportError as error:
        stop(f"Missing dependency: {error.name}. Run python -m pip install -r requirements.txt")
    return librosa, np, sf


def detect_beats(audio_path, hop_length=512):
    librosa, np, _ = require_audio_libs()
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    if y.size == 0:
        stop(f"Audio file is empty: {audio_path}")

    tempo, beat_times = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, units="time")
    tempo = float(np.asarray(tempo).reshape(-1)[0])
    beat_ms = [int(round(time * 1000)) for time in beat_times if time > 0]
    beat_ms = sorted(set(beat_ms))
    if not beat_ms:
        stop("No beats detected.")
    return tempo, beat_ms


def write_timestamps(beat_ms, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        yaml.safe_dump({"type1": beat_ms}, file, sort_keys=False)


def beats_command(args):
    tempo, beat_ms = detect_beats(args.audio_path, args.hop_length)
    write_timestamps(beat_ms, Path(args.output))
    print(f"Detected {len(beat_ms)} beats at {tempo:.2f} BPM.")
    print(f"Timestamps: {args.output}")


def load_timestamps(path):
    with open(path, encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    timestamps = data.get("type1")
    if not isinstance(timestamps, list):
        stop(f"{path} does not contain a type1 timestamp list.")
    timestamps = [int(round(float(value))) for value in timestamps]
    return sorted(value for value in timestamps if value > 0)


def audio_for_soundfile(audio_path):
    librosa, np, _ = require_audio_libs()
    y, sr = librosa.load(audio_path, sr=None, mono=False)
    if y.ndim == 1:
        return y, sr
    return np.asarray(y).T, sr


def cut_audio(audio_path, timestamps_path, output_dir, include_tail=False):
    _, _, sf = require_audio_libs()
    audio, sr = audio_for_soundfile(audio_path)
    total_samples = len(audio)
    total_ms = int(round(total_samples * 1000 / sr))
    timestamps = [value for value in load_timestamps(timestamps_path) if value < total_ms]
    boundaries = [0] + timestamps
    if include_tail:
        boundaries.append(total_ms)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for index, (start_ms, end_ms) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if end_ms <= start_ms:
            continue
        start_sample = round(start_ms * sr / 1000)
        end_sample = round(end_ms * sr / 1000)
        output_path = output_dir / f"beat_{index:04d}_{start_ms:09d}-{end_ms:09d}ms.wav"
        sf.write(output_path, audio[start_sample:end_sample], sr)
        written.append(output_path)
    return written


def cuts_command(args):
    written = cut_audio(args.audio_path, args.timestamps, args.output_dir, args.include_tail)
    print(f"Wrote {len(written)} beat-aligned WAV cuts to {args.output_dir}")


def prepare_command(args):
    audio_path, track = download_track(args)
    timestamps_path = Path(args.output_dir) / f"{Path(audio_path).stem}_beats.yaml"
    tempo, beat_ms = detect_beats(audio_path, args.hop_length)
    write_timestamps(beat_ms, timestamps_path)
    print(f"Detected {len(beat_ms)} beats at {tempo:.2f} BPM.")
    print(f"Timestamps: {timestamps_path}")
    if args.cuts:
        cuts_dir = Path(args.output_dir) / f"{Path(audio_path).stem}_beat_cuts"
        written = cut_audio(audio_path, timestamps_path, cuts_dir, args.include_tail)
        print(f"Wrote {len(written)} beat-aligned WAV cuts to {cuts_dir}")

    attribution = f"{track_artists(track)} - {track.get('title', 'Untitled')} | Free To Use: freetouse.com/music"
    print(f"Attribution: {attribution}")


def build_parser():
    parser = argparse.ArgumentParser(description="Free To Use music and beat tooling for EasyBeatSync.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API base URL. Default: {DEFAULT_API_BASE}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent Free To Use tracks.")
    list_parser.add_argument("--limit", type=int, default=10)
    list_parser.add_argument("--offset", type=int, default=0)
    list_parser.add_argument("--order", default="release_date")
    list_parser.add_argument("--sort", default="desc")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(query=None, func=list_tracks)

    search_parser = subparsers.add_parser("search", help="Search Free To Use tracks.")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--offset", type=int, default=0)
    search_parser.add_argument("--order", default="release_date")
    search_parser.add_argument("--sort", default="desc")
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(func=list_tracks)

    download_parser = subparsers.add_parser("download", help="Download a track MP3 by ID.")
    download_parser.add_argument("track_id")
    download_parser.add_argument("--output-dir", default="downloads")
    download_parser.set_defaults(func=download_track)

    beats_parser = subparsers.add_parser("beats", help="Detect beat timestamps for an audio file.")
    beats_parser.add_argument("audio_path")
    beats_parser.add_argument("--output", default="timestamps.yaml")
    beats_parser.add_argument("--hop-length", type=int, default=512)
    beats_parser.set_defaults(func=beats_command)

    cuts_parser = subparsers.add_parser("cuts", help="Cut audio into WAV files between beat timestamps.")
    cuts_parser.add_argument("audio_path")
    cuts_parser.add_argument("timestamps")
    cuts_parser.add_argument("--output-dir", default="beat_cuts")
    cuts_parser.add_argument("--include-tail", action="store_true", help="Also write the final segment after the last beat.")
    cuts_parser.set_defaults(func=cuts_command)

    prepare_parser = subparsers.add_parser("prepare", help="Download a track, detect beats, and optionally cut it.")
    prepare_parser.add_argument("track_id")
    prepare_parser.add_argument("--output-dir", default="free_music_project")
    prepare_parser.add_argument("--hop-length", type=int, default=512)
    prepare_parser.add_argument("--cuts", action="store_true")
    prepare_parser.add_argument("--include-tail", action="store_true")
    prepare_parser.set_defaults(func=prepare_command)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
