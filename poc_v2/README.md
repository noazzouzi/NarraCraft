# Proof of Concept V2 — Simplified Pipeline

## Approach: Static Scene Images + Lip-Sync + Ken Burns
Based on analysis of a successful Instagram reference (@linanerdyfacts).

## Key Learnings from Reference
- NO full body animation needed — static images with lip-sync + camera movement
- More scenes with quick cuts (8+) > fewer scenes with complex animation
- "Cosplay photography" aesthetic > "game cinematic" aesthetic
- Portrait-quality face lighting in every scene regardless of environment
- Camera angle variety across scenes keeps it dynamic
- Dramatic facial expressions, not neutral

## Pipeline (Simplified)
1. **Script** — Gemini (free) → 8-10 short scenes with quick cuts
2. **Scene Images** — Google Flow / Midjourney → one composed image per scene
3. **Voice** — ElevenLabs → one audio file per scene
4. **Lip-Sync** — Hedra / Kling → animate narrator face only
5. **Assembly** — CapCut → Ken Burns motion on images + lip-sync clips + captions + music

## Cost Reduction vs V1
- No Hailuo credits needed (no full body motion)
- Lip-sync only on narrator close-up scenes (not every scene)
- More scenes but cheaper per scene (most are static images in CapCut)

## Files
| File | Purpose |
|------|---------|
| `01_image_quality_guide.md` | How to achieve reference-level image quality |
| `02_script.md` | Updated script — 8 scenes, quick cuts |
| `03_scene_prompts.md` | Scene image prompts (photographic style) |
| `04_voice_guide.md` | ElevenLabs voice direction |
| `05_lipsync_guide.md` | Lip-sync workflow (Hedra / Kling) |
| `06_assembly_guide.md` | CapCut assembly with Ken Burns + captions |
| `07_iteration_log.md` | Track prompt iterations toward 95% quality match |
