# Architecture

This document explains how the platform is built and how its components map to patterns lifted from [LTX-Video](https://github.com/Lightricks/LTX-Video).

## Mental model

A reel is a **storyboard**: an ordered list of **shots**, each anchored to a time range, with a still image (or generated frame), motion parameters, optional text overlay, and a transition into the next shot. A **template** is a parameterized storyboard that the AI agent fills in using the user's uploaded images.

## Pattern mapping (LTX-Video → Realstate)

| LTX-Video concept | Realstate equivalent | File |
|---|---|---|
| `ConditioningItem(media, frame_number, strength)` | `Shot(image, start_time, duration, motion_strength)` | [`backend/realstate/models/shot.py`](backend/realstate/models/shot.py) |
| YAML configs (`configs/ltxv-*.yaml`) | Template YAMLs (`backend/realstate/templates/*.yaml`) | [`backend/realstate/templates/`](backend/realstate/templates/) |
| `LTXVideoPipeline.__call__()` | `ReelPipeline.render()` | [`backend/realstate/pipelines/reel_pipeline.py`](backend/realstate/pipelines/reel_pipeline.py) |
| `LTXMultiScalePipeline` (low-res preview → high-res refine) | `MultiPassRenderer` (draft preview → final 1080p/4K) | [`backend/realstate/pipelines/multiscale_pipeline.py`](backend/realstate/pipelines/multiscale_pipeline.py) |
| `RectifiedFlowScheduler` (timestep schedule) | `PacingScheduler` (beat-aware shot timing) | [`backend/realstate/schedulers/pacing.py`](backend/realstate/schedulers/pacing.py) |
| `SymmetricPatchifier` (latents → patches + coords) | `Storyboard` (template + images → resolved shot list with timing coords) | [`backend/realstate/models/storyboard.py`](backend/realstate/models/storyboard.py) |
| Prompt enhancement chain (Florence-2 caption → Llama-3.2 refine) | Image analysis (OpenAI vision) → shot matcher → fallback to Nano Banana / fal | [`backend/realstate/agents/`](backend/realstate/agents/) |
| `SkipLayerStrategy` (skip transformer blocks per timestep) | `EffectSkipStrategy` (skip color-grade on already-graded shots, skip Ken Burns on gen-motion shots) | [`backend/realstate/effects/`](backend/realstate/effects/) |
| `ASPECT_RATIO_*_BIN` resolution snapping | Output aspect-ratio presets (9:16 reel, 1:1 grid, 16:9 web) | [`backend/realstate/render/encoder.py`](backend/realstate/render/encoder.py) |
| `InferenceConfig` dataclass | `RenderConfig` Pydantic model | [`backend/realstate/models/render_config.py`](backend/realstate/models/render_config.py) |

## Layered architecture

### Layer 1 — Models (Pydantic)
Pure data classes. No I/O, no logic. `Shot`, `Storyboard`, `Template`, `RenderConfig`, `Project`. Mirrors the dataclass discipline of LTX-Video's `InferenceConfig` and `ConditioningItem`.

### Layer 2 — Agents (AI orchestration)
- **`ImageAnalyzer`** — OpenAI vision call (`gpt-4o-mini` by default). Tags each upload with: room type, quality score (0-1), framing notes, lighting, dominant colors, suggested camera move. Cached per image hash.
- **`ShotMatcher`** — Given a template's shot slots and analyzed images, assigns each slot the best image. Falls back to Nano Banana / fal when no upload satisfies a slot's requirements (e.g. "sunset exterior" but only daytime photos uploaded).
- **`PromptTranslator`** — Converts a pro editor's natural-language brief ("4-second zoom on exterior, cut to foyer at 4s, music starts then…") into a valid template YAML. Uses OpenAI (`gpt-4o` by default) with structured output validated against the `Template` schema.

### Layer 3 — Pipelines
- **`ReelPipeline`** — single-pass render: storyboard → effects → FFmpeg → MP4.
- **`MultiPassRenderer`** — wraps `ReelPipeline` for two passes:
  1. **Draft pass** — 540p, low CRF, watermark, fast → preview in <30s
  2. **Final pass** — 1080p (or 4K), high quality → user downloads

This is the same pattern as `LTXMultiScalePipeline`'s low-res-then-refine.

### Layer 4 — Schedulers
- **`PacingScheduler`** — analyzes the chosen audio track (BPM via `librosa`) and snaps shot boundaries to beats or downbeats based on the template's `pacing_mode` (`beat`, `downbeat`, `bar`, `free`). Mirrors LTX's resolution-aware timestep shifting: instead of shifting timesteps based on resolution, we shift cut points based on tempo.

### Layer 5 — Effects
Pure functions that take a still image + parameters and produce an FFmpeg filtergraph fragment.

- **`ken_burns`** — pan/zoom on stills (5 presets: `slow_zoom_in`, `slow_zoom_out`, `pan_left`, `pan_right`, `static`)
- **`transitions`** — `cut`, `dissolve`, `slide`, `whip_pan`, `morph` (between shots)
- **`color_grade`** — apply LUT, exposure, saturation tweaks (per-shot or global)
- **`text_overlay`** — property info cards (price, beds/baths, sqft, address)

### Layer 6 — Render
- **`FFmpegBuilder`** — turns a resolved storyboard into one big FFmpeg command. Handles input loop flags, filter graph, audio mixing, encoding params.
- **`Encoder`** — runs FFmpeg, parses progress (via `-progress pipe:`), pushes percent updates to the WebSocket.

### Layer 7 — Integrations (external APIs)
Adapter pattern. Each integration implements a small interface so the pipeline doesn't care which provider is wired up.

- `nano_banana.py` — Google Gemini 2.5 Flash Image (text-to-image, image edit, smart crop, virtual staging)
- `runway.py` — Runway Gen-3 / Gen-4 for hero-shot generative motion
- `elevenlabs.py` — TTS voiceover + music
- `stock_audio.py` — local royalty-free library scanner

All integrations degrade gracefully: missing API key → adapter returns `None` and the pipeline falls back to deterministic defaults.

### Layer 8 — Storage
- **`db.py`** — SQLite via SQLAlchemy. Tables: `projects`, `uploads`, `analyses` (cached image analyses), `renders`, `audio_tracks`.
- **`filesystem.py`** — file layout under `storage_data/`. One folder per project: `uploads/`, `generated/`, `renders/draft.mp4`, `renders/final.mp4`, `storyboard.json`.

### Layer 9 — API (FastAPI)
- `POST /projects` — create
- `POST /projects/{id}/uploads` — multipart image upload
- `GET  /templates` — list bundled templates
- `POST /templates/from-prompt` — invoke `PromptTranslator`
- `POST /projects/{id}/storyboard` — run agents, produce a draft storyboard
- `PATCH /projects/{id}/storyboard` — manual edits (drag/drop, reassign shots)
- `POST /projects/{id}/render?pass=draft|final` — start render
- `GET  /projects/{id}/renders/{name}` — download MP4
- `WS   /projects/{id}/progress` — live render percentage

### Layer 10 — Frontend (Next.js)
- Dashboard → list projects
- New Project wizard → upload → template → storyboard editor → render
- Pink/purple/white theme via Tailwind v4 + shadcn/ui

## Data flow for a single render

```
1. User creates Project via POST /projects
2. User uploads photos via POST /projects/{id}/uploads
   └─ Files written to storage_data/{id}/uploads/, rows inserted
3. User selects template (or uploads NL brief → PromptTranslator → template)
4. User clicks "Generate Storyboard"
   └─ ImageAnalyzer runs on each upload (cached)
   └─ ShotMatcher assigns images to template slots
   └─ Missing slots → NanoBanana generates (or pipeline marks them and shows the editor)
   └─ Returns a Storyboard JSON
5. User reviews storyboard, optionally drags shots around
6. User clicks "Render Draft"
   └─ MultiPassRenderer.draft() → 540p preview in ~30s
7. User watches preview in browser
8. User clicks "Render Final"
   └─ MultiPassRenderer.final() → 1080p MP4
9. WebSocket pushes %progress throughout
10. User downloads final MP4
```

## Design decisions (and their LTX-Video parallels)

**Two-pass rendering.** LTX-Video does it for compute efficiency (low-res first pass costs much less GPU time, then upsample). We do it for *user feedback* — a watchable preview in seconds is more valuable than a 1080p result in two minutes.

**Template = parameterized config.** LTX-Video's configs encode `guidance_scale`, `stg_scale`, `skip_block_list` per timestep. Our templates encode `motion`, `transition`, `text_overlay`, `audio_window` per shot. Both let an expert tune behavior without code changes.

**Pacing as a scheduler.** LTX-Video shifts denoising timesteps based on resolution; we shift shot boundaries based on tempo. The pattern — "let a domain-specific scheduler decide *when* things happen" — is the same.

**Agent fallback chain.** Mirrors LTX-Video's prompt enhancement (Florence-2 captions images → Llama-3.2 refines into a cinematic prompt). Ours is: OpenAI vision analyzes images → matcher selects → Nano Banana / fal fills gaps. The chain is decoupled so each agent is swappable.

**Skip strategies.** LTX-Video skips transformer layers per timestep for speed. We skip effect passes per shot when redundant — e.g. if a shot is generative-motion (already moving), skip Ken Burns; if a shot's source is already color-graded, skip the LUT pass.

## What's *not* lifted from LTX-Video

- We don't use a diffusion transformer. Real estate reels are about *editing* still photos with motion, not synthesizing video from noise. Generative video (Runway/Nano Banana) is used surgically for hero shots only.
- No causal VAE, no latent space — we operate in pixel space via FFmpeg.
- No rectified flow, no patchifier — irrelevant outside of generative latent models.

## Extensibility

To add a new template: drop a YAML file into `backend/realstate/templates/`.
To add a new effect: implement a function in `backend/realstate/effects/` that returns an FFmpeg filter string, register it in `effects/__init__.py`.
To add a new generative provider: implement the adapter interface in `backend/realstate/integrations/`.
To add a new agent: subclass `BaseAgent` in `backend/realstate/agents/`.

The whole system is designed so a pro video editor (without coding) authors templates in YAML or natural language, and the engineering team adds capabilities by implementing well-typed adapters.
