# NarraCraft V2 — Design Document

> **Last updated:** 2026-03-29 — Final pipeline validated (Veo 3.1)

## Understanding Summary

- **What:** A content preparation app that helps produce 30-60 second YouTube Shorts / Instagram Reels / TikToks featuring AI-generated realistic characters narrating gaming and anime lore
- **Why:** Automate the tedious parts of short-form video creation to generate revenue from monetized content
- **Who:** Solo creator with intermediate Python/React skills, tight budget, no GPU
- **Format:** "Did You Know?" style — a franchise character narrates a lore fact in first person with lip-sync, 8+ scenes with quick cuts
- **Reference:** Instagram account @linanerdyfacts — AI-generated Resident Evil content, photorealistic characters, 8+ scenes per video

## Priorities (Ranked)

1. **Reliability** — it works every time, minimal debugging
2. **Visual quality** — videos need to look impressive
3. **Speed to first dollar** — get monetized as fast as possible
4. **Low cost** — minimize paid tools and API fees
5. **Uniqueness** — stand out from other AI content channels
6. **Scalability** — once it works, increase volume

## Constraints

- No GPU available — all AI tools must be cloud/browser-based
- Budget: $0-8/month to start (Veo 3 free tier + optional $7.99 AI Plus), scale up after proving concept
- Must comply with YouTube monetization policies (human creative direction, unique content, mandatory AI disclosure)
- Solo developer and creator — the tool must be maintainable by one person

## Non-Goals (For Now)

- Long-form content
- Non-gaming/anime niches
- Full end-to-end automation (some manual steps are acceptable)
- Browser automation (Playwright) — explicitly removed as a design choice
- Publishing automation
- Separate voice generation tools (ElevenLabs) — Veo 3 handles voice natively
- Separate lip-sync tools (Hedra, Kling) — Veo 3 handles lip-sync natively

---

## Architecture

### Core Concept

NarraCraft V2 is a **prompt factory + content organizer**, not an end-to-end pipeline. It does all the thinking (scripts, prompts, metadata) and the creator executes the quality-critical steps manually using external tools.

### Tool Chain (FINAL — Validated 2026-03-29)

| Step | Tool | Cost | Status |
|------|------|------|--------|
| Script generation | Gemini 2.5 (free tier / API) | Free | Validated |
| Character reference images | Google Flow (text-only, no game refs) | Free | Validated (~92% quality) |
| **Video clips (video + voice + lip-sync)** | **Google Veo 3.1 via Flow / AI Studio** | **Free tier (~10/day) or $7.99/mo** | **Validated (~93-95% quality)** |
| Assembly | CapCut Pro (manual) | Already paid | Trivial |

**Total monthly cost: $0-8**

> **Note:** The previous pipeline (Flow images + ElevenLabs voice + Hedra lip-sync) has been deprecated.
> Veo 3.1 replaces three separate tools with a single generation that produces video + voice + lip-sync in one pass.

### What the App Does

- Franchise onboarding (wiki scraping, character bible generation)
- Asset library (store and manage approved character reference images)
- Topic discovery and queue management
- Script generation via Gemini API (8+ scenes with quick cuts)
- **Veo 3 prompt generation** — ready-to-paste prompts per scene, with dialogue in quotes, emotion direction, environment description
- Organize and package all outputs per video
- Track video production status

### What the Creator Does Manually

- Generate character reference images in Google Flow (one-time per character, text-only prompts)
- Generate video clips in Veo 3.1 (using app-provided prompts + character reference images, ~8 clips per video)
- Assemble clips in CapCut (combine clips, add captions, music, transitions)
- Upload to TikTok / Instagram / YouTube

### What the App Does NOT Do

- Browser automation (Playwright) — removed entirely
- Video assembly or rendering
- Publishing to platforms
- Separate voice generation (Veo 3 handles this)
- Separate lip-sync generation (Veo 3 handles this)

---

## Video Style (Validated via POC)

### Structure
- **7-8 scenes per video** with quick cuts (6-8 seconds each)
- **Scene 1 (hook):** ALL characters together facing camera, one delivers the hook line
- **Middle scenes:** Alternate between characters — each speaks from their own perspective
- **Final scene (closer):** ALL characters together again, bookend effect
- **Total duration:** 45-55 seconds
- **Pacing:** Fast cuts keep it dynamic — no long static holds

### Scene Types

