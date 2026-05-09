# Realstate — AI Reel Generator for Real Estate

An AI-powered platform that takes 50–150 property photos and produces a ~1-minute cinematic reel for Instagram. Built for AutoHDR's video team to replace manual editing with reproducible, template-driven generation.

## What it does

1. **Upload** 50–150 photos of a property.
2. **Choose a template** authored by a pro video editor (e.g. *Luxury Listing*, *Quick Flip*, *Cinematic Walkthrough*).
3. **AI agents** analyze each image (room type, quality, framing, lighting), match them to storyboard slots, and fill missing shots via Nano Banana Pro.
4. **Render** a beat-aware reel with Ken Burns motion, transitions, color grading, text overlays, and music.
5. **Download** the final 1080p MP4.

## Architecture in one diagram

```
   User photos          Template YAML          Pro editor's
   (50-150)             (storyboard +          natural-language
        │                pacing + audio        prompt
        │                 timing)              (optional)
        │                  │                    │
        ▼                  ▼                    ▼
  ┌──────────────────────────────────────────────────┐
  │        AI AGENT LAYER (OpenAI + fal/Gemini)      │
  │  ┌─────────────┐  ┌──────────────┐  ┌────────┐   │
  │  │ Image       │→ │ Shot Matcher │→ │ Prompt │   │
  │  │ Analyzer    │  │ (assign      │  │ Trans- │   │
  │  │ (vision)    │  │  imgs to     │  │ lator  │   │
  │  │             │  │  slots)      │  │ NL→YAML│   │
  │  └─────────────┘  └──────────────┘  └────────┘   │
  │                          │                       │
  │                          ▼                       │
  │                   Missing shots? ──→ Nano Banana │
  └──────────────────────────────────────────────────┘
                             │
                             ▼
                       ┌──────────┐
                       │Storyboard│  (resolved shot list +
                       │  (json)  │   timing + effects)
                       └──────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────┐
  │         REEL PIPELINE (lifted from LTX-Video)    │
  │                                                   │
  │   Pacing Scheduler  ──┐                           │
  │   (beat-aware)        │                           │
  │                       ▼                           │
  │   Effects ──→ Ken Burns / transitions / LUTs /   │
  │               text overlays / generative motion  │
  │                       │                           │
  │                       ▼                           │
  │   FFmpeg Builder ──→ Two-pass render:            │
  │                      draft (preview) → final     │
  └──────────────────────────────────────────────────┘
                             │
                             ▼
                        Final MP4
```

The architecture borrows directly from the LTX-Video repo (see `docs/architecture.md` for the mapping).

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp ../.env.example .env   # add API keys (optional for local dev)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Required system dependencies

- **FFmpeg** (`brew install ffmpeg`) — for video assembly
- **Python 3.10+**
- **Node 20+**

### Optional API keys (in `.env`)

- `OPENAI_API_KEY` — OpenAI for agent reasoning + image analysis (`gpt-4o` / `gpt-4o-mini`)
- `FAL_KEY` — fal.ai for image gen (FLUX Kontext) + image-to-video (Kling/Luma)
- `GEMINI_API_KEY` — Nano Banana Pro (`gemini-3-pro-image-preview`) for image gen; `GOOGLE_API_KEY` is also accepted
- `RUNWAY_API_KEY` — direct Runway access (covered by fal too)
- `ELEVENLABS_API_KEY` — TTS voiceover + music generation

Without keys, the system runs in **offline mode**: deterministic rule-based shot matching, Ken Burns only, audio from the local library.

## Templates

Templates live in `backend/realstate/templates/*.yaml` — see `docs/template-authoring.md`. Bundled templates:

- `luxury-listing.yaml` — slow, cinematic, 60s, classical/ambient
- `quick-flip.yaml` — fast cuts, 30s, upbeat
- `cinematic-walkthrough.yaml` — 75s, narrative arc with text overlays
- `airbnb-spotlight.yaml` — lifestyle-focused, 45s, vibey

A pro editor can write a template either by hand or by giving OpenAI a natural-language brief like:

> "Open with a 4-second slow zoom on the exterior. Cut to the foyer at 4s with a push-in. Music starts at 4s. Show kitchen highlights between 8–16s. End on a sunset shot of the backyard."

The **prompt translator agent** converts that into a valid YAML template.

## Project layout

```
realstate/
├── backend/                  # FastAPI + AI agents + render pipeline
│   ├── main.py
│   ├── realstate/
│   │   ├── api/              # REST + WebSocket routes
│   │   ├── models/           # Pydantic models (Shot, Storyboard, Template)
│   │   ├── pipelines/        # ReelPipeline, MultiScalePipeline (draft+final)
│   │   ├── agents/           # OpenAI/fal/Gemini-powered agents
│   │   ├── effects/          # Ken Burns, transitions, color grade, overlays
│   │   ├── schedulers/       # Beat-aware shot pacing
│   │   ├── integrations/     # Nano Banana, Runway, ElevenLabs adapters
│   │   ├── render/           # FFmpeg orchestration
│   │   ├── storage/          # SQLite + filesystem
│   │   └── templates/        # Bundled YAML templates
│   ├── audio_library/        # Drop royalty-free MP3s here
│   └── storage_data/         # Project files (gitignored)
├── frontend/                 # Next.js 15 + Tailwind + shadcn (pink/purple/white)
└── docs/
```

See `ARCHITECTURE.md` for the full design and how it maps to LTX-Video.
