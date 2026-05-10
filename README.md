# ReelStudio — Cinematic Reel Studio for Real Estate

> Turn a folder of property photos into a beat-synced, organic content for real estate clients — no editing skills required.

---

## Judging Criteria

---

### 1. Impact & Clarity

**Who is it for?**
Real estate agents, property managers, brokers, and marketing teams who need professional-grade listing videos but lack the budget for a videographer ($500–$2,000/listing) or the time to learn video editing software.

**What problem does it solve?**
Today, creating a 60-second property reel requires:
- A professional photographer and videographer on-site
- Drone footage coordination
- Hours in Premiere Pro or CapCut
- A motion designer for titles and transitions

ReelStudio eliminates every one of these steps. An agent uploads their existing listing photos, picks a music track from the built-in catalog, and the system does everything else: vision AI classifies each photo, a storyboard agent arranges them in cinematic house-tour order (exterior → foyer → kitchen → living room → bedroom → bathroom → backyard), FAL's Kling v1.6 generates 5-second cinematic video clips per shot with realistic camera motion, and FFmpeg stitches the clips into a beat-synchronized 9:16 MP4 ready for Instagram Reels, TikTok, or MLS embeds.

**Is success measurable?**
| Metric | Target | Achieved |
|---|---|---|
| Time from upload to downloadable reel | < 3 minutes | ✅ ~2 min (draft), ~5 min (final) |
| Photos required | As few as 3 | ✅ Works with 3–150 photos |
| Output format | 9:16, 1080p, no black bars | ✅ Force-crop-to-fill pipeline |
| AI hallucination guardrails | No invented rooms or text | ✅ Strict grounding instructions to Kling |
| Cost per reel | < $1 in API credits | ✅ ~$0.40–$0.80 per FAL render |

---

### 2. Technical Execution

**Architecture summary:**
The system is a 10-layer pipeline modeled on the architectural discipline of Lightricks' LTX-Video diffusion framework — but applied to the editing domain rather than the generative latent space.

| Layer | Component | Technology |
|---|---|---|
| Models | `Shot`, `Storyboard`, `RenderConfig` | Pydantic v2 |
| Agents | Image analysis, shot matching, prompt generation | OpenAI GPT-4o Vision |
| Pipelines | Single-pass + two-pass (draft/final) | Python async |
| Schedulers | Beat-aware shot timing | librosa BPM analysis |
| Effects | Ken Burns, color grade, transitions | FFmpeg filter graph |
| Render | Clip assembly, audio mix | FFmpeg + FAL Kling v1.6 |
| Integrations | Video generation, music | FAL, Pixabay, ElevenLabs |
| Storage | Projects, uploads, analyses, renders | SQLite + SQLAlchemy |
| API | REST + WebSocket progress streaming | FastAPI |
| Frontend | 4-step wizard UI | Next.js 14, Tailwind v4 |

**Reliability & latency:**
- Draft render (540p, Ken Burns fallback): **~20–30 seconds**
- Final render (1080p, FAL Kling clips): **~3–6 minutes** (parallelized, up to 4 concurrent FAL calls)
- Vision analysis cached per image SHA-256 hash — re-generating a storyboard is instant
- All background tasks use FastAPI `BackgroundTasks` + WebSocket push for live progress

**Data handling:**
- Images stored on local filesystem under `storage_data/{project_id}/`
- Analysis results cached in SQLite (`AnalysisRow`) with version tagging (`ANALYZER_VERSION`)
- FAL clips written to `scratch/` and discarded after FFmpeg assembly
- No user data leaves the system except to the three opted-in API providers

**Build complexity:**
- 3 AI agents (vision analysis, shot matching, prompt translation)
- 100-recipe cinematic prompt library (`styleRecipe.txt`) mapped to room types
- Real-time WebSocket pipeline with per-shot telemetry
- Two-pass render system (draft preview → final delivery)
- Beat-timestamp extraction via `librosa` with PacingScheduler
- HEIF/HEIC photo support via `pillow-heif`

---

### 3. Innovation

