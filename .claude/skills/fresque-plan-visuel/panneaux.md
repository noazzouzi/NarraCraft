# Les treize panneaux

Le motion design du pipeline. Aucun ne coûte un centime, tous sont rendus
par Remotion dans les couleurs et la typographie du template.

**Chaque panneau porte de la donnée qui vient de `01-research.md`.** Un
chiffre, une date, une citation, une colonne de tableau : si ce n'est pas
dans la recherche, ça ne va pas dans un panneau. Un graphique inventé est
pire qu'une illustration générique, parce qu'il a l'air d'une preuve.

Tous prennent `"mouvement": "static"` : l'animation est interne.

---

## Ce qui vient d'où

| Table de `01-research.md` | Panneaux qu'elle alimente |
|---|---|
| Chronologie | `chronologie` |
| Chiffres | `chiffre`, `barres`, `proportion` |
| Contesté ou incertain | `comparaison` |
| Citations | `citation` |
| Personnes | `reseau` |
| Mécanique | `tableau`, `document` |
| — | `carte`, `journal`, `maquette` |

---

## `chronologie` — une frise datée

Le panneau le plus utile sur un sujet daté.

```json
{"kind": "chronologie", "titre": "Trois affaires",
 "evenements": [
   {"date": "déc. 2024", "texte": "Bismuth — définitif"},
   {"date": "sept. 2025", "texte": "Financement libyen — cinq ans"}
 ]}
```

Deux événements minimum — en dessous c'est une date, pas une frise. Sept
maximum. Les libellés font une ligne, pas une phrase.

## `chiffre` — un nombre isolé

```json
{"kind": "chiffre", "valeur": "20", "libelle": "jours à la Santé",
 "comparaison": "avant une libération sous contrôle judiciaire"}
```

`comparaison` est facultative et presque toujours souhaitable : un chiffre
nu ne laisse aucune trace, à l'écran comme à l'oral. C'est la colonne
« ordre de grandeur parlant » de la recherche.

## `barres` — des quantités comparées

```json
{"kind": "barres", "titre": "Restaurants aux États-Unis",
 "series": [
   {"libelle": "2015", "valeur": 27103},
   {"libelle": "2021", "valeur": 20576}
 ]}
```

Deux séries minimum — en dessous c'est un `chiffre`, pas un graphique. Six
maximum. Valeurs positives.

## `proportion` — une part dans un tout

```json
{"kind": "proportion", "valeur": 8, "total": 100,
 "libelle": "du chiffre d'affaires, versé chaque semaine"}
```

`valeur` entre zéro et `total`. `total` strictement positif. Un chiffre
isolé ne dit rien tant qu'on ne sait pas de quoi il est la part.

## `tableau` — lignes et colonnes

Quatre chefs d'accusation en face de quatre décisions disent en une image
ce que la narration met trente secondes à établir.

```json
{"kind": "tableau", "titre": "Ce qui a été retenu",
 "colonnes": ["Chef", "Décision"],
 "lignes": [
   ["Association de malfaiteurs", "Coupable"],
   ["Corruption", "Relaxe"]
 ],
 "colonne_accent": 1}
```

Deux à quatre colonnes. Une à six lignes. Chaque ligne a exactement autant
de cellules que de colonnes. `colonne_accent` est un index, facultatif.

## `comparaison` — deux colonnes opposées

Ce qu'on croit à gauche, ce qui a été établi à droite. C'est la table
« Contesté ou incertain » de la recherche, mise à l'écran.

```json
{"kind": "comparaison",
 "gauche": {"titre": "La version publique", "points": ["…", "…"]},
 "droite": {"titre": "Ce que dit le contrat", "points": ["…"]}}
```

Chaque côté a un `titre` et un à quatre `points`. Les deux colonnes se
lisent en parallèle : au-delà de quatre, personne ne suit.

## `citation` — un extrait avec sa source

```json
{"kind": "citation", "texte": "…",
 "source": "Jugement du 25 septembre 2025"}
```

La `source` est obligatoire. Une citation sans source n'est pas utilisable.
Le texte est celui de la recherche, mot pour mot.

## `document` — une pièce officielle surlignée