| Type | How it's made | Tool | Frequency |
|------|---------------|------|-----------|
| Multi-character (hook + closer) | Full video with lip-sync | Veo 3.1 R2V | 2 per video |
| Character A close-up with dialogue | Full video with lip-sync | Veo 3.1 R2V | 2-3 per video |
| Character B close-up with dialogue | Full video with lip-sync | Veo 3.1 R2V | 2-3 per video |

### Visual Style
- **"Real person cosplay photography"** — NOT "game character made realistic"
- Characters should look like real humans dressed in costume, photographed professionally
- Beauty portrait lighting on face in every scene, even dark environments
- Varied camera angles per scene (selfie, high, low, dutch, over-shoulder)
- Strong facial expressions (angry, scared, disgusted, determined — never neutral)
- 9:16 vertical, DSLR photographic quality

---

## Image Generation (Critical Discoveries)

### The Rules

1. **NEVER use game screenshots or artwork as reference images** — they anchor output to a CG/game-render look
2. **First character image:** Generate with text-only prompt, no references → establishes a "real person" face
3. **All subsequent images:** Use the previously generated output as reference for consistency
4. **Describe outfits explicitly in text** (e.g., "blue tactical tube top, shoulder armor pads, STARS beret, fingerless gloves")
5. **Always include these keywords:** "real person cosplay photography, editorial portrait quality, beauty portrait lighting, DSLR, photographic realism"
6. **Always include franchise-specific elements in character images** — backgrounds should contain recognizable franchise logos, environments, props, or creatures. A character portrait without franchise context looks generic.
7. **For Veo 3: use Reference-to-Video (R2V) mode** — upload character image as ingredient/reference, not starting frame. This prevents identical first frames across scenes.

### Master Prompt Template

```
Photograph, shot on Canon EOS R5, [focal length] lens, f/[aperture],
shallow depth of field. 9:16 vertical composition.

[CHARACTER — described as a real person in cosplay, explicit outfit details]

[EXPRESSION — strong specific emotion with micro-expression details]

[ENVIRONMENT — detailed, contextual to the story beat]

Beauty portrait lighting — [specific setup]. Bright catch-lights in eyes.
Warm glowing skin, natural skin with fine pores. Real person cosplay
photography, editorial portrait quality, DSLR, photographic realism.
```

### Quality Metrics Achieved
- Individual portraits: ~92% match with professional Instagram reference
- Composed multi-character scenes: ~93% match
- Cross-scene character consistency: ~88-90%
- Lip-sync quality after Hedra: ~85-88%

---

## Veo 3.1 Prompt Format

### How Veo 3 Dialogue Works
Use **double quotation marks** with a **lead-in verb** to trigger lip-synced dialogue:
```
[Character] says in [emotion] voice, "[dialogue]"
```

### Master Veo 3 Prompt Template
```
[SHOT TYPE] of [CHARACTER DESCRIPTION in cosplay photography style].
[CHARACTER] [EMOTION DIRECTION] says, "[ONE SENTENCE OF DIALOGUE]"
[ENVIRONMENT DESCRIPTION]. [AUDIO DIRECTION: "No background music" or SFX notes].
Photorealistic, 9:16 vertical, cinematic lighting.
```

### Example (validated)
```
Close-up of a young woman with shoulder-length dark brown hair, blue-green
eyes, wearing a blue tactical tube top with STARS beret and shoulder armor.
She faces the camera directly in a dark police office. She says in an angry,
determined voice, "He was kidnapped as a child. Taken by Umbrella's founder,
Oswell Spencer." No background music. Photorealistic, 9:16 vertical,
cinematic lighting.
```

### Key Rules for Veo 3 Prompts
1. **Max ~15-17 words of dialogue per clip** — longer dialogue gets truncated. Split into multiple clips if needed.
2. **Visible character MUST be the speaker** — Veo 3 cannot do off-screen narration. It will always lip-sync the visible character regardless of prompt instructions.
3. **Max 8 seconds per clip** — fits our 5-8 second scene structure perfectly
4. **Use Reference-to-Video (R2V) mode** — upload character image as reference/ingredient, NOT as starting frame. This prevents all scenes starting with identical frames.
5. **Describe voice emotion** before the quote: "says in a weary voice", "shouts angrily"
6. **Add "No background music"** for clean dialogue (add music in CapCut instead)
7. **9:16 vertical** for Shorts/Reels/TikTok format
8. Keep the "cosplay photography" style keywords for photorealistic quality
9. **Every scene MUST include franchise-specific visual elements** — logos, iconic environments, recognizable props, creatures. Characters alone look generic without franchise context.
10. **Repeat key character descriptors** in every prompt (hair style, outfit details) alongside the reference image for maximum consistency
11. **Vary camera angle and environment** for every scene — no two scenes should have the same setup
12. **Scene 1 must show ALL characters together** facing camera — maximum hook/scroll-stopping effect. The closer scene should mirror this as a bookend.
13. **Each character speaks their own lines** from their own perspective. No character narrates over another's scene.

