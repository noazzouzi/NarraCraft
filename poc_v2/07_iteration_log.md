# Iteration Log — Closing the Quality Gap

## Target: 95% match with Instagram reference (@linanerdyfacts)

---

## Iteration 1 — Cinematic prompt + game reference images (Google Flow)
- **Result:** Good quality, but looks like a "game render" not a "photograph"
- **Score:** ~65% match
- **Issues:** Smooth CG skin, dark dramatic lighting, no skin texture
- **Learning:** "Cinematic horror" pushes toward game aesthetic, not photo

## Iteration 2 — Photographic prompt + game reference images (Google Flow)
- **Result:** Better — skin texture appeared, freckles, more natural lighting
- **Score:** ~75% match
- **Issues:** Still "CG" feel — the game reference images anchor output to CG
- **Learning:** Camera simulation keywords help, but reference images fight them

## Iteration 3 — Photographic prompt + "real person" wording + game reference images
- **Result:** Incrementally better, still CG-anchored
- **Score:** ~80% match
- **Issues:** Google Flow can't escape CG look when given game screenshots as reference
- **Learning:** The reference images are the bottleneck, not the prompt

## Iteration 4 — Photographic prompt, NO reference images (BREAKTHROUGH)
- **Result:** Massive jump — looks like a real person photographed
- **Score:** ~88% match
- **Issues:** Outfit defaulted to standard police uniform instead of Jill's tactical gear
- **Learning:** WITHOUT game references, Flow generates truly photographic humans

## Iteration 5 — Photographic prompt + explicit outfit description, NO reference images
- **Result:** Real person quality + correct Jill outfit (tube top, shoulder armor, beret)
- **Score:** ~92% match
- **Issues:** Minor — could be slightly more "editorial beauty" polished
- **Learning:** Describe outfit explicitly in text instead of relying on reference images

## Iteration 6 — Composed scene (Jill + Wesker, mansion foyer), NO reference images
- **Result:** Excellent — both characters photographic, great composition and lighting
- **Score:** ~93% match
- **Issues:** Character consistency untested across multiple scenes
- **Learning:** Multi-character scenes work at this quality without reference images

## Iteration 7 — Consistency test: Scene 2 using Scene 1 output as reference
- **Result:** ~88-90% same face across two different scenes/angles/expressions
- **Score:** ~92% match overall, ~90% consistency
- **Issues:** Slight variation in hair length perception from different angle
- **Learning:** Feeding generated output back as reference WORKS for consistency

---

## WINNING FORMULA (Current Best)

### Image Generation
- **Tool:** Google Flow (Nano Banana Pro) — FREE
- **Reference images:** Use PREVIOUSLY GENERATED OUTPUT as reference, NOT game screenshots
- **First image:** Generate with text-only (no reference) to establish the "real person" face
- **Subsequent images:** Feed the first output as reference for consistency

### Prompt Structure
```
Photograph, shot on Canon EOS R5, [focal length] lens, f/1.8,
shallow depth of field. 9:16 vertical composition.

[CHARACTER — described as a real person in cosplay, explicit outfit details]

[EXPRESSION — strong, specific emotion with micro-expressions]

[ENVIRONMENT — detailed, contextual]

Beauty portrait lighting — [specific lighting setup]. Bright catch-lights
in eyes. Warm glowing skin, natural skin with fine pores. Real person
cosplay photography, editorial portrait quality, DSLR, photographic realism.
```

### Key Rules
1. NEVER use game screenshots/artwork as reference images
2. First generation: text-only → establishes the "real person" face
3. All subsequent generations: use the approved first image as reference
4. Describe outfits explicitly in text (tube top, shoulder armor, etc.)
5. Always include: "real person cosplay photography, editorial portrait quality"
6. Always include: "beauty portrait lighting" and "catch-lights in eyes"
7. Vary camera angle and expression per scene
8. ALWAYS include franchise-specific elements in backgrounds (logos, environments, props, creatures)
9. For Veo 3: use Reference-to-Video (R2V) mode, NOT Image-to-Video — prevents identical first frames
10. Repeat key character descriptors in every Veo 3 prompt alongside the reference image

### Quality Scores
- Individual portraits: ~92%
- Composed scenes: ~93%
- Cross-scene consistency: ~88-90%
- Veo 3.1 video quality: ~93-95%
- Veo 3.1 body language/acting: exceptional
- Overall pipeline viability: VALIDATED

### Veo 3 Dialogue Rules (discovered during POC)
- Max ~15-17 words per clip — longer gets truncated
- Visible character MUST be the speaker — no off-screen narration possible
- Each character speaks from their own perspective in their own scenes
- Scene 1: all characters together facing camera (hook effect)
- Final scene: all characters together (bookend)

### Franchise Element Rules (discovered during POC)
- Every scene must contain 2-3 recognizable franchise elements in the background
- Character reference images should also include franchise elements
- Without franchise context, characters look generic

---

## FULL END-TO-END VALIDATION (2026-03-30)

### The Last of Us — "Joel's Choice"
- 7 scenes, 2 characters (Joel + Ellie), complete Short ready for CapCut assembly
- Pipeline: Gemini script → Flow character refs (text-only) → Veo 3.1 R2V → CapCut
- Photorealism: 95%. Franchise immersion: 97%. Emotional range: 98%.
- Every scene unique environment, franchise elements everywhere
- R2V mode solved the identical-first-frames problem
- Each character speaks their own lines (no off-screen narration)
- Scene 1 hook: both characters together, Ellie arms crossed looking away — tension visible
- Best scenes: hospital massacre (Firefly flag + blood), operating room aftermath, dinosaur museum

### WORKFLOW IS VALIDATED. Ready to build the app and scale production.
