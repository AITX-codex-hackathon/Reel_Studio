# Codex Integration Brief

This repository is the Easy Beat Sync tool plus a new Free To Use music workflow.
Use this file as the handoff context when integrating the repo into another
editing/webapp project.

## What This Repo Already Does

### Beat-synced video rendering

Entry point:

```sh
python EasyBeatSync.py /path/to/project-folder
```

`EasyBeatSync.py` expects one project folder containing:

```txt
project-folder/
  song.mp3
  timestamps.yaml
  images_or_videos/
    clip_or_photo_001.mp4
    clip_or_photo_002.jpg
```

The renderer:

1. Finds the first audio file in the project folder.
2. Finds the first `.yaml` timestamp file in the project folder.
3. Finds the first child folder containing image/video media.
4. Extracts frames from the media.
5. Matches frames to beat/timestamp clips.
6. Uses `ffmpeg` to render a beat-synced MP4.

Relevant files:

```txt
EasyBeatSync.py
main/Assets.py
main/Clip.py
main/Item.py
common/common.py
```

Important timestamp format:

```yaml
type1:
  - 46
  - 592
  - 1115
```

All timestamp values are milliseconds.

### Free To Use music, beat detection, and audio cuts

New tool:

```txt
tools/free_music_beats.py
```

It uses the Free To Use public API:

```txt
https://api.freetouse.com/v3
```

API endpoints currently used:

```txt
GET /music/tracks/all
GET /music/tracks/search
GET /music/tracks/{id}
```

Important track fields from the API:

```txt
id
title
duration
genre
artists
categories
tags
tags_categories
thumbnails
files.mp3
```

The tool can:

1. List free music tracks.
2. Search free music tracks.
3. Download a selected track MP3.
4. Save the full API metadata JSON locally.
5. Detect beat timestamps using `librosa`.
6. Write EasyBeatSync-compatible YAML timestamps.
7. Cut decoded audio into beat-aligned WAV segments using `soundfile`.

Commands:

```sh
python tools/free_music_beats.py list --limit 10
python tools/free_music_beats.py search cinematic --limit 10
python tools/free_music_beats.py download TRACK_ID --output-dir ./downloads
python tools/free_music_beats.py beats ./downloads/song.mp3 --output ./timestamps.yaml
python tools/free_music_beats.py cuts ./downloads/song.mp3 ./timestamps.yaml --output-dir ./beat_cuts
python tools/free_music_beats.py prepare TRACK_ID --output-dir ./free_music_project --cuts
```

The `prepare` command is the main end-to-end workflow for the webapp:

```sh
python tools/free_music_beats.py prepare TRACK_ID --output-dir ./free_music_project --cuts
```

It creates:

```txt
free_music_project/
  Artist - Title.mp3
  Artist - Title.json
  Artist - Title_beats.yaml
  Artist - Title_beat_cuts/
    beat_0001_000000000-000000046ms.wav
    beat_0002_000000046-000000592ms.wav
```

The WAV cuts are written from decoded audio sample indexes derived from the
detected millisecond timestamps. That means the cuts are exact to the detected
beat timestamps, but beat detection itself is algorithmic and may not match a
human-edited beat grid perfectly.

## Dependencies

Required Python packages are listed in `requirements.txt`:

```txt
natsort
pyyaml
librosa
soundfile
```

`ffmpeg` and `ffprobe` must be available on the system path for video rendering
and media probing.

The old GUI file picker dependencies are intentionally optional. Do not make the
webapp depend on `pywebview`. Always pass explicit paths from the app/backend.

## Target Webapp Workflow

The destination editing tool should expose Free To Use songs directly in its UI
so the user can choose music while editing a video.

Desired user flow:

1. User opens the editor.
2. User opens a Music or Free Music panel.
3. Webapp lists Free To Use tracks from the API.
4. User can search/filter tracks.
5. User can preview/play a track from the list.
6. User selects a preferred song.
7. User clicks Insert.
8. Backend downloads the MP3 locally.
9. Backend detects beat timestamps.
10. Backend cuts audio into beat-aligned WAV chunks if the editor needs cuts.
11. Backend saves all generated assets under the current video project.
12. Editor attaches the chosen song and beat timestamp data to the video render
    workflow.

