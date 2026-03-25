# NARRACRAFT — Claude Code Build Brief
## YouTube Shorts Automation System

> **Give this file to Claude Code as the starting point.** It contains everything needed to understand, scaffold, and build the project. All design decisions are final — implement, don't redesign.

---

## 1. WHAT THIS IS

A fully automated system that creates and publishes YouTube Shorts about gaming and anime/manga lore. Format: "Did You Know?" facts narrated by AI-generated characters (e.g., Jill Valentine narrates a fact about Resident Evil while other characters act it out in the background).

**One button press → pipeline produces a complete Short → user reviews → published to YouTube, TikTok, Instagram, Facebook.**

---

## 2. REFERENCE DOCUMENTS

Read these files before writing any code. They contain exhaustive design specs:

| File | What it contains | Priority |
|------|-----------------|----------|
| `project-summary.md` | Full architecture overview, all decisions, pipeline flow | READ FIRST |
| `config-schema.yaml` | Complete technical config — every setting for every module | IMPLEMENT FROM THIS |
| `franchise-registry.yaml` | Content database structure — franchises, characters, narrators, voice settings | DATA MODEL |
| `prompts/script_system.txt` | 3-layer script generation prompt (system + franchise + topic) | PROMPT TEMPLATE |
| `youtube-shorts-monetization-checklist.md` | YouTube compliance rules, YPP requirements | COMPLIANCE RULES |
| `pipeline-diagram.jsx` | Interactive pipeline workflow (React) — shows all 8 steps | VISUAL REFERENCE |
| `dashboard-mockup.jsx` | UI theme system with 10 themes + dashboard preview | UI REFERENCE |

---

## 3. TECH STACK (non-negotiable)

```
Backend:    Python 3.12+, FastAPI, SQLite, Playwright
Frontend:   React (Vite + TypeScript), shadcn/ui, Tailwind CSS
TTS:        Chatterbox (local Docker + GPU) OR ElevenLabs (Playwright browser automation)
Images:     Google Flow / Nano Banana 2 (Playwright browser automation)
Video:      Kling AI (Playwright browser automation, lip sync + motion)
Assembly:   VectCutAPI → CapCut
Upload:     YouTube Data API v3, Playwright for TikTok/IG/FB
Deploy:     Docker Compose (3 containers)
```

---

## 4. PROJECT STRUCTURE

