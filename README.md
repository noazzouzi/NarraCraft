# Fresque

Production locale de documentaires narrés, en français, pilotée par Claude Code.

Un sujet en entrée, un `.mp4` monté en sortie. Le tout tourne sur ta machine,
avec tes clés API — il n'y a rien à louer et personne pour couper l'accès.

## Pourquoi ce n'est pas une application

Pas de serveur, pas de base de données, pas d'interface web. Chaque étape lit
des fichiers et en écrit d'autres dans `projects/<slug>/`.

Le bénéfice est concret : **tu peux corriger n'importe quel fichier à la main
et relancer à partir de là.** Le script te déplaît ? Tu l'édites, tu relances
l'étape suivante. Rien de ce qui était bon n'est refait, rien n'est perdu
dans un état invisible.

## Installation

```bash
cp .env.example .env   # puis renseigner les clés
```

Une seule clé est nécessaire : **Gemini**, pour les images. La voix tourne en
local avec Kokoro, gratuitement et sans limite. **ElevenLabs** est optionnel,
pour la finition d'une vidéo qu'on publie.

Il n'y a volontairement pas de clé Anthropic : Claude Code est lui-même le
runtime LLM du projet. Le script, la recherche et le montage ne coûtent donc
rien de plus que ton abonnement.

## Utilisation

```bash
claude
> /fresque Le naufrage du Titanic vu depuis la salle des machines
```

Le pipeline s'arrête à deux endroits, et deux seulement :

1. **après le script** — un mauvais script gâche la voix et cent cinquante images ;
2. **après le plan visuel** — dernier point avant de dépenser en API.

Entre ces deux points et jusqu'au fichier final, rien ne t'interrompt.

## Coût

Environ **2,50 à 4 € par documentaire de quinze minutes**, presque
entièrement en génération d'images — la voix locale ne coûte rien. Le pipeline cherche d'abord dans les archives libres
(Wikimedia Commons, Archive.org, Gallica, Library of Congress) et ne génère
que ce qui manque réellement. Un plafond de sécurité est défini dans
`fresque.config.yaml`.

## Réglages

Tout se règle dans `fresque.config.yaml` : débit de narration, durée cible,
structure en actes, voix, modèle d'image, style de mouvement, budget maximal.

## État d'avancement

| Jalon | Contenu | État |
|---|---|---|
| 1 | Structure, configuration, conventions | fait |
| 2 | Écriture : brief → recherche → script | fait |
| 3 | Voix off (Kokoro / ElevenLabs) et alignement forcé | à venir |
| 4 | Plan visuel, archives, génération d'images | à venir |
| 5 | Timeline et rendu Remotion | à venir |
| 6 | Motion graphics : cartes, unes de journaux, archives | à venir |
| 7 | Page de validation, miniature, export vers éditeur | à venir |

Le jalon 2 est utilisable seul et ne coûte rien : on peut écrire et itérer
sur autant de scripts qu'on veut avant de brancher la moindre API payante.

---

Architecture et conventions détaillées : [`CLAUDE.md`](CLAUDE.md).