This must feel like one seamless editor action, not a separate command-line step.

## Recommended Webapp UI

Build a compact music browser inside the editing UI.

Minimum UI controls:

```txt
Search input
Track list
Play/pause preview
Selected track state
Insert button
Progress state while downloading/analyzing
Error state for network/download/beat detection failures
Attribution/license notice near selected track or final export metadata
```

Each track row should show:

```txt
cover thumbnail
title
artist
duration
genre/tags
preview/play control
insert/select action
```

Use the API `files.mp3` URL for preview when allowed by the frontend runtime.
If browser CORS or app security blocks direct playback, proxy preview audio
through the app backend.

Do not force users to wait for beat detection before browsing. Only download and
analyze when the user clicks Insert, unless the app has a background cache.

## Recommended Backend API For The Editing Tool

Adapt names to the target framework, but preserve this shape.

```txt
GET /api/free-music/tracks?limit=20&offset=0&order=release_date&sort=desc
GET /api/free-music/tracks/search?query=cinematic&limit=20&offset=0
POST /api/projects/:projectId/music/insert
GET /api/jobs/:jobId
```

Suggested insert request:

```json
{
  "trackId": "87e28ee3-818a-4416-81be-70760bfacabe",
  "makeCuts": true,
  "includeTail": false
}
```

Suggested insert response:

```json
{
  "jobId": "job_123",
  "status": "queued"
}
```

Suggested completed job payload:

```json
{
  "status": "complete",
  "trackId": "87e28ee3-818a-4416-81be-70760bfacabe",
  "audioPath": "projects/demo/music/Nebulite - Eternal Rise.mp3",
  "metadataPath": "projects/demo/music/Nebulite - Eternal Rise.json",
  "timestampsPath": "projects/demo/music/Nebulite - Eternal Rise_beats.yaml",
  "cutsDir": "projects/demo/music/Nebulite - Eternal Rise_beat_cuts",
  "tempo": 112.35,
  "beatCount": 353
}
```

## Recommended Local Storage Layout

For the target project, prefer a stable track-id-based cache instead of only
artist-title filenames. The current CLI names files by artist/title; the webapp
can either preserve those outputs or wrap them in a stable directory.

Recommended per-project layout:

```txt
projects/
  PROJECT_ID/
    music/
      free-to-use/
        TRACK_ID/
          track.mp3
          metadata.json
          beats.yaml
          manifest.json
          cuts/
            beat_0001_000000000-000000046ms.wav
            beat_0002_000000046-000000592ms.wav
```

Recommended `manifest.json`:

```json
{
  "source": "free-to-use",
  "apiBase": "https://api.freetouse.com/v3",
  "trackId": "87e28ee3-818a-4416-81be-70760bfacabe",
  "title": "Eternal Rise",
  "artist": "Nebulite",
  "audioPath": "track.mp3",
  "metadataPath": "metadata.json",
  "timestampsPath": "beats.yaml",
  "cutsDir": "cuts",
  "timestampUnit": "ms",
  "timestampFormat": "yaml:type1",
  "cutFormat": "wav",
  "attribution": "Nebulite - Eternal Rise | Free To Use: freetouse.com/music"
}
```

## Integration Options

There are two acceptable integration styles.

### Option A: Call the CLI from the backend

This is fastest and safest for initial integration.

```sh
python tools/free_music_beats.py prepare TRACK_ID --output-dir PROJECT_MUSIC_DIR --cuts
```

Use a background job because download, beat detection, and cutting can take
several seconds or longer.

Pros:

```txt
least code movement
easy to test manually
keeps current repo behavior intact
```

Cons:

```txt
requires subprocess management
harder to stream granular progress
artist-title filenames are less stable than track-id filenames
```

### Option B: Import/refactor the Python functions

This is better for a polished app.

