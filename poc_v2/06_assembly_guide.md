# Assembly Guide — CapCut Pro

## Project Settings
- **Aspect ratio:** 9:16 (vertical)
- **Resolution:** 1080x1920
- **Frame rate:** 30fps
- **Target duration:** 50-55 seconds

---

## The Two Types of Scenes

### Type A: Static Image + Ken Burns (Scenes 1, 3, 5, 7)
1. Import scene image onto the video track
2. Set duration to match the voiceover audio length
3. Apply Ken Burns effect:
   - Slow zoom IN (start at 100%, end at 110-115%)
   - OR slow PAN across the image
   - Different movement per scene to keep it varied
4. Place voiceover audio on the audio track
5. No lip-sync — Jill's voice plays over the scene image

### Type B: Lip-Sync Video (Scenes 2, 4, 6, 8)
1. Import the lip-sync video file (from Hedra/Kling/D-ID)
2. Trim to match audio length exactly
3. Audio is already baked into the lip-sync video — but double check sync
4. Optionally add subtle zoom (102-105%) for consistency with Type A scenes

---

## Timeline

```
TIME    0s ----- 5s ----- 11s ---- 17s ---- 22s ---- 28s ---- 34s ---- 40s ---- 46s
SCENE   | Sc.1  | Sc.2   | Sc.3   | Sc.4  | Sc.5   | Sc.6   | Sc.7   | Sc.8   |
TYPE    | Static| LIPSYNC| Static | LIPSYNC| Static| LIPSYNC| Static | LIPSYNC|
MOTION  | Zoom  | Video  | Pan R  | Video | Zoom  | Video  | Pan L  | Video  |
AUDIO   | v_01  | v_02   | v_03   | v_04  | v_05  | v_06   | v_07   | v_08   |
```

---

## Transitions

- **Between scenes:** Hard cut or very fast cross-dissolve (0.2-0.3 seconds max)
- **The reference uses mostly hard cuts** — this keeps the pacing snappy
- First scene: fade from black (0.5s)
- Last scene: fade to black (1s)
- Do NOT use fancy transitions (wipes, spins, etc.) — keep it cinematic

---

## Text / Captions

The reference video uses **burned-in captions** (not YouTube auto-captions).

**Style:**
- Font: Bold sans-serif (Montserrat Bold, Impact, or CapCut's built-in bold)
- Color: White
- Outline/stroke: Black, 2-3px (for readability on any background)
- Shadow: subtle drop shadow
- Position: Lower third of screen (centered horizontally)
- Size: Large enough to read on a phone

**How to add:**
- CapCut has auto-caption generation — use it, then manually clean up any errors
- Or manually add text per scene matching the voice script
- Captions should appear word-by-word or phrase-by-phrase, synced to voice

---

## Background Music

- **Type:** Low, ominous ambient drone — horror/suspense
- **Volume:** 10-15% (barely audible under the voice)
- **Where to find:** CapCut's built-in music library → search "dark ambient", "horror", "suspense", "cinematic tension"
- **One continuous track** under the whole video (no music changes between scenes)
- **Fade out** music in the last 2 seconds

---

## Sound Effects (subtle, optional)

| Scene | Effect | Volume |
|-------|--------|--------|
| Scene 1 | Low bass hit on "never really one of us" | 20% |
| Scene 3 | Faint lab equipment beeping, syringe sound | 15% |
| Scene 5 | Fire crackling, distant explosion | 15% |
| Scene 7 | Wind / volcanic rumble | 15% |
| Scene 8 | Deep bass drop on "built to be one" | 25% |

---

## Ken Burns Variations (keep it varied)

| Scene | Movement |
|-------|----------|
| Scene 1 | Slow zoom in toward Jill's face (100% → 112%) |
| Scene 3 | Slow pan right, revealing the scientists (centering shifts) |
| Scene 5 | Slow zoom in on Wesker's cracked sunglasses (100% → 115%) |
| Scene 7 | Slow push in toward Wesker over Chris's shoulder (100% → 110%) |

---

## Export Settings

- **Format:** MP4
- **Resolution:** 1080x1920
- **Frame rate:** 30fps
- **Quality:** High / Best
- **File name:** `RE_wesker_project_w_v2_final.mp4`

---

## Final Checklist

- [ ] Total duration 50-60 seconds?
- [ ] Voice is clear and dominant over music?
- [ ] Lip-sync scenes look natural?
- [ ] Ken Burns motion is smooth (no jerky movement)?
- [ ] Captions are readable on a phone screen?
- [ ] Transitions are snappy (hard cuts or very fast dissolves)?
- [ ] No AI watermarks visible? (crop or overlay if needed)
- [ ] Music fades out at the end?
- [ ] Opening grabs attention in first 2 seconds?
- [ ] Final line hits hard?
