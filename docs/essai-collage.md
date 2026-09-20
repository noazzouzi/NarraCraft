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

---

# Résultat

Les deux images sont dans `docs/essai-collage/`. Générées à la main, en
`gemini-3.1-flash-image`, 1376 × 768.

## Verdict : l'hypothèse tient, et la règle de lettrage est le bon correctif

**A répond oui aux quatre questions.** Papier déchiré, adhésif aux quatre
coins, points de trame, ombres portées ; les pièces sont à des profondeurs
distinctes — pile de documents, feuille soulevée, marteau, fragment de
calendrier, flèches, accents géométriques — chacune avec son bord net.
Texture gravée sur le marteau et la tranche de la pile : imprimé, pas
rendu 3D.

**« EXÉCUTION PROVISOIRE » est parfait**, accent compris, en condensé de
presse charbon sur crème, sur une bande déchirée dans le tiers supérieur.
Le français accentué n'était pas gagné : il l'est.

**Et la règle de lettrage a tenu.** Tous les autres documents sont de la
texture pure — barres grises, blocs d'encre, pavés de trame. Aucun mot
inventé.

**B échoue exactement comme prévu**, et c'est ce qui rend l'essai
concluant. Avec la formulation de `vox-director`, le modèle fabrique
« NOMOIGNAGE CHOC » pour témoignage, « COCRY DECISION DELAYED »,
« P. CISL.E », du faux manuscrit, et mélange anglais et français au
hasard. Le même charabia que dans leurs propres films de démonstration.

## Un effet de bord qu'on n'attendait pas

B ne perd pas que le texte : **il perd le style**. Mesuré sur les deux
images réduites :

| | A (avec règle) | B (témoin) |
|---|---|---|
| Couleur dominante | `#600000` — **29 %** | gris `#909090` — 22 % |
| Saturation moyenne | **95**/255 | 48/255 |

A est un collage plat sur fond rouge franc, comme demandé. B est une
**photographie de papiers sur un bureau en bois**, avec une lumière
réaliste : deux fois moins saturé, dominé par des gris. Le bloc de style
demandait pourtant « flat even scanned-document light, straight-on » dans
les deux cas.

Ce qui l'a fait basculer est le mot **« newspaper clippings »** laissé libre
dans la scène : il tire le modèle vers la photo de coupures sur une table.
La règle de lettrage, en imposant « texture only », le ramène au graphisme.

**La règle protège donc deux choses à la fois** — l'honnêteté documentaire
et la direction artistique. C'est deux raisons de la garder, pas une.

## Ce qui reste à corriger

- **Les chiffres ont survécu.** Le calendrier de A affiche 5 à 28 et un 2
  entouré, alors que le prompt interdisait explicitement les nombres. Ils
  sont plausibles — ce n'est pas du charabia — mais la règle n'est pas
  étanche. Deux options : l'accepter pour les chiffres, ou bannir le
  calendrier des scènes. À trancher au moment de coder.
- **Le format n'est pas exactement 16:9** : 1376 × 768 donne 1,792 au lieu
  de 1,778. Sans conséquence — `06-timeline.json` porte déjà un champ
  `ratio` par plan et le moteur adapte plutôt que de rogner.

## Ce que ça débloque

Le reclassement du style collage en troisième position n'est plus une
hypothèse. Le chantier est bien celui qui était annoncé :

1. Un bloc `visuels.collage` dans le template — bloc de style, banque de
   thèmes, couleur de fond par beat. **De la donnée.**
2. `images.build_prompt()` compose en cinq parties au lieu d'une ligne, et
   porte la règle de lettrage. **Une fonction.**
3. Un bake-off branché sur le checkpoint 2. **Une commande.**

Le bloc de style de A — ses trois premiers paragraphes, qui ne parlent ni
de Sarkozy ni de tribunal — part tel quel dans le template.

---

# Le modèle de coût, qui décide de la viabilité

L'essai valide le rendu. Il reste à vérifier que le style est payable —
et ce n'est pas acquis.

## Il n'y a pas de tier gratuit

