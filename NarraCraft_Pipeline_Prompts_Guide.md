# NarraCraft Pipeline — Prompts & Steps Guide

This document walks through the full pipeline using a concrete example:
**Franchise:** Resident Evil Village
**Character:** Mother Miranda
**Fact:** *"She is the 'Mother' of Umbrella: In the 1950s, Miranda rescued a young, lost hiker named Oswell E. Spencer. She taught him about her experiments with the Mold, which directly inspired him to found the Umbrella Corporation."*

Each section maps directly to what the NarraCraft app does today.

---

## Table of Contents

1. [Step 1 — Character Bible Generation](#step-1--character-bible-generation)
2. [Step 2 — Character Image Generation (Google Flow)](#step-2--character-image-generation-google-flow)
3. [Step 3 — Environment Image Generation (Google Flow)](#step-3--environment-image-generation-google-flow)
4. [Step 4 — Script Generation (Gemini)](#step-4--script-generation-gemini)
5. [Step 5 — Voice Generation (Chatterbox / ElevenLabs)](#step-5--voice-generation-chatterbox--elevenlabs)
6. [Step 6 — Scene Image Generation (Google Flow)](#step-6--scene-image-generation-google-flow)
7. [Step 7 — Video Clip Generation (Kling AI)](#step-7--video-clip-generation-kling-ai)
8. [Step 8 — Final Assembly (VectCutAPI / CapCut)](#step-8--final-assembly-vectcutapi--capcut)

---

## Step 1 — Character Bible Generation

**What it does:** Takes wiki data from onboarding (summary + infobox) and produces an abstract character description that never uses the real character name. This "bible" is what every downstream AI prompt uses.

**Module:** `backend/services/onboarding/bible_generator.py`

**Input (from wiki scraper during onboarding):**

```
Character name: Mother Miranda (stored as source_character_name — NEVER used in AI prompts)

Wiki summary: "Miranda was a priestess and biological researcher in an Eastern European
village. After losing her daughter Eva to the Spanish Flu in 1919, she discovered the
Megamycete, a sentient fungal superorganism. She spent a century experimenting with the
Mold to find a way to resurrect Eva..."

Infobox:
  gender: Female
  occupation: Priestess, Researcher
  abilities: Shapeshifting, Mold manipulation, Superhuman regeneration
  hair: Dark (concealed by hood)
  eyes: Golden/yellow
```

**Output — Character Bible:**

```yaml
archetype_id: "mother_miranda"  # Generated from name, used as abstract ID everywhere
visual_description: "Female, dark hair concealed by hood, golden/yellow eyes"
character_bible: >
  Female. A priestess and biological researcher from a remote Eastern European
  village. Wears dark robes with a hooded cloak concealing most of her features.
  Eyes glow golden. Her face shows signs of age but retains an unsettling beauty.
  Occupation: Priestess, Researcher. Abilities: Shapeshifting, Mold manipulation,
  Superhuman regeneration. Expression defaults to serene authority with an
  undercurrent of obsession.
source_character_name: "Mother Miranda"  # Real name — never in AI prompts
```

**How to do this manually:**
1. Go to the **Onboarding** page
2. Search "Resident Evil Village" → select it → Discover Characters
3. Select "Miranda" from the character list
4. The app calls `/api/onboarding/generate-bible` which runs `bible_generator.py`
5. The resulting bible is saved with the franchise config

---

## Step 2 — Character Image Generation (Google Flow)

**What it does:** Creates the persistent character reference images (portrait, full body, narrator poses) that will be reused in every future video. Done ONCE per character during onboarding, then approved by the user.

**Tool:** [Google Flow](https://labs.google/flow) (browser automation via `backend/browser/google_flow.py`)

**Module:** `backend/services/pipeline/image_gen.py` → `_build_image_prompt()`

### Prompt: Portrait (Face Lock)

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Close-up portrait, character facing camera directly.

Character: Female, dark hair concealed by hood, golden/yellow eyes. A priestess
and biological researcher from a remote Eastern European village. Wears dark robes
with a hooded cloak concealing most of her features. Eyes glow golden. Her face
shows signs of age but retains an unsettling beauty. Expression: serene, calm
authority.

Setting: Dimly lit stone chapel with candles and religious iconography.

Vertical composition (9:16), cinematic lighting, high detail.
```

**Reference images uploaded alongside the prompt:**
- `assets/source_refs/resident_evil/miranda_ref_01.jpg` (official artwork or screenshot)
- `assets/source_refs/resident_evil/miranda_ref_02.jpg`

> These reference images are what makes Google Flow produce accurate results despite never naming "Mother Miranda" in the text prompt. The AI sees the reference and matches the look.

### Prompt: Full Body

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Full body shot, character standing, facing viewer.

Character: Female, dark hair concealed by hood, golden/yellow eyes. Wears dark
robes with a hooded cloak. Eyes glow golden. Abilities: Shapeshifting, Mold
manipulation. Standing in a regal, commanding pose with arms slightly extended.

Setting: Ancient underground ritual chamber with the Megamycete (massive fungal
structure) visible in the background, bioluminescent glow.

Vertical composition (9:16), cinematic lighting, high detail.
```

### Prompt: Front-Facing Narrator Pose (for lip sync)

> Only needed if Miranda is set as the narrator for a video.

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Close-up portrait, character facing camera directly. Expression: raised eyebrow,
knowing smile.

Character: Female, dark hair concealed by hood, golden/yellow eyes. Wears dark
robes with a hooded cloak. Expression shows subtle amusement mixed with authority.
Direct eye contact with camera. Mouth clearly visible (not obscured by hood).

Setting: Dark stone chapel, candlelight, shallow depth of field.

Vertical composition (9:16), cinematic lighting, high detail.
```

**Output stored at:**
```
assets/library/resident_evil_village/characters/mother_miranda/
  portrait.png          ← face lock
  full_body.png         ← outfit + proportions lock
  narrator/
    front_facing.png    ← lip sync base image (if narrator)
    front_amused.png    ← variant
  metadata.json         ← status, creation date, prompts used
```

---

## Step 3 — Environment Image Generation (Google Flow)

**What it does:** Creates persistent environment/location images, done ONCE during onboarding.

### Prompt: Village Church

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Wide establishing shot, no characters.

Setting: Ancient Eastern European stone church interior. Candles lining the
walls, religious murals faded with age, stone altar with ritual implements.
Dust particles in shafts of light from broken stained glass windows. Cold,
oppressive atmosphere.

Vertical composition (9:16), cinematic lighting, high detail.
```

### Prompt: Village Square

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Wide establishing shot, no characters.

Setting: Snow-covered Eastern European village square. Old stone and timber
houses, well in the center, cobblestone path. Overcast sky, barren trees,
ominous atmosphere. Mountain fortress visible in the distance.

Vertical composition (9:16), cinematic lighting, high detail.
```

**Output stored at:**
```
assets/library/resident_evil_village/environments/village_church/
  wide_shot.png
assets/library/resident_evil_village/environments/village_square/
  wide_shot.png
```

---

## Step 4 — Script Generation (Gemini)

**What it does:** Takes the topic/fact + franchise context and generates a full scene-by-scene script in JSON. Sent to Gemini via browser automation.

**Module:** `backend/services/pipeline/script_gen.py`
**Prompt template:** `data/prompts/script_system.txt` (3-layer system)

### Full Prompt Sent to Gemini

**SECTION 1 — System (constant, same for every video):**

```
You are a script writer for short-form vertical video content (YouTube Shorts,
45-55 seconds).

You write scripts where a fictional character narrates directly to the camera,
sharing a surprising fact or piece of lore about their world. The character
speaks AS themselves — in first person, with their own personality, opinions,
and way of talking. This is NOT a neutral documentary narrator. This is a
character reacting to and sharing lore from their own universe.

## FORMAT RULES
- Total script length: 100-155 words. This is CRITICAL. Count carefully.
  At 2.8 words per second, 100 words = ~36s and 155 words = ~55s.
  Target the 120-145 word sweet spot for a ~45-50 second video.
- Structure: Hook (3-5 seconds) → Body (35-45 seconds) → Closer (5-8 seconds)
- The hook must stop the scroll in the first 2 seconds. Start with "Did you
  know?" or a bold/shocking claim.
- The closer varies in style (see CLOSER STYLES below).

## CHARACTER NAME RULES
- The narrator CAN and SHOULD use character names and franchise references in
  dialogue. This is spoken commentary content.
- YouTube title and description SHOULD include franchise and character names.
- NOTE: Image generation handles its own name restrictions separately.

## SCENE STRUCTURE RULES
- narrator_with_characters: Narrator foreground facing camera, others behind.
  USE THIS for the hook (first scene).
- narrator_alone: Narrator close-up, facing camera. Good for emphasis.
- characters_only: Narrator NOT visible. Voice plays over characters acting.

RULES:
- First scene MUST be narrator_with_characters
- Never use the same shot type 3+ times consecutively
- 4-6 scenes typical. Each scene 5-12 seconds.

## CLOSER STYLES (use the style specified in the input)
- style_cta: "Follow me for more secrets."
- style_teaser: "But that's not even the craziest thing..."
- style_punchline: Mic drop, no CTA.
- style_question: Ask the viewer a question.
- style_reveal: Save biggest surprise for the final line.

## OUTPUT FORMAT
Respond with ONLY a JSON object. No markdown, no commentary.
[See full JSON schema in data/prompts/script_system.txt]
```

**SECTION 2 — Franchise Context (from franchise registry):**

```
--- FRANCHISE ---
Franchise: Resident Evil Village
Category: gaming
Visual aesthetic: cinematic horror, dark industrial environments, bio-organic mutations

--- NARRATOR ---
Narrator character: mother_miranda
Narrator visual: Female, dark hair concealed by hood, golden/yellow eyes
Personality: serene authority, obsessive devotion, unsettling calm
Speech style: speaks as if addressing her children, mixing tenderness with menace
Example line: "Did you know? I once rescued a lost boy in the mountains. He went
on to build an empire... from MY research."

How the narrator refers to other characters:
- ethan_winters: "the outsider", "that persistent father"
- alcina_dimitrescu: "my daughter Alcina", "the Countess"

--- AVAILABLE CHARACTERS ---
- Archetype ID: ethan_winters
  Description: Male, early 30s, brown hair, civilian clothing, bandaged hands
  Bible: Everyman survivor, determined father...

- Archetype ID: alcina_dimitrescu
  Description: Extremely tall elegant woman in white dress, wide-brimmed hat, pale skin
  Bible: Towering aristocratic vampire-like figure...

- Archetype ID: village_elder
  Description: Elderly man with weathered face, heavy coat, walking cane
  Bible: Long-time village resident, suspicious of outsiders...

--- AVAILABLE ENVIRONMENTS ---
- Environment ID: village_church
  Description: Ancient stone church interior with candles, religious murals, stone altar
- Environment ID: village_square
  Description: Snow-covered village square with stone houses, central well
- Environment ID: miranda_laboratory
  Description: Underground bio-research lab, fungal growths, specimen jars, ritual markings
```

**SECTION 3 — Topic Input (from topic queue):**

```
--- TOPIC ---
Fact to cover: She is the "Mother" of Umbrella
Source details: In the 1950s, Miranda rescued a young, lost hiker named Oswell E.
Spencer. She taught him about her experiments with the Mold, which directly inspired
him to found the Umbrella Corporation.
Source excerpts:
  - "Miranda's research with the Megamycete directly influenced Spencer's vision
    for immortality through biological enhancement."

Characters involved: mother_miranda, village_elder
Narrator for this video: mother_miranda
Closer style for this video: style_reveal

--- INSTRUCTION ---
Write the script now.

Remember:
- 100-155 words total (count carefully)
- In-character as mother_miranda with their personality and speech style
- Use character names naturally in dialogue
- First scene: narrator_with_characters (show the cast)
- Vary shot types across scenes
- Closer style: style_reveal
- Output ONLY the JSON object, nothing else
```

### Expected Output from Gemini

```json
{
  "title": "Resident Evil Village — Miranda Created Umbrella?! 😱",
  "description": "The secret origin of Umbrella Corporation traces back to a remote village and one woman's obsession. Mother Miranda's research changed the world forever. #ResidentEvil #REVillage #Umbrella #GamingFacts #DidYouKnow",
  "tags": ["resident evil", "resident evil village", "mother miranda", "umbrella", "gaming facts", "did you know", "re village lore"],
  "total_word_count": 138,
  "estimated_duration_seconds": 49,
  "closer_style": "style_reveal",
  "scenes": [
    {
      "scene_number": 1,
      "dialogue": "Did you know? The entire Umbrella Corporation — every virus, every outbreak, every monster — exists because of me.",
      "shot_type": "narrator_with_characters",
      "narrator_expression": "serene smile, slight head tilt, knowing eyes",
      "action_characters": [
        {
          "archetype_id": "village_elder",
          "action": "standing nervously behind, clutching his cane"
        }
      ],
      "environment": "village_church",
      "duration_seconds": 6
    },
    {
      "scene_number": 2,
      "dialogue": "In the 1950s, a young man — lost, freezing — stumbled into my village. His name was Oswell Spencer. I took him in. I showed him my work.",
      "shot_type": "characters_only",
      "narrator_expression": null,
      "action_characters": [
        {
          "archetype_id": "village_elder",
          "action": "young version, shivering in snow, looking up at a hooded figure offering a hand"
        }
      ],
      "environment": "village_square",
      "duration_seconds": 10
    },
    {
      "scene_number": 3,
      "dialogue": "The Megamycete. The Mold. Decades of my research into life, death, and rebirth. He watched. He learned. He took notes.",
      "shot_type": "narrator_alone",
      "narrator_expression": "eyes narrowing, mix of pride and resentment",
      "action_characters": [],
      "environment": "miranda_laboratory",
      "duration_seconds": 9
    },
    {
      "scene_number": 4,
      "dialogue": "Then he left. Took my ideas, built a pharmaceutical empire, and twisted my work into bioweapons.",
      "shot_type": "characters_only",
      "narrator_expression": null,
      "action_characters": [
        {
          "archetype_id": "village_elder",
          "action": "walking away from village into modern cityscape, briefcase in hand"
        }
      ],
      "environment": "village_square",
      "duration_seconds": 8
    },
    {
      "scene_number": 5,
      "dialogue": "Every outbreak you've ever seen in Resident Evil — Raccoon City, the Spencer Mansion — all of it traces back to one woman, in one village. Me.",
      "shot_type": "narrator_alone",
      "narrator_expression": "calm authority turning to cold satisfaction, direct eye contact",
      "action_characters": [],
      "environment": "miranda_laboratory",
      "duration_seconds": 10
    },
    {
      "scene_number": 6,
      "dialogue": "Oh, and Spencer? He never did figure out immortality. I did.",
      "shot_type": "narrator_with_characters",
      "narrator_expression": "slow, satisfied smile",
      "action_characters": [],
      "environment": "village_church",
      "duration_seconds": 6
    }
  ],
  "long_form_potential": {
    "suitable_for_deep_dive": true,
    "suggested_long_form_title": "The Complete History of Mother Miranda — The True Origin of Umbrella",
    "outline_bullets": [
      "Miranda's backstory: the loss of Eva and discovery of the Megamycete",
      "Spencer's visit and what he learned from Miranda",
      "How Miranda's Mold research became Umbrella's foundation",
      "The Four Lords: Miranda's failed experiments to resurrect Eva",
      "Miranda vs. Spencer — parallel paths of obsession"
    ],
    "estimated_long_form_duration_minutes": 15
  },
  "cross_platform": {
    "tiktok_caption": "Umbrella exists because of HER 😱 #residentevil #revillage #mothermiranda #gaming #fyp",
    "instagram_caption": "The secret origin of Umbrella Corporation... one woman, one village, one obsession. 🧬\n\n#ResidentEvil #MotherMiranda #Umbrella #GamingLore #DidYouKnow"
  }
}
```

---

## Step 5 — Voice Generation (Chatterbox / ElevenLabs)

**What it does:** Generates spoken audio for each scene's dialogue. Runs in PARALLEL with image generation.

**Module:** `backend/services/pipeline/voice_gen.py`

### Option A: Chatterbox (Local Docker — voice cloning)

For each scene, a POST request is sent to the local Chatterbox service:

```
POST http://localhost:8001/tts

{
  "text": "Did you know? The entire Umbrella Corporation — every virus, every outbreak, every monster — exists because of me.",
  "reference_audio": "assets/library/resident_evil_village/characters/mother_miranda/voice/reference.wav",
  "exaggeration": 0.3,
  "cfg_weight": 0.6
}
```

> **reference_audio**: A clean voice clip extracted from RE Village cutscenes (Miranda speaking). This is the voice the TTS clones.
>
> **exaggeration**: 0.3 = controlled, authoritative (Miranda speaks calmly, not expressively)
>
> **cfg_weight**: 0.6 = moderate adherence to reference voice

### Option B: ElevenLabs (Browser automation)

The app navigates to `https://elevenlabs.io/app/speech-synthesis`, selects the pre-configured voice, pastes the dialogue, generates, and downloads the MP3.

### Output

Per-scene audio files are generated and then concatenated:

```
data/output/resident_evil_village/{topic_id}/audio/
  scene_1_{timestamp}.wav
  scene_2_{timestamp}.wav
  scene_3_{timestamp}.wav
  scene_4_{timestamp}.wav
  scene_5_{timestamp}.wav
  scene_6_{timestamp}.wav
  full_voiceover.wav      ← all scenes concatenated
```

---

## Step 6 — Scene Image Generation (Google Flow)

**What it does:** For each scene in the script, generates a unique image using the character bibles + environment descriptions + previously approved reference images. Runs in PARALLEL with voice generation.

**Module:** `backend/services/pipeline/image_gen.py`

### Scene 1 Image Prompt (narrator_with_characters)

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Scene composition: main character facing camera in foreground, other characters
visible behind.

Main character expression: serene smile, slight head tilt, knowing eyes

Character: Female, dark hair concealed by hood, golden/yellow eyes. A priestess
wearing dark robes with a hooded cloak. Eyes glow golden. Action: facing camera
with serene authority.

Character: Elderly man with weathered face, heavy coat, walking cane. Action:
standing nervously behind, clutching his cane.

Setting: Ancient stone church interior with candles, religious murals, stone altar.

Vertical composition (9:16), cinematic lighting, high detail.
```

**Reference images uploaded to Google Flow alongside the prompt:**
1. `assets/library/resident_evil_village/characters/mother_miranda/portrait.png` (pre-approved face lock)
2. `assets/library/resident_evil_village/characters/village_elder/portrait.png`
3. `assets/library/resident_evil_village/environments/village_church/wide_shot.png`

### Scene 3 Image Prompt (narrator_alone)

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Close-up portrait, character facing camera directly.

Expression: eyes narrowing, mix of pride and resentment

Character: Female, dark hair concealed by hood, golden/yellow eyes. A priestess
wearing dark robes with a hooded cloak. Eyes glow golden. Action: speaking
directly to camera with intensity.

Setting: Underground bio-research lab, fungal growths, specimen jars, ritual markings.

Vertical composition (9:16), cinematic lighting, high detail.
```

**Reference images:**
1. `assets/library/resident_evil_village/characters/mother_miranda/narrator/front_facing.png`
2. `assets/library/resident_evil_village/environments/miranda_laboratory/wide_shot.png`

### Scene 4 Image Prompt (characters_only)

```
Style: cinematic horror, dark industrial environments, bio-organic mutations.
survival horror atmosphere, photorealistic, cinematic lighting, 9:16 vertical.

Action scene, characters performing actions.

Character: Elderly man with weathered face, heavy coat, walking cane. Action:
walking away from village into modern cityscape, briefcase in hand.

Setting: Snow-covered village square with stone houses, central well.

Vertical composition (9:16), cinematic lighting, high detail.
```

### Output

```
data/output/resident_evil_village/{topic_id}/images/
  scene_1.png
  scene_2.png
  scene_3.png
  scene_4.png
  scene_5.png
  scene_6.png
```

---

## Step 7 — Video Clip Generation (Kling AI)

**What it does:** Turns each static scene image into a ~5-second animated video clip. Narrator scenes get lip sync (mouth moves with audio). Action scenes get motion animation.

**Tool:** [Kling AI](https://klingai.com) (browser automation via `backend/browser/kling.py`)

**Module:** `backend/services/pipeline/video_gen.py`

### Narrator Scenes (lip sync mode)

For scenes 1, 3, 5, 6 (shot types `narrator_alone` or `narrator_with_characters`):

**Input to Kling:**
- **Image:** `scene_3.png` (Miranda facing camera)
- **Audio:** `scene_3_{timestamp}.wav` (Miranda's dialogue for that scene)
- **Mode:** Lip Sync

Kling takes the static image + the audio and generates a video where Miranda's mouth moves in sync with the spoken words, with subtle natural head movements.

**Motion prompt (added for naturalness):**
```
subtle head turn, natural blinking, slight expression change, gentle breathing motion
```

### Action Scenes (motion mode)

For scenes 2, 4 (shot type `characters_only`):

**Input to Kling:**
- **Image:** `scene_2.png` (Spencer arriving in village)
- **Audio:** None (voiceover is added later in assembly)
- **Mode:** Image-to-Video with motion prompt

**Motion prompt:**
```
character performing action, dynamic movement, cinematic camera pan
```

### Credit Cost

| Mode     | Credits per clip |
|----------|-----------------|
| Standard | 10              |
| Professional | 35          |

For a 6-scene video in Standard mode: **60 credits**.

### Output

```
data/output/resident_evil_village/{topic_id}/clips/
  scene_1.mp4   (lip sync — Miranda + village elder)
  scene_2.mp4   (motion — Spencer arriving)
  scene_3.mp4   (lip sync — Miranda close-up)
  scene_4.mp4   (motion — Spencer leaving)
  scene_5.mp4   (lip sync — Miranda close-up)
  scene_6.mp4   (lip sync — Miranda satisfied smile)
```

---

## Step 8 — Final Assembly (VectCutAPI / CapCut)

**What it does:** Combines all video clips + voiceover audio + background music + SFX + captions into a single final 9:16 vertical video.

**Tool:** VectCutAPI (local server at `http://localhost:9001`)

**Module:** `backend/services/pipeline/assembly.py`

### Assembly Payload

```json
{
  "project_settings": {
    "width": 1080,
    "height": 1920,
    "fps": 30
  },
  "render_mode": "cloud",
  "tracks": [
    {
      "type": "video",
      "clips": [
        {
          "file_path": "data/output/.../clips/scene_1.mp4",
          "start_time": 0,
          "duration": 6,
          "transition": "fade_in",
          "keyframes": { "zoom": "slow_push_in" }
        },
        {
          "file_path": "data/output/.../clips/scene_2.mp4",
          "start_time": 6,
          "duration": 10,
          "transition": "cross_dissolve"
        },
        {
          "file_path": "data/output/.../clips/scene_3.mp4",
          "start_time": 16,
          "duration": 9,
          "transition": "fade_in"
        },
        {
          "file_path": "data/output/.../clips/scene_4.mp4",
          "start_time": 25,
          "duration": 8,
          "transition": "cross_dissolve"
        },
        {
          "file_path": "data/output/.../clips/scene_5.mp4",
          "start_time": 33,
          "duration": 10,
          "transition": "fade_in"
        },
        {
          "file_path": "data/output/.../clips/scene_6.mp4",
          "start_time": 43,
          "duration": 6,
          "transition": "fade_in"
        }
      ]
    },
    {
      "type": "audio",
      "label": "voiceover",
      "clips": [
        { "file_path": ".../audio/scene_1.wav", "start_time": 0, "duration": 6, "volume": 1.0 },
        { "file_path": ".../audio/scene_2.wav", "start_time": 6, "duration": 10, "volume": 1.0 },
        { "file_path": ".../audio/scene_3.wav", "start_time": 16, "duration": 9, "volume": 1.0 },
        { "file_path": ".../audio/scene_4.wav", "start_time": 25, "duration": 8, "volume": 1.0 },
        { "file_path": ".../audio/scene_5.wav", "start_time": 33, "duration": 10, "volume": 1.0 },
        { "file_path": ".../audio/scene_6.wav", "start_time": 43, "duration": 6, "volume": 1.0 }
      ]
    },
    {
      "type": "audio",
      "label": "music",
      "clips": [
        {
          "file_path": "data/audio/music/dark_cinematic/track_07.mp3",
          "start_time": 0,
          "duration": 49,
          "volume": 0.08,
          "fade_in": 1.0,
          "fade_out": 2.0
        }
      ]
    },
    {
      "type": "audio",
      "label": "sfx",
      "clips": [
        { "file_path": "data/audio/sfx/impacts/deep_boom.wav", "start_time": 0, "duration": 1.0, "volume": 0.3 },
        { "file_path": "data/audio/sfx/transitions/whoosh_01.wav", "start_time": 5.7, "duration": 0.8, "volume": 0.2 },
        { "file_path": "data/audio/sfx/transitions/whoosh_02.wav", "start_time": 15.7, "duration": 0.8, "volume": 0.2 }
      ]
    },
    {
      "type": "caption",
      "label": "captions",
      "clips": [
        {
          "type": "caption",
          "start_time": 0,
          "duration": 6,
          "word_timestamps": [
            { "word": "Did", "start": 0.0, "end": 0.2 },
            { "word": "you", "start": 0.2, "end": 0.35 },
            { "word": "know?", "start": 0.35, "end": 0.7 }
          ],
          "style": { "font": "Bebas Neue", "color": "#FFFFFF", "stroke": "#000000" }
        }
      ]
    }
  ]
}
```

### Final Output

```
data/output/resident_evil_village/{topic_id}/
  final_video.mp4         ← 1080x1920, 30fps, ~49 seconds
```

This video is then passed to the Quality Gate (Step 7 in the orchestrator) and if it passes, published to YouTube, TikTok, Instagram, and Facebook.

---

## Quick Reference: Tools Used Per Step

| Step | Tool | Access Method |
|------|------|---------------|
| Character Bible | Local Python | `bible_generator.py` |
| Character Images | Google Flow | Browser automation |
| Environment Images | Google Flow | Browser automation |
| Script | Gemini | Browser automation |
| Voice | Chatterbox (local Docker) or ElevenLabs (browser) | REST API / Browser |
| Scene Images | Google Flow | Browser automation |
| Video Clips | Kling AI | Browser automation |
| Assembly | VectCutAPI | REST API (`localhost:9001`) |
| Publishing | YouTube API + Playwright | API + Browser |

---

## How to Run This Manually (Step by Step)

If you want to test the pipeline manually for the Mother Miranda / Umbrella fact:

1. **Onboard the franchise**: Search "Resident Evil Village" → select → discover characters → select Miranda, Dimitrescu, Ethan, etc. → save
2. **Generate character bibles**: Happens automatically during save, or call `/api/onboarding/generate-bible` manually
3. **Create reference images**: Open Google Flow → paste the character portrait prompt (Step 2) → upload reference screenshots → download and save to `assets/library/`
4. **Create environment images**: Same process with environment prompts (Step 3)
5. **Discover topics**: Go to Discover page → run discovery → queue the Umbrella fact topic
6. **Generate script**: Copy the full prompt from Step 4 → paste into Gemini → get the JSON script
7. **Generate voice**: Use Chatterbox or ElevenLabs with each scene's dialogue
8. **Generate scene images**: For each scene, paste the prompt from Step 6 into Google Flow with reference images
9. **Generate video clips**: Upload each scene image to Kling AI with the matching audio (for narrator scenes) or motion prompt (for action scenes)
10. **Assemble**: Load all clips into CapCut or send to VectCutAPI → add music, SFX, captions → export
