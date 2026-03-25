# NarraCraft — Project Summary
## YouTube Shorts Automation System — All Decisions & Architecture (as of March 2026)

---

## 1. Project Goal

Build a fully automated system that creates and publishes YouTube Shorts
across multiple niches (starting with gaming/anime lore "Did You Know?" format).
One button press → pipeline generates everything → user reviews final output.

---

## 2. Content Format

**"Did You Know?" — Fictional Universe Lore**

- Each Short covers one surprising fact, theory, or hidden detail from a game or anime
- AI-generated characters "inspired by" (never copying) franchise characters appear on screen
- Characters are shown doing/reacting to what the narrator describes
- Same characters persist with consistent design across all videos they appear in
- Covers both gaming (RE, Dark Souls, Zelda, etc.) and anime/manga (One Piece, AoT, Naruto, JJK, etc.)
- Target duration: 45-55 seconds

---

## 3. Tool Stack — 100% Free

| Pipeline Step        | Tool                    | Integration Method     | Cost       |
|---------------------|-------------------------|------------------------|------------|
| Script Generation   | Gemini (web UI)         | Browser automation     | FREE       |
| Compliance Check    | Gemini (web UI)         | Browser automation     | FREE       |
| Character Images    | Google Flow (Nano Banana 2) | Browser automation | FREE (0 credits) |
| Image → Video       | Kling AI (web UI)       | Browser automation     | FREE (66 credits/day) |
| Voiceover           | Chatterbox / Coqui XTTS | Local Python          | FREE (runs locally) |
| Video Assembly      | VectCutAPI → CapCut     | HTTP API + local render| FREE       |
| Stock Footage       | Pexels                  | Free API               | FREE       |
| YouTube Upload      | YouTube Data API        | Python SDK             | FREE       |

**Browser automation powered by Playwright (Python).**
Uses persistent Chrome profile to maintain login sessions.

---

## 4. Daily Production Capacity (Free Tier)

| Resource              | Daily Allowance        | Needed Per Video | Status     |
|----------------------|------------------------|------------------|------------|
| Gemini prompts       | Generous free tier     | 2-3 prompts      | ✅ Fine    |
| Flow images (Nano Banana 2) | Unlimited (0 credits) | 5-8 images  | ✅ Fine    |
| Kling video clips    | 66 credits (~6 clips)  | 5-6 clips        | ⚠️ Tight   |
| Local TTS            | Unlimited              | 1 voiceover      | ✅ Fine    |
| CapCut renders       | Unlimited              | 1 render         | ✅ Fine    |

**Target: 1 video per day, 5 per week.**

---

## 5. Application Architecture

**Single deployable app** — Python backend (FastAPI) + React frontend + VectCutAPI.
Dockerized, runs locally for dev, deployable to VPS later.

### Tech Stack
- **Backend:** Python 3.12+, FastAPI, Playwright, SQLite
- **Frontend:** React (Vite + TypeScript), shadcn/ui, Tailwind CSS
- **TTS:** Chatterbox (local, GPU) or ElevenLabs (browser automation or API)
- **Video Assembly:** VectCutAPI (separate container) → CapCut desktop
- **Deployment:** Docker Compose (3 containers: backend, frontend, vectcut-api)

### UI Theme System
10 selectable themes — user picks like light/dark mode, changeable anytime in Settings.
Each theme defines: colors, fonts, card styling, and in-context terminology.
Themes: Gothic Cathedral, Survival Horror, Manga Ink, Neon Arcade, Ancient Scroll,
Shinobi Dusk, Grand Line, Cosmic Void, Volcanic Ember, Studio Minimal.
See `dashboard-mockup.jsx` for the full theme definitions and preview.

### Docker Compose Services
```
backend   (FastAPI + Playwright + TTS)  → port 8000, GPU access
frontend  (React + Vite)                → port 3000
capcut-api (VectCutAPI server)          → port 9001
```
All share a persistent data volume for assets, DB, and browser profiles.

### Backend Structure
```
backend/
├── api/           → REST endpoints (onboarding, topics, assets, pipeline, settings)
├── services/      → Business logic
│   ├── onboarding/   (wiki scraper, IGDB, MAL, image search, bible generator)
│   ├── topics/       (wiki trivia, reddit, YT transcripts, scorer, dedup)
│   └── pipeline/     (orchestrator, script, compliance, images, video, voice, assembly, quality, publish)
├── browser/       → Playwright automation layer
│   ├── manager.py    (shared session manager — single browser, lock mechanism)
│   ├── gemini.py     (Gemini web UI wrapper)
│   ├── google_flow.py (Flow web UI wrapper)
│   └── kling.py      (Kling web UI wrapper)
└── db/            → SQLite models, migrations
```

