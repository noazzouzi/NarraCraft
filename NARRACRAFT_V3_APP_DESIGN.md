# NarraCraft V3 — App Design Document

> **Created:** 2026-03-31 — Clean-start app design based on validated V2 pipeline

## What This Is

A web app (FastAPI + React + SQLite) that serves as a **prompt factory and production tracker** for AI-generated gaming/anime lore Shorts. The app does all the thinking (scripts, prompts, metadata) and the creator executes manually in external tools.

## Validated Pipeline (from V2 POC)

```
Gemini API → Script + Prompts
        ↓
Google Flow (manual) → Character reference images
        ↓
Google Veo 3.1 R2V (manual) → Video clips with voice + lip-sync
        ↓
CapCut (manual) → Assembly + captions + music
        ↓
TikTok / Instagram / YouTube → Manual upload
```

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS
- **Database:** SQLite (async via aiosqlite)
- **LLM:** Gemini API free tier (Flash/Flash-Lite, 20 RPD each). Multi-provider support for future benchmarking.
- **No browser automation. No Playwright.**

## Constraints

- Single user (no auth)
- Gemini free tier: 20 RPD per Flash model (~2-3 calls per Short, 2 Shorts/day)
- No video/image/voice generation — user does this manually
- No publishing automation — user uploads manually

---

## Pages (4)

### 1. Franchise Library

Grid of franchise cards. Click → franchise detail with characters.

**Features:**
- Add franchise: enter name + category → LLM generates visual aesthetic, iconic elements → save
- Add character: enter name → LLM generates appearance, outfit, personality, speech style → save
- Upload character reference image (generated in Google Flow)
- Store Flow URL per character
- Edit/delete franchises and characters

### 2. New Short (Wizard)

Linear 5-step wizard. Step indicator bar at top. Can go back but not skip forward. Progress persisted — can close and resume.

**Step 1 — Topic:**
Select franchise → click "Suggest Topics" → LLM returns 5-10 topic cards → user picks one

**Step 2 — Script:**
Click "Generate Script" → LLM returns scene-by-scene script (7-8 scenes) → displayed as editable list (scene number, dialogue, expression, environment, who speaks) → user can tweak → Next

**Step 3 — Characters:**
Lists characters needed for this script. For each:
- Character prompt (copyable) for Google Flow
- Upload button for generated character image (if not already in library)
- Flow URL field
- Green check if character already has an image in the library
- All characters must have images to proceed

**Step 4 — Scenes:**
Lists all scenes. For each:
- Generated Veo 3 R2V prompt (copyable)
- Which character reference image to upload as ingredient
- Flow URL field (optional)
- Status toggle (pending → done)
- User generates each in Veo 3, marks done → Next when all done

**Step 5 — Publish:**
- Upload metadata displayed: YouTube title + description + tags, TikTok caption, Instagram caption (all copyable)
- Checklist: assembled in CapCut, exported, uploaded per platform
- Mark as Published → moves to History

### 3. History

Table/grid of all Shorts. Columns: topic, franchise, status, date, scene count.
- Filter by franchise, status
- Click → full detail view (script, all prompts, Flow URLs, metadata, per-scene status)
- Resume draft Shorts (reopens wizard at current step)

### 4. Settings

- LLM Provider dropdown (Gemini Flash / Flash-Lite / future providers)
- API Key input (masked)
- App theme (light / dark)

---

## Database Schema (4 tables)

### `franchises`
```sql
id              TEXT PRIMARY KEY
name            TEXT NOT NULL
category        TEXT NOT NULL  -- "gaming" or "anime"
visual_aesthetic TEXT          -- e.g., "post-apocalyptic, overgrown urban"
iconic_elements TEXT          -- e.g., "Firefly logos, FEDRA signs, infected"
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### `characters`
```sql
id              TEXT PRIMARY KEY
franchise_id    TEXT NOT NULL REFERENCES franchises(id) ON DELETE CASCADE
name            TEXT NOT NULL
appearance      TEXT          -- full visual description for prompts
outfit          TEXT          -- specific clothing details
personality     TEXT          -- character traits
speech_style    TEXT          -- how they talk
image_path      TEXT          -- uploaded reference image file path
flow_url        TEXT          -- Google Flow session URL
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### `shorts`
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
franchise_id    TEXT NOT NULL REFERENCES franchises(id)
topic           TEXT
script_json     TEXT          -- full script with all scenes
status          TEXT DEFAULT 'draft'  -- draft/scripted/in_production/assembled/published
current_step    INTEGER DEFAULT 1     -- 1-5
upload_metadata_json TEXT     -- titles, tags, captions per platform
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
published_at    TIMESTAMP
```

### `scenes`
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
short_id        INTEGER NOT NULL REFERENCES shorts(id) ON DELETE CASCADE
scene_number    INTEGER NOT NULL
character_id    TEXT REFERENCES characters(id)
dialogue        TEXT
expression      TEXT
environment     TEXT
veo3_prompt     TEXT          -- generated, ready to copy
flow_url        TEXT          -- optional
status          TEXT DEFAULT 'pending'  -- pending/done
```

---

## API Endpoints (~18)

### Franchises
```
GET    /api/franchises              List all franchises
POST   /api/franchises              Create franchise (LLM generates details)
GET    /api/franchises/:id          Get franchise with characters
PUT    /api/franchises/:id          Update franchise
DELETE /api/franchises/:id          Delete franchise
```

### Characters
```
POST   /api/franchises/:id/characters    Add character (LLM generates description)
PUT    /api/characters/:id               Update character
DELETE /api/characters/:id               Delete character
POST   /api/characters/:id/image         Upload character reference image
```

