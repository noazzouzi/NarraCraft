# Animation Guide — Lip-Sync & Motion

## Tool Options (pick one to test)

| Tool | What it does | Free tier | Best for |
|------|-------------|-----------|----------|
| **Kling AI** (klingai.com) | Image + audio → lip-sync video | Yes, limited daily credits | High quality, flexible settings |
| **Hedra** (hedra.com) | Image + audio → talking head video | Yes, short clips | Simplest workflow, purpose-built for this |
| **D-ID** (d-id.com) | Image + audio → talking avatar | Trial credits | Polished, reliable |

**Recommendation:** Start with **Kling AI** or **Hedra** — both have free tiers and are built for exactly this.

---

## Step-by-Step: Kling AI Lip-Sync

### First Time Setup
1. Go to **klingai.com**
2. Sign up with Google or email
3. You get free daily credits (~66 credits for new users)

### For Each NARRATOR Scene (Scenes 1, 3, 5 — where Jill speaks to camera)

1. Go to **"Lip Sync"** feature (under AI Tools or main menu)
2. **Upload image:** Your generated scene image (e.g., `scene_01.png` — the composed scene with Jill + Wesker)
3. **Upload audio:** The voice clip for that scene (e.g., `scene_01.mp3` from ElevenLabs)
4. **Settings:**
   - Aspect ratio: **9:16** (vertical)
   - Quality: **Professional** if available (uses more credits but much better)
   - Duration: **match audio length**
5. Click **Generate** — wait 2-10 minutes
6. **Preview** the result — check:
   - Does Jill's mouth sync to the audio?
   - Does the image look stable (no weird warping)?
   - Does Wesker in the background stay still or have subtle motion?
7. **Download** if it looks good, **regenerate** if not
8. Save as: `scene_01_animated.mp4`

### For Each NON-NARRATOR Scene (Scenes 2, 4 — voiceover only, no lip-sync)

These scenes have Jill's voice playing OVER the image, but no one is speaking on screen. You have two options:

**Option A — Animate with motion only (no lip-sync)**
1. Go to **"Image to Video"** (NOT lip-sync)
2. Upload your scene image (e.g., `scene_04.png` — Wesker in destroyed lab)
3. Add a motion prompt:
```
Subtle camera push-in. Fire flickering in background. Smoke and dust
particles drifting. Character standing still with minimal breathing
motion. Cinematic, slow, dramatic. 9:16 vertical.
```
4. Set duration: **5-10 seconds**
5. Generate and download

**Option B — Use the static image with Ken Burns effect in CapCut**
1. Skip AI animation entirely for this scene
2. In CapCut, use a slow zoom-in or pan on the static scene image
3. This is simpler, free, and often looks just as good for non-speaking scenes

**My recommendation:** Use **Option B** for non-narrator scenes. Save your Kling credits for the lip-sync scenes where AI animation actually matters.

---

## Step-by-Step: Hedra (Alternative)

If Kling doesn't work well or you run out of credits:

1. Go to **hedra.com**
2. Sign up
3. Click **"Create"**
4. **Upload portrait image** — works best with a face-focused image
5. **Upload audio file** (MP3 or WAV)
6. Click **Generate**
7. Download the result

**Hedra limitation:** It works best with single-face close-ups. For composed scenes (Jill + Wesker), Kling is likely better since Hedra may only animate one face.

---

## Scene-by-Scene Animation Plan

| Scene | Type | Animation Method | What to Upload |
|-------|------|-----------------|----------------|
| Scene 1 | Narrator + characters | **Kling Lip-Sync** | scene_01.png + scene_01.mp3 |
| Scene 2 | Characters only (voiceover) | **CapCut Ken Burns** (or Kling Image-to-Video) | scene_02.png (static) |
| Scene 3 | Narrator alone | **Kling Lip-Sync** | scene_03.png + scene_03.mp3 |
| Scene 4 | Characters only (voiceover) | **CapCut Ken Burns** (or Kling Image-to-Video) | scene_04.png (static) |
| Scene 5 | Narrator + characters | **Kling Lip-Sync** | scene_05.png + scene_05.mp3 |

**Total Kling generations needed: 3** (only the lip-sync scenes)
**The other 2 scenes: handled in CapCut for free**

---

## Tips for Best Lip-Sync Results

1. **Face must be clearly visible** — no obstructions on mouth/jaw
2. **Front-facing or slight 3/4 angle** — extreme angles fail
3. **Neutral or slightly open mouth** in the source image works best
4. **Clean audio** — no background music or noise in the voice file
5. **Keep clips short** — 5-10 seconds per clip. Longer = more chance of artifacts
6. **If the result is bad:** try regenerating (results vary) or try a slightly different source image crop
7. **Professional mode > Standard** — worth the extra credits for quality

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Mouth doesn't sync | Try a different source image with more visible mouth/jaw |
| Face warps or distorts | Use a higher resolution image, try Professional mode |
| Background characters move weirdly | Crop to focus more on the narrator face, composite background separately in CapCut |
| Credits ran out | Switch to Hedra for the remaining clips, or wait for daily credit refresh |
| Result is too short | Kling may cap free tier duration — split long audio into shorter chunks if needed |