Vérifié par notre propre appel (`limit: 0`) et confirmé par la
documentation : Google ne publie aucun tier gratuit pour la sortie image.
L'application Gemini grand public donne une vingtaine d'images par jour en
1K, ce qui sert à faire un bake-off à la main — c'est ainsi que les deux
images de cet essai ont été produites — mais pas à monter un film.

Le crédit de bienvenue de 300 $ de Google Cloud existe toujours (90 jours,
nouveau compte) et **ne s'applique pas** à l'API Gemini d'AI Studio, qui
est celle que `images.py` appelle. Il s'applique à Gemini sur Vertex AI,
qui sert les mêmes modèles derrière une autre URL. Basculer d'endpoint est
donc une vraie option, et un vrai petit chantier.

## Ce que coûte un film, selon le découpage

Tarif de `gemini-3.1-flash-image` : environ 0,045 $ en 512 px, jusqu'à
0,15 $ en 4K.

**Une affiche par plan** — le découpage naïf, à 25 plans/minute :

| Prix/image | Film de 15 min (375 affiches) | Essai de 2 min |
|---|---|---|
| 0,045 $ | 16,88 $ | 2,25 $ |
| 0,150 $ | 56,25 $ | 7,50 $ |

Le `README` annonce 2,50 à 4 € par documentaire. Ce découpage-là le fait
donc exploser d'un facteur cinq à quinze. **Inacceptable en l'état.**

**Une affiche par beat**, avec plusieurs plans qui entrent dedans — ce que
fait `vox-director` (« one poster per beat »), et ce que nos projets font
déjà : 2,1 et 2,3 plans par beat mesurés sur les deux montages Sarkozy.

| Prix/image | Film de 15 min (~100 beats) | Essai de 2 min (12 beats) |
|---|---|---|
| 0,045 $ | 4,50 $ | 0,54 $ |
| 0,150 $ | 15,00 $ | 1,80 $ |

C'est une autre affaire, et ça ne demande aucun mécanisme nouveau : nos
plans portent déjà un `poids` dans le beat, et le mouvement de caméra est
déjà une vitesse. Trois plans dans la même affiche, ce sont trois cadrages
et trois mouvements — exactement ce que Frontier fait avec ses plans longs
qui bougent tout du long.

**Conséquence pour la feature** : le collage impose « une affiche par
beat, plusieurs plans dedans ». Ce n'est pas une optimisation qu'on
ajoutera après, c'est la contrainte qui rend le style payable, et elle doit
être dans le plan visuel dès le départ.

---

# Variante locale — un modèle ouvert sur CPU

Question posée : un modèle libre, tournant sans clé ni facturation,
produit-il un collage Vox exploitable ? La réponse importe : la voix
tourne déjà en local avec Kokoro, et l'image suivrait la même logique —
modèle local par défaut, Gemini en finition.

Essai fait sur cette machine, sans GPU, 4 cœurs, 15 Go de RAM :
**SDXL base 1.0**, `bfloat16`, 1024 × 576, 24 étapes. Résultat dans
`docs/essai-collage/C-sdxl-local.jpg`, obtenu en **42 à 110 secondes**
selon la taille — bien plus rapide qu'attendu pour du CPU.

## Le résultat : la matière, pas la scène

**La texture est bonne.** Bords déchirés, papier réglé, trame, rayures,
ombres portées, palette crème/rouge/charbon tenue. C'est du vrai collage
papier ; la matière est là.

**La scène est absente.** Aucun marteau, aucune pile de documents, aucune
flèche — alors que tous trois étaient demandés. Le modèle a produit un
collage **abstrait** : une texture, pas un plan.

## La contrainte qui décide, et elle est mesurée

Le premier essai était faussé par ma faute, et le diagnostic vaut plus que
l'image :

```
235 tokens dans le prompt · limite CLIP de SDXL : 77
-> "following part of your input was truncated"
```

Le modèle n'avait vu que le bloc de style. Toute la scène, le fond et la
bande réservée au titre avaient été **silencieusement jetés**.

C'est une contrainte d'architecture, pas un réglage :

| Famille | Encodeur de texte | Budget | Notre prompt en 5 blocs |
|---|---|---|---|
| SDXL | CLIP ×2 | **77 tokens** | tronqué aux deux tiers |
| FLUX, Qwen-Image | T5 | ~512 tokens | passe entier |