```
narracraft/
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
│
├── backend/
│   ├── main.py                        # FastAPI app entrypoint
│   ├── config/
│   │   ├── config_loader.py           # Reads config-schema.yaml at startup
│   │   └── config-schema.yaml         # THE config file (copy from reference)
│   │
│   ├── api/                           # REST API routes (one file per domain)
│   │   ├── onboarding.py             # POST /onboard/search, /onboard/save
│   │   ├── topics.py                 # GET /topics/discover, POST /topics/queue
│   │   ├── assets.py                 # GET /assets, POST /assets/approve
│   │   ├── pipeline.py              # POST /pipeline/run, GET /pipeline/status (WebSocket)
│   │   ├── analytics.py             # GET /analytics/dashboard, /analytics/insights
│   │   └── settings.py              # GET/PUT /settings
│   │
│   ├── services/                      # Business logic (no HTTP concerns here)
│   │   ├── onboarding/
│   │   │   ├── wiki_scraper.py       # Fandom wiki HTML scraper
│   │   │   ├── igdb_client.py        # IGDB API (Twitch auth)
│   │   │   ├── mal_client.py         # MyAnimeList via Jikan API / AniList GraphQL
│   │   │   ├── image_search.py       # Google Image search via Playwright
│   │   │   └── bible_generator.py    # LLM generates character bibles from wiki text
│   │   │
│   │   ├── topics/
│   │   │   ├── wiki_trivia.py        # Scrape Trivia/Easter Eggs sections
│   │   │   ├── reddit_scraper.py     # Top posts from franchise subreddits
│   │   │   ├── youtube_research.py   # Search YT → get transcripts → LLM extracts facts
│   │   │   ├── ai_suggestions.py    # LLM generates additional topic ideas
│   │   │   ├── topic_scorer.py       # Multi-signal scoring algorithm
│   │   │   └── topic_dedup.py        # Cross-source deduplication
│   │   │
│   │   └── pipeline/
│   │       ├── orchestrator.py       # Main pipeline runner — chains all modules
│   │       ├── script_gen.py         # Playwright → Gemini → parse JSON script
│   │       ├── compliance.py         # Script similarity check + content filter
│   │       ├── voice_gen.py          # Chatterbox (local) OR ElevenLabs (Playwright)
│   │       ├── image_gen.py          # Playwright → Google Flow → download images
│   │       ├── video_gen.py          # Playwright → Kling AI (lip sync + motion)
│   │       ├── assembly.py           # HTTP → VectCutAPI → CapCut project
│   │       ├── quality_gate.py       # 9-point pre-publish checklist
│   │       └── publisher.py          # YouTube API + Playwright (TikTok, IG, FB)
│   │
│   ├── browser/                       # Playwright automation layer
│   │   ├── manager.py                # CRITICAL: shared session manager
│   │   │                             # Single Chromium instance, lock mechanism,
│   │   │                             # persistent profile (stays logged in),
│   │   │                             # human-like delays, screenshot on error
│   │   ├── gemini.py                 # Gemini web UI automation wrapper
│   │   ├── google_flow.py            # Google Flow automation wrapper
│   │   ├── kling.py                  # Kling AI automation wrapper
│   │   └── elevenlabs.py            # ElevenLabs web UI automation wrapper
│   │
│   ├── db/
│   │   ├── database.py               # SQLite connection + migrations
│   │   └── models.py                 # Tables: topics, assets, scripts, videos, analytics
│   │
│   └── data/                          # Persistent data (Docker volume mount)
│       ├── library/                  # Approved visual assets (characters, envs, props)
│       ├── source_refs/              # Private reference images (official art, voice clips)
│       ├── audio/                    # Music and SFX library
│       │   ├── music/               # Organized by mood (dark_cinematic, epic_adventure, etc.)
│       │   └── sfx/                 # Organized by function (impacts, transitions, reveals, etc.)
│       ├── output/                   # Generated videos ready for review
│       ├── quarantine/              # Failed/rejected videos
│       ├── long_form_outlines/      # Deep dive outlines generated alongside Shorts
│       ├── browser_data/            # Playwright persistent profiles
│       └── shorts.db                # SQLite database
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── themes/
│   │   │   └── themes.ts            # 10 theme definitions (from dashboard-mockup.jsx)
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # Mission Control — status, activity, queue preview
│   │   │   ├── Onboarding.tsx       # Search → discover assets → select refs → save
│   │   │   ├── AssetLibrary.tsx     # Grid view, approve/reject, status badges
│   │   │   ├── TopicDiscovery.tsx   # Source selection → scored results → card/list view
│   │   │   ├── TopicQueue.tsx       # Kanban: Discovered → Queued → Production → Published
│   │   │   ├── Pipeline.tsx         # Run/stop, real-time WebSocket progress, logs
│   │   │   ├── Analytics.tsx        # Charts, franchise perf, narrator comparison, insights
│   │   │   └── Settings.tsx         # Theme picker, voice provider, browser accounts, schedule
│   │   ├── components/              # Reusable UI components
│   │   │   ├── ThemeProvider.tsx     # Context provider for active theme
│   │   │   ├── Sidebar.tsx
│   │   │   ├── CommandPalette.tsx   # ⌘K search + quick actions
│   │   │   ├── ImageGrid.tsx        # Selectable image grid (onboarding + assets)
│   │   │   ├── TopicCard.tsx        # Score badge, source icons, asset readiness
│   │   │   ├── KanbanBoard.tsx      # Drag-and-drop columns
│   │   │   ├── PipelineProgress.tsx # Step-by-step live progress with WebSocket
│   │   │   └── VideoPreview.tsx     # Play video before approving publish
│   │   └── api/
│   │       └── client.ts            # Typed API client for all backend endpoints
│   ├── package.json
│   └── tailwind.config.ts
│
└── data/                              # Config files (mounted into backend container)
    ├── config-schema.yaml
    ├── franchise-registry.yaml
    └── prompts/
        └── script_system.txt
```

