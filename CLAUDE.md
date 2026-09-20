# Fresque

Pipeline local de production de documentaires narrés (10–20 min, français),
piloté par Claude Code.

## Démarrer

```bash
cd pipeline && python -m fresque doctor      # modèles, node_modules, clés
python -m pytest pipeline/tests -q           # depuis la RACINE, toujours
```

Les deux répertoires ne sont pas interchangeables : depuis la racine,
`python -m fresque` répond `No module named fresque` ; depuis `pipeline/`,
deux tests échouent — ceux qui lisent `remotion/src/` par chemin relatif.
Installation : `README.md`.

Aucune commande ne lit `.env` : les clés vivent dans l'environnement du
processus. Et une commande dont le code de sortie décide de quelque chose ne
passe jamais par un pipe : `| tail` rend 0 pendant que des tests échouent.

## Principe fondateur

**Ce projet n'est pas une application. C'est un atelier de fichiers.**

Il n'y a ni base de données, ni machine à états. Chaque étape lit des
fichiers et en écrit d'autres dans `projects/<slug>/`. Toute étape est donc
reprenable, inspectable, et corrigeable à la main.

Corollaire à respecter absolument : **si une étape a besoin d'un état qui
n'est pas dans un fichier du projet, le design est faux.** Ne jamais stocker
un résultat intermédiaire uniquement dans le contexte de la conversation.

`fresque serve` est la seule exception au « pas de serveur », et il ne
détient rien. Son contrat est en tête de `pipeline/fresque/serveur.py` : le
lire avant d'y toucher.

## Répartition des rôles

Claude Code juge : angle, recherche, script, choix des plans, prompts
d'image, critique qualité. `pipeline/` exécute : appels API, timecodes, mises
en page, rendu. Il n'y a pas de clé Anthropic — Claude Code *est* le runtime
LLM, et chaque étape de jugement produit un fichier au format stable qui
**ne se couple jamais à la suivante autrement que par ce fichier.**

Règle non négociable : **aucun calcul de timing n'est fait par un LLM.** Les
durées sont calculées par du code, à partir de la **longueur réelle de
l'audio produit** — jamais d'un timestamp rapporté par un moteur. La seule
source de vérité temporelle est `04-audio/alignment.json`, dont le champ
`source` dit d'où viennent les nombres (`fresque.aligner`).

## Commandes

Dix-huit, que `--help` liste. Quatre choses qu'il ne dit pas :

- `images` et `essai-image` sont **les seules commandes payantes** ; tout le
  reste est local et gratuit, `fetch` et `rushes` compris.
- `align` et `aligner` diffèrent. Une fois `voice` passé, on ne relance plus
  jamais `align` : il rétrograde `alignment.json` et efface des mesures.
- `shots` est la seule commande qui refuse un checkpoint ; `placeholders` la
  seule qui donne un montage regardable sans rien dépenser.
- Le seul plafond de dépense armé est
  `visuels.generation.max_images_par_projet` ; `budget.max_eur_par_projet`
  n'est lu par aucune ligne de code.

On ne vérifie jamais une modification de rendu par un rendu complet — environ
1,6× la durée du film : `--frames` et `--scale` sont là pour ça. `--browser`
accepte un Chromium déjà présent, dont le chemin dépend de la machine et ne
s'écrit dans aucun fichier versionné.

## La carte

Ce tableau ne contient que des chemins : c'est ce qui l'empêche de mentir.

| Avant de… | Ouvrir |
|---|---|
| écrire, chercher, découper, illustrer | `.claude/skills/` — chaque front-matter dit ce qu'il produit |
| toucher au serveur | `pipeline/fresque/serveur.py` |
| toucher au rythme, aux panneaux, au collage | `pipeline/fresque/shots.py`, `docs/essai-collage.md` |
| brancher un fournisseur d'images | `README.md`, `docs/etude-vertex.md` |
| toucher à l'alignement | `pipeline/fresque/aligner.py`, `docs/essai-alignement.md` |

## Anatomie d'un projet

```
projects/<slug>/
├── projet.yaml       le template utilisé, et les `reglages` de ce projet
├── 00-brief.md       angle, promesse, structure, durée cible
├── 01-research.md    faits sourcés + pistes d'archives
├── 02-script.md      narration découpée en beats          ← CHECKPOINT 1
├── 03-shots.json     plan visuel par beat                 ← CHECKPOINT 2
├── 04-audio/         beats/B001.wav, voix.wav, alignment.json
│   └── sons/         transitions et lit musical, écrits par `timeline`
├── 05-visuals/       images + assets.json (licences)
├── 06-timeline.json  source de vérité du montage
├── 07-out/           video.mp4
├── journal/          sortie des commandes lancées depuis l'atelier
├── review.html       page de validation (ouvrable en file://)
└── .render/          staging Remotion, jetable, recréé à chaque rendu
```

Les fichiers numérotés se lisent dans l'ordre. Une étape ne lit **que** les
fichiers qui la précèdent, jamais ceux qui la suivent.