Toute l'approche `vox-director` repose sur un prompt long et structuré —
bloc de style répété mot pour mot, scène décrite pièce par pièce, fond,
titre. **SDXL ne peut structurellement pas la recevoir.** Même ramené à
75 tokens, il n'a pas lié les objets à la scène : c'est sa faiblesse
connue face aux modèles à T5.

**Conclusion : si on va en local, c'est FLUX ou Qwen-Image, pas SDXL.**
Sur 16 Go de VRAM, FLUX quantifié passe confortablement. Ce n'est plus une
préférence, c'est une contrainte mesurée.

## Ce qui reste non vérifié

FLUX n'a pas été testé ici : en `bfloat16` il demande plus de RAM que
cette machine n'en a, et la version quantifiée aurait demandé une pile de
dépendances supplémentaire pour un résultat toujours limité par l'absence
de GPU. **Le test concluant se fera sur la machine cible.**

## Mes deux erreurs de protocole, pour ne pas les refaire

- `float32` sur 15 Go de RAM : SDXL pèse ~13 Go de poids dans ce format,
  le chargement est parti en thrashing (1,7 s puis 14 s par bloc) et le
  processus a été tué. `bfloat16` charge en 15 s.
- 768 × 448, en dessous de la résolution d'entraînement de SDXL : motif
  répété en damier, sa signature d'échec classique. À 1024 il disparaît.

Aucune des deux ne disait quoi que ce soit sur les modèles ouverts. Elles
disaient que mon banc d'essai était mal réglé.

## Conséquence sur les dépendances

`torch` et `diffusers` sont installés dans ce conteneur mais **ne sont pas
ajoutés à `pipeline/requirements.txt`** : ce serait imposer deux gigaoctets
à qui n'en veut pas. Si la voie locale est retenue, elle devient un extra
optionnel, exactement comme Kokoro l'est pour la voix.

---

# Qwen-Image en local — la question tranchée, deux problèmes ouverts

Généré sur la machine cible (Radeon RX 7800 XT, ComfyUI) avec le prompt
long en cinq blocs de `REPRODUIRE.md`. Résultat :
`docs/essai-collage/D-qwen-local.jpg`, 1024 × 1024.

## Ce qui est réglé : le prompt passe entier

**La scène est là.** Pile de documents, feuille soulevée, marteau, fragment
de calendrier, flèches vers le bas, ciseaux, accents géométriques, cachet
rouge, adhésif. Tous les éléments demandés, y compris ceux du troisième
paragraphe du prompt.

C'est exactement ce que SDXL ne pouvait pas faire : son encodeur CLIP
coupait à 77 tokens et n'avait vu que le bloc de style. **L'hypothèse T5 est
vérifiée** — un modèle à 512 tokens reçoit notre structure en cinq blocs.

Le fond aussi : 71 % de l'image est en rouges sang (`#300000`, `#900000`,
`#600000`). L'instruction de fond plat a porté.

## Ce qui échoue : le lettrage

**La règle de lettrage n'a pas tenu.** « LEOMKIVFAS », « Pro… Cilvin on
1News », « QJIVI » — du charabia inventé, exactement ce que la règle devait
empêcher, et ce que Gemini avait évité.

| | Gemini (A) | Qwen (D) |
|---|---|---|
| Scène complète | oui | **oui** |
| Titre net et accentué | oui | — (absent) |
| Faux texte ailleurs | **aucun** | **plusieurs** |

La règle est donc **spécifique au modèle**, pas universelle. Une formulation
qui discipline Gemini ne discipline pas Qwen.

**Conséquence directe : composer le titre dans Remotion devient obligatoire,
plus optionnel.** C'était déjà l'option préférée — accents fiables,
typographie du template, titre animable. Ça devient la seule qui marche sur
les deux moteurs.

Et il faut une deuxième ligne de défense contre le faux texte, parce que le
prompt ne suffit pas : demander explicitement des scraps **sans aucun
caractère** (formes, trames, bandes de couleur), au lieu de demander du
texte illisible — un texte « flou » reste du texte pour le modèle.

## Ce qui échoue aussi : la matière