---

## 5. CRITICAL ARCHITECTURAL DECISIONS

### Playwright Session Manager (browser/manager.py)
This is the most important shared component. ALL browser automation goes through it.
- Single persistent Chromium instance shared across ALL modules
- One browser profile → stays logged into Google (Gemini + Flow), Kling, ElevenLabs
- Lock mechanism → only one module uses the browser at a time
- Human-like delays between actions (randomized 0.5-2s)
- Screenshot on error for debugging
- Modules call: `await manager.get_page("gemini")` → returns ready page

### Pipeline Execution Order
```
1. RESEARCH     → Pull topic from queue (DB read)
2. SCRIPT       → Playwright → Gemini → parse JSON → validate word count
3. COMPLIANCE   → Similarity check (local) + content filter (Gemini)
4. VOICE + IMAGES → PARALLEL
   ├→ VOICE (local Chatterbox OR Playwright → ElevenLabs)
   │  → Full voiceover → split into per-scene segments with timestamps
   └→ IMAGES (Playwright → Google Flow)
      → Narrator shots + action shots + mixed shots
5. ANIMATE      → SEQUENTIAL (needs BOTH voice + images done)
   ├→ Narrator scenes: Kling LIP SYNC (image + audio segment)
   └→ Action scenes: Kling MOTION only (no audio)
6. ASSEMBLE     → HTTP → VectCutAPI → CapCut project
7. QUALITY GATE → 9-point automated checklist
8. PUBLISH      → YouTube API + Playwright (TikTok, IG, FB)
                → Save long-form outline
                → Pin comment with CTA
```

### Voice System (dual provider)
User selects active provider in Settings: Chatterbox (local, free, needs GPU) or ElevenLabs (browser automation, best quality, free tier limited).
Each narrator character has per-provider voice settings stored in the franchise registry.
Reference audio is extracted from game cutscenes — stored in the asset library.
See `config-schema.yaml` voice section for full details.

### Narrator System
- Each franchise has a default narrator (user-selected character)
- The narrator speaks IN CHARACTER, not as a neutral voice
- Scripts are written as first-person dialogue with the narrator's personality
- Narrator has front-facing assets for lip sync (separate from standard character assets)
- User picks narrator per topic (app suggests, user confirms)
- Character names ARE used in dialogue and YouTube metadata (fair use commentary)
- Character names are NOT used in AI image generation text prompts (tools block them)

### Three Shot Types in Every Video
- `narrator_with_characters` — Narrator foreground + others behind (ALWAYS first scene)
- `narrator_alone` — Narrator close-up, speaking to camera
- `characters_only` — Narrator not visible, voice-over action scene
- Rule: never 3+ of same type consecutively

### Asset Library (Persistent, Reusable)
All visual assets are permanent — generated once in Phase 1, approved once, reused forever.
Characters are versioned per game entry (RE1 Chris ≠ RE5 Chris).
Directory: `data/library/{franchise}/{asset_type}/{asset_id}/`
Narrator characters have extra `narrator/` and `voice/` subdirectories.

### Topic Discovery Sources
1. Fandom Wiki trivia/easter egg sections (scraping)
2. Reddit top posts from franchise subreddits (scraping)
3. YouTube transcripts → LLM extracts individual facts (youtube-transcript-api + Gemini)
4. LLM-generated suggestions (fact-checked flag required)
Topics are scored, deduplicated, and ranked. States: Discovered → Queued → In Production → Published → Skipped.

### Audio Design (3 layers, all automated)
1. Background music — royalty-free, organized by mood, auto-selected per franchise, 8% volume
2. Sound effects — impacts on hook, whooshes on transitions, reveals on key facts
3. Ambient (optional) — subtle atmosphere per franchise (rain for RE, wind for DS)

