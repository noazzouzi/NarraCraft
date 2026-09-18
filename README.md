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
cp .env.example .env              # puis renseigner les clés
pip install -r pipeline/requirements.txt
npm install --prefix remotion     # moteur de rendu
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

Les étapes mécaniques s'appellent aussi à la main, sur n'importe quel projet :

```bash
python -m fresque align  <slug>   # timings depuis le script
python -m fresque shots  <slug>   # valider le plan visuel
python -m fresque timeline <slug> # construire le montage
python -m fresque render <slug>   # produire le mp4
python -m fresque status <slug>   # où en est le projet
```

`python -m fresque placeholders <slug>` fabrique des visuels de substitution :
tu peux regarder le montage, juger le rythme et le découpage **avant** d'avoir
sourcé ou généré la moindre image.

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
| 5 | Timeline et rendu Remotion | fait |
| 4a | Plan visuel (skill) et validation | fait |
| 4b | Sourcing Wikimedia Commons | écrit, non testé |
| 4c | Génération d'images Gemini | à venir |
| 3 | Voix off (Kokoro / ElevenLabs) et alignement forcé | à venir |
| 6 | Motion graphics : cartes, unes de journaux, archives | à venir |
| 7 | Page de validation, miniature, export vers éditeur | à venir |

En attendant la voix, les timings sont **estimés** à partir du compte de mots.
Le format est identique à celui de l'alignement forcé, donc brancher la voix
plus tard ne changera pas une ligne du montage.

Le sourcing Wikimedia est écrit mais n'a pas pu être exercé contre l'API :
elle est bloquée depuis l'environnement où il a été développé.

Tests : `PYTHONPATH=pipeline python3 -m pytest pipeline/tests -q`

---

Architecture et conventions détaillées : [`CLAUDE.md`](CLAUDE.md).
