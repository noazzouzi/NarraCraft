# Fresque

Pipeline local de production de documentaires narrés (10–20 min, français),
piloté par Claude Code.

## Principe fondateur

**Ce projet n'est pas une application. C'est un atelier de fichiers.**

Il n'y a ni base de données, ni machine à états. Chaque étape lit des
fichiers et en écrit d'autres dans `projects/<slug>/`. Toute étape est donc
reprenable, inspectable, et corrigeable à la main.

Corollaire à respecter absolument : **si une étape a besoin d'un état qui
n'est pas dans un fichier du projet, le design est faux.** Ne jamais stocker
un résultat intermédiaire uniquement dans le contexte de la conversation.

### Le serveur, et ce qu'il n'a pas le droit d'être

`fresque serve` ouvre l'atelier dans un navigateur. C'est une exception
assumée au « pas de serveur » d'origine, et elle ne tient qu'à trois
conditions, qui ne sont pas négociables :

1. **Il ne mémorise rien.** Chaque page relit les fichiers. Aucun cache,
   aucun index, aucune session. Le tuer et le relancer ne perd rien.
2. **Il n'implémente aucune étape.** Pour agir, il lance
   `python -m fresque <commande>` en sous-processus. Tout ce qu'il sait
   faire se refait au terminal, à l'identique.
3. **Toute sortie de commande devient un fichier**, dans
   `projects/<slug>/journal/`. Ce que le serveur garde en mémoire n'est
   jamais que la poignée d'un processus vivant.

Le jour où l'on est tenté d'ajouter au serveur un état qui lui est propre —
une file d'attente, un utilisateur, un cache de rendu — c'est le signe qu'il
manque un fichier, pas une table. Le pipeline doit rester utilisable sans
lui.

## Répartition des rôles

| Qui | Quoi |
|---|---|
| **Claude Code (skills)** | Jugement : angle, recherche, script, choix des plans, prompts d'image, critique qualité |
| **Scripts `pipeline/`** | Mécanique : appels API, calculs de timecodes, mises en page, ffmpeg, rendu |

Règle non négociable : **aucun calcul de timing n'est fait par un LLM.**
Les durées, offsets et synchronisations sont calculés par du code, à partir
des timestamps réels renvoyés par le TTS. C'est la cause n°1 de désynchro
dans ce genre de pipeline.

## Runtime LLM

Il n'y a **pas de clé API Anthropic** dans ce projet. Claude Code *est* le
runtime LLM : les étapes de jugement sont des Skills exécutées dans la
session. La seule API payante systématiquement appelée par du code est
Gemini (images) ; la voix tourne en local par défaut (Kokoro), ElevenLabs
n'étant qu'une option de finition.

Conséquence à garder en tête pour toute évolution : chaque étape LLM doit
produire un **fichier au format stable et documenté**. Le jour où l'on veut
du batch non-supervisé, il suffira d'écrire un runner API qui produit les
mêmes fichiers. Ne jamais coupler une étape LLM à la suivante autrement que
par son fichier de sortie.

## Rythme, ouverture, transitions

Trois règles de montage vivent dans le code plutôt que dans les skills,
parce qu'un premier documentaire complet a montré que la prose ne suffit pas.

**La durée d'un plan a un plafond.** `montage.duree_plan_max_s`. Vérifié deux
fois : par `shots.density()` au checkpoint 2, depuis le compte de mots, donc
avant toute dépense ; puis par `timeline.check()` sur l'audio réel, qui est le
seul endroit où un montage lent est vraiment attrapable. Les deux regardent le
plan le plus **lourd** du beat, jamais la moyenne.

**Le premier plan porte le sujet et une phrase.** `shots.ouverture()` refuse
un documentaire qui ouvre sur un panneau graphique ou sans `accroche`, et
`fresque shots` sort en erreur. C'est la seule chose qui mérite de faire
échouer un checkpoint : tout le reste ne concerne que les spectateurs qui ont
passé les quinze premières secondes.