### Shorts
```
GET    /api/shorts                  List all shorts (history)
POST   /api/shorts                  Create new short
GET    /api/shorts/:id              Get short with scenes and prompts
PUT    /api/shorts/:id              Update short (status, step, metadata)
DELETE /api/shorts/:id              Delete short
```

### Wizard
```
POST   /api/shorts/:id/generate-topics   LLM suggests topics for franchise
POST   /api/shorts/:id/generate-script   LLM generates script from topic
POST   /api/shorts/:id/generate-prompts  Generate Veo 3 prompts from script + characters
PUT    /api/scenes/:id                   Update scene (status, flow_url)
```

### Settings & LLM
```
GET    /api/settings                Get all settings
PUT    /api/settings                Update settings
GET    /api/llm/status              Check LLM availability + remaining RPD
```

---

## LLM Integration

### Provider Interface
```python
class LLMProvider:
    async def generate(self, prompt: str, system: str = None) -> str
    async def check_status(self) -> dict  # remaining RPD, model info
```

### Implementations
- `GeminiFlashProvider` — uses google-generativeai SDK, free tier
- `GeminiFlashLiteProvider` — lighter model, free tier
- Future: `ClaudeProvider`, `OpenAIProvider`

### LLM Tasks

**Franchise onboarding** (1 call):
```
System: You are a gaming/anime franchise expert.
Prompt: For the franchise "{name}" ({category}), provide:
1. Visual aesthetic (comma-separated style keywords for AI image generation)
2. Iconic visual elements (logos, signs, props, creatures fans would recognize)
Return as JSON.
```

**Character onboarding** (1 call):
```
System: You are a character design expert for {franchise_name}.
Prompt: For the character "{character_name}", provide:
1. Physical appearance (age, hair, eyes, build, distinguishing features)
2. Outfit (specific clothing items, colors, accessories)
3. Personality (3-5 traits)
4. Speech style (how they talk, tone, accent, mannerisms)
Return as JSON.
```

**Topic suggestions** (1 call):
```
System: You are a gaming/anime lore expert and viral content strategist.
Prompt: For {franchise_name}, suggest 8 "Did You Know?" topics that would
make great 45-60 second Shorts. Each topic should involve 1-2 characters
and have a surprising hook. Focus on: plot twists, hidden lore, character
backstories, moral dilemmas, easter eggs. Return as JSON array.
```

**Script generation** (1-2 calls):
```
System: You are a script writer for short-form vertical video content.
Prompt: Write a 7-8 scene script for a 45-55 second Short about:
Topic: {topic}
Franchise: {franchise_name}
Characters: {character_list with descriptions}
Franchise elements to include: {iconic_elements}

Rules:
- Each scene: max 15-17 words of dialogue
- Visible character must be the speaker (no off-screen narration)
- Scene 1: all characters together facing camera (hook)
- Last scene: all characters together (bookend/closer)
- Each character speaks from their own perspective
- Every scene must include 2-3 franchise-specific visual elements
- Vary camera angle and environment per scene

Return as JSON with scenes array.
```

**Veo 3 prompt generation** (0 calls — template-based):
Assembled from script data + stored character descriptions + franchise elements. No LLM needed.

### Prompt Template for Veo 3 Scenes
```
{shot_type} of {character.appearance}, {character.outfit}.
{environment_description with franchise iconic_elements}.
{character pronoun} says in {expression} voice, "{dialogue}"
No background music. Photorealistic, 9:16 vertical, cinematic lighting.
```

---

## File Storage

```
data/
├── db/
│   └── narracraft.db          -- SQLite database
├── images/
│   └── characters/
│       └── {character_id}.png  -- Uploaded reference images
└── settings.json               -- App settings
```

---

## Prompt Engineering Rules (Baked Into App)

These rules from our validated POC are hardcoded into the prompt generation logic:

1. **No game screenshots as references** — text-only prompts for photographic quality
2. **"Real person cosplay photography"** keywords in every character prompt
3. **Franchise elements in every scene** — logos, environments, props, creatures
4. **Veo 3 R2V mode** — reference as ingredient, not starting frame
5. **Max ~15-17 words dialogue per clip**
6. **Visible character must be the speaker** — no off-screen narration
7. **Scene 1: all characters together** facing camera (hook)
8. **Final scene: all characters together** (bookend)
9. **Each character speaks their own lines** from their own perspective
10. **Vary camera angle and environment** per scene
11. **Beauty portrait lighting** + catch-lights in eyes + warm skin tones
12. **"No background music"** in every Veo 3 prompt (music added in CapCut)

---

## Decision Log

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 1 | Clean start | Adapt V1 | V1 built for automation; V2 is fundamentally different |
| 2 | FastAPI + React + SQLite | Other stacks | User knows these, proven |
| 3 | Web dashboard | CLI, hybrid | Better UX, history tracking, professional |
| 4 | LLM for onboarding | Wiki scraping + APIs | More accurate, no dependencies, any franchise |
| 5 | Gemini API free tier | Browser automation of LLM websites | Reliable, no fragility, 20 RPD sufficient |
| 6 | Multi-provider LLM support | Single provider | Allows benchmarking later |
| 7 | Linear wizard (5 steps) | Single page, Kanban | Cleaner, professional, manageable |
| 8 | LLM suggests topics | Manual input, topic bank | Faster, LLM knows lore, user picks |
| 9 | Store images + Flow URLs | External file management | Single source of truth |
| 10 | 4 DB tables | 8 tables (V1) | YAGNI — only what's needed |
| 11 | No analytics/publishing | Full automation | Manual is fine for now |
| 12 | Template-based Veo 3 prompts | LLM-generated prompts | Saves API calls, consistent quality, rules baked in |