Current importable functions in `tools/free_music_beats.py`:

```python
from tools.free_music_beats import (
    DEFAULT_API_BASE,
    request_json,
    get_track,
    detect_beats,
    write_timestamps,
    cut_audio,
)
```

`download_track(args)` and `prepare_command(args)` currently expect
`argparse`-style objects. If embedding this in a backend service, refactor these
into pure functions:

```python
download_track_by_id(api_base, track_id, output_path_or_dir)
prepare_track(track_id, project_music_dir, make_cuts=True, include_tail=False)
```

Keep the CLI as a thin wrapper around those functions.

## Exact Insert Behavior For Agents

When the user clicks Insert in the webapp:

1. Read the selected `trackId`.
2. Create or reuse the project music directory.
3. Fetch full track details from:

```txt
GET https://api.freetouse.com/v3/music/tracks/{trackId}
```

4. Download `track.files.mp3`.
5. Save metadata JSON.
6. Run beat detection on the local MP3.
7. Save `beats.yaml` in EasyBeatSync format:

```yaml
type1:
  - 46
  - 592
```

8. If the editing UI needs individual audio chunks, run audio cutting into WAVs.
9. Save a manifest tying the selected track, local audio, timestamps, cuts, and
   attribution together.
10. Attach the manifest or file paths to the current video project.
11. Update the UI with completion and make the chosen song active.

Do not render the final video immediately unless the editor workflow already
does that after insert. Insert should prepare/select the song and beat data.

## Using The Prepared Music With EasyBeatSync

To render with EasyBeatSync, the app needs to create a folder like this:

```txt
render-job/
  selected-song.mp3
  selected-song-beats.yaml
  input-media/
    clip1.mp4
    image1.jpg
```

Then run:

```sh
python EasyBeatSync.py /absolute/path/to/render-job
```

The EasyBeatSync renderer will use the first audio and first YAML file it finds
in that folder.

## Agent Notes And Constraints

Use these rules when adapting this repo:

1. Do not copy `venv/` into the target project. Recreate the virtualenv and run
   `python -m pip install -r requirements.txt`.
2. Do not depend on the optional GUI picker in production.
3. Keep API/network work on the backend, not in a frontend-only environment, if
   the app needs local files for rendering.
4. Cache by `trackId` to avoid downloading and analyzing the same song again.
5. Show progress states because beat detection and cutting are not instant.
6. Treat `files.mp3` as the canonical source audio URL from the API response.
7. Preserve attribution/license metadata in the project manifest and export
   metadata.
8. Validate that `ffmpeg` and `ffprobe` are available before allowing render.
9. The generated YAML timestamps are in milliseconds and are compatible with
   the existing EasyBeatSync renderer.
10. The generated WAV cuts are for editing tools that need audio chunks; they
    are not required by `EasyBeatSync.py` itself.

## Manual Verification Commands

From this repo root:

```sh
source venv/bin/activate
python -m pip install -r requirements.txt
python tools/free_music_beats.py list --limit 5
python tools/free_music_beats.py search cinematic --limit 5
python tools/free_music_beats.py prepare TRACK_ID --output-dir ./free_music_project --cuts
python EasyBeatSync.py /path/to/render-job
```

Sample verification already performed in this repo:

```txt
Free To Use list command returned live tracks.
Beat detection on samples/example_song_lovefool.mp3 found 353 beats at 112.35 BPM.
Cut generation wrote 353 beat-aligned WAV files in /private/tmp.
```

## Future Improvements

Good next tasks for an integration agent:

1. Refactor `tools/free_music_beats.py` into a small library module plus CLI
   wrapper.
2. Add JSON output mode for `prepare` so backend jobs can parse results without
   scraping console output.
3. Add a stable `--track-id-dir` or `--filename-mode id` option for cache-safe
   webapp storage.
4. Add progress callbacks/events for download, beat detection, and cut writing.
5. Add tests for timestamp YAML writing, API payload normalization, and cut file
   naming.
6. Add optional beat-grid adjustment controls if users need manual correction.