**La manière dont un plan arrive est calculée, pas choisie.**
`timeline._transition()` la déduit de la place du plan dans le récit — même
beat, beat suivant, acte suivant, panneau graphique — et rien d'autre. Un LLM
ne décide d'aucune transition, au même titre qu'il ne calcule aucun timecode.

Les sons de transition sont **synthétisés localement** par `fresque.sons`, à
partir d'une graine fixe. Aucun téléchargement, aucune licence à suivre,
aucun réseau — et des fichiers identiques d'une machine à l'autre.

**Une planche de collage est composée, jamais générée.** `fresque.collage`
calcule la mise en page — quelles pièces, où, à quelle profondeur — et le
moteur ne fait que la dessiner. Quatre modèles d'image ont été mesurés avant
d'en arriver là (`docs/essai-collage.md`) : le meilleur rendait une planche
correcte en quatre secondes pour 0,0336 $, et restait un aplat cuit dans des
pixels. On ne peut ni animer ses couches séparément, ni changer sa palette
avec le template, ni corriger la position d'une pièce.

La règle qui en découle vaut au-delà du collage : **avant de payer un modèle
pour dessiner quelque chose, vérifier que ce quelque chose n'est pas
composable.** Un élément composé est plus cher à écrire une fois, et moins
cher à toutes les autres — en argent, en temps de rendu, et en contrôle.

## Voix et alignement

La voix et l'alignement mot-à-mot sont **deux étapes distinctes**, et c'est
délibéré.

Le moteur TTS produit un fichier audio par beat. Un **aligneur forcé**
distinct réaligne ensuite le texte du script — qu'on connaît déjà
exactement — sur l'audio produit, pour écrire `alignment.json`.

Deux raisons, et elles comptent :

1. **C'est plus précis.** On ne devine pas la transcription, on possède la
   vérité terrain du texte. On ne fait que chercher où chaque mot tombe.
2. **Ça rend les moteurs interchangeables.** Kokoro en local pour itérer
   gratuitement, ElevenLabs pour la finition — sans qu'une seule ligne du
   montage en aval ne change.

Règle qui en découle : **ne jamais consommer les timestamps renvoyés par un
moteur TTS.** La seule source de vérité temporelle est `alignment.json`, dont
le champ `source` dit toujours d'où viennent les nombres :

| `source` | Bornes de beat | Position des mots | Coût |
|---|---|---|---|
| `estimate` | estimées | estimées | nul, sans audio |
| `kokoro` | **mesurées sur l'audio** | estimées par syllabes | nul, local |
| `forced` | mesurées | **mesurées** | local, gratuit |

`kokoro` mesure la longueur réelle de la forme d'onde produite — ce n'est pas
un timestamp rapporté par le moteur. Les coupes du montage tombent donc au bon
endroit dès `voice` ; seule la position d'un mot *à l'intérieur* d'un beat
reste approchée, ce qui n'affecte que les sous-titres.

`fresque aligner` remplace cette approximation par une mesure. L'écart
n'était pas anecdotique : relevé sur un montage réel, la position estimée
d'un mot tombait à **305 ms** de sa position réelle en médiane, et jusqu'à
1,7 s. Quatre mots sur cinq étaient décalés de plus de 150 ms. Un
surlignage mot à mot ne tient pas là-dessus.

L'aligneur tourne en local (modèle MMS, 1,2 Go, téléchargé une fois) et ne
coûte rien. `torch` et `torchaudio` restent **optionnels** : sans eux le
pipeline tourne en `kokoro`, comme avant.

## Templates

Un **template** est une thématique de documentaire : criminel, historique,
entreprise, célébrité. Il définit le registre d'écriture, la structure
narrative, les interdits propres au genre, le rythme, les sources
privilégiées et la direction artistique complète.

```
templates/documentaire-historique.yaml
```

Un template est une **surcouche** de `fresque.config.yaml` : il ne redéfinit
que ce qui change. Les mappings fusionnent en profondeur, les listes
remplacent — redéfinir un ordre de sources signifie le remplacer, pas y
ajouter. Les champs `meta.*` sont en prose et lus par les skills ; tout le
reste est lu par le code.