### Access & Limits
- **AI Studio** (aistudio.google.com): ~10 free clips/day at 720p
- **Google Flow** (labs.google/flow): 50 credits/day = ~2-3 clips/day
- **AI Plus** ($7.99/mo): ~3 clips/day at 720p with priority
- **AI Ultra** ($249.99/mo): ~5 clips/day at 1080p (overkill for now)

---

## Prompt Template System (for App Generation)

Prompts are built from 3 layers, combined automatically by the app:

### Layer 1 — Franchise Style (set once during onboarding)

```
Category: gaming / anime
Visual aesthetic: "cinematic horror, dark industrial, bio-organic"
Color palette: "desaturated, cold blues, sickly greens"
Typical environments: "police stations, labs, mansions, forests"
```

### Layer 2 — Character Details (from approved bible)

```
Appearance: "Young woman, mid 20s, shoulder-length dark brown hair, blue-green eyes"
Outfit: "Blue tactical tube top, shoulder armor pads, STARS beret, fingerless gloves, leather straps"
Default expression: "confident, alert"
Personality: "military-trained, determined, human"
Speech style: "direct, emotional, like a soldier telling a campfire story"
```

### Layer 3 — Scene Context (from generated script)

```
Camera angle: "selfie angle from slightly below"
Expression: "angry, jaw tight, brow furrowed"
Environment: "dark police office, Umbrella files on desk"
Other characters: "none" or "Wesker in background, arms crossed"
```

Templates are editable per franchise. Changing a franchise's style updates all future prompts.

---

## Character Consistency Strategy

1. Generate first character portrait with **text-only prompt** (no reference images)
2. Review and approve — this becomes the "face lock" image
3. For all future scenes with this character, upload the approved image as reference
4. This maintains ~88-90% face consistency across scenes
5. Fast cuts (5-8 sec) in the final video hide minor variations
6. Future improvement: test Midjourney --cref or face-swap for ~98% consistency

---

## App Pages (5 total)

### 1. Franchise Onboarding
- Search game/anime → pull wiki data → generate character bibles
- Set franchise visual style (aesthetic, palette, lighting)
- Generate character image prompts (text-only, following master template)
- Upload approved character images back into the app (used as references for future scene prompts)

### 2. Asset Library
- Grid of approved character images per franchise
- Each character: portrait (face lock), plus any approved scene images
- Status: approved / needs redo

### 3. Topic Discovery + Queue
- Discover lore facts from wiki/Reddit sources
- Simple list with queue management
- Filter by franchise, category

### 4. Video Production Dashboard (core screen)
- Select a queued topic → generate script (8+ scenes) → review/edit
- Step-by-step prompt view:
  - **Step 1: Scene images** — for each scene: image gen prompt ready to paste into Google Flow, with note on which reference image to upload
  - **Step 2: Voice** — script text per scene + character voice direction (copy to ElevenLabs or auto via API)
  - **Step 3: Lip-sync** — for narrator scenes: packages image + audio, instruction to upload to Hedra
  - **Step 4: Assembly notes** — scene order, Ken Burns direction, caption text, timing, music suggestions
  - **Step 5: Upload metadata** — title, description, tags, hashtags for each platform
- Checkboxes to mark each step done
- Status tracking: scripted → images done → voiced → lip-synced → assembled → published

### 5. Settings
- API keys (Gemini, ElevenLabs)
- Default franchise preferences
- Prompt template editor (edit master template, per-franchise overrides)

---

## YouTube Monetization Compliance

Based on YouTube's July 2025 "inauthentic content" policy:

- **Human creative direction:** Creator selects topics, reviews/edits scripts, generates images manually, reviews clips, assembles final video in CapCut
- **Unique content:** Each video has a unique script, unique narration, unique scene composition
- **AI disclosure:** Mandatory toggle on upload — does NOT affect reach or monetization
- **Not mass-produced:** Human review gate at every step prevents template-identical output
- **Educational value:** Gaming/anime lore is educational entertainment content

---

## Decision Log

