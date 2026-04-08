# Proof of Concept — Resident Evil / Wesker Lore

## Franchise: Resident Evil
## Narrator: Jill Valentine
## Topic: Wesker was engineered — Project W

---

## Step-by-Step Workflow

### Step 1: Character Images (Google Flow) — ONE TIME
Use the prompts in `01_character_image_prompts.md`
→ Generate individual character portraits → Approve and save
✅ DONE — Jill and Wesker generated

### Step 2: Script
Already written in `02_script.md`
→ Review and tweak if needed

### Step 3: Scene Images (Google Flow) — NEW STEP
Use the prompts in `02b_scene_image_prompts.md`
→ Upload approved character refs + scene prompt → Generate one composed image per scene
→ 5 scene images total

### Step 4: Voice (ElevenLabs)
Use the voice direction in `03_voice_prompts.md`
→ Generate audio per scene → Download as scene_01.mp3, scene_02.mp3, etc.

### Step 5: Animation (Kling AI / Hedra)
Use the guide in `04_animation_prompts.md`
→ Lip-sync scenes (1, 3, 5): Upload scene image + audio → Kling lip-sync
→ Voiceover scenes (2, 4): Use static image with Ken Burns effect in CapCut

### Step 6: Assembly (CapCut)
Follow the notes in `05_assembly_notes.md`
→ Combine animated clips + static scenes + audio + text → Export

---

## Files

| File | Purpose |
|------|---------|
| `01_character_image_prompts.md` | One-time character generation prompts (Google Flow) |
| `02_script.md` | Full 5-scene script + upload metadata |
| `02b_scene_image_prompts.md` | Scene composition prompts — one image per scene (Google Flow) |
| `03_voice_prompts.md` | ElevenLabs voice direction per scene |
| `04_animation_prompts.md` | Kling AI / Hedra lip-sync guide + motion tips |
| `05_assembly_notes.md` | CapCut timeline, text, music, export settings |
