---
name: fresque-script
description: Écrit la narration d'un documentaire Fresque à partir du brief et de la recherche — découpée en beats numérotés, calibrée en durée, optimisée pour la synthèse vocale française. Produit `02-script.md`, premier checkpoint humain du pipeline. À utiliser après `fresque-recherche`, ou quand l'utilisateur demande d'écrire, réécrire ou retravailler le script d'un projet Fresque.
---

# Écriture du script

Produire `projects/<slug>/02-script.md` à partir de `00-brief.md` et
`01-research.md`. C'est le **checkpoint 1** : le fichier sera lu et corrigé
par un humain avant toute dépense d'API.

Lire `projet.yaml` pour connaître le template, puis `templates/<template>.yaml` : ses champs `meta.registre`, `meta.structure_narrative` et `meta.interdits_specifiques` priment sur les consignes génériques de ce skill.

Lire `fresque.config.yaml` : `mots_par_minute`, `duree_cible_min`,
`relance_retention_s` et `hook_s` pilotent l'écriture.

## Ce qui distingue une narration documentaire

Ce texte ne sera **jamais lu**. Il sera **entendu**, une seule fois, sans
possibilité de revenir en arrière. Tout découle de là :

- Une idée par phrase. Le spectateur ne peut pas relire.
- Le sujet avant le verbe, et vite. Les longues subordonnées avant le verbe
  principal se perdent à l'oral.
- Les chiffres sont ancrés : « trois mille deux cents tonnes — le poids d'un
  Airbus à vide ». Un chiffre nu ne laisse aucune trace.
- Le silence est un outil. Une phrase courte isolée après un paragraphe dense
  frappe plus fort que n'importe quel adjectif.
- On ne commente pas les faits, on les ordonne. L'émotion vient du montage
  des informations, pas des adjectifs qu'on met dessus.

## Procédure

**1. Budget de mots.** `duree_cible_min × mots_par_minute` = budget total.
Répartir par acte selon le brief. Le noter en tête de fichier.

**2. Écrire le hook en premier**, et le réécrire trois fois. Les quinze
premières secondes décident du reste. Un hook réussi pose un fait précis et
troublant, sans le résoudre, et sans annoncer qu'il va être résolu.

Trois contraintes, vérifiées par `fresque lint` :

- **`B001` tient dans `hook_s`**, soit `hook_s × mots_par_minute / 60` mots.
  Ce qui dépasse appartient à `B002`.
- **La première phrase fait vingt mots au plus.** Le fait qui fait rester
  tombe d'un bloc, pas au bout de trois subordonnées.
- **Aucune question dans `B001`.** On pose un fait.

Le fait retenu est le plus dérangeant dont on dispose, pourvu qu'il soit
exact et sourcé dans `01-research.md`. Le brief a déjà choisi lequel et a
noté l'accroche de huit mots qui l'accompagnera à l'écran : s'y tenir.

**3. Écrire acte par acte**, en gardant le compte de mots.

**4. Placer les relances.** Tous les `relance_retention_s` secondes au
maximum — c'est-à-dire tous les ~`relance_retention_s × mots_par_minute / 60`
mots — il faut un changement d'état : une révélation, une question ouverte,
un changement de rythme, un changement de lieu ou d'échelle. Les marquer
dans la colonne de contrôle en fin de fichier.

**5. Lancer `python -m fresque lint <slug>`** et corriger jusqu'à ce qu'il ne
reste aucune violation bloquante. Ce n'est pas optionnel : les règles de ce
skill y sont vérifiées mécaniquement, et l'utilisateur ne doit relire qu'un
script qui passe déjà cette barre. Recommencer autant de fois que nécessaire.

**6. Présenter à l'utilisateur** : le compte de mots réel vs cible, les
points où l'on s'est écarté du brief et pourquoi, et les deux ou trois
passages dont on est le moins sûr. Puis s'arrêter — c'est un checkpoint.

## Format de `02-script.md`

Le fichier est parsé par le pipeline. **La structure ci-dessous est un
contrat, pas une suggestion.**

```markdown
# Script — <titre>

- **mots** : <réel> / <budget> · **durée estimée** : <n> min <n> s
- **statut** : brouillon | validé

---

## Acte I — <titre>

### B001
> intention: <une ligne — ce qu'on voit pendant ce beat>
Le texte de la narration. Une ou plusieurs phrases, en paragraphes.
Tel qu'il sera prononcé, mot pour mot.

### B002
> intention: <...>
...
```

Règles de format, strictes :

- Les beats sont numérotés `B001`, `B002`… en continu à travers tout le
  document, sans trou et sans reprise à chaque acte.
- Un beat = un plan visuel = 10 à 25 secondes de narration (soit ~25 à 60
  mots). Un beat plus long n'est pas tenable visuellement ; plus court, le
  montage devient haché.
