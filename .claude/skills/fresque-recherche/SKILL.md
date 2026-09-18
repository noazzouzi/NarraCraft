---
name: fresque-recherche
description: Mène la recherche documentaire d'un projet Fresque à partir de son brief — faits sourcés, chronologie, détails sensoriels, pistes d'archives visuelles libres. Produit `01-research.md`. À utiliser après `fresque-brief`, ou quand l'utilisateur demande la recherche, les sources ou la documentation d'un projet Fresque.
---

# Recherche documentaire

Produire `projects/<slug>/01-research.md` à partir de `00-brief.md`.

Lire le brief en entier avant de chercher quoi que ce soit. La recherche
sert **l'angle**, pas le sujet. Un fait vrai et intéressant qui ne sert pas
l'angle retenu n'entre pas dans le fichier — il encombre le script.

## Ce que ce fichier doit contenir, et pourquoi

Un script de documentaire échoue presque toujours au même endroit : il
énonce des faits corrects mais abstraits. Ce qui rend une narration
crédible, ce sont les **détails concrets et vérifiables** — l'heure exacte,
le nom de la rue, la température ce jour-là, ce qu'un témoin a dit
textuellement. Ces détails ne s'inventent pas au moment d'écrire. Ils se
collectent maintenant, ou ils n'existeront jamais.

C'est pourquoi la section « Détails sensoriels » n'est pas un bonus : c'est
la section qui détermine si le documentaire sonnera vrai.

## Procédure

**1.** Lire `00-brief.md`, en particulier l'angle, le pivot et la structure.

**2.** Chercher, acte par acte. Viser 6 à 12 requêtes web par acte. Pour
chaque acte, on cherche : les faits établis, la chronologie fine, les
personnes nommées, les chiffres, les citations textuelles, et ce qui est
contesté.

**3.** Vérifier les faits porteurs.** Tout fait sur lequel repose le pivot,
ou qui sera énoncé comme certain, doit être confirmé par **deux sources
indépendantes**. Une source qui en cite une autre ne compte pas pour deux.

**4.** Repérer les archives visuelles. Pour chaque acte, lister les pistes
concrètes : quelle catégorie Wikimedia Commons, quelle collection
Archive.org, quelle recherche Gallica. Ne pas télécharger — juste repérer et
noter les URL. C'est ce qui permettra plus tard de ne générer que ce qui
manque vraiment, et donc de diviser le coût par deux.

**5.** Écrire `01-research.md`.

**6.** Signaler à l'utilisateur, en deux ou trois lignes : ce qui est solide,
ce qui est fragile, et si quelque chose oblige à revoir l'angle du brief.

## Format de `01-research.md`

```markdown
# Recherche — <titre>

> Sources consultées : <n> · Faits vérifiés à deux sources : <n>
> Dernière mise à jour : <AAAA-MM-JJ>

## Chronologie
| Quand | Quoi | Source |
|---|---|---|
| 1986-04-26 01:23:04 | <fait précis> | [nom](url) |

## Personnes
### <Nom> — <rôle en 4 mots>
<Ce qu'il faut savoir, et seulement ce qui sert l'angle.> [source](url)

## Faits par acte
### Acte I
- <Fait, formulé précisément.> [source](url) [source2](url)
- ...

## Chiffres
| Valeur | Ce que c'est | Ordre de grandeur parlant | Source |
|---|---|---|---|
| 3 200 t | masse du couvercle | un Airbus A320 à vide | [src](url) |

<Un chiffre sans comparaison concrète ne veut rien dire à l'oral. Toujours
remplir la colonne « ordre de grandeur ».>

## Citations
> « <texte exact> »
> — <qui>, <quand>, [source](url)

## Détails sensoriels
<Ce qui permet d'écrire une narration incarnée. Heure, météo, bruit, odeur,
couleur, geste, objet. Chaque ligne sourcée. Viser 10 à 20 entrées.>
- <détail> [source](url)

## Contesté ou incertain
| Affirmation | Position A | Position B | Comment le script doit traiter |
|---|---|---|---|

<Règle : ce qui est incertain est énoncé comme incertain dans le script.
Cette colonne est une instruction, pas une note.>

## Pistes d'archives visuelles
### Acte I
- **Wikimedia Commons** — catégorie `<nom exact>` — <ce qu'on y trouve> — <url>
- **Archive.org** — collection `<id>` — <url>
- **Gallica** — recherche `<termes>` — <url>
<Noter la licence quand elle est visible. Domaine public / CC-BY / etc.>

## Ce qu'on n'a pas trouvé
<Trous documentaires. Le script devra les contourner ou les assumer
explicitement. Ne jamais les combler par de la déduction présentée comme
un fait.>
```

## Règles de fond

**Aucun fait sans URL.** Sans exception. Si une affirmation ne peut pas être
sourcée, elle va dans « Contesté ou incertain » ou elle disparaît.

**Ne jamais faire dire à une source ce qu'elle ne dit pas.** En cas de doute
sur une formulation, citer textuellement plutôt que paraphraser.

**Wikipédia est un point de départ, pas une source.** Suivre ses notes de
bas de page jusqu'à la source primaire et citer celle-ci.

**Chercher aussi en langue d'origine du sujet.** Un événement russe, japonais
ou allemand a ses meilleures sources dans sa langue — et surtout ses
meilleures archives visuelles, qui sont souvent invisibles depuis une
recherche en français.

**Signaler tout de suite si la recherche contredit le brief.** Il est infiniment
moins coûteux de corriger l'angle maintenant que d'avoir écrit le script.