Chaque projet enregistre son template dans `projet.yaml`, et toute commande
l'applique en l'ouvrant. Un projet reste donc auto-descriptif : le relancer
six mois plus tard reproduit la même chose.

**Règle qui décide de la viabilité du projet : un template est de la donnée,
jamais du code.** Il n'a pas de composant Remotion à lui. La direction
artistique — palette, typographie, amplitude des mouvements, grain, vignette
— voyage dans `06-timeline.json` sous la clé `style`, et le moteur ne fait
que l'appliquer. Si une thématique semble exiger son propre composant, c'est
le signe qu'il manque un paramètre, pas un composant. Sans quoi la quatrième
thématique laisse quatre moteurs divergents à maintenir, et le projet meurt.

## Anatomie d'un projet

```
projects/<slug>/
├── projet.yaml       le template utilisé
├── 00-brief.md       angle, promesse, structure, durée cible
├── 01-research.md    faits sourcés + pistes d'archives
├── 02-script.md      narration découpée en beats          ← CHECKPOINT 1
├── 03-shots.json     plan visuel par beat                 ← CHECKPOINT 2
├── 04-audio/         beats/B001.wav… + alignment.json (mot-à-mot)
├── 05-visuals/       images + assets.json (licences)
├── 06-timeline.json  source de vérité du montage
├── 07-out/           video.mp4, thumbnail.png, captions.srt
├── journal/          sortie des commandes lancées depuis l'atelier
└── review.html       page de validation (statique, ouvrable en file://)
```

Les fichiers numérotés se lisent dans l'ordre. Une étape ne lit **que** les
fichiers qui la précèdent, jamais ceux qui la suivent.

## Checkpoints humains

Deux, et deux seulement :

1. **Après `02-script.md`** — un mauvais script gâche la voix et 150 images.
2. **Après `03-shots.json`** — dernier point avant de dépenser en API.

Entre ces points et jusqu'au mp4, le pipeline tourne sans interruption.
Ne pas ajouter de checkpoint sans raison explicite de l'utilisateur.

## Skills

| Skill | Entrée | Sortie |
|---|---|---|
| `fresque-brief` | un titre ou un sujet | `00-brief.md` |
| `fresque-recherche` | `00-brief.md` | `01-research.md` |
| `fresque-script` | `00-brief.md`, `01-research.md` | `02-script.md` |

(Les skills des jalons suivants — plan visuel, voix, visuels, montage — sont
à venir. Voir `README.md` pour l'état d'avancement.)

## Style de réponse

Répondre court. L'utilisateur suit une discussion longue, pas un rapport.

- Phrases simples, une idée par phrase.
- Puces plutôt que paragraphes.
- Ne dire que ce qui change quelque chose pour lui : un résultat, une
  décision, un blocage, une question.
- Pas de récapitulatif de ce qu'il vient de lire. Pas de justification d'un
  choix qu'il n'a pas contesté. Pas de reformulation de sa demande.
- Un tableau seulement quand il remplace du texte, jamais quand il s'ajoute.
- Signaler les échecs et les réserves, brièvement, sans les développer tant
  qu'on ne les creuse pas.

Le détail va dans les fichiers du dépôt et les messages de commit, pas dans
la réponse.

## Conventions

- **Langue de production : français.** Les scripts, briefs et recherches sont
  en français. Le code et les commentaires de code sont en anglais.
- **Toute affirmation factuelle porte une source.** Pas d'exception. Un fait
  sans URL vérifiable n'entre pas dans `01-research.md`.
- **Tout asset visuel porte sa licence.** Champ obligatoire dans `assets.json`.
- Les slugs de projet sont en kebab-case sans accent : `tchernobyl-nuit-du-26`.
- Ne jamais écrire dans `projects/` autre chose que via les skills ou le
  pipeline. Ce dossier est ignoré par git (sauf `.gitkeep`).

## Réglages

Tous les paramètres de production (débit de narration, durées cibles, voix,
modèles d'image, budget) vivent dans `fresque.config.yaml`. Ne jamais coder
en dur une valeur qui a sa place dans ce fichier.
