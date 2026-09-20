# Essai collage — les prompts, et ce qu'ils doivent trancher

`docs/etude-vox-director.md` reclasse le style collage de huitième à
troisième, sur une hypothèse non vérifiée : que notre
`gemini-3.1-flash-image` rende le collage aussi bien que le
`nano-banana-2` de `vox-director`. Même famille de modèles ne veut pas
dire même résultat.

Cet essai tranche ça avant qu'on engage du code.

## Pourquoi il se lance à la main

Le free tier Gemini donne **zéro** quota sur ce modèle — pas un quota
épuisé, un plafond à zéro :

```
HTTP 429 · RESOURCE_EXHAUSTED
Quota exceeded for metric: generate_content_free_tier_input_token_count,
limit: 0, model: gemini-3.1-flash-image
```

Il n'y a donc rien à attendre ni à réessayer : sans facturation activée,
la génération passe par l'interface, à la main.

## Le plan choisi

Le beat **B003** du projet `sarkozy-essai-2min`, qui est le pivot du film :

> « Dans les dernières pages, une mention que presque personne n'écoute ce
> jour-là. Le tribunal ordonne l'exécution provisoire de la peine. »

Choisi exprès : c'est un plan **abstrait** — un dispositif de jugement. Les
archives libres n'ont rien à offrir là-dessus, et c'est précisément le trou
que le collage doit combler. Si ça marche ici, ça marche là où on en a
besoin.

Thème retenu : `newsprint-editorial` — une de journal du milieu du siècle,
crème / rouge sang / moutarde / charbon. C'est l'idiome d'une affaire
judiciaire française.

## Ce que l'essai doit trancher

Deux questions, d'où deux images.

| | Question |
|---|---|
| **A** | Le modèle rend-il le collage, **et** notre règle d'absence de texte inventé tient-elle ? |
| **B** | Sans cette règle, produit-il le même charabia que `vox-director` ? |

B est le témoin. S'il fabrique « DELLIORS » et des coupures illisibles
comme dans leurs films, et que A n'en fabrique pas, alors la règle est le
bon correctif et on peut la coder. Si A en fabrique aussi, il faudra
composer les éléments textuels par-dessus dans Remotion — plus de travail,
et il vaut mieux le savoir maintenant.

**À regarder, dans cet ordre :**

1. Est-ce que ça ressemble à du papier découpé, ou à une illustration
   lissée ? (Le « NOT 3D / NOT CGI / keep grain » est censé tenir ça.)
2. Les pièces ont-elles des bords nets et des ombres portées distinctes ?
   C'est ce qui rend l'animation en parallaxe possible ensuite.
3. « EXÉCUTION PROVISOIRE » est-il net, bien orthographié, accents
   compris ? Le français accentué est un vrai risque.
4. Reste-t-il du faux texte ailleurs dans l'image ?

## Prompt A — avec la règle de lettrage

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

On a bold flat deep oxblood-red paper background.

IMPORTANT — LETTERING RULE: the ONLY legible lettering anywhere in the
image is one torn-paper banner carrying the headline "EXÉCUTION
PROVISOIRE" in a bold condensed newsprint grotesque, all caps, charcoal
ink on cream paper, placed in the upper third. Every other paper scrap,
document, clipping and label must be TEXTURE ONLY: abstract grey ruled
lines, ink bars, halftone blocks and blurred unreadable type — no words,
no letters, no numbers, no signatures, no seals with writing. Do not
invent newspaper text.

Palette limited to aged cream, deep oxblood red, mustard and charcoal.
Aspect ratio 16:9, 2k resolution.
```

## Prompt B — témoin, sans la règle

Identique à A, mais le bloc « IMPORTANT — LETTERING RULE » est remplacé
par celui-ci, qui est la formulation de `vox-director` :

```
A torn-paper banner with a big bold headline "EXÉCUTION PROVISOIRE",
plus newspaper clippings and document scraps around the scene.
```

## Le reste du bloc de style est réutilisable tel quel

Les trois premiers paragraphes de A ne parlent ni de Sarkozy ni d'un
tribunal. C'est le **bloc de style**, et il est destiné à être répété mot
pour mot sur chaque beat du film — c'est ce qui fait qu'une suite d'images
générées se lit comme un seul film plutôt que comme une banque d'images.

S'il tient, il devient un champ de template, sous `visuels.collage`, et
rien de plus : un template reste de la donnée.