Saturation moyenne **187/255**, contre 95 pour Gemini. Ce n'est pas du
papier imprimé : c'est de l'illustration vectorielle propre, posée sur une
table avec une ombre portée, en perspective. Le `NOT 3D / NOT CGI` a tenu —
rien n'est photoréaliste — mais `halftone print dots`, `print grain`,
`aged newsprint texture` et `flat even scanned-document light,
straight-on` n'ont pas porté.

Deux pistes, à essayer dans cet ordre :

1. **Monter le poids des termes de matière** et les mettre en tête du
   prompt. Sur Qwen l'ordre compte, et notre bloc de style les noie au
   milieu d'une longue phrase.
2. **Nommer un procédé d'impression précis** plutôt que des adjectifs :
   « risograph », « letterpress », « screenprint », qui sont des styles que
   les modèles connaissent comme tels.

## Ce qui n'a pas été respecté non plus

- **Le format.** 1024 × 1024 au lieu de 16:9. À forcer dans le workflow
  ComfyUI, pas dans le prompt.
- **La bande vide du tiers supérieur** : écart-type de luminance 72, donc
  chargée. La pile de journaux l'occupe. À reformuler, ou à obtenir par
  composition plutôt que par prompt.

## Où ça laisse la feature

Le point bloquant — « est-ce qu'un modèle local reçoit notre prompt ? » —
est levé. Les deux points restants sont des réglages de prompt et de
workflow, pas des impossibilités. Le style collage reste donc classé
troisième, et il est maintenant réalisable **sans facturation**.

---

# Épilogue — la feature n'a finalement rien généré

Le banc d'essai s'est terminé sur trois modèles de plus, chronométrés par
l'utilisateur sur sa machine :

| Modèle | Temps | Texte inventé | Matière | Composition |
|---|---|---|---|---|
| SDXL Turbo | 65 s | **partout** | — | aucune |
| z-image turbo + qwen | 99 s | aucun | trame présente, bords vectoriels | pictogrammes alignés |
| **Nano Banana 2 Lite** | **4 s** | aucun | trame, fibre, bords déchirés | superposée, profondeur réelle |

SDXL Turbo confirme la v1 par l'autre bout : 77 jetons CLIP, le prompt est
tronqué avant même d'arriver à la scène. Nano Banana 2 Lite rend une
planche qui tient la comparaison avec Frontier, en quatre secondes, pour
**0,0336 $** — moitié moins en Batch API.

## Et c'est là que la feature a changé de nature

Le calcul du coût était devenu acceptable — 2,79 $ pour quatre-vingts
planches, 1,39 $ en batch, sous le plafond de huit euros. Sauf que la
question n'était plus le prix.

L'analyse du concurrent disait déjà la réponse, et elle avait été lue sans
être entendue (`analyse-frontier.md`) :

> Il ne demande aucune image générée : il demande un **moteur de
> composition**.

Une planche générée, même excellente, a ses couches cuites dans les pixels.
Trois choses deviennent impossibles :

- **l'animer par couches** — donc pas de parallaxe, et la parallaxe est
  précisément ce qui distingue une planche d'une image posée ;
- **changer sa palette avec le template** — il faudrait tout regénérer ;
- **corriger la position d'une pièce** — il faudrait relancer le modèle et
  espérer.

Les trois sont des choses qu'un template est censé pouvoir faire, et la
troisième est le principe même de l'atelier : « tu peux corriger n'importe
quel fichier à la main et relancer à partir de là ».

## Ce qui a été construit à la place

`fresque.collage` calcule la mise en page — quelles pièces, où, à quelle
profondeur — et `Collage.tsx` la dessine. La planche atterrit dans
`06-timeline.json`, où elle se relit et se corrige. Coût par documentaire :
**zéro**.

Le banc d'essai n'a donc pas servi à choisir un fournisseur. Il a servi à
mesurer la borne haute de ce qu'une image générée pouvait donner — et à
constater qu'elle était en dessous de ce qu'on pouvait composer.

**La règle à retenir dépasse le collage** : avant de payer un modèle pour
dessiner quelque chose, vérifier que ce quelque chose n'est pas composable.
Un élément composé coûte plus cher à écrire une fois, et moins cher à toutes
les autres — en argent, en temps de rendu, et en contrôle.