### Captions
Word-by-word highlight synced to voiceover timestamps. Center of screen.
Franchise-specific color presets (RE: blood red, Zelda: golden, JJK: hot orange).

### Multi-Platform Publishing
Same MP4 → YouTube (API) + TikTok (Playwright) + Instagram Reels (Playwright) + Facebook Reels (Playwright).
Platform-specific metadata (captions, hashtags) generated by the script module.

### Monetization (5-layer stack)
1. Shorts ad revenue (passive, $50-300/mo)
2. Long-form funnel — script module generates deep-dive outline alongside every Short ($500-2000/mo)
3. Brand deals ($500-2000/mo)
4. Fan funding — Super Thanks, memberships ($50-200/mo)
5. Cross-platform revenue ($50-150/mo)

### Analytics Feedback Loop
YouTube API pulls metrics at 24h/7d/30d. Feeds back into: topic scoring, franchise weighting, hook pattern analysis, narrator comparison, posting time optimization. Dashboard shows auto-generated weekly insights.

---

## 6. FRONTEND DESIGN SYSTEM

### UI Library: shadcn/ui + Tailwind CSS

### Theme System (10 themes)
Themes are a user preference — selectable in Settings like light/dark mode.
Each theme defines: background, surface, border, text colors (3 levels), accent color, success/warning/danger, 3 font families (display, body, mono), card styling, and in-context terminology.

The 10 themes and their identities:
1. **Gothic Cathedral** — Dark Souls aesthetic (gold on charred black, Cinzel serif)
2. **Survival Horror** — Resident Evil aesthetic (phosphor green, monospace terminal)
3. **Manga Ink** — One Piece/JJK (red on warm parchment, bold panel borders) — LIGHT THEME
4. **Neon Arcade** — Retro gaming (magenta on deep purple, pixel font)
5. **Ancient Scroll** — Zelda/Elden Ring (aged gold on warm brown, medieval serif)
6. **Shinobi Dusk** — Naruto/Demon Slayer (ember orange on twilight purple)
7. **Grand Line** — One Piece sea adventure (ocean blue on deep navy)
8. **Cosmic Void** — Final Fantasy/KH (violet on deep space black, Orbitron)
9. **Volcanic Ember** — Monster Hunter (fire orange on ember black)
10. **Studio Minimal** — Clean professional (dark on light, Sora sans) — LIGHT THEME

Full theme definitions with exact colors, fonts, and card styles are in `dashboard-mockup.jsx`.

### Key UX Patterns
- **Command palette (⌘K)** — search franchises, topics, trigger actions
- **WebSocket for pipeline monitoring** — real-time step progress
- **Kanban board** for topic queue management (drag between columns)
- **Image grids** with tap-to-select for onboarding and asset management
- **Toast notifications** for pipeline events and milestones

### Pages (8 total)
1. Dashboard — status cards, activity log, queue preview, franchise performance, insights
2. Franchises — onboarding wizard (search → discover → select refs → save)
3. Assets — grid view of all visual assets, approve/reject workflow
4. Discover — topic discovery with source selection, scoring, card/list view
5. Queue — kanban board (Discovered → Queued → In Production → Published)
6. Pipeline — run/stop button, real-time progress, log viewer
7. Analytics — charts, franchise comparison, narrator performance, auto-insights
8. Settings — theme picker, voice provider, browser accounts, schedule, API keys

---

## 7. BUILD ORDER (suggested)

### Phase 1: Skeleton
1. `docker-compose.yml` with 3 services (backend, frontend, vectcut-api placeholder)
2. FastAPI app with health check endpoint
3. React app with Vite + TypeScript + shadcn/ui + Tailwind
4. Theme system (ThemeProvider + 10 themes + Settings page with theme picker)
5. Sidebar navigation + page routing
6. SQLite database with initial schema (topics, assets, scripts, videos, analytics tables)

