# Image Quality Guide — Matching the Reference

## The Goal
Our images should look like **a real person in cosplay, photographed on a professional set** —
NOT like a video game character rendered realistically.

## Quality Pillars

### 1. Photographic Realism (not CG realism)
The reference looks like photography. Use these keywords in EVERY prompt:
```
photograph, shot on Canon EOS R5, 85mm portrait lens, f/1.8 aperture,
shallow depth of field, natural skin texture with visible pores,
photographic realism, DSLR quality
```

### 2. Face Lighting
Even in dark horror environments, the face always has flattering light.
Always include:
```
soft fill light on face, subtle catch-lights in eyes, natural skin tones,
warm undertones on skin even in cold environments
```

### 3. Skin Quality
The reference has REAL skin — not smooth CG skin. Include:
```
realistic skin texture, visible pores, subtle freckles, natural
complexion with slight color variation, no airbrushing, no CGI
smoothing, skin imperfections
```

### 4. "Cosplay Photography" Feel
We want the character to look like a real human dressed as the character:
```
real person cosplay photography, practical costume, real fabric
textures, visible stitching on clothing, real leather, real cloth
```

### 5. Expression Variety
Never use neutral expressions. Each scene gets a STRONG emotion:
- Angry, disgusted, scared, determined, shocked, sad, suspicious, defiant
- Include specific micro-expressions: "brow furrowed", "jaw clenched",
  "eyes wide", "lip curled", "nostrils flared"

### 6. Camera Angle Variety
Change the camera angle EVERY scene:
- Selfie angle (slightly below, close)
- High angle looking down
- Low angle looking up (makes character powerful)
- Eye level direct
- Over-shoulder
- Dutch angle (slight tilt for tension)

---

## Master Prompt Template

```
[CAMERA] [LENS]

[CHARACTER DESCRIPTION — from approved bible]

[EXPRESSION — strong, specific emotion with micro-expression details]

[ENVIRONMENT — detailed, contextual to the story beat]

[LIGHTING — always include face fill light]

Photographic realism, real person cosplay photography, natural skin
texture with visible pores, real fabric textures, DSLR quality,
shallow depth of field. 9:16 vertical composition.
```

---

## Tool Recommendations

### Google Flow (Nano Banana Pro)
- What we've been using
- Good quality, free, accepts reference images
- Photographic prompts significantly improve output
- May have a ceiling for "real person" quality

### Midjourney (test this)
- Arguably the best for photorealistic human portraits
- --cref flag for character consistency across scenes
- Free trial available
- Could be the tool the reference creator is using

### Flux Pro (test this)
- Very strong at photorealistic faces
- Available via free tiers on Replicate, fal.ai, etc.
- IP-Adapter support for face consistency

### Face Swap Approach (if needed)
- Generate scene with a generic character → swap in your approved face
- Tools: InsightFace, ReActor (open source, need GPU) or paid alternatives
- This may be what the reference creator is doing for perfect consistency

---

## Iteration Strategy

1. Generate same scene with same prompt across Google Flow, Midjourney, and Flux
2. Compare results side by side
3. Pick the tool that gets closest to reference quality
4. Refine prompts on that tool until we hit 95%
5. Document the winning prompt template for all future use

---

## Quality Checklist (score each image)

- [ ] Does it look like a PHOTOGRAPH of a real person? (not a render)
- [ ] Is the skin realistic? (pores, texture, natural tones)
- [ ] Is the face well-lit even if the environment is dark?
- [ ] Is the expression strong and specific? (not neutral)
- [ ] Does the costume look like real fabric? (not painted on)
- [ ] Is the environment detailed and contextual?
- [ ] Is the depth of field natural? (sharp face, softer background)
- [ ] Would this pass as a cosplay photo on Instagram?
