# Prompt v2 — ce qu'il corrige, et comment mesurer

La v1 a tranché la question qui bloquait : un modèle à encodeur T5 reçoit
notre prompt en cinq blocs, là où SDXL en jetait les deux tiers. Restaient
deux échecs mesurés sur le résultat Qwen (`D-qwen-local.jpg`) :

| Échec | Mesure | Correctif v2 |
|---|---|---|
| Faux texte inventé | « LEOMKIVFAS », « QJIVI » | **aucun caractère autorisé**, au lieu de « texte illisible » |
| Matière vectorielle | saturation 187/255 contre 95 | **procédé d'impression nommé**, placé en tête |
| Scène posée sur une table en perspective | ombre portée au sol | **à plat, caméra perpendiculaire** |
| Bande du titre occupée | écart-type 72 | bande décrite **en premier**, en pourcentage |

## Les trois corrections, et pourquoi

**1. Zéro caractère, pas « du texte illisible ».**

La v1 demandait des scraps en « blurred unreadable type ». Pour un modèle
de diffusion, du texte flou reste du texte : il en dessine, et il le dessine
mal. La v2 n'autorise aucun glyphe nulle part, et décrit à la place ce qui
doit occuper la place — des filets, des pavés d'encre, des trames.

Le titre ne fait plus partie du prompt. Il sera **composé dans Remotion**,
ce qui règle trois choses d'un coup : les accents français sont fiables, la
typographie vient du template, et le titre devient animable — un surligneur
peut le balayer au moment où la voix le dit, ce qu'un titre cuit dans un
pixel ne permettra jamais.

**2. Un procédé nommé, pas des adjectifs.**

« halftone print dots », « print grain », « aged newsprint texture » sont des
adjectifs que le modèle pondère faiblement. **« Risograph print »** et
**« letterpress »** sont des styles qu'il connaît comme tels, avec leur
grain, leur mauvais repérage de couches et leur palette limitée. Et ils
passent en tête : sur la plupart des modèles, le début du prompt pèse plus
lourd.

**3. À plat, sans table.**

Le résultat Qwen posait la scène sur un plan de travail avec une ombre au
sol et une fuite perspective. La v1 disait « flat even scanned-document
light, straight-on head-on framing » — trop indirect. La v2 interdit
nommément la table, le sol et l'ombre portée au sol, et demande une vue du
dessus.

---

## v2 — version longue (modèles à encodeur T5 : Qwen-Image, FLUX)

```
Risograph-printed paper collage, flat lay, photographed straight down from
directly overhead. Two-colour riso print on cream paper: deep oxblood red
and charcoal ink, visible halftone dot screen, slight ink misregistration,
paper fibre and print grain. Flat even light, no perspective, no vanishing
point, no table, no floor, no cast shadow on any surface — the paper IS the
whole frame.

The top third of the frame is empty cream paper, completely clear: no
object, no scrap, nothing crosses into it.

In the lower two thirds, hand-cut paper shapes layered at distinct depths,
each with a visible torn or scissor-cut edge and its own small soft paper
drop shadow: a tall stack of documents seen edge-on, one single sheet
lifted out of the stack and tilted forward as the main shape, a judge's
gavel, a small torn calendar square, two cut-paper arrows pointing down at
the lifted sheet, scattered geometric paper accents — triangles, circles,
zigzags — and two strips of tape.

ABSOLUTELY NO TEXT: no letters, no words, no numbers, no glyphs, no
handwriting, no signature, no logo, no watermark anywhere in the image. The
documents and scraps carry only abstract printed marks — thin horizontal
grey rules, solid ink bars, halftone blocks, blank cream areas. Nothing in
this image is readable.

Palette strictly limited to cream, deep oxblood red and charcoal.
```

**Négatif** (SDXL, Qwen, Seedance — **pas** FLUX, qui n'en a pas) :

```
text, letters, words, numbers, typography, handwriting, signature,
watermark, logo, 3d render, cgi, photorealistic, glossy, perspective,
table, desk, wooden surface, drop shadow on floor
```

## v2 — version courte (≤ 77 tokens, pour un encodeur CLIP)

À utiliser sur SDXL et sur toute variante turbo qui garderait CLIP. Elle
sacrifie la scène détaillée — c'est inévitable — et garde la matière.

```
risograph print paper collage, flat lay from directly overhead, cream paper,
oxblood red and charcoal ink, halftone dots, ink misregistration, torn
scissor-cut paper shapes, stack of documents, gavel, paper arrows, geometric
scraps, no text, no letters, blank paper, flat even light, no perspective
```

---

## Protocole de mesure

Pour que les résultats de plusieurs modèles soient comparables :

- **Même graine** sur tous les modèles — 7, par exemple. Sinon on compare
  deux tirages, pas deux modèles.
- **Format 16:9** forcé dans le workflow ComfyUI, pas dans le prompt : la
  v1 l'a ignoré et a rendu du carré.
- **1344 × 768 au minimum.** En dessous, les découpes deviennent molles
  quand le montage les met à l'échelle ; notre Ken Burns monte à ×1,30.
- **Noter le temps par image**, c'est le critère qui décide autant que le
  rendu. À une affiche par beat, un documentaire de 15 minutes en demande
  une centaine :

  | Temps par image | Un documentaire de 15 min |
  |---|---|
  | 20 min (Qwen-Image complet) | **33 heures** — inutilisable |
  | 40 s (z-image turbo) | 67 min — une passe de nuit |
  | 10 s | 17 min — confortable |

## Ce qu'on regarde, dans l'ordre

1. **Aucun caractère nulle part ?** C'est le critère qui décide : notre
   template interdit la reconstitution déguisée en archive, et une fausse
   coupure de presse illisible en est une.
2. **Est-ce que ça a l'air imprimé ?** Grain, trame, mauvais repérage — ou
   bien des aplats vectoriels propres.
3. **À plat, ou posé sur une table ?** La perspective et l'ombre au sol
   sont ce qui a fait basculer la v1 vers l'illustration 3D.
4. **Les pièces ont-elles des bords nets et des ombres distinctes ?** C'est
   ce qui permettra l'animation en parallaxe ensuite.
5. **La bande du tiers supérieur est-elle vide ?** Elle accueillera le
   titre composé.