### Phase 2: Pre-Production Tools
7. Franchise onboarding — wiki scraper, IGDB client, MAL client, image search
8. Onboarding UI — search bar, results display, asset categorization, ref image selection
9. Asset library UI — grid view, approval workflow, status badges
10. Topic discovery — wiki trivia scraper, Reddit scraper, YouTube transcript extractor
11. Topic scoring algorithm + deduplication
12. Topic discovery UI — card view, list view, filters, sorting
13. Topic queue UI — kanban board with drag-and-drop

### Phase 3: Pipeline Core
14. Playwright session manager (the critical shared component)
15. Script generation module (Playwright → Gemini → JSON parse → validation)
16. Compliance module (similarity check + content filter)
17. Voice module — Chatterbox integration (local Docker)
18. Voice module — ElevenLabs integration (Playwright browser automation)
19. Image generation module (Playwright → Google Flow)
20. Video generation module (Playwright → Kling AI, lip sync + motion)
21. Assembly module (HTTP → VectCutAPI)
22. Quality gate module (9-point checklist)
23. Pipeline orchestrator (chains all modules, parallel voice+images, error handling)
24. Pipeline UI — run/stop, WebSocket progress, log viewer

### Phase 4: Publishing & Analytics
25. YouTube upload module (YouTube Data API v3)
26. Multi-platform publishing (Playwright → TikTok, IG, FB)
27. Long-form outline generation (alongside every Short)
28. Analytics collection (YouTube API → DB at 24h/7d/30d)
29. Analytics dashboard UI (charts, franchise perf, insights)
30. Feedback loop (topic scoring adjustment, schedule optimization)

### Phase 5: Polish
31. Command palette (⌘K)
32. Toast notifications
33. Dashboard page (aggregate view with all widgets)
34. Error handling, retry logic, quarantine workflow
35. End-to-end test with a real video

---

## 8. DATABASE SCHEMA (SQLite)

```sql
-- Franchises and their entries
CREATE TABLE franchises (
    id TEXT PRIMARY KEY,              -- "resident_evil_1"
    name TEXT NOT NULL,               -- "Resident Evil (2002 Remake)"
    franchise_group TEXT NOT NULL,    -- "resident_evil"
    category TEXT NOT NULL,           -- "gaming" or "anime"
    config_json TEXT NOT NULL,        -- Full franchise config (from registry YAML)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visual assets (characters, environments, props)
CREATE TABLE assets (
    id TEXT PRIMARY KEY,              -- "resident_evil_1/characters/resourceful_agent"
    franchise_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,         -- "character", "environment", "prop"
    archetype_id TEXT,
    status TEXT DEFAULT 'pending',    -- "pending", "generated", "approved", "rejected"
    is_narrator BOOLEAN DEFAULT FALSE,
    model_dir TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Topics discovered and queued
CREATE TABLE topics (
    id TEXT PRIMARY KEY,              -- "re1_winchester_mansion"
    franchise_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,                    -- "characters", "dev_design", "lore", "easter_egg", etc.
    freshness TEXT DEFAULT 'evergreen', -- "evergreen", "trending", "time_sensitive"
    score REAL DEFAULT 0,
    score_breakdown_json TEXT,
    sources_json TEXT,               -- Array of source objects with excerpts
    characters_needed_json TEXT,
    asset_status TEXT DEFAULT 'unknown', -- "ready", "blocked", "partial"
    suggested_hook TEXT,
    status TEXT DEFAULT 'discovered', -- "discovered", "queued", "in_production", "published", "skipped"
    narrator_archetype TEXT,
    closer_style TEXT,
    queued_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Generated scripts
CREATE TABLE scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT NOT NULL,
    script_json TEXT NOT NULL,        -- Full JSON output from Gemini
    word_count INTEGER,
    total_duration_seconds REAL,
    similarity_score REAL,           -- vs. last 100 scripts
    status TEXT DEFAULT 'generated', -- "generated", "approved", "rejected"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

-- Published videos
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT NOT NULL,
    script_id INTEGER NOT NULL,
    franchise_id TEXT NOT NULL,
    narrator_archetype TEXT,
    
    -- Platform IDs
    youtube_video_id TEXT,
    tiktok_video_id TEXT,
    instagram_video_id TEXT,
    facebook_video_id TEXT,
    
    -- File paths
    video_path TEXT,
    long_form_outline_path TEXT,
    
    -- Metadata
    title TEXT,
    description TEXT,
    tags_json TEXT,
    closer_style TEXT,
    
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (script_id) REFERENCES scripts(id),
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Analytics snapshots
CREATE TABLE analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    snapshot_type TEXT NOT NULL,      -- "24h", "7d", "30d"
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    avg_view_duration_pct REAL,
    click_through_rate REAL,
    subscribers_gained INTEGER DEFAULT 0,
    traffic_sources_json TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- Pipeline run history
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT,
    status TEXT DEFAULT 'running',   -- "running", "completed", "failed", "aborted"
    current_step TEXT,
    steps_log_json TEXT,             -- Array of {step, status, duration, error}
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Audio track usage (for deduplication)
CREATE TABLE audio_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    track_path TEXT NOT NULL,
    track_type TEXT NOT NULL,         -- "music", "sfx"
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- User settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Default settings to insert:
-- ("active_theme", "gothic")
-- ("voice_provider", "chatterbox")
-- ("youtube_api_configured", "false")
-- ("tiktok_enabled", "false")
-- ("instagram_enabled", "false")
-- ("facebook_enabled", "false")
```