- La ligne `> intention:` est obligatoire et fait **une seule ligne**. Elle
  décrit ce que le spectateur voit, pas ce qu'il entend.
- Le corps du beat ne contient **que le texte prononcé**. Aucune didascalie,
  aucun crochet, aucune indication de mise en scène — tout cela partirait
  tel quel dans la synthèse vocale.

## Écrire pour la synthèse vocale française

Ces règles ne sont pas cosmétiques : chaque violation produit une erreur
audible dans le fichier final, qu'il faudra corriger à la main.

**À écrire en toutes lettres :**

| Ne pas écrire | Écrire |
|---|---|
| `01h23` | `une heure vingt-trois` |
| `%` | `pour cent` |
| `km/h`, `m²`, `°C` | `kilomètres-heure`, `mètres carrés`, `degrés` |
| `M. Dupont`, `Dr Faure` | `Monsieur Dupont`, `le docteur Faure` |
| `n°4`, `§3` | `numéro quatre`, `paragraphe trois` |
| `1er`, `2e` | `premier`, `deuxième` |
| `&`, `+`, `=` | `et`, `plus`, `égale` |

**Les années en chiffres sont correctement lues** (`1986`, `2004`) et
restent plus lisibles à la relecture humaine. Les garder ainsi.

**Acronymes.** Ceux qui se lisent comme un mot s'écrivent normalement
(`OTAN`, `SIDA`). Ceux qui s'épellent se ponctuent : `U.R.S.S.`, `F.B.I.`,
`E.D.F.`. Sans quoi la synthèse tranchera au hasard.

**Noms propres étrangers.** Quand la prononciation française attendue diffère
de l'orthographe, écrire la forme phonétique dans le texte et signaler le
choix à l'utilisateur au moment de présenter le script.

**Ponctuation = respiration.** Le point produit une vraie pause, la virgule
une courte. Les points de suspension et le tiret cadratin donnent des
résultats imprévisibles : les éviter. Pour un silence appuyé, faire une
phrase de trois mots sur sa propre ligne.

**Pas de parenthèses.** Elles sont lues à plat et cassent la phrase. Ce qui
est entre parenthèses est soit une phrase à part entière, soit à supprimer.

**Citations.** Isoler toute citation dans son propre beat, en annonçant qui
parle avant. La synthèse ne changera pas de voix — c'est la construction de
la phrase qui doit le faire comprendre.

## Traitement des faits

- Ce qui est marqué contesté dans `01-research.md` est énoncé comme contesté.
  La formulation exacte est indiquée dans la colonne « Comment le script doit
  traiter » de la recherche : la respecter.
- Ne jamais introduire un fait absent de `01-research.md`. En cas de manque,
  s'arrêter et le signaler plutôt que de combler. C'est ainsi qu'un
  documentaire se fait démonter en commentaires.
- Les trous documentaires s'assument à voix haute : « on ne sait pas ce qui
  s'est dit dans cette pièce » est une phrase de documentaire. L'inventer ne
  l'est pas.

## Contrôle

Avant de présenter le script, le relire une fois **à voix haute, dans sa
tête**, et vérifier :

- [ ] Le hook tient en `hook_s` secondes et pose un fait, pas une question.
- [ ] Aucune phrase ne dépasse 25 mots. Les couper.
- [ ] Aucune phrase ne demande de reprendre son souffle en cours de route.
- [ ] Chaque chiffre important a son ordre de grandeur concret.
- [ ] Une relance au moins tous les `relance_retention_s` secondes.
- [ ] Chaque acte se termine sur une question ouverte, sauf le dernier.
- [ ] Le pivot du brief est bien présent, et il est audible.
- [ ] Aucun interdit du brief n'a été enfreint.
- [ ] Aucune didascalie n'a survécu dans le corps d'un beat.
- [ ] Le compte de mots est dans la tolérance de `fresque.config.yaml`.
- [ ] Tout beat fait entre 25 et 60 mots.

Les points de cette liste qui peuvent l'être sont vérifiés par
`python -m fresque lint` : longueur des beats et des phrases, pièges de
synthèse vocale, formules proscrites, budget de mots, espacement des
relances. **Lancer le lint plutôt que de les vérifier à l'œil** — il ne
passe rien.

Le reste ne se vérifie pas mécaniquement et reste ton travail : le hook pose
un fait plutôt qu'une question, chaque acte se termine sur une question
ouverte, le pivot est présent et audible, aucune phrase ne demande de
reprendre son souffle en cours de route.

Terminer `02-script.md` par une section `## Contrôle` avec ces points-là,
plus un tableau des relances (numéro de beat et nature). L'utilisateur doit
pouvoir vérifier le travail sans relire le script en entier.
