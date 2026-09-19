# Fresque

Production locale de documentaires narrés, en français, pilotée par Claude Code.

Un sujet en entrée, un `.mp4` monté en sortie. Le tout tourne sur ta machine,
avec tes clés API — il n'y a rien à louer et personne pour couper l'accès.

## Pourquoi ce n'est pas une application

Pas de base de données, pas de compte, pas de service. Chaque étape lit des
fichiers et en écrit d'autres dans `projects/<slug>/`.

Le bénéfice est concret : **tu peux corriger n'importe quel fichier à la main
et relancer à partir de là.** Le script te déplaît ? Tu l'édites, tu relances
l'étape suivante. Rien de ce qui était bon n'est refait, rien n'est perdu
dans un état invisible.

## L'atelier

```bash
python -m fresque serve          # http://127.0.0.1:4321
```

Une page pour voir ce qu'on a et lancer ce qui manque : les projets avec leur
avancement, chaque projet avec ses plans, ses licences et ses alertes, les
templates avec leur direction artistique.

Ce serveur ne détient rien. Il relit les fichiers à chaque page, et pour agir
il n'appelle que les commandes ci-dessous — celles-là mêmes qu'on tape au
terminal. L'arrêter ne perd aucun état ; la sortie de chaque commande reste
dans `projects/<slug>/journal/`.

## Installation

```bash
cp .env.example .env              # puis renseigner les clés
pip install -r pipeline/requirements.txt
npm install --prefix remotion     # moteur de rendu

# Voix locale : modèle Kokoro (~340 Mo, une fois pour toutes)
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
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
python -m fresque align  <slug>   # timings estimés, sans audio
python -m fresque shots  <slug>   # valider le plan visuel
python -m fresque voice  <slug>   # voix Kokoro + timings réels
python -m fresque fetch  <slug>   # sourcer les archives libres
python -m fresque timeline <slug> # construire le montage
python -m fresque render <slug>   # produire le mp4
python -m fresque status <slug>   # où en est le projet
```

`fetch --dry-run` cherche et affiche les archives trouvées sans rien
télécharger — utile pour juger la qualité des requêtes avant de remplir le
disque.

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
| 3a | Voix off Kokoro, durées réelles | fait |
| 4b | Sourcing Wikimedia Commons + Openverse | fait, vérifié en réel |
| 4c | Génération d'images Gemini | à venir |
| 3b | Alignement forcé mot-à-mot | à venir |
| 6 | Motion graphics : cartes, unes de journaux, archives | à venir |
| 7 | Page de validation, miniature, export vers éditeur | à venir |

Les durées de beat sont désormais **mesurées sur l'audio Kokoro**, donc les
coupes tombent exactement là où la narration change. Seule la position d'un
mot à l'intérieur d'un beat reste estimée, ce qui n'affecte que les
sous-titres.

Le sourcing Wikimedia tourne contre l'API réelle : 8 plans sur 8 sourcés,
licences libres uniquement, sans dépasser les limites de débit du service.

**Temps de rendu** : mesuré à 0,053 s par frame sur 4 cœurs, soit environ
1,6× la durée de la vidéo. Remotion plafonne la concurrence au nombre de
cœurs, donc le temps décroît proportionnellement : sur 8 cœurs, un
documentaire de 15 min se rend en une douzaine de minutes.

Tests : `PYTHONPATH=pipeline python3 -m pytest pipeline/tests -q`

---

Architecture et conventions détaillées : [`CLAUDE.md`](CLAUDE.md).
