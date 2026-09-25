# Refaire l'essai collage — sur ComfyUI, avec un GPU

Les trois images de ce dossier viennent de deux moteurs différents. Voici
exactement ce qui a produit chacune, pour qu'on puisse les comparer à ce
que sort une autre machine.

| Image | Moteur | Prompt |
|---|---|---|
| `A-avec-regle.jpg` | `gemini-3.1-flash-image`, à la main | long, 5 blocs, avec règle de lettrage |
| `B-temoin.jpg` | idem | long, formulation `vox-director` |
| `C-sdxl-local.jpg` | SDXL base 1.0, CPU, ce conteneur | **court**, 75 tokens |

## Comment l'essai SDXL a été fait

Pas sur ta machine : dans le conteneur cloud de la session, **sans GPU**,
4 cœurs, 15 Go de RAM. `diffusers` en Python, pas ComfyUI.

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install diffusers transformers accelerate safetensors
```

```python
import torch
from diffusers import StableDiffusionXLPipeline

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    dtype=torch.bfloat16, variant="fp16", use_safetensors=True,
).to("cpu")
pipe.enable_attention_slicing()

image = pipe(
    prompt=PROMPT, negative_prompt=NEGATIF,
    width=1024, height=576, num_inference_steps=24,
    guidance_scale=6.5, generator=torch.Generator("cpu").manual_seed(7),
).images[0]
```

110 secondes pour l'image finale. Deux pièges rencontrés, à ne pas refaire :

- **`float32` ne tient pas dans 15 Go** — SDXL pèse alors ~13 Go de poids,
  le chargement part en thrashing et le processus est tué. `bfloat16`
  charge en 15 s. Sur un GPU de 16 Go, `float16` est le bon choix.
- **En dessous de 1024 sur le grand côté**, SDXL produit un motif répété en
  damier. C'est sa signature d'échec hors résolution d'entraînement.

## Le prompt exact de `C-sdxl-local.jpg`

**Positif** (75 tokens — volontairement sous la limite CLIP de 77) :

```
hand-cut paper collage, torn scissor-cut edges, tape corners, halftone dots,
aged newsprint, paper drop shadows, cut-out stack of legal documents, a
judge's gavel, cut-out paper arrows, geometric paper scraps, flat deep
oxblood red background, cream mustard charcoal, editorial zine, flat
scanned, not 3d
```

**Négatif** :

```
3d render, cgi, photorealistic, smooth digital painting, glossy, text,
letters, words, watermark, signature, blurry
```

**Réglages** : 1024 × 576 · 24 étapes · CFG 6,5 · graine 7 · échantillonneur
par défaut de `diffusers` (Euler discret).

> Note : SDXL accepte les prompts négatifs. FLUX **non** — il n'a pas de
> guidage négatif au sens classique. Sur FLUX, tout doit être formulé
> positivement.

## Ce qu'il faut vraiment tester sur la 7800 XT

Reproduire SDXL n'a qu'un intérêt de contrôle. Le résultat mesuré ici est
que **SDXL ne peut pas recevoir notre prompt** : il fait 235 tokens et
CLIP en accepte 77. Le modèle n'a vu que le bloc de style, et la scène a
été jetée en silence.

Le vrai essai est donc **FLUX.1-dev ou Qwen-Image**, qui utilisent T5 et
encaissent ~512 tokens. Sur 16 Go de VRAM, les deux passent en quantifié.

Prompt long, en cinq blocs — le même que `A-avec-regle.jpg`, moins la
consigne de titre puisque le titre sera composé dans Remotion :

```
Mixed-media hand-cut PAPER COLLAGE, editorial zine style, in the visual
idiom of a mid-century front-page news feature. Torn and scissor-cut paper
edges, tape corners, halftone print dots, paper-stencil shapes, aged
newsprint texture, slight print misregistration, real paper drop shadows.
Figures and objects are PRINTED, illustrated cut-outs — engraved or
woodblock printed texture — NOT CGI, NOT a 3D render, NOT photoreal; keep
print grain and paper imperfections. Flat even scanned-document light,
straight-on head-on framing. High-contrast, sober, editorial.

SCENE as clearly layered paper cut-outs, each piece with its own visible
edge and drop shadow, at distinct depths: a tall stack of legal papers
seen from the side, a single sheet lifted out of the stack and tilted
forward as the hero piece, a judge's gavel resting flat, a small torn
calendar fragment, a pair of scissors-cut arrows pointing down at the
lifted sheet, scattered geometric paper accents — triangles, circles,
zigzags — and two strips of washi tape.

On a bold flat deep oxblood-red paper background. A wide empty band of
plain oxblood paper across the upper third, clear of any object, reserved
for a headline that will be composited later.

LETTERING RULE: every paper scrap, document, clipping and label is TEXTURE
ONLY — abstract grey ruled lines, ink bars, halftone blocks and blurred
unreadable type. No words, no letters, no numbers, no signatures. Do not
invent newspaper text.

Palette limited to aged cream, deep oxblood red, mustard and charcoal.
16:9, 2k resolution.
```

**Réglages suggérés** : 1344 × 768 · FLUX.1-dev 20–28 étapes, guidance 3,5
(schnell : 4 étapes, guidance 0) · graine fixe pour comparer.

### Ce qu'on regarde dans le résultat

1. **Du papier, ou une illustration lissée ?** C'est ce que `NOT 3D / NOT
   CGI / keep grain` est censé tenir.
2. **Les pièces ont-elles des bords nets et des ombres portées distinctes ?**
   C'est ce qui rendra la parallaxe possible ensuite.
3. **La bande vide du tiers supérieur est-elle respectée ?** Si oui, le
   titre se compose par-dessus et on gagne des accents corrects, une
   typographie pilotée par le template, et un titre animable.
4. **Reste-t-il du faux texte ?** C'est la règle qui protège à la fois
   l'honnêteté documentaire et la direction artistique — mesuré sur
   `B-temoin.jpg`, sans elle le modèle bascule vers la photo de bureau.

## ComfyUI sur une Radeon RX 7800 XT

Attention à la marque : c'est une **Radeon**, donc **ROCm**, pas CUDA.
16 Go de VRAM, RDNA 3 — largement au-dessus du seuil pour FLUX quantifié.

- **Linux** : ROCm est officiellement supporté sur RDNA 3. Installer
  `torch` ROCm, puis ComfyUI normalement.
- **Windows** : plus bricolé — HIP SDK, ou une version de ComfyUI empaquetée
  pour AMD. Compter une soirée plutôt qu'une heure.

Ces indications viennent de la documentation publique, pas d'un essai :
cette session n'a pas de GPU et n'a rien pu vérifier de ce côté.
