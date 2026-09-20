# Analyse de Frontier

Étude de trois vidéos produites par Frontier, le produit concurrent. Deux
documentaires échantillons et une vidéo de promotion qui décrit le produit.

Ce document n'est pas une impression : chaque nombre qui y figure a été
mesuré, et la méthode est donnée pour qu'on puisse le refaire. Les
affirmations non mesurées sont signalées comme telles.

## Méthode

Les trois fichiers sont en 1920×1080, H.264, 30 images/seconde.

| Fichier | Durée | Débit | Contenu |
|---|---|---|---|
| `Messi - Frontier sample` | 33,9 s | 3,5 Mbit/s | documentaire, style sombre |
| `one_wrong_turn_2` | 21,4 s | 8,8 Mbit/s | documentaire, style collage |
| `ezyZip` (promo) | 72,0 s | 2,4 Mbit/s | 8 s de documentaire + 64 s de promo |

Les mesures ont été faites en extrayant les images une à une avec ffmpeg,
puis en les comparant en Python :

- **Coupes** : différence absolue moyenne entre images consécutives, en
  niveaux de gris réduits à 192×108. Un pic isolé au-dessus de 12 est une
  coupe franche ; une série de valeurs basses est un mouvement.
- **Zoom** : pour deux images d'un même plan, on cherche l'échelle qui
  superpose le mieux la première sur la seconde, par balayage de 1,000 à
  1,180 au pas de 0,004.
- **Couleurs et géométrie du texte** : masques sur les canaux RVB,
  boîtes englobantes en pixels sur l'image pleine.
- **Audio** : RMS par fenêtres de 20 ms, et spectre par transformée de
  Fourier sur les creux de niveau.

Ce qui n'a **pas** été mesuré et reste une lecture à l'œil : l'identité
exacte des polices, et le texte de la narration, faute de transcription.

## Ce qu'est Frontier

La vidéo de promotion décrit le produit sans ambiguïté, et ce qu'elle
décrit est notre propre architecture.

**Une application locale.** L'interface tourne sur `localhost:7860` — le
port par défaut de Gradio. Elle liste les projets avec leur état
(`RENDERING 58 %`, `DONE`), exactement comme l'atelier de Fresque.

**Quatre clés d'API, dans un `.env`** :