### Frontend Pages
```
Dashboard        → Overview, pipeline status, recent uploads
Onboarding       → Franchise search, asset discovery, reference image selection
AssetLibrary     → Browse, approve, manage persistent visual assets
TopicDiscovery   → Discover, score, filter, review topics from all sources
TopicQueue       → Kanban board (Discovered → Queued → In Production → Published)
Pipeline         → Trigger runs, real-time progress (WebSocket), logs
Settings         → Config, browser accounts, schedules
```

### Playwright Session Manager (Critical Shared Component)
- Single persistent Chromium instance shared across all browser modules
- One browser profile → stays logged into Google (Gemini + Flow) and Kling
- Lock mechanism → only one module uses the browser at a time
- Modules call: `manager.get_page("gemini")` → returns a ready-to-use page
- Human-like delays, retry logic, screenshot on error

### Pipeline Execution Strategy
```
SEQUENTIAL (browser-dependent, one at a time):
  Script gen (Gemini) → Compliance (Gemini) → Image gen (Flow) → Video gen (Kling)

PARALLEL with browser steps:
  Voice gen (local GPU) runs alongside image generation

INDEPENDENT (no browser needed):
  Assembly (HTTP API) → Quality gate (local) → Upload (YouTube API)
```

### Real-time Monitoring (WebSocket)
Pipeline pushes live status updates to the dashboard:
```
✅ Step 1: Script generated (12s)
✅ Step 2: Compliance passed  
🔄 Step 3a: Generating image 4/6 in Flow...
🔄 Step 3b: Voice generating locally (parallel)
⏳ Step 4: Video animation
⏳ Step 5: Assembly  
⏳ Step 6: Quality gate
⏳ Step 7: Publish
```

---

## 6. Visual Asset Library (Persistent, Reusable)

All visual assets are **permanent** — generated once, approved once, reused forever.
Assets are stored per franchise entry (not global), because characters change between games.

```
assets/library/{franchise_entry}/
├── characters/{archetype_id}/
│   ├── portrait.png          ← Face lock
│   ├── full_body.png         ← Outfit + proportions lock
│   ├── expressions/          ← Emotion variants
│   └── metadata.json         ← Status, prompts, approval date
├── environments/{env_id}/
│   ├── wide_shot.png
│   ├── variations/
│   └── metadata.json
├── props/{prop_id}/
│   ├── image.png
│   └── metadata.json
└── ui_elements/
    └── title_card.png
```

**Key rules:**
- Characters are versioned per game entry (RE1 Chris ≠ RE5 Chris)
- Before generating any scene, system checks if approved asset exists
- If exists → reuse. If missing → halt pipeline, run Phase 1 first
- Never regenerate approved assets unless manually flagged for redesign
- Source reference images (official art) used privately during generation, never published

**Image generation approach (validated by testing):**
- Use Google Flow with Nano Banana 2 (0 credits, unlimited)
- Upload source reference images alongside text prompt for accuracy
- Character names blocked by AI tools in text → use character bibles instead
- Photorealistic/cinematic style ("shot on 35mm film, not CGI")
- Always generate in 9:16 vertical for Shorts format

---

## 7. Three Pre-Production Tools

Before the automated pipeline can run, three tools prepare everything:

### Tool 1: Franchise Onboarding
- User searches for a specific game/anime entry (not whole franchise)
- Sources: Fandom Wiki, Wikipedia, IGDB, MyAnimeList/AniList, Google Images
- Auto-discovers and categorizes: characters, locations, props
- User selects assets and picks reference images from results
- Auto-generates character bibles from wiki descriptions (user reviews/edits)
- Output: franchise registry entry + source reference images saved locally

### Tool 2: Asset Library Generation (Phase 1)
- Takes onboarded franchise with source refs
- Generates model sheets in Google Flow (portrait → full body → expressions)
- Generates environment images, prop images
- User manually approves each asset
- Output: approved persistent assets in the library

### Tool 3: Topic Discovery & Queue Management
- Separate from onboarding — run anytime to fill the topic queue
- Sources: Wiki trivia sections, Reddit (top posts), YouTube transcripts, AI suggestions
- YouTube transcript extraction via youtube-transcript-api → LLM parses facts
- Topics scored by: wiki presence, Reddit upvotes, YouTube views on similar content, multi-source validation
- Deduplication across sources (same fact in 3 videos = high confidence)
- Topics categorized: characters, dev/design, lore, easter eggs, cut content, memes
- Freshness tagged: evergreen vs trending vs time-sensitive
- Display: card view, compact list, or kanban board
- Topic states: Discovered → Queued → In Production → Published → Skipped
- Asset readiness check per topic (are all needed characters/environments approved?)
- Suggested hook line pre-generated by LLM

