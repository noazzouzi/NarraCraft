---
name: fresque-recherche
description: Mène la recherche documentaire d'un projet Fresque sur cinq axes parallèles — chronologie, mécanique, chiffres, contradiction, archives. Écrit un plan, un journal de sources append-only, puis la synthèse `01-research.md`. Reprend où elle s'était arrêtée après un crash. À utiliser après le choix d'une piste, ou quand l'utilisateur demande la recherche ou les sources d'un projet.
---

# Recherche

## RÔLE

Rassembler tout ce sur quoi le script s'appuiera. Aucun fait ne s'invente plus tard.

## ENTRÉE

- `projects/<slug>/pistes.md` — la piste retenue : angle, pivot, preuves.
- `projects/<slug>/00-brief.md` s'il existe.
- Le web : WebSearch et WebFetch. Rien d'autre.

## SORTIE

Trois fichiers, dans cet ordre :

| Fichier | Quoi | Quand |
|---|---|---|
| `01-plan.md` | les cinq axes et leurs questions | écrit **avant** de chercher |
| `01-sources.jsonl` | une ligne par source lue, append-only | pendant |
| `01-research.md` | la synthèse | à la fin |

Le script ne lit que `01-research.md`. Les deux autres existent pour survivre à un crash.

Une ligne de `01-sources.jsonl` :

```json
{"axe":"chiffres","url":"...","titre":"...","date":"2024-03-11","type":"primaire","extrait":"...","sert":"le taux de redevance"}
```

## PROCÉDURE

**1. Écrire `01-plan.md`.** Cinq axes, trois à six questions chacun. Une question est précise et a une réponse : « quel pourcentage du chiffre d'affaires », pas « quelle était la situation financière ».

| Axe | Ce qu'il rapporte |
|---|---|
| Chronologie | dates, heures, ordre exact des faits |
| Mécanique | comment ça marchait concrètement — contrats, règles, procédures |
| Chiffres | montants, volumes, taux, et leur ordre de grandeur parlant |
| Contradiction | ce qui est contesté, les deux versions, qui dit quoi |
| Archives | images libres de droits repérées, jamais téléchargées |

**2. Lancer les cinq axes en parallèle**, un agent par axe, Sonnet 5. Chaque agent lit `01-plan.md`, cherche, et écrit ses lignes dans `01-sources.jsonl`. Un axe qui échoue ne fait pas échouer l'étape : on le note et on continue.

**3. Trier les sources** — Opus 5, jamais Haiku. Écarter les sources qui se recopient, garder la primaire.

**4. Écrire `01-research.md`** — Opus 5.

**5. Dire à l'utilisateur** en trois lignes : ce qui est solide, ce qui est fragile, et si la recherche oblige à changer d'angle.

## REPRISE

Par défaut, on reprend. Au démarrage : lire `01-sources.jsonl`, compter les sources par axe, ne relancer que les axes incomplets. `--recommencer` efface et repart de zéro.

## SOURCES

Une source primaire est le document lui-même, pas l'article qui en parle.

- Dépôts d'entreprise, jugements, rapports parlementaires, transcriptions d'audience, archives d'État.
- **Franchise Disclosure Document** pour toute franchise américaine : public, il contient le taux de redevance exact — souvent le chiffre central du pivot. Sans ce réflexe, la recherche s'arrête à la presse.
- Chercher dans la langue du sujet. Un événement russe, japonais ou allemand a ses meilleures sources — et ses meilleures archives — dans sa langue.
- Wikipédia est un point de départ. Suivre ses notes de bas de page et citer la source primaire.

## RÈGLES

- Aucun fait sans URL. Sans exception.
- Tout fait qui porte le pivot est confirmé par deux sources indépendantes. Une source qui en cite une autre ne compte pas pour deux.
- Ne jamais faire dire à une source ce qu'elle ne dit pas. En cas de doute, citer textuellement.
- Chaque chiffre a son ordre de grandeur concret. Un chiffre nu ne laisse aucune trace à l'oral.
- Viser 10 à 20 détails sensoriels sourcés — heure, météo, bruit, couleur, geste, objet. C'est ce qui rend la narration incarnée, et ça ne s'invente pas plus tard.
- Les archives se repèrent, ne se téléchargent pas : Wikimedia Commons, Archive.org, Gallica. Noter la catégorie exacte, l'URL et la licence.
- Signaler tout de suite si la recherche contredit la piste. Corriger l'angle maintenant coûte moins cher qu'après le script.

## REFUS

- Un fait sans source ne va pas dans « Faits ». Il va dans « Contesté » ou il disparaît.
- Un trou documentaire s'écrit dans « Ce qu'on n'a pas trouvé ». Il ne se comble jamais par déduction.
- Le pivot ne tient sur aucune source solide → s'arrêter et le dire, avant d'écrire la synthèse.

## Format de `01-research.md`

```markdown
# Recherche — <titre>

> Sources : <n> · Primaires : <n> · Faits à deux sources : <n>
> <AAAA-MM-JJ>

## Chronologie
| Quand | Quoi | Source |
|---|---|---|

## Mécanique
<Comment ça marchait, concrètement. Contrats, règles, procédures.> [source](url)

## Personnes
### <Nom> — <rôle en quatre mots>
<Seulement ce qui sert l'angle.> [source](url)

## Chiffres
| Valeur | Ce que c'est | Ordre de grandeur parlant | Source |
|---|---|---|---|

## Citations
> « <texte exact> »
> — <qui>, <quand>, [source](url)

## Détails sensoriels
- <détail> [source](url)

## Contesté ou incertain
| Affirmation | Position A | Position B | Comment le script doit traiter |
|---|---|---|---|

<La dernière colonne est une instruction pour le script, pas une note.>

## Archives repérées
- **Wikimedia Commons** — catégorie `<nom exact>` — <licence> — <url>
- **Archive.org** — collection `<id>` — <url>
- **Gallica** — recherche `<termes>` — <url>

## Ce qu'on n'a pas trouvé
- <trou documentaire>
```