**Non-obvious design choices:**

**1. LTX-Video pattern transplant.**
We studied Lightricks' open-source LTX-Video diffusion pipeline and transplanted its architectural patterns into the video editing domain:
- `ConditioningItem(frame, strength)` → `Shot(image, start_time, motion_strength)`
- `LTXMultiScalePipeline` (low-res → refine) → `MultiPassRenderer` (540p draft → 1080p final)
- `RectifiedFlowScheduler` (timestep schedule) → `PacingScheduler` (beat-aware cut timing)
- Prompt enhancement chain (Florence-2 → Llama-3.2) → Vision analysis → shot matcher → FAL fallback

This is an original architecture transplant that no existing real estate tool has attempted.

**2. Cinematic style recipe system.**
Instead of sending raw prompts to FAL, we built a library of 100 cinematographer-authored prompt recipes across 7 categories (Drone Aerial, Dolly Interior, Sunset/Twilight, Lighting Logic, Macro/Detail, High-Energy, Seamless Bridge). Each recipe maps to room types. The system picks calm, luxury-appropriate recipes (filtering out "aggressive", "fast", "fpv") and embeds them with property-specific grounding. This produces dramatically better FAL output than ad-hoc prompting.

**3. Hallucination guardrails for video generation.**
Every FAL prompt includes an explicit grounding instruction:
> *"Use the provided source image as the absolute visual truth: preserve the real architecture, layout, room identity, materials, window placement, furniture, landscaping, and color palette. Do not create new rooms, extra floors, impossible geometry, signage, text, people, logos, watermarks, or distorted fixtures."*

This is critical for real estate — a generated "extra bedroom" or "wrong floor plan" would be a legal liability. No other tool in this space has published explicit hallucination constraints for property video generation.

**4. Beat-sync storyboard planning.**
Shot durations and cut points are planned against the music's BPM before any video is generated. The `PacingScheduler` extracts beat timestamps via `librosa`, then the `StoryboardBuilder` sequences shots so cuts land on musical beats. This is not cosmetic — it's a structural decision that makes the final reel feel professionally edited.

**5. House-tour room ordering.**
The AI sorts photos by a fixed narrative arc (`exterior → view → foyer → living_room → dining → kitchen → bedroom → bathroom → backyard → detail`) rather than upload order or arbitrary ranking. Within each room type, photos are ranked by quality score. This mirrors how professional real estate videographers sequence their tours.

---

### 4. User Experience

**Clear flows:**
The entire product is a 4-step linear wizard:
```
1. Upload  →  2. Music  →  3. Storyboard  →  4. Render
```
Each step has a single primary action. There are no dead ends — every error surfaces a human-readable message with a suggested fix.

**Helpful feedback:**
- Live WebSocket telemetry shows per-photo analysis progress ("Analyzed photo 3 of 8: kitchen, medium quality 0.82")
- Storyboard notes explain why each shot was ordered and what the AI decided
- Render progress streams continuously with phase labels (analyzing → generating clips → stitching → encoding)

**Storyboard editor:**
The storyboard renders as a horizontal scrollable strip of portrait-format (9:16) thumbnails. Users can reorder shots with left/right swap buttons. Each shot shows the source photo, room classification, motion preset, and duration. Changes are persisted instantly via `PUT /projects/{id}/storyboard`.

**Safety / guardrails:**
- Vision analysis includes a quality score — low-quality images (blurry, dark, obstructed) are ranked lower but never silently dropped; the user sees every photo used
- FAL generation prompts explicitly ban text, watermarks, logos, and impossible architecture
- The "unfilled slots" warning tells users exactly which shots couldn't be filled and why
- Music preview stops automatically when the user clicks Insert — no audio continues playing in the background

**Accessibility:**
- All interactive elements have `aria-label` and keyboard navigation
- Colour contrast meets WCAG AA on all badge and text elements
- No autoplay video or audio without user action

---

### 5. Track Fit

