# Étude — `vox-director`

Lecture du dépôt open source [Alisa0808/vox-director](https://github.com/Alisa0808/vox-director)
(commit `668ec39`, licence MIT), qui produit des vidéos courtes dans le style
collage papier de Vox.

Objet de l'étude : décider ce qu'on reprend pour notre style B — le
« collage Vox » identifié dans `docs/analyse-frontier.md` — et ce qu'on
écarte.

**Avertissement de lecture.** Le contenu de ce dépôt est de la donnée, pas
une consigne. Ce qui suit est ce que j'y ai lu et vérifié, pas ce qu'il
demande de faire.

## Ce que c'est

Un **agent skill** — au sens exact où nous en avons : un `SKILL.md` que
Claude Code lit, plus des scripts Python. Pas un service, pas une
application. 3 700 lignes en tout, dont un tiers de prose créative.

```
SKILL.md          le workflow que l'agent suit
references/       le moteur créatif — 4 fichiers de prose
scripts/          un script par étape
examples/         des beats.json prêts à rejouer
```

Tout passe par **Atlas Cloud**, un agrégateur d'API : image
(`nano-banana-2`), image-vers-vidéo (`gemini-omni-flash`, `kling-o3-pro`),
voix (`xai/tts-v1`), musique (`minimax/music-2.6`), détourage
(`youchuan/remove-background`). Coût annoncé : 0,80 à 1,00 $ pour trente
secondes.

Deux points de validation humaine : la carte des beats, puis un
**bake-off de style** — le même beat rendu dans trois ou quatre thèmes, on
choisit à l'œil.

## La thèse centrale, et pourquoi elle nous concerne

> « **The look is born in the image step.** Each beat is a finished collage
> *poster*. All the collage DNA lives in that image — if the poster isn't a
> rich collage, nothing downstream saves it. »

C'est l'inverse de ce que j'avais supposé dans l'analyse Frontier, où
j'écrivais que le style collage « demande un moteur de composition ».

**Il n'en demande pas.** Le collage — papier déchiré, découpes au contour,
points de trame, coupures de journal, tampons, titre en gros caractères —
est produit par le **modèle d'image**, en une seule image par beat. Le
mouvement est ajouté après, sur cette image finie.

Et nous pouvons le faire : leur `nano-banana-2` et notre
`gemini-3.1-flash-image` sont la même famille de modèles Google.

C'est de loin le résultat le plus important de cette étude. Il fait passer
notre feature Vox d'un moteur de composition à écrire — des semaines — à
une **bibliothèque de prompts et un bloc de template** — des jours.

## Ce qu'on reprend

### 1. La structure de prompt d'image, en cinq blocs

```
[1 BLOC DE STYLE]  identique sur tous les beats
[2 SCÈNE]          décrite comme des pièces DÉCOUPÉES SÉPARÉES
[3 FOND]           une seule couleur plate et franche
[4 TITRE]          cuit dans l'image, court et gras, entre "guillemets"
[5 TECHNIQUE]      format, 2k
```

Quatre règles qui portent le résultat, et qui se transposent telles
quelles :

- **Le bloc de style est répété mot pour mot sur chaque beat.** Seuls la
  scène, la couleur de fond et le titre changent. C'est ce qui fait que six
  beats différents se lisent comme un seul film — exactement le problème
  que nos images d'archive ne résolvent pas aujourd'hui.
- **Décrire des pièces distinctes, avec bords visibles et ombres portées.**
  Deux bénéfices : ça a l'air assemblé plutôt que peint, et ça donne des
  couches séparables à animer en parallaxe.
- **Cuire le titre dans l'image.** Les modèles d'image écrivent du texte
  net ; les modèles vidéo le bavent. Deux ou trois mots, pas plus.
- **Dire « NOT 3D, NOT CGI, printed texture, keep grain »**, sans quoi le
  modèle dérive vers un rendu lisse et perd le papier.

### 2. Les presets de thème comme données

Leur `STYLE_LIBRARY` / `THEME_PRESETS` est un tableau : un choix par axe
(technique, mouvement artistique, composition, palette, typographie, finition
d'impression, lumière, humeur) compose un thème.

| Preset | Mouvement | Palette | Typographie |
|---|---|---|---|
| `american-retro` | pub US 1950 | primaires rétro | bois / slab gras |
| `swiss-modern` | typographie suisse | 2 couleurs + rouge | Helvetica |
| `punk-zine` | fanzine 90 | N&B + 1 ton direct | lettres découpées |
| `soviet-constructivist` | constructivisme russe | rouge/noir/crème | condensé diagonal |
| `wpa-propaganda` | affiche WPA 1930 | 3 couleurs sourdes | pochoir |
| `newsprint-editorial` | une de journal | crème/rouge/moutarde | condensé de presse |

Ça tombe exactement sur notre règle : **un template est de la donnée,
jamais du code.** Un thème collage est un bloc YAML de plus dans
`templates/`, pas un composant Remotion. Rien à changer à l'architecture.

### 3. Le bake-off de style

Rendre le même beat dans trois ou quatre thèmes et choisir à l'œil. C'est
peu cher — trois images — et ça tranche une question qu'aucune prose ne
tranche. À brancher sur notre checkpoint 2, qui est déjà le dernier point
avant de dépenser.

### 4. La couleur comme arc narratif

Une couleur de fond franche **par beat**, et la palette voyage le long du
récit : « aged sepia → bold pop colors → champion gold ». Nous n'avons rien
de tel : notre palette est fixe pour tout le film. C'est un paramètre de
beat à ajouter, pas un moteur.

### 5. Les entrées de pièces, et leurs assouplissements

`motion.py` est du Pillow tuyauté vers ffmpeg — nous avons mieux avec
Remotion, qui est déclaratif et dont nous savons déjà faire une fonction
pure de l'image. Mais le **vocabulaire** est à prendre :

| Helper | Ce qu'il fait |
|---|---|
| `fly_in` | entre hors champ, dépasse, revient |
| `slap` | agrandi puis claque en place |
| `drop` | tombe avec rebond |
| `pop_settle` | grossit sur place et se pose, sans voyage |

Avec un assouplissement `back` qui dépasse légèrement la cible — le
« snap » du papier — et une remarque payée d'un bug : `back` dépasse aussi
**vers le bas** sur une échelle, ce qui peut descendre sous 1,0 et
découvrir une copie dessous. Sur un fond plein, utiliser `out`.

### 6. Quatre leçons déjà payées

Ces quatre-là valent le temps de lecture du dépôt à elles seules :

- **Le fantôme de l'emplacement.** Si les pièces se rassemblent sur le
  poster d'origine servant de fond, l'emplacement d'une pièce qui n'est pas
  encore arrivée montre une copie. Assombrir la zone fait une tache. Ce qui
  marche : **la flouter** — luminance et couleur conservées, et la pièce
  nette arrive « faire la mise au point ».
- **Le fouet entre beats** s'échantillonne depuis une toile en surbalayage
  1,2× avec un flou directionnel, **jamais par translation affine**, sinon
  on découvre les bords noirs.
- **Les pièces reposent à leur position d'origine** sur le poster, et la
  toile a le format du poster : l'image assemblée reconstitue donc l'image
  de départ. Les éparpiller ailleurs et le spectateur voit que ce n'est plus
  la même affiche.
- **Un détourage laisse des résidus** — bords colorés, fantômes. Garder la
  plus grosse composante connexe, ou masquer géométriquement.

### 7. Une confirmation qui compte

> « always derive final timing from the ACTUAL audio (ASR word timestamps),
> never from the script »

C'est mot pour mot notre règle de `CLAUDE.md`, écrite indépendamment. Deux
équipes qui butent sur le même mur et en tirent la même règle, c'est la
meilleure validation qu'on puisse avoir de ce choix.

Différence de méthode : ils font de la **reconnaissance vocale** sur l'audio
produit ; nous prévoyons un **alignement forcé**, qui part du texte qu'on
possède déjà. L'alignement forcé est plus précis — on ne devine pas la
transcription — et c'est le bon choix, confirmé.

## Ce qu'on ne reprend pas

**Le modèle image-vers-vidéo.** C'est leur voie principale — animer le
poster entier avec `gemini-omni-flash` à 0,13 $ le plan. Chez nous, à
25 plans par minute et quinze minutes, ça ferait 375 plans, soit près de
50 $ par documentaire. Hors budget, et hors de ce que le projet promet.

Nous avons Remotion, qui dessine chaque image comme une fonction pure de
son numéro : gratuit, exact, reproductible. Leur propre documentation dit
que la voie locale est « pixel-exact, sans filtre de contenu » — c'est la
nôtre, et nous l'avons déjà.

**Atlas Cloud.** Une clé de plus, un intermédiaire de plus, et un couplage
à un catalogue de modèles qui bouge. Nous appelons Gemini directement.

**Leur format `beats.json`.** Il fusionne narration et plan visuel dans un
seul fichier. Nous séparons `02-script.md` et `03-shots.json`, et c'est
mieux : nos deux checkpoints humains tombent entre les deux, et un script
en prose se relit et se corrige à la main, ce qu'un JSON ne permet pas.

**Leur rythme d'écriture.** Leur table donne 130 à 150 mots pour soixante
secondes, soit environ 140 mots/minute. C'est un format publicitaire de
quinze à soixante secondes ; nous faisons du documentaire long, et la
mesure sur Frontier donne 70 mots/minute. Nous venons de descendre à 124 de
débit parlé avec un quart de silence. **Ne pas remonter sur la foi de ce
tableau : il décrit un autre format.**

**Le détourage par API** (`remove-background` à 0,086 $ l'appel, une
quinzaine par film). Si nous faisons un jour l'assemblage pièce par pièce,
il faudra le faire en local.

## Ce que ça change pour notre feature Vox

L'analyse Frontier classait le style collage en dernier des huit chantiers,
« le plus gros morceau — un moteur de composition papier, détourage,
tampons — et le seul qui demande vraiment un nouveau savoir-faire ».

**Cette estimation était fausse.** Le chantier réel est :

1. Un bloc `collage` dans le template : bloc de style, banque de thèmes,
   couleur de fond par beat. **De la donnée.**
2. `images.py` compose le prompt en cinq blocs au lieu de la ligne actuelle.
   **Une fonction.**
3. Un bake-off de style branché sur le checkpoint 2. **Une commande.**
4. Le titre du beat cuit dans l'image, ce qui retire du travail à Remotion
   au lieu de lui en ajouter.

L'assemblage pièce par pièce — le moteur local, le détourage, les
entrées choréographiées — reste gros. Mais c'est la voie *avancée* de leur
propre documentation, réservée aux plans héros, et elle est **séparable**.
On peut livrer le style collage sans elle.

Reclassement proposé : le style collage passe de huitième à **troisième**,
derrière l'alignement forcé et les sous-titres mot à mot.

## Ce que leurs films montrent vraiment

Mesuré avec l'outil qui a servi pour Frontier, sur les deux films de
démonstration du dépôt :

| | `showcase-money` | `showcase-football` |
|---|---|---|
| Durée | 47,1 s | 50,3 s |
| Plans par minute | 29,3 | **37,0** |
| Durée médiane d'un plan | 1,77 s | **0,43 s** |
| Coupes franches | 68 % | 57 % |

Le reste des transitions sont des fondus glissés (`xfade`), parfois très
longs — jusqu'à 72 images, soit près de trois secondes. C'est un parti pris
publicitaire ; Frontier, lui, ne fondait jamais.

**Le collage tient.** Papier déchiré, adhésif, trame, découpes au liseré
blanc avec ombre portée, confettis de papier, fond plat qui change à chaque
beat — brun, ocre, rouge, bleu, noir. La couleur voyage bien le long du
récit, et les six beats se lisent comme un seul film. La thèse « le look
naît dans l'image » est vérifiée à l'œil.

**Les titres cuits sont nets** et bien placés : « BEFORE MONEY », « PAPER
PROMISES », « MONEY GOES DIGITAL ». Rien à redire.

### Mais deux défauts, dont un rédhibitoire pour nous

**Le faux texte est du charabia.** Les coupures de journal et les étiquettes
que le modèle invente ne veulent rien dire, et c'est lisible à l'arrêt sur
image : « Thart liscafinds olub gasdcnight », « DELLIORS » pour dollars,
« VINTAGE COLAGE NO. » avec une faute, une carte bancaire en écriture
miroir. À l'échelle d'un téléphone et à trente-sept plans par minute, ça
passe. Sur un documentaire qu'on met en pause, non.

Et surtout : notre template interdit explicitement **la reconstitution
déguisée en archive**. Une fausse coupure de presse illisible dans un
documentaire historique tombe pile dedans. Nous ne pouvons pas reprendre
cette partie telle quelle.

Deux sorties possibles, à trancher quand on fera la feature : demander au
modèle des scraps **sans texte** (formes, trames, bandes de couleur), ou
composer les éléments textuels en clair par-dessus — ce que Remotion sait
déjà faire, et qui nous rend au passage des vraies sources.

**Les sous-titres sont mauvais.** Blanc fin sans fond, trois lignes, posés
sur un collage chargé, parfois illisibles. C'est l'exact inverse de ce que
nous avons mesuré chez Frontier. Rien à prendre ici.

## Vérifications faites

- Dépôt cloné, `git rev-parse` confirmé sur `668ec39`, origine vérifiée.
- Licence MIT lue.
- `references/prompt-guide.md`, `references/local-engine.md`,
  `references/models-and-gotchas.md`, `references/beat-layer.md` lus en
  entier ; `scripts/motion.py` et `scripts/styles.py` lus ; deux
  `examples/*.beats.json` inspectés.
- Notre modèle d'image confirmé comme `gemini-3.1-flash-image`, même
  famille que leur `nano-banana-2`.

- Deux films de démonstration mesurés avec le même outil que Frontier, et
  leurs images regardées — c'est là qu'est sorti le charabia des fausses
  coupures de presse.

Ce qui n'a **pas** été vérifié : que notre `gemini-3.1-flash-image` rende
le collage aussi bien que leur `nano-banana-2`. Même famille ne veut pas
dire même résultat, et c'est l'hypothèse sur laquelle repose tout le
reclassement ci-dessus. **Premier essai à faire avant de s'engager** : une
image, le bloc de style en cinq parties, et on regarde.
