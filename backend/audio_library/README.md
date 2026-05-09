# Audio Library

Drop royalty-free audio tracks here. The pipeline scans this folder for files
matching `*.mp3`, `*.m4a`, `*.wav`, `*.aac`, `*.ogg`, `*.flac`.

## Tagging

Tags can be encoded two ways:

### 1. Filename (quick)

`{mood}-{tempo}-{extra}.mp3` — e.g.:
- `cinematic-slow-warm.mp3` → mood=cinematic, tempo=slow, tags=[cinematic, slow, warm]
- `upbeat-fast-modern.mp3` → mood=upbeat, tempo=fast
- `vibey-medium-coastal.mp3` → mood=vibey, tempo=medium

### 2. Sidecar JSON (precise)

For each `track.mp3`, optionally drop a `track.mp3.json` next to it:

```json
{
  "mood": "cinematic",
  "tempo": "slow",
  "tags": ["piano", "warm", "ambient"],
  "bpm": 72
}
```

## Where to get tracks

The bundled templates query for these moods:
- `cinematic` (slow tempo) — luxury / cinematic templates
- `upbeat` (fast) — quick-flip
- `vibey` (medium) — Airbnb spotlight

Free sources (CC0 / royalty-free, but verify each track's license yourself):
- https://pixabay.com/music/
- https://mixkit.co/free-stock-music/
- https://www.bensound.com/free-music-for-videos
- https://freemusicarchive.org/

## What if there are no tracks?

The renderer will still produce a video — just silent. The `audio_cues` in the
template will be skipped, the WebSocket will log "cue had no resolvable audio",
and you can re-render once you've added music.