Sur un sujet judiciaire ou administratif, souvent **le plan le plus fort
disponible** : les mots exacts d'un jugement disent ce qu'aucune façade de
tribunal ne dira.

```json
{"kind": "document", "ecriture": "dactylographie",
 "entete": "Tribunal correctionnel de Paris",
 "reference": "Jugement du 25 septembre 2025 — extrait du dispositif",
 "lignes": [
   "DÉCLARE le prévenu coupable des faits d'association de malfaiteurs ;",
   "LE CONDAMNE à la peine de cinq années d'emprisonnement ;"
 ],
 "surligne": 1,
 "surligne_a": "Le tribunal le condamne"}
```

Huit lignes maximum. `ecriture` vaut `dactylographie` ou `officiel`.

**`surligne_a` décide de l'instant, et c'est ce qui fait la différence.**
Deux ou trois mots de la narration du beat, copiés mot pour mot : `timeline`
y retrouve la frame dans `alignment.json` et le surligneur passe **au moment
exact où la voix dit la ligne**. Sans ce champ, le balayage part une seconde
et demie après l'arrivée du panneau — un ornement au lieu d'une
démonstration. Deux mots minimum : un mot seul se retrouve ailleurs dans le
beat. S'il ne se retrouve pas, `fresque timeline` le signale et le
surligneur garde son retard par défaut. Il ne devine jamais.

**Ne jamais inventer le contenu d'une pièce réelle.** Le texte vient mot
pour mot de `01-research.md`, avec sa source.

## `journal` — une une construite

Les unes de presse sont sous droits et quasi jamais disponibles librement.
Ce panneau en **fabrique** une : il porte le nom du journal et la date comme
des faits énoncés, il ne reproduit aucune mise en page existante.

```json
{"kind": "journal", "journal": "Le Quotidien", "date": "26 septembre 2025",
 "titre": "Cinq ans de prison prononcés",
 "chapeau": "Le tribunal assortit la peine d'une exécution provisoire.",
 "surligne_a": "cinq ans"}
```

**Ne jamais donner le nom d'un titre réel avec une une qu'il n'a pas
publiée.** `surligne_a` marche ici aussi, sur le titre.

## `maquette` — une fenêtre de navigateur construite

Même principe que `journal`, pour le web. Jamais une capture d'écran.

```json
{"kind": "maquette", "site": "Registre du commerce", "url": "registre.gouv",
 "date": "12 mars 2019",
 "titre": "Dépôt des comptes annuels — exercice 2018",
 "chapeau": "Résultat net : moins 4,2 millions d'euros.",
 "source": "Extrait du dépôt du 12 mars 2019"}
```

`site`, `titre` et `source` sont obligatoires. La source est affichée sous
la fenêtre : elle dit que ce n'est pas une capture.

## `carte` — les lieux cités

```json
{"kind": "carte", "titre": "Deux capitales, 2007",
 "marqueurs": [
   {"nom": "Paris", "coord": [2.35, 48.85]},
   {"nom": "Tripoli", "coord": [13.19, 32.89]}
 ],
 "relier": true, "pays": ["France", "Libya"]}
```

**`coord` est `[longitude, latitude]`**, dans cet ordre. C'est l'inverse de
l'habitude française, et c'est l'erreur la plus fréquente : inversé, Paris
tombe dans l'océan Indien. Le pipeline refuse les valeurs hors limites,
mais pas une inversion qui reste plausible.

Cinq marqueurs maximum. `pays` met en avant des pays entiers, avec les noms
de Natural Earth, en anglais (`France`, `Libya`, `United States of
America`). Le cadrage est automatique.

## `reseau` — des personnes et ce qui les relie

Sur une association de malfaiteurs, c'est une illustration littérale de
l'infraction retenue.

```json
{"kind": "reseau", "titre": "Qui parlait à qui",
 "noeuds": [
   {"nom": "L'intermédiaire"},
   {"nom": "Le directeur de cabinet"},
   {"nom": "Le fonds souverain"}
 ],
 "liens": [{"de": 0, "a": 1}, {"de": 0, "a": 2}]}
```

Deux à huit nœuds — au-delà, les noms se chevauchent sur le cercle. `de` et
`a` sont des index dans `noeuds`.