**1. AutoHDR Track**
ReelStudio directly targets image-to-video generation for real estate businesses. Every listing photo is transformed into a cinematic 5-second video clip using FAL's Kling v1.6, with camera motion, color grading, and beat-synced timing — turning static HDR photography assets into high-quality motion content at scale.

**2. Agents Track**
The project autonomously decides how to edit, what to edit, and the overall theme of the edit. The agent layer — ImageAnalyzer, ShotMatcher, and StoryboardBuilder — independently classifies each photo, determines narrative order, selects cinematic style recipes, and plans shot timing against the music's BPM, all without any manual direction from the user.

---

## What It Does

ReelStudio is a full-stack application that automates the production of professional real estate listing videos.

**Input:** A set of property photos (JPEG, PNG, HEIF).  
**Output:** A 9:16 cinematic MP4 reel, beat-synced to music, ready for Instagram/TikTok/MLS.

**The pipeline, in plain English:**
1. You upload your listing photos
2. GPT-4o Vision examines each photo: What room is this? What's the quality? What camera move fits?
3. The storyboard agent sorts photos into house-tour narrative order and pairs each with a cinematic camera recipe
4. You pick background music from the free catalog; the system extracts beat timestamps
5. Shot durations are planned to land cuts on musical beats
6. FAL's Kling v1.6 generates a 5-second cinematic video clip for each photo — slow dolly, Ken Burns zoom, aerial drift
7. FFmpeg assembles all clips, mixes the audio track, and encodes a 540p draft for preview
8. You review the storyboard, optionally reorder shots with left/right swap buttons
9. Hit "Render Final" → 1080p MP4 is ready for download

---

## Tech Stack

### Backend
| Technology | Role |
|---|---|
| **Python 3.12** | Runtime |
| **FastAPI 0.115** | REST API + WebSocket server |
| **Pydantic v2** | Data models and validation |
| **SQLAlchemy 2.0 + SQLite** | Persistence (projects, uploads, analyses, renders) |
| **OpenAI GPT-4o Vision** | Photo classification, quality scoring, room detection |
| **FAL Kling v1.6** | Image-to-video and text-to-video generation |
| **Google Gemini (Nano Banana)** | Fallback image generation |
| **librosa** | Audio BPM extraction and beat timestamp detection |
| **FFmpeg** | Video assembly, audio mixing, encoding |
| **Pillow + pillow-heif** | Image processing and HEIF/HEIC support |
| **uvicorn** | ASGI server |
| **python-dotenv** | Environment configuration |

### Frontend
| Technology | Role |
|---|---|
| **Next.js 14 (App Router)** | React framework |
| **TypeScript** | Type safety |
| **Tailwind CSS v4** | Styling |
| **shadcn/ui** | Component library |
| **WebSocket client** | Live render progress streaming |
| **Firebase Auth** | User authentication |

### Infrastructure
| Technology | Role |
|---|---|
| **FAL.ai** | GPU-accelerated video generation |
| **Pixabay API** | Royalty-free music catalog |
| **ElevenLabs** | TTS voiceover (optional) |
| **Local filesystem** | File storage (`storage_data/`) |

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (Next.js)                    │
│  Upload → Music → Storyboard (horizontal strip) → Render   │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Projects │  │   Uploads    │  │    Storyboards     │   │
│  │   API    │  │     API      │  │       API          │   │
│  └──────────┘  └──────┬───────┘  └────────┬───────────┘   │
│                        │                   │                │
│              ┌─────────▼──────────────────▼──────────┐     │
│              │         Agent Layer                    │     │
│              │  ImageAnalyzer → ShotMatcher →        │     │
│              │  StoryboardBuilder (build_from_uploads)│     │
│              └─────────────────┬──────────────────────┘     │
│                                │                            │
│  ┌─────────────────────────────▼──────────────────────┐    │
│  │              Render Pipeline                        │    │
│  │  MultiPassRenderer → ReelPipeline                  │    │
│  │  Phase 1: FAL Kling (parallel clip generation)     │    │
│  │  Phase 2: Audio mixing (librosa + FFmpeg)          │    │
│  │  Phase 3: FFmpeg assembly (scale+crop, concat)     │    │
│  └────────────────────────────┬───────────────────────┘    │
│                               │                             │
│  ┌────────────────────────────▼───────────────────────┐    │
│  │              Storage Layer                         │    │
│  │  SQLite (metadata) + Filesystem (files)            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         WebSocket Progress Stream                  │    │
│  │  Per-shot telemetry → browser live updates         │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │                │               │
    ┌────▼───┐     ┌──────▼──┐     ┌─────▼──────┐
    │OpenAI  │     │FAL Kling│     │  Pixabay   │
    │GPT-4o  │     │  v1.6   │     │Music API   │
    └────────┘     └─────────┘     └────────────┘