---

## 9. API ENDPOINTS (overview)

```
# Onboarding
GET  /api/onboarding/search?q=resident+evil     → search results from all sources
POST /api/onboarding/save                        → save franchise entry + refs

# Assets
GET  /api/assets?franchise_id=...&type=...       → list assets with filters
POST /api/assets/{id}/approve                    → mark asset as approved
POST /api/assets/{id}/reject                     → mark asset as rejected

# Topics
POST /api/topics/discover                        → run discovery for a franchise
GET  /api/topics?status=discovered&franchise=...  → list topics with filters
PUT  /api/topics/{id}/queue                      → move to queued
PUT  /api/topics/{id}/skip                       → skip topic
PUT  /api/topics/{id}                            → edit topic (narrator, closer_style, etc.)

# Pipeline
POST /api/pipeline/run                           → start pipeline (pulls next queued topic)
POST /api/pipeline/stop                          → abort current run
WS   /api/pipeline/ws                            → WebSocket for real-time progress

# Analytics
GET  /api/analytics/dashboard                    → aggregate stats
GET  /api/analytics/insights                     → auto-generated recommendations
GET  /api/analytics/franchise/{id}               → per-franchise breakdown

# Settings
GET  /api/settings                               → all settings
PUT  /api/settings                               → update settings (theme, provider, etc.)
```

---

## 10. COMPLIANCE RULES (non-negotiable)

These must be enforced in the quality gate before ANY video publishes:

1. Script is original — cosine similarity < 0.7 vs. last 100 scripts
2. Voiceover is present and > 10 seconds
3. Visual style varies — not identical template to last 5 videos
4. No copyrighted material in published content (images, music, footage)
5. All content is advertiser-friendly (no violence, profanity, etc.)
6. Duration is under 60 seconds
7. Title + description + tags are complete and include franchise/character names
8. Upload pattern is not bot-like — respect cooldown (6h) and jitter (±30min)
9. Video structure differs from last 5 uploads (closer style, shot type sequence)

If ANY check fails → video goes to quarantine, not published.

---

## 11. IMPORTANT NOTES

- **Character names CAN be spoken in dialogue** and used in titles/descriptions (fair use)
- **Character names CANNOT be used in AI image generation text prompts** (tools block them)
- **Source reference images** (official art) are uploaded alongside prompts during generation — private input, never published
- **All music and SFX must be royalty-free** with no Content ID claims
- **Upload pacing**: max 1 video/day, 5/week, with time jitter
- **The system is config-driven** — niche = parameter, not hardcoded. Franchise registry is the content database.
- **Every visual asset is permanent** — generated once, approved once, reused forever. Never regenerate approved assets unless manually flagged.