Effacer `04-audio/` pour refaire la voix emporte aussi les sons, que
`timeline` avait écrits.

Un projet sans `projet.yaml` tourne sur la configuration de base **sans un
message d'erreur** — plafond de plan à dix secondes au lieu de trois et
demie, débit faux, doctrine de rythme désactivée. Ce fichier s'écrit à la
création, avant tout le reste.

## Checkpoints humains

Deux, et deux seulement :

1. **Après `02-script.md`** — un mauvais script gâche la voix et 150 images.
2. **Après `03-shots.json`** — dernier point avant de dépenser en API.

Entre ces points et jusqu'au mp4, le pipeline tourne sans interruption. Ne
pas ajouter de checkpoint sans raison explicite de l'utilisateur.

Un fichier qui n'a pas passé sa commande n'est pas présenté à l'humain :
`lint` avant le premier, `shots` avant le second.

## Réglages : trois couches

`fresque.config.yaml` → `templates/<nom>.yaml` → `projet.yaml` clé
`reglages`. **Le projet a le dernier mot.** Les mappings fusionnent en
profondeur, les listes remplacent. `fresque template` montre d'où vient
chaque valeur.

Un essai est un réglage de projet : on ne modifie jamais un template pour
itérer, c'est une modification qu'on doit penser à défaire. Et ne jamais
coder en dur une valeur qui a sa place dans une de ces trois couches.

**Règle qui décide de la viabilité du projet : un template est de la donnée,
jamais du code.** Il n'a pas de composant Remotion à lui. La direction
artistique voyage dans `06-timeline.json` sous la clé `style`, et le moteur
ne fait que l'appliquer. Si une thématique semble exiger son propre
composant, c'est le signe qu'il manque un paramètre. Sans quoi la quatrième
thématique laisse quatre moteurs divergents à maintenir, et le projet meurt.

## Ce que le code ne rattrapera pas

Cinq erreurs déjà commises ici. Aucune n'a de fichier qu'on penserait à
ouvrir avant de la commettre : c'est le seul critère qui les garde ici.

**Avant de payer un modèle pour dessiner quelque chose, vérifier que ce
quelque chose n'est pas composable.** Un élément composé est plus cher à
écrire une fois, moins cher à toutes les autres — en argent, en temps de
rendu, et en contrôle (`docs/essai-collage.md`).

**Une métadonnée est une promesse ; le fichier sur le disque est le fait.**
Toute dimension qui décide d'un cadrage se mesure sur le fichier écrit : un
modèle d'image rend 1344 px en disant oui à une demande de 2K.

**Une supposition sur une API externe n'est jamais attrapée par un test**,
parce que le test s'écrit sur la même supposition. On sonde d'abord, et on
note le résultat dans `docs/`.

**Une règle automatique qui se déclenche sur du contenu normal vaut moins que
pas de règle.** Toute vérification nouvelle se mesure d'abord sur du contenu
juste. Si elle crie au loup, on la remplace ou on ne l'écrit pas.

**Un processus long se surveille par son pid**, jamais par une recherche de
texte : `pgrep -f` trouve sa propre ligne de commande et attend un processus
déjà mort. Quatre-vingt-dix minutes perdues.

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

- **Langue de production : français**, y compris les commentaires qui
  expliquent un pourquoi. Les identifiants suivent le domaine : anglais pour
  la mécanique (`build`, `check`, `render`), français pour le métier
  (`plafond_s`, `accroche`, `planche`).
- **Toute affirmation factuelle porte une source.** Pas d'exception. Un fait
  sans URL vérifiable n'entre pas dans `01-research.md`.
- **Tout asset porte sa licence.** Trois conditions cumulatives : usage
  commercial, modification — un Ken Burns en est une —, attribution
  enregistrée. NC et ND sont éliminatoires.
- **Un secret vit dans l'environnement**, jamais dans une conversation, une
  URL ou une sortie de commande : tout ce qui s'imprime depuis l'atelier
  finit dans `journal/`. Un état d'authentification nomme la variable, jamais
  son contenu.
- Slugs en kebab-case sans accent : `tchernobyl-nuit-du-26`.
- Ne jamais écrire dans `projects/` autrement que via les skills ou le
  pipeline. Ce dossier est ignoré par git.

## Ce qui entre ici

Ce fichier avait triplé en dix commits : chaque fonctionnalité y déposait sa
prose. N'entre ici que ce qui change le comportement dans la majorité des
sessions, ou ce qu'un agent ne penserait pas à chercher. Une mesure va dans
`docs/`, une consigne d'étape dans le skill de l'étape, une règle qui doit
tenir dans du code qui sort en erreur.

**Ce qui sort d'ici doit atterrir quelque part de nommé** : un renvoi sans
destination n'est pas une coupe, c'est un oubli. Quatre tests gardent le
fichier honnête — chemins, commandes, réglages, budget de mots.