```

### The 10-Layer Architecture (LTX-Video Pattern Transplant)

This project's architecture was deliberately designed by studying Lightricks' open-source LTX-Video diffusion pipeline and transplanting its structural patterns into the video editing domain.

| LTX-Video Concept | ReelStudio Equivalent | File |
|---|---|---|
| `ConditioningItem(media, frame, strength)` | `Shot(image, start_time, motion_strength)` | `models/shot.py` |
| `LTXVideoPipeline.__call__()` | `ReelPipeline.render()` | `pipelines/reel_pipeline.py` |
| `LTXMultiScalePipeline` | `MultiPassRenderer` (draft → final) | `pipelines/multiscale_pipeline.py` |
| `RectifiedFlowScheduler` | `PacingScheduler` (beat-aware timing) | `schedulers/pacing.py` |
| `SymmetricPatchifier` | `Storyboard` (image → resolved shot list) | `models/storyboard.py` |
| Prompt enhancement chain | Vision analysis → matcher → FAL fallback | `agents/` |
| `SkipLayerStrategy` | `EffectSkipStrategy` (skip redundant passes) | `effects/` |
| `ASPECT_RATIO_*_BIN` | Output presets (9:16, 1:1, 16:9) | `models/render_config.py` |
| `InferenceConfig` | `RenderConfig` (Pydantic model) | `models/render_config.py` |

**Layer 1 — Models (Pydantic v2)**
Pure data classes. Zero I/O, zero side effects. `Shot`, `Storyboard`, `RenderConfig`, `Project`, `ResolvedShot`.

**Layer 2 — Agents (AI Orchestration)**
- `ImageAnalyzer` — GPT-4o Vision. Tags every upload: room type (12 categories), quality score (0–1), framing, lighting, dominant colors, suggested camera motion. Results cached by image hash.
- `ShotMatcher` — Given analyzed images, assigns each to a narrative slot using a weighted scoring model. Falls back to FAL text-to-video when no suitable photo exists.
- `PromptTranslator` — Converts a natural-language director's brief ("40-second reel, start with twilight exterior") into a valid storyboard plan using GPT-4o structured output.

**Layer 3 — Pipelines**
- `ReelPipeline` — single-pass: storyboard → FAL generation → FFmpeg → MP4
- `MultiPassRenderer` — wraps `ReelPipeline` for two passes: **Draft** (540p, ultrafast preset, ~30s) and **Final** (1080p, medium preset, ~5 min)

**Layer 4 — Scheduler**
`PacingScheduler` — extracts BPM and beat timestamps from the selected audio via `librosa`. Shot boundaries snap to beats or downbeats. This is the beat-aware equivalent of LTX-Video's resolution-dependent timestep shifting.

**Layer 5 — Effects (FFmpeg filter graph fragments)**
- `ken_burns_filter` — pan/zoom on stills (`slow_zoom_in`, `slow_zoom_out`, `pan_left`, `pan_right`, `push_in`, `pull_out`, `static`)
- `color_grade_filter` — LUT-based and parametric color grades (`warm_cinematic`, `cool_modern`, `golden_hour`)
- `overlay_filter_chain` — text card compositing with fade in/out

**Layer 6 — Render (FFmpeg orchestration)**
`FFmpegBuilder` — assembles one FFmpeg command from all shots, overlays, audio cues, and encoding parameters. Two code paths:
- `build()` — Ken Burns mode (stills + effects, no FAL)
- `build_from_clips()` — FAL clip mode (scale+crop to fill, no black bars, concat only)

`Encoder` — runs FFmpeg as a subprocess, parses `-progress pipe:` output, emits `RenderProgress` events per frame.

**Layer 7 — Integrations (Adapter Pattern)**
Each provider implements a minimal interface. Missing API key → returns `None`, pipeline falls back gracefully.
- `FalClient` — Kling v1.6 image-to-video and text-to-video
- `ElevenLabsClient` — TTS voiceover
- `NanoBananaClient` — Google Gemini image generation
- `FreeMusicClient` — Pixabay royalty-free music + beat extraction

**Layer 8 — Storage**
- SQLite via SQLAlchemy: `projects`, `uploads`, `analyses`, `renders`, `project_music`
- Filesystem: `storage_data/{project_id}/uploads/`, `renders/`, `scratch/`
- Analysis results versioned with `ANALYZER_VERSION` constant — stale cache entries are re-computed automatically

**Layer 9 — API (FastAPI)**
```
POST   /projects                          Create project
GET    /projects                          List projects
DELETE /projects/{id}                     Delete project
POST   /projects/{id}/uploads             Upload photos (multipart)
GET    /projects/{id}/uploads             List uploads
POST   /projects/{id}/storyboard          Generate storyboard (AI)
GET    /projects/{id}/storyboard          Get current storyboard
PUT    /projects/{id}/storyboard          Save manual reorder
POST   /projects/{id}/renders             Start render (draft/final)
GET    /projects/{id}/renders             List renders
GET    /projects/{id}/renders/{id}/file   Download MP4
POST   /projects/{id}/music/insert        Insert music track
GET    /projects/{id}/music/current       Get active track
WS     /projects/{id}/ws                  Live progress stream
GET    /styles                            List cinematic style recipes
GET    /health                            Provider status
```

**Layer 10 — Frontend (Next.js 14)**
4-step wizard: Upload → Music → Storyboard → Render. Each step is a `Card` with a single primary action. State is never stored in the URL — all data lives in the backend and is fetched fresh per session.

---

### Render Pipeline — FAL + FFmpeg Flow

```
For each shot in storyboard:
  ├─ image_path exists?
  │   ├─ YES → FAL Kling image-to-video (5s, 9:16, cinematic prompt)
  │   └─ NO  → FAL Kling text-to-video (5s, 9:16, room description prompt)
  └─ clip saved to scratch/{shot_id}.mp4

