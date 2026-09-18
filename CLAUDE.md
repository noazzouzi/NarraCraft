# Fresque

Pipeline local de production de documentaires narrés (10–20 min, français),
piloté par Claude Code.

## Principe fondateur

**Ce projet n'est pas une application. C'est un atelier de fichiers.**

Il n'y a ni serveur, ni base de données, ni machine à états. Chaque étape lit
des fichiers et en écrit d'autres dans `projects/<slug>/`. Toute étape est
donc reprenable, inspectable, et corrigeable à la main.

Corollaire à respecter absolument : **si une étape a besoin d'un état qui
n'est pas dans un fichier du projet, le design est faux.** Ne jamais stocker
un résultat intermédiaire uniquement dans le contexte de la conversation.

## Répartition des rôles

| Qui | Quoi |
|---|---|
| **Claude Code (skills)** | Jugement : angle, recherche, script, choix des plans, prompts d'image, critique qualité |
| **Scripts `pipeline/`** | Mécanique : appels API, calculs de timecodes, ffmpeg, rendu |

Règle non négociable : **aucun calcul de timing n'est fait par un LLM.**
Les durées, offsets et synchronisations sont calculés par du code, à partir
des timestamps réels renvoyés par le TTS. C'est la cause n°1 de désynchro
dans ce genre de pipeline.

## Runtime LLM

Il n'y a **pas de clé API Anthropic** dans ce projet. Claude Code *est* le
runtime LLM : les étapes de jugement sont des Skills exécutées dans la
session. Les seules APIs payantes appelées par du code sont ElevenLabs (voix)
et Gemini (images).

Conséquence à garder en tête pour toute évolution : chaque étape LLM doit
produire un **fichier au format stable et documenté**. Le jour où l'on veut
du batch non-supervisé, il suffira d'écrire un runner API qui produit les
mêmes fichiers. Ne jamais coupler une étape LLM à la suivante autrement que
par son fichier de sortie.

## Anatomie d'un projet

```
projects/<slug>/
├── 00-brief.md       angle, promesse, structure, durée cible
├── 01-research.md    faits sourcés + pistes d'archives
├── 02-script.md      narration découpée en beats          ← CHECKPOINT 1
├── 03-shots.json     plan visuel par beat                 ← CHECKPOINT 2
├── 04-audio/         voix.mp3 + alignment.json (mot-à-mot)
├── 05-visuals/       images + assets.json (licences)
├── 06-timeline.json  source de vérité du montage
├── 07-out/           video.mp4, thumbnail.png, captions.srt
└── review.html       page de validation (statique, sans serveur)
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