### Full flow:
```
Franchise Onboarding → source refs + registry entry
    ↓
Asset Library Generation (Phase 1) → approved models/environments/props
    ↓
Topic Discovery → scored & ranked topic queue
    ↓
Production Pipeline (Phase 2) → pulls from queue + asset library → published Short
```

---

## 8. Key Configuration Files

| File                                  | Purpose                                    |
|---------------------------------------|--------------------------------------------|
| `CLAUDE_CODE_BRIEF.md`               | **Master build guide for Claude Code** — start here |
| `config-schema.yaml`                  | Full system config (pipeline, quality, tools)|
| `franchise-registry.yaml`             | Content database (franchises, characters, topics) |
| `prompts/script_system.txt`           | 3-layer script generation prompt template   |
| `youtube-shorts-monetization-checklist.md` | Compliance reference (policies, rules)  |
| `project-summary.md`                  | This document — all decisions & architecture |
| `pipeline-diagram.jsx`               | Interactive visual pipeline workflow        |
| `dashboard-mockup.jsx`               | UI theme system with 10 themes + dashboard preview |

---

## 9. Compliance Guardrails (from YouTube Policy Research)

- **#1 Risk:** YouTube's Inauthentic Content Policy (Jan 2026: 16 channels terminated)
- Every script must be original (similarity check vs. last 100 scripts)
- Visual style must vary across videos (no identical templates)
- Upload pacing: max 1/day, 5/week, with time jitter
- Character names CAN be spoken in dialogue and used in titles/descriptions (fair use commentary)
- Name restrictions ONLY apply to AI image generation prompts (tools block them)
- Source reference images (official art) used only during private generation, never in videos
- No copyrighted music
- Pre-publish checklist must pass before any video goes live
- All content must be advertiser-friendly (automated content filter check)

---

## 10. Monetization Strategy — 5-Layer Revenue Stack

Shorts are the GROWTH ENGINE. Revenue comes from stacking multiple streams.

| Layer | Revenue Source | Expected Monthly | How |
|-------|---------------|-----------------|-----|
| 1 | Shorts ad revenue | $50-300 | Automatic via YPP (45% of allocated pool) |
| 2 | Long-form funnel | $500-2000 | Shorts tease → long-form deep dive (10-50x RPM) |
| 3 | Brand deals | $500-2000 | Gaming/anime brands sponsor videos |
| 4 | Fan funding | $50-200 | Super Thanks, Channel Memberships |
| 5 | Cross-platform | $50-150 | Same video → TikTok, IG Reels, FB Reels |

**Realistic range after 6 months: $1,200 - $4,650/month**

### The Long-Form Funnel (most important)
- Script module generates a long-form outline alongside every Short
- Outline covers the same topic in 10-15 minute depth
- Short's closer or pinned comment drives viewers to the long-form video
- User produces long-form videos separately (manual or semi-automated)
- Long-form RPM: $2-12 per 1,000 views vs. Shorts $0.03-0.10

### Multi-Platform Publishing
- Same MP4 published to: YouTube, TikTok, Instagram Reels, Facebook Reels
- Platform-specific metadata (captions, hashtags) generated by script module
- Browser automation handles TikTok/IG/FB uploads
- One production pipeline → 4x distribution

---

## 11. Niche Expansion Path

```
Phase 1: Gaming + Anime lore "Did You Know?" (current)
Phase 2: Add more franchise entries via onboarding tool
Phase 3: Duplicate channel config for entirely different niche types
         (the system is niche-agnostic by design)
Phase 4: Long-form content production (semi-automated)
Phase 5: Multiple channels across different niches
```

---

## 12. Next Steps

- [ ] Build the Franchise Onboarding Tool (web UI)
- [ ] Build the Topic Discovery Tool
- [ ] Build Playwright browser automation wrappers for Flow, Kling, Gemini, ElevenLabs
- [ ] Run Phase 1 for first franchise (Resident Evil 1)
- [ ] Test voice generation (Chatterbox vs ElevenLabs comparison)
- [ ] Build and test each pipeline module
- [ ] Integration testing with a real end-to-end video
- [ ] Set up multi-platform publishing (TikTok, IG, FB)
- [ ] Produce first long-form deep dive from Short outline

