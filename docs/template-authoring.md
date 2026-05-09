# Template Authoring Guide

A template is a YAML file that describes a reel as an ordered list of **shot slots**, plus audio cues and text overlays. The AI fills the slots with the user's uploaded photos at runtime.

This guide is for the pro video editor (the human who knows what makes a good real estate reel).

---

## Two ways to author

### 1. Natural-language brief (recommended)

Write a paragraph describing the reel. The `/templates` page in the UI sends it to Claude, which produces a valid YAML you can save and reuse.

> **Example brief**
> "60-second cinematic reel for a luxury home. Open with a 4-second slow zoom on the exterior at golden hour with the address overlaid. Cut to a foyer push-in at 4s. Music starts at 4s, slow cinematic. Show kitchen wide → kitchen detail → living room (3s each) between 8 and 17s. Spend 10 seconds on bedrooms and bathrooms with slow zooms. Then 8 seconds on the backyard with a pan right. End on a twilight exterior pull-out with the price overlaid for 4 seconds, fading to black."

The translator honors *exact* timing requests like "music from 4s to 8s" or "8s detail beat at 12s".

### 2. Hand-authored YAML

Drop a `*.yaml` file into `backend/realstate/templates/`. The format is documented below.

---

## YAML schema

```yaml
template_id: my-template          # kebab-case, must be unique
name: My Template                 # display name
description: One-paragraph summary
author: AutoHDR                   # who wrote it
version: "1.0.0"

target_duration_sec: 60.0         # rough total length
aspect_ratio: "9:16"              # 9:16, 1:1, or 16:9
pacing_mode: free                 # free | beat | downbeat | bar

# Optional: applied to every shot unless overridden
global_color_grade: warm_cinematic

# Two-pass render quality
draft_resolution_p: 540
final_resolution_p: 1080
draft_crf: 28                     # higher = lower quality, faster
final_crf: 18

shot_slots: [...]                 # see below
audio_cues:  [...]
text_overlays: [...]
```

### Shot slots

Each `shot_slot` describes *what kind of image* should fill the slot. The matcher picks the user's best upload that fits.

```yaml
shot_slots:
  - slot_id: hero_exterior        # unique within template
    description: >
      Wide establishing shot of the exterior at golden hour. Use the highest-quality
      exterior photo with dramatic sky.
    room_type: exterior           # see vocabulary below
    duration_sec: 5.0
    motion: slow_zoom_in          # see motion presets below
    motion_strength: 0.3          # 0..1 — how dramatic the move is
    transition_in: fade           # see transitions below
    color_grade: null             # null = inherit global
    text_overlay_id: address_card # references a text_overlay below
    must_fill: true               # if false, slot is dropped when no upload matches
    fallback_to_generated: true   # if must_fill and no match, generate via Nano Banana
    generation_prompt: >
      Cinematic wide-angle exterior of a luxury home at golden hour, dramatic sky,
      lush landscaping, warm window glow, architectural photography
```

#### Vocabulary

**`room_type`** — one of:
`exterior`, `foyer`, `kitchen`, `living_room`, `bedroom`, `bathroom`, `dining`, `backyard`, `view`, `amenity`, `lifestyle`, `detail`

**`motion`** — Ken Burns presets:
- `slow_zoom_in`, `slow_zoom_out` — gentle 18% zoom
- `push_in`, `pull_out` — stronger 30% zoom
- `pan_left`, `pan_right`, `pan_up`, `pan_down` — horizontal/vertical pan
- `static` — no motion
- `generative` — punt to Runway/Luma for true generative motion (slow + costly; reserve for hero shots)

**`transition_in`** — how the shot enters:
- `cut` — hard cut
- `dissolve` — 0.4s crossfade
- `fade` — 0.7s fade from black (use on the very first shot)
- `slide_left`, `slide_right`, `whip_pan` — currently fall back to dissolve in v1; full xfade support coming

### Audio cues

```yaml
audio_cues:
  - track_query: "mood:cinematic tempo:slow"
    # OR a literal filename: "loft-vibe.mp3"
    # OR generative: "gen:soft piano underscore, 60 bpm"
    kind: music                   # music | voiceover | sfx
    start_time_sec: 0.0
    end_time_sec: null            # null = end of reel
    volume_db: -3.0               # -6 = half volume; +3 = louder
    fade_in_sec: 1.5
    fade_out_sec: 2.5
```

`track_query` resolution order:
1. **Exact path** — `track_query: "luxury/cinematic-slow-warm.mp3"`
2. **Tag query** — `mood:X tempo:Y extra_tags`. Library scans `audio_library/` and matches by sidecar JSON or filename tags.
3. **Generative** — prefix with `gen:` to use ElevenLabs (TTS for voiceover, Music API for music).
4. **Fallback** — random track from library.

### Text overlays

```yaml
text_overlays:
  - overlay_id: address_card
    text_template: "{{ property.address }}"
    position: bottom_left         # top_left, top_right, bottom_left, bottom_right, center
    font_family: Inter
    font_size_px: 56
    color_hex: "#FFFFFF"
    background_hex: "#00000066"   # null for no pill background
    duration_sec: 4.0             # null = whole shot
    fade_in_sec: 0.5
    fade_out_sec: 0.5
```

The `text_template` is a Jinja2 template. Available variables:

- `{{ property.name }}` — project name
- `{{ property.address }}`
- `{{ property.price }}`
- `{{ property.beds }}`
- `{{ property.baths }}`
- `{{ property.sqft }}` (already comma-formatted)
- `{{ property.description }}`

To use an overlay on a shot, set `text_overlay_id: address_card` on the slot.

---

## Tips from real shoots

1. **Open with a fade**, not a cut. Reels need a beat to land.
2. **Detail beats are the secret sauce.** Real estate reels feel cinematic when you cut from a wide to a 1.5-second detail (faucet, art, plant). Mix at least 2-3 details per template.
3. **Don't over-pan.** `motion_strength` above 0.6 starts to feel motion-sicky on phone screens.
4. **Pacing matters more than length.** A 30s reel with 12 shots feels punchier than 60s with 8.
5. **Always close on the price** if it's a luxury listing. The viewer is watching for it.
6. **Use `must_fill: false` generously.** Slots that aren't critical (e.g. "second bedroom", "amenity") should be droppable so the renderer doesn't need to generate filler.
7. **Generative fallbacks should be used sparingly.** Set `fallback_to_generated: true` only for hero opens / closes where the slot is critical to the structure of the reel.

---

## How the system uses your template

1. **`StoryboardBuilder`** reads the template, calls the **vision agent** to analyze each upload, then the **shot matcher** picks the best upload for each slot (or generates one).
2. **`PacingScheduler`** computes shot start times. In `pacing_mode: beat`, it loads the chosen audio with `librosa`, detects beats, and snaps each shot boundary to the nearest beat.
3. **`FFmpegBuilder`** turns the resolved storyboard into one big FFmpeg command — Ken Burns motion, color grade, pre-rendered text overlay PNGs, audio mix, x264 encode.
4. **`MultiPassRenderer`** runs it twice: a 540p draft (quick preview) and a 1080p final (the deliverable).

For the architectural mapping back to LTX-Video patterns, see `ARCHITECTURE.md` in the repo root.
