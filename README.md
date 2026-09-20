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

Une seule clé est nécessaire, pour les images. La voix tourne en local avec
Kokoro, gratuitement et sans limite.

Deux portes mènent aux mêmes modèles d'image, et le choix est comptable :

| `visuels.generation.provider` | Ce qu'il faut | Pourquoi |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` | le plus simple : une clé, rien d'autre |
| `vertex` | une clé **ou** un jeton | le crédit d'essai de 300 $ ne paie **plus** AI Studio depuis le 2 mars 2026, mais il paie Vertex |

Vertex accepte deux justificatifs, et une seule adresse les sert tous les
deux — mesuré, une clé d'API porte bien un projet
(`docs/etude-vertex.md`). La clé passe avant le jeton si les deux sont là.

```bash
# soit un jeton, qui expire seul et se rattache à des rôles — préférable
gcloud auth application-default login

# soit une clé, pour une machine sans session interactive
echo "VERTEX_API_KEY=…" >> .env

python -m fresque essai-image "un couloir inondé"   # une image, ~0,07 $
```

`VERTEX_PROJECT` est facultatif : sans lui, le serveur retrouve le projet
depuis le justificatif. Le nommer rend seulement l'appel lisible dans les
journaux.

`python -m fresque images --list-models` vérifie gratuitement le jeton, le
projet, la région, l'activation de l'API et les identifiants de modèles —
mais **seulement avec un jeton** : la route des fiches de modèle n'accepte
pas les clés d'API. Avec une clé, la seule vérification est une génération.

`essai-image` génère **une** image, sans projet Fresque, et imprime ses
dimensions réelles — le seul endroit où l'on constate si le format demandé a
été honoré. Un modèle peut l'ignorer sans le dire : mesuré,
`gemini-2.5-flash-image` rend 1344 px quand on lui demande du 2K.

Deux clés optionnelles : **Pexels** (gratuite, pour le métrage vidéo libre)
et **ElevenLabs** (payante, pour la finition d'une vidéo qu'on publie).

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
python -m fresque aligner <slug>  # position réelle de chaque mot (local)
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

## Les planches de collage

Le style « Vox » — une photographie d'archive collée sur du papier, avec son
tampon déchiré, son liseré blanc et ses accents découpés — est **composé par
le pipeline**, pas généré par un modèle d'image.

```json
{"beat":"B006","type":"collage","requete":"palais justice Paris",
 "intention":"le tribunal, le jour du verdict","mouvement":"zoom_in"}
```

Le calcul est fait avant le montage : la mise en page atterrit dans
`06-timeline.json`, où elle se relit et se corrige à la main. Les pièces
existent séparément jusqu'à la dernière image, donc elles **bougent à des
vitesses différentes** selon leur profondeur — ce qu'une affiche générée, dont
les couches sont cuites dans les pixels, ne peut pas faire.

Le choix a été tranché par la mesure, pas par principe. Quatre modèles
comparés sur le même prompt (`docs/essai-collage.md`) : SDXL Turbo inventait
du faux texte, z-image alignait des pictogrammes, et le meilleur — Nano
Banana 2 Lite, quatre secondes et 0,0336 $ l'image — rendait une belle
planche qu'on ne pouvait ni animer ni retoucher. À quatre-vingts planches par
documentaire, c'est 2,79 $ pour une image morte.

Le template `documentaire-collage` en fait une thématique complète, **sans
une ligne de composant supplémentaire** : papier, encres, trame, parallaxe,
sous-titres en encre sombre, panneaux accordés.

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
| 3b | Alignement forcé mot-à-mot | fait, vérifié en réel |
| 6 | Motion graphics : cartes, unes de journaux, archives | à venir |
| 6b | Planches de collage, style Vox | fait, vérifié au rendu |
| 7 | Page de validation, miniature, export vers éditeur | page faite |

Les durées de beat sont **mesurées sur l'audio Kokoro**, et depuis
`fresque aligner` la position de chaque mot l'est aussi. L'écart valait la
peine : l'estimation syllabique tombait à 305 ms de la position réelle en
médiane, et jusqu'à 1,7 s. L'aligneur tourne en local, gratuitement.

`torch` et `torchaudio` sont **optionnels** — sans eux, le pipeline garde
les positions estimées et tout le reste fonctionne :

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Le sourcing Wikimedia tourne contre l'API réelle : 8 plans sur 8 sourcés,
licences libres uniquement, sans dépasser les limites de débit du service.

**Temps de rendu** : mesuré à 0,053 s par frame sur 4 cœurs, soit environ
1,6× la durée de la vidéo. Remotion plafonne la concurrence au nombre de
cœurs, donc le temps décroît proportionnellement : sur 8 cœurs, un
documentaire de 15 min se rend en une douzaine de minutes.

Tests : `PYTHONPATH=pipeline python3 -m pytest pipeline/tests -q`

---

Architecture et conventions détaillées : [`CLAUDE.md`](CLAUDE.md).