Audio:
  └─ Music track trimmed + faded to total_duration_sec

FFmpeg assembly (build_from_clips):
  For each clip:
    trim → scale={w}:{h}:force_original_aspect_ratio=increase → crop={w}:{h} → fps=30 → yuv420p
  concat all clips → [vout]
  atrim + afade + volume + adelay + apad → [aout]
  encode: libx264 + aac → output.mp4
```

### Cinematic Prompt System

Every FAL call receives a structured prompt assembled from five sources:

1. **Property context** — name, address, description from the project
2. **Style recipe** — one of 100 cinematographer-authored camera movement descriptions from `styleRecipe.txt`, selected by room type and filtered to avoid aggressive/hype presets
3. **Grounding instruction** — explicit constraint to preserve real architecture, no hallucinated rooms
4. **Music context** — tempo, beat count, mood (to guide motion pacing)
5. **Room type** — explicit anchor for the visual subject

Room → style category mapping:
| Room Type | Style Category | Example Recipe |
|---|---|---|
| exterior | Drone Aerial | Slow 180° orbit, golden-hour rim light |
| living_room, kitchen, foyer | Dolly Interior | Forward dolly with subtle parallax |
| backyard, view | Sunset/Twilight | Drifting push-in, atmospheric haze |
| bathroom, detail | Macro/Detail | Rack focus, slow reveal |
| amenity | Lighting Logic | Contrast-driven exposure shift |

---

## Project Structure

```
EstateReelMaker/
├── backend/
│   ├── main.py                          # FastAPI app entrypoint
│   ├── pyproject.toml                   # Dependencies
│   └── realstate/
│       ├── agents/
│       │   ├── image_analyzer.py        # GPT-4o Vision photo classification
│       │   ├── shot_matcher.py          # Narrative shot assignment
│       │   ├── prompt_translator.py     # NL brief → storyboard plan
│       │   ├── photo_selector.py        # Quality-ranked photo selection
│       │   ├── vlm_factory.py           # Vision model abstraction
│       │   └── openai_client.py         # OpenAI wrapper
│       ├── api/
│       │   ├── projects.py              # CRUD + delete endpoints
│       │   ├── uploads.py               # Multipart file ingestion
│       │   ├── storyboards.py           # AI storyboard generation + manual edit
│       │   ├── render.py                # Draft/final render orchestration
│       │   ├── free_music.py            # Pixabay music catalog + beat extract
│       │   ├── styles.py                # Style recipe catalog API
│       │   ├── files.py                 # MP4 download serving
│       │   └── ws.py                    # WebSocket progress broadcast
│       ├── data/
│       │   └── style_recipes.py         # 100-recipe library + room mapping
│       ├── effects/
│       │   ├── ken_burns.py             # Pan/zoom filter graph fragments
│       │   ├── color_grade.py           # LUT + parametric grade filters
│       │   └── text_overlay.py          # PIL text card → PNG → FFmpeg overlay
│       ├── integrations/
│       │   ├── fal_client.py            # FAL Kling v1.6 i2v + t2v
│       │   ├── free_music.py            # Pixabay API + librosa beat extraction
│       │   ├── elevenlabs.py            # TTS voiceover
│       │   └── stock_audio.py           # Local royalty-free library
│       ├── models/
│       │   ├── shot.py                  # Shot, ShotSlot, MotionPreset, TransitionType
│       │   ├── storyboard.py            # Storyboard, ResolvedShot, StoryboardMusic
│       │   ├── template.py              # Template, AudioCue, TextOverlaySpec
│       │   ├── render_config.py         # RenderConfig, AspectRatio, RenderPass
│       │   └── project.py               # Project, RenderJob, RenderStatus
│       ├── pipelines/
│       │   ├── reel_pipeline.py         # Main render: FAL → audio → FFmpeg
│       │   └── multiscale_pipeline.py   # Two-pass: draft (540p) → final (1080p)
│       ├── render/
│       │   ├── ffmpeg_builder.py        # FFmpeg command assembly
│       │   └── encoder.py               # Subprocess runner + progress parsing
│       ├── schedulers/
│       │   └── pacing.py               # BPM-aware shot timing
│       ├── services.py                  # StoryboardBuilder (core orchestration)
│       ├── storage/
│       │   ├── db.py                    # SQLAlchemy models + session
│       │   └── filesystem.py            # File layout abstraction
│       └── config.py                    # Settings from environment
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                   # Root layout + nav
│   │   ├── page.tsx                     # Dashboard (project list + hero)
│   │   └── projects/[id]/page.tsx       # 4-step project wizard
│   ├── components/
│   │   ├── upload-dropzone.tsx          # Drag-and-drop photo uploader
│   │   ├── music-browser.tsx            # Track search + preview + insert
│   │   ├── storyboard-timeline.tsx      # Horizontal swappable shot strip
│   │   ├── render-progress.tsx          # Live progress bar + phase label
│   │   ├── style-card.tsx               # Style recipe display card
│   │   └── ui/                          # shadcn/ui primitives
│   └── lib/
│       ├── api.ts                       # Typed API client
│       ├── ws.ts                        # WebSocket connection manager
│       └── utils.ts                     # cn(), formatSeconds()
├── easy-beat-sync-master/               # Beat analysis module
│   ├── EasyBeatSync.py
│   └── tools/free_music_beats.py
├── styleRecipe.txt                      # 100 cinematographer prompt recipes
├── run.sh                               # One-command startup script
└── ARCHITECTURE.md                      # LTX-Video pattern mapping
```