| Clé | Fournisseur | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | script, jugement |
| `ALGROW_API_KEY` | [Algrow](https://algrow.online/) | voix (relais ElevenLabs), recherche de niches et données YouTube |
| `WAVESPEED_API_KEY` | [WaveSpeed](https://wavespeed.ai/pricing) | images et vidéos générées |
| `PEXELS_API_KEY` | Pexels | métrage de banque |

**Personnalisé avec Claude Code.** Un panneau entier y est consacré : le
terminal montre `claude ~/Frontier` et la commande
`make it my channel: true crime, dark red look, a map every chapter,
slower cuts`, qui réécrit des fichiers de style (`styles/true-crime.json`).
Huit modules gravitent autour de « Your channel » : SCRIPT, VOICE,
FOOTAGE, MAPS, NEWSPAPERS, GRAPHICS, EDIT.

**Coût annoncé** : 50 centimes par minute de documentaire, toutes API
comprises ; 1 à 2 dollars pour trente minutes dans le style le plus
simple. Plausible : WaveSpeed facture 0,005 $ l'image en Flux Dev, ce qui
met 25 images par minute à 0,125 $.

**Distribution** : vendu sur Whop, par lots (52 places, épuisées en quatre
jours), avec le téléchargement de l'outil, des guides de personnalisation
et des cours sur les niches.

> **Ce que ça nous dit.** Nous ne sommes pas en retard sur l'architecture :
> nous avons déjà l'application locale, les clés en propre, Claude comme
> runtime de jugement et les templates en données. L'écart est entièrement
> dans le **métier du rendu**. C'est une bonne nouvelle : c'est la partie
> qui se rattrape par du code, pas par un modèle qu'on n'a pas.

## Deux styles, pas un

Frontier ne produit pas un look unique. Les échantillons montrent deux
directions artistiques nettement séparées, ce qui confirme que le style
voyage en donnée.

### Style A — « sombre cinématographique » (Messi)

Fond quasi noir, photographies réelles en pleine largeur, un seul accent
doré. Panneaux de chiffres, globe animé, captures de presse. Registre
sobre, proche de ce que nous faisons déjà.

### Style B — « collage Vox » (Sarajevo, Indianapolis)

Fond papier beige, photos **découpées au contour avec un liseré blanc**,
tampons rouges en papier déchiré, barre de censure noire sur les yeux,
carte illustrée à plat qui reste à l'écran pendant que le récit avance.

C'est le style que le promo appelle « Vox-style editing », et c'est le
plus éloigné de nous. Il ne demande aucune image générée : il demande un
**moteur de composition**.

## Le montage

### Rythme

| | Frontier (Messi) | Frontier (Sarajevo) | Frontier (promo) | Fresque aujourd'hui |
|---|---|---|---|---|
| Plans par minute | 24,8 | 25,2 | 17,5 | 13,0 |
| Durée médiane d'un plan | 1,73 s | 2,37 s | 3,07 s | ~4,6 s |
| Plan le plus court | 0,17 s | 0,17 s | 0,40 s | — |

**Frontier coupe deux fois plus vite que nous.** Et il descend à
5 images — un sixième de seconde — là où notre plancher implicite est
bien plus haut.

Le plan de 10,3 s dans Messi n'est pas une exception au rythme : c'est la
séquence de l'article de presse, qui est animée en continu. Un plan long
n'est toléré que s'il bouge tout du long.

### Les coupes sont franches

Sur 13 transitions dans Messi et 8 dans Sarajevo, **toutes** sont des
coupes d'une image. Aucun fondu enchaîné, aucun fondu au noir, aucune
transition glissée. Vérifié image par image autour de chaque coupe.

Nous faisons l'inverse : 0,3 s de transition et 0,6 s de fondu au noir.
Sur un film à 25 plans/minute, 0,3 s de transition mangerait 12 % du
temps d'écran.

### La caméra

Mouvement mesuré sur des plans fixes : **+2,1 à +3,1 % d'échelle par
seconde**. Un plan de 2,5 s fait donc ×1,056 en tout.

Notre template va de 1,06 à 1,30 sur la durée du plan, soit +3,5 %/s sur
un plan de 6,5 s. L'ordre de grandeur est le bon — mais comme nos plans
durent deux fois plus longtemps, **l'amplitude totale est deux fois plus
grande**, et c'est ce qui se voit : un zoom qui n'en finit pas.

Certaines séquences ont un zoom nul : les panneaux graphiques et les
captures d'écran ne dérivent pas, ils s'animent autrement.

## Les sous-titres

C'est l'écart le plus visible, et le plus mécanique à combler.

### Ce qu'ils font

La phrase entière est affichée, centrée, sur **une seule ligne**, et le
mot prononcé passe en doré. Mesuré sur l'image pleine :

| Grandeur | Mesure |
|---|---|
| Blanc du texte | `#FAFAFA` |
| Doré du mot courant | `#F5BC4D` |
| Hauteur capitale + descendante | 58 px sur 1080, soit 5,4 % du cadre |
| Ligne de base | 90,8 % de la hauteur du cadre |
| Alignement | centré (x = 958 pour un cadre de 1920) |
| Fond | **aucun bandeau** — l'image reste visible derrière |
| Lisibilité | ombre portée douce, pas de contour dur |
| Graisse | grasse, sans géométrique |

### Le détail qui change tout

Le surlignage **ne saute pas d'un mot à l'autre : il fond**. Sur une
séquence échantillonnée toutes les 0,1 s, on voit « Messi » redevenir
blanc pendant que « said » devient doré, en deux à trois images. C'est ce
fondu qui fait que le texte respire au lieu de clignoter.

### Pourquoi nous ne pouvons pas le faire aujourd'hui

Un surlignage mot à mot exige la position réelle de chaque mot dans
l'audio. Notre `alignment.json` est en `source: kokoro` : les bornes de
beat sont mesurées, mais **la position des mots est estimée par syllabes**.
Sur une phrase de six mots, l'erreur cumulée se verrait immédiatement.

C'est donc la première justification concrète de l'alignement forcé, qui
attendait au jalon 3b sans raison pressante. Il en a une maintenant.

## Les panneaux graphiques

Le promo énumère sept familles, avec leur sous-titre technique :

| Famille | Sous-titre du promo | Ce qu'on voit |
|---|---|---|
| Animated maps | « real geography · timed to the voice » | carte remplie, frontières fines, épingle rouge, nom révélé lettre à lettre |
| Vox-style editing | — | photos découpées, tampons, papier |
| Animated newspapers | « real articles · the line you need, highlighted » | vraie page web, **la ligne utile surlignée au feutre jaune**, source et date en bas |
| Real objects come alive | « real products · cut out and animated » | canettes Coca/Pepsi détourées, animées en 3D |
| Motion graphics | « numbers · charts · social posts · timelines » | grand nombre qui **compte** (106 → 125), libellé au-dessus, unité en dessous |
| Full documentaries | — | le produit fini |

Nous avons treize types de panneaux. La différence n'est pas le nombre,
c'est que **les leurs sont animés dans le temps de la voix** : le
surligneur balaie la ligne du journal au moment où elle est lue, le
compteur monte pendant que le chiffre est prononcé.

### La capture de presse

Traitement remarquable et facile à reprendre : la page du navigateur
arrive **en perspective 3D**, inclinée, puis s'aplatit face caméra. Le
titre est ensuite surligné ligne par ligne, comme au feutre. En bas à
gauche, en petites capitales grises : `AP News · 31 August 2026`.

C'est exactement notre besoin d'attribution — ils en ont fait un élément
de design au lieu d'une contrainte.

## L'audio

### Le lit musical

| Film | Pic | Médiane | Plancher | Dynamique |
|---|---|---|---|---|
| Messi | −12,1 dBFS | −21,3 | −30,5 | 18,3 dB |
| Sarajevo | −11,9 | −22,2 | −45,0 | 33,1 dB |

Dans les creux, **63 à 67 % de l'énergie est entre 150 et 500 Hz** : il y
a bien un lit musical, et il est dans le registre où on l'entend. Le lit
est à environ 9 dB sous la médiane de la voix.

Notre `niveau_relatif_db` est à −22. Frontier est plus haut, autour de
−18. Nous sommes donc encore un peu timides.

### Pas de sons de transition

Mesuré : l'énergie au-dessus de 3 kHz dans les 250 ms qui suivent une
coupe est **plus faible** qu'ailleurs dans le film (0,6 % contre 6,4 %
pour Messi ; 4,8 % contre 7,6 % pour Sarajevo). Il n'y a donc **aucun
souffle ni whoosh** aux coupes.

Nous en avons ajouté. C'est un contresens à corriger.

### Ce qu'ils font à la place

Dans Sarajevo, le motif est net et se répète à chaque coupe : le niveau
tombe à −37/−47 dBFS juste avant, puis remonte à −10 juste après. **Un
silence, puis la coupe sur un impact.** Le rythme vient du vide qu'on
laisse avant, pas d'un effet qu'on ajoute par-dessus.

### La narration est lente

Comptage des mots lisibles dans les sous-titres de Messi : environ 40
mots en 34 secondes, soit **~70 mots/minute** sur la durée totale, et
~105 mots/minute pendant les passages parlés (la voix se tait 34 % du
temps).

Nous sommes à 170 mots/minute.

C'est le résultat le plus contre-intuitif de cette analyse, et le plus
important :

> **Frontier parle lentement et coupe vite.** Nous faisons exactement
> l'inverse. Quand l'utilisateur a trouvé notre premier documentaire
> « ennuyant et monotone », nous avons accéléré la narration de 140 à
> 170 mots/minute. C'était la mauvaise moitié du problème : le rythme
> d'un documentaire se joue à l'image, et la voix doit laisser de la
> place pour qu'on le sente.

Phrases typiques, dans leur intégralité : « August 31st, 2026. » —
« It started in Rosario. » — « A World Cup in Qatar. » Trois à six mots,
un plan chacun, du silence entre.

## Écart, poste par poste

| Poste | Frontier | Fresque | Verdict |
|---|---|---|---|
| Architecture | app locale + clés | app locale + clés | **à égalité** |
| Runtime LLM | Claude | Claude Code | à égalité |
| Personnalisation | Claude Code sur fichiers de style | templates YAML | à égalité |
| Plans/minute | 25 | 13 | **écart ×2** |
| Transitions | coupe franche | 0,3 s + fondu noir 0,6 s | **contresens** |
| Sons de transition | aucun | synthétisés à chaque coupe | **contresens** |
| Narration | ~70 mots/min | 170 mots/min | **écart ×2,4** |
| Sous-titres | mot à mot doré, fondu | phrase blanche fixe | **manquant** |
| Alignement | forcé (implicite) | estimé par syllabes | **manquant** |
| Panneaux | 6 familles, animées sur la voix | 13 types, animés sur le plan | à rattraper |
| Cartes | remplies, épingle, label lettre à lettre | d3-geo présent | proche |
| Presse | page réelle + surligneur + source | absent | **manquant** |
| Sources d'images | WaveSpeed + Pexels | Wikimedia + Openverse + Gemini | à diversifier |
| Lit musical | ~−18 dB | −22 dB | à remonter |

## Ce qu'il faut changer, par ordre d'impact

L'ordre est celui du rapport entre ce que ça change à l'écran et ce que
ça coûte à écrire.

> **Suivi.** Les points 1 et 3 sont faits (commit `d291cea`), ainsi que le
> point 2 — et celui-ci a révélé un défaut que l'analyse n'avait pas vu :
> `pause_phrase_s` ne créait aucun silence, il ne servait qu'à estimer la
> position des mots. Kokoro ne laisse que 0,10 s après un point. Le beat est
> désormais synthétisé phrase par phrase avec un vrai blanc entre les
> morceaux, ce qui porte la part de silence de 19 % à 31 % — dans la bande
> mesurée chez Frontier.

1. **Couper deux fois plus vite, et en franc.** `plans_par_minute` à 25,
   `duree_plan_max_s` à 3, transitions à 0, fondu noir réservé aux
   changements d'acte, sons de transition désactivés par défaut. Ce sont
   des valeurs de template : aucun code à écrire, et c'est le changement
   le plus visible.
2. **Ralentir la narration et raccourcir les phrases.**
   `mots_par_minute` à 100, plafond de mots par beat très bas, et une
   règle de lint qui refuse une phrase de plus de douze mots. Le silence
   devient un élément du script, pas un accident.
3. **Réduire l'amplitude du zoom.** Viser +2,5 %/s calculé sur la durée
   réelle du plan, au lieu d'une plage fixe parcourue quelle que soit la
   durée.
4. **L'alignement forcé.** Sans lui, pas de sous-titre mot à mot. Avec
   lui, on gagne aussi la précision des panneaux animés sur la voix.
5. **Les sous-titres mot à mot**, une fois l'alignement en place :
   `#FAFAFA`, mot courant `#F5BC4D`, fondu sur trois images, ligne de
   base à 91 %, pas de bandeau.
6. **Le panneau de presse** — page réelle, surligneur sur la ligne utile,
   source et date en bas. C'est notre obligation d'attribution
   transformée en élément de design.
7. **Pexels**, pour le métrage libre. `rushes.py` sait déjà télécharger
   un film une fois et y pointer plusieurs plans : il lui manque une
   source de vidéo utilisable.
8. **Le style collage**, en dernier. C'est le plus gros morceau — un
   moteur de composition papier, détourage, tampons — et le seul qui
   demande vraiment un nouveau savoir-faire.

## Ce que nous ne reprendrons pas

**Le métrage YouTube.** Le promo l'annonce dans les API comprises
(« YouTube footage »), et la clé Algrow donne accès à du scraping de
chaînes. La quasi-totalité de YouTube est en tous droits réservés :
découper des vidéos de tiers pour les republier dans un documentaire
monétisé tomberait sous le filtre de licence que nous avons déjà, et il
n'y a pas de raison de le désactiver. Pexels, Wikimedia et le domaine
public couvrent le besoin légalement.