| # | Decision | Alternatives Considered | Why This Option |
|---|----------|------------------------|-----------------|
| 1 | Style A — AI realistic characters with lip-sync narration | Gameplay footage, slideshows, cartoon style | Matches reference, proven on Instagram |
| 2 | Minimal tool chain (4 tools) | 6+ tools chained via Playwright | Reliability is #1 priority |
| 3 | Semi-automated with human review | Fully automated pipeline | V1 full-auto broke constantly |
| 4 | No Playwright browser automation | Automate everything via browser | Main source of fragility in V1 |
| 5 | App is a prompt factory + content organizer | App does end-to-end generation | Simpler, maintainable solo |
| 6 | Static images + lip-sync + Ken Burns | Full body animation (Hailuo/Kling) | Reference uses this approach; cheaper, simpler, proven |
| 7 | Text-only prompts, no game reference images | Game screenshots as AI references | Game refs cap quality at ~75%; text-only reaches ~92% |
| 8 | Feed generated output as reference for consistency | LoRA training, Midjourney --cref | Free, works at ~88-90%, no GPU needed |
| 9 | Hedra for lip-sync | Kling two-step, D-ID, HeyGen | Simplest (image+audio direct), free tier available |
| 10 | 8+ scenes with quick cuts | 4-6 scenes with complex animation | Reference uses this; more dynamic, each scene cheaper |
| 11 | Narrator lip-sync only (4 of 8 scenes) | Animate every scene | Saves credits, static+Ken Burns looks good for non-narrator |
| 12 | "Cosplay photography" aesthetic | "Cinematic game render" aesthetic | Looks more real, better engagement, proven by reference |
| 13 | **Veo 3.1 for video + voice + lip-sync** | Separate tools (Flow + ElevenLabs + Hedra) | Single generation replaces 3 tools; free tier; better quality (~93-95%); full body movement + expressions |
| 14 | TikTok/Instagram first, YouTube later | YouTube first | No AI content restrictions on TikTok/IG monetization; YouTube YPP threshold takes months |
| 15 | AI voice (via Veo 3) instead of own voice | Record own voice | User's primary language is not English; female characters need female voice |

## Risks

- YouTube monetization is uncertain for fully AI-generated content — mitigate by starting on TikTok/Instagram first
- Veo 3 free tier may become more restricted over time — $7.99/mo AI Plus is the fallback
- Character consistency across separate Veo 3 clips needs more testing (within one clip it's ~95%)
- TikTok has banned some AI content accounts (Fruit Love Island) — monitor platform policies
- Veo 3 voice quality/accent control is limited — you describe emotion but can't upload a specific voice

---

## Proof of Concept Results (2026-03-29)

### What Was Tested
- Franchise: Resident Evil
- Topic: "Wesker Was Engineered — Project W"
- Characters: Jill Valentine (narrator), Albert Wesker

### Results Summary — Multi-Tool Pipeline (deprecated)
- Scene image quality: ~92% match with @linanerdyfacts reference
- Multi-character composition: excellent (Jill foreground, Wesker background, Spencer Mansion)
- Character consistency across scenes: ~88-90% using output-as-reference approach
- Lip-sync (Hedra): functional, ~85-88% quality, slight skin smoothing

### Results Summary — Veo 3.1 R2V Pipeline (FINAL — Validated 2026-03-30)

**Full end-to-end Short produced:** The Last of Us "Joel's Choice" — 7 scenes, 2 characters

| Metric | Score |
|--------|-------|
| Photorealism | 95% — looks like a TV show |
| Joel consistency across 5 scenes | ~92% |
| Ellie consistency across 2 scenes | ~90% |
| Franchise immersion | 97% — FEDRA, Fireflies, hospital massacre, dinosaur museum, overgrown ruins |
| Emotional range | 98% — guilt, cold violence, heartbreak all conveyed through acting |
| Publishable? | YES |

**Key scenes:** Hospital corridor with Firefly flag + blood (97%), operating room aftermath with Joel blood-spattered (96%), dinosaur museum deep-cut from TLOU Part II (95%)

**What makes it work:**
- R2V mode: each scene has unique environment/angle, reference only guides face/outfit
- Franchise elements in every frame: FEDRA signs, Firefly flags, overgrown ruins, iconic locations
- Characters speak their own lines — no off-screen narration
- Hook scene: both characters together, tension visible in body language
- Max ~15-17 words per scene dialogue — prevents truncation

### POC Files Location
- `poc_v2/tlou_result/` — Complete TLOU Short: 2 character refs + 7 video clips (ready for CapCut assembly)
- `poc_v2/` — RE Jill/Wesker earlier tests, guides, iteration log
- `poc/` — Original V1 POC (deprecated)
- `poc/y3gd59.mp4` — Instagram reference video from @linanerdyfacts
