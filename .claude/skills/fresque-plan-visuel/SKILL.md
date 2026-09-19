---
name: fresque-plan-visuel
description: Établit le plan visuel d'un documentaire Fresque — un ou plusieurs plans par beat, arbitrage entre archives libres et images générées, mouvement de caméra, prompts de génération. Produit `03-shots.json`, deuxième checkpoint humain. À utiliser après validation du script, ou quand l'utilisateur demande le plan visuel, les images, les plans ou le découpage visuel d'un projet Fresque.
---

# Plan visuel

Produire `projects/<slug>/03-shots.json` à partir de `00-brief.md`,
`01-research.md` et `02-script.md`.

C'est le **checkpoint 2** : le dernier point avant que le pipeline ne dépense
en génération d'images. Tout ce qui est validé ici sera payé.

Lire `fresque.config.yaml` : `plans_par_minute`, `max_images_par_projet` et
`budget.max_eur_par_projet` encadrent le travail.

## L'arbitrage central

Chaque plan est soit une **archive** (gratuite, réelle), soit une **image
générée** (payante, inventée). Cet arbitrage décide à la fois du coût et de la
crédibilité du documentaire.

La règle : **une archive chaque fois qu'il en existe une.** Sur un sujet
historique, une photographie d'époque imparfaite est plus convaincante qu'une
illustration générée impeccable — et le spectateur fait la différence, même
sans savoir l'expliquer.

La section « Pistes d'archives visuelles » de `01-research.md` est le point de
départ. Elle a déjà repéré les collections. Ne pas la contourner.

On ne génère que dans trois cas :

1. Rien de réel n'existe (intérieur détruit, scène sans témoin, abstraction).
2. Ce qui existe est inutilisable (licence non libre, résolution trop faible).
3. Le plan est un raccord, pas un document — une texture, une ambiance.

## Découpage

Viser `plans_par_minute` plans par minute de montage, soit un changement
d'image toutes les 7 à 8 secondes environ. Un beat de 20 secondes prend donc
deux ou trois plans.

Ce rythme n'est pas cosmétique : une image tenue plus de dix secondes sur une
narration continue fait décrocher, même avec un mouvement de caméra. À
l'inverse, descendre sous trois secondes par plan transforme un documentaire
en bande-annonce.

Répartir les plans d'un beat avec `poids`. Un plan de poids 2 occupe deux
fois plus de temps qu'un plan de poids 1 dans le même beat.

## Mouvement

Le champ `mouvement` prend : `zoom_in`, `zoom_out`, `pan_left`, `pan_right`,
`pan_up`, `pan_down`, `static`.

Le choisir en fonction du contenu de l'image, pas au hasard :

| Contenu | Mouvement |
|---|---|
| Visage, détail, objet isolé | `zoom_in` — on entre dedans |
| Scène large, paysage, foule | `pan_*` — on parcourt |
| Révélation, élargissement du contexte | `zoom_out` |
| Document, carte, portrait officiel | `static` — la caméra se tait |

**Ne jamais répéter le même mouvement sur deux plans consécutifs.** C'est ce
qui fait qu'un montage automatique se voit immédiatement. Le pipeline varie
déjà l'amplitude de chaque mouvement, mais il ne choisit pas la direction —
c'est ton travail.

## Requêtes d'archive

Le champ `requete` part directement dans l'API de Wikimedia Commons.

**Trois ou quatre termes, pas plus.** C'est la règle la plus importante, et
elle est contre-intuitive. Commons combine les termes en ET : plus la requête
est précise, plus elle a de chances de ne **rien** renvoyer. Mesuré sur ce
pipeline — `Titanic boiler room stokers 1912` renvoie zéro fichier, même sans
aucun plancher de résolution, tandis que `Titanic engineers memorial
Southampton` en renvoie trois excellents.

Le pipeline sait élargir tout seul une requête trop longue, mais il le fait en
coupant les termes de queue, donc **mets les termes les plus déterminants en
premier**. `Titanic boiler room stokers 1912` sera réessayé en `Titanic boiler
room` — ce qui marche. `Photographie de 1912 du Titanic` deviendrait
`Photographie de 1912`, ce qui ne veut plus rien dire.

Le reste :

- **Chercher en anglais**, et aussi dans la langue d'origine du sujet. Les
  fonds sont catalogués dans ces langues, rarement en français.
- Employer des termes de catalogue, pas de la prose : `Titanic boiler room`
  et non `des hommes qui pellettent du charbon`.
- Une date aide quand le sujet existe à plusieurs époques, mais elle compte
  comme un terme — et sur un sujet daté, elle est souvent redondante.
- Éviter les termes qui ramènent des affiches de film, des captures de jeu ou
  des reconstitutions 3D.

Le pipeline écarte déjà les PDF et les scans de livres, ne retient que les
licences libres, et privilégie les images en format paysage. Tu n'as pas à
t'en préoccuper dans la requête.

## Prompts de génération

Le champ `prompt` part dans l'API de génération d'images.

**Direction artistique unique pour tout le documentaire.** Choisir une fois —
photographie documentaire, gravure, peinture à l'huile, archive colorisée — et
la répéter dans chaque prompt. Des images générées dans cinq styles différents
détruisent l'illusion plus sûrement qu'une image médiocre.

À faire figurer dans chaque prompt : le médium, l'époque, la lumière, le
cadrage. À proscrire :

- **Aucun nom de personne réelle.** Ni pour obtenir sa ressemblance, ni comme
  référence de style. Question de droit à l'image, et la chaîne est monétisée.
- **Aucun texte dans l'image.** Les modèles le rendent mal, et un panneau mal
  orthographié à l'écran ruine la crédibilité d'un plan.
- Aucune indication de ratio ou de qualité : la configuration s'en charge.

## Budget

Compter les plans `generated` et vérifier contre `max_images_par_projet`.
Si le total dépasse, **arbitrer avant d'écrire le fichier** : convertir des
plans générés en archives, ou augmenter le `poids` de plans existants pour en
supprimer.

Annoncer le compte à l'utilisateur au moment de présenter le plan.

## Format de `03-shots.json`

```json
{
  "version": 1,
  "shots": [
    {
      "beat": "B001",
      "type": "archive",
      "intention": "la proue de nuit, mer parfaitement calme",
      "requete": "RMS Titanic bow photograph 1912",
      "mouvement": "zoom_in",
      "poids": 1
    },
    {
      "beat": "B001",
      "type": "generated",
      "intention": "l'eau qui entre entre deux plaques de coque",
      "prompt": "Water forcing through a narrow gap between riveted steel hull plates, dim work lighting, 1912 ocean liner interior, documentary photograph, desaturated",
      "mouvement": "pan_right",
      "poids": 2
    }
  ]
}
```

Contraintes vérifiées par le pipeline, qui refusera le fichier sinon :

- **Tout beat du script a au moins un plan.** Aucune exception.
- Les beats sont référencés par leur identifiant exact (`B001`…).
- `type` vaut `archive`, `generated` ou `motion`.
- Un plan `archive` a une `requete`, un plan `generated` a un `prompt`.
- `poids` est strictement positif.
- `mouvement` appartient à la liste ci-dessus.

## Plans `video` — métrage d'archive

Du vrai métrage qui bouge, sourcé à la Library of Congress. **C'est ce qui
distingue le plus un documentaire d'un diaporama** : quinze minutes d'images
fixes, même bien animées, se reconnaissent immédiatement.

```json
{"beat":"B004","type":"video","intention":"une prison filmée",
 "requete":"prison","mouvement":"static"}
```

`"mouvement": "static"` est obligatoire : le métrage bouge déjà, lui ajouter
un travelling donne deux mouvements qui se contrarient.

**Requêtes d'un ou deux mots.** La recherche LOC combine les termes comme
Commons. Mesuré sur le fonds `national-screening-room` : `prison` donne cinq
clips utilisables sur huit, `city` vingt-huit sur trente, mais `courtroom
judge` zéro.

**Le rendement dépend surtout de la durée.** Les fichiers sont des films
entiers, et le pipeline refuse au-delà de quinze minutes — un item de
vingt-sept minutes pèse un gigaoctet. Certaines requêtes ne ramènent que des
longs métrages : le pipeline le dit alors explicitement, et il faut
reformuler vers un sujet plus court.

**Réutiliser.** Plusieurs plans peuvent porter la même `requete` : le
pipeline télécharge le film une fois et place chaque plan à un point
d'entrée différent. Un téléchargement, trois plans. En abuser montre
cependant le même décor trois fois — deux ou trois plans par film au plus.

Le fonds est américain et ancien (1890-1960 pour l'essentiel). Sur un sujet
français contemporain, il servira d'illustration générique, pas de document.

## Plans `motion`

Trois panneaux existent. Sur un sujet fait de dates, de chefs d'accusation et
de peines, **ils valent souvent mieux qu'une photo d'illustration** — et ils
ne coûtent rien.

**`chronologie`** — une frise datée. Le panneau le plus utile du lot.
```json
{"kind": "chronologie", "titre": "Trois affaires",
 "evenements": [
   {"date": "déc. 2024", "texte": "Bismuth — définitif"},
   {"date": "sept. 2025", "texte": "Financement libyen — cinq ans"}
 ]}
```
Deux événements minimum — en dessous c'est une date, pas une frise. Sept
maximum — au-delà c'est illisible, il faut scinder en deux plans. Les
libellés font une ligne, pas une phrase.

**`citation`** — un extrait avec sa source. Sur un sujet judiciaire, les mots
exacts d'un jugement pèsent plus que n'importe quelle façade de tribunal.
```json
{"kind": "citation", "texte": "…", "source": "Jugement du 25 septembre 2025"}
```
La `source` est obligatoire. Une citation sans source n'est pas utilisable.

**`chiffre`** — un nombre isolé et ce à quoi il se compare.
```json
{"kind": "chiffre", "valeur": "20", "libelle": "jours à la Santé",
 "comparaison": "avant une libération sous contrôle judiciaire"}
```
La `comparaison` est facultative mais presque toujours souhaitable : un
chiffre nu ne laisse aucune trace, à l'écran comme à l'oral.

**`carte`** — une carte cadrée sur les lieux cités, avec un trajet éventuel.
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
tombe dans l'océan Indien. Le pipeline refuse les valeurs hors limites, mais
il ne peut pas détecter une inversion qui reste plausible.

Cinq marqueurs maximum, sinon les étiquettes se chevauchent. `pays` met en
avant des pays entiers — les noms sont ceux de Natural Earth, en anglais
(`France`, `Libya`, `United States of America`). Le cadrage est automatique.

**`journal`** — une une construite, jamais un fac-similé.
```json
{"kind": "journal", "journal": "Le Quotidien", "date": "26 septembre 2025",
 "titre": "Cinq ans de prison prononcés",
 "chapeau": "Le tribunal assortit la peine d'une exécution provisoire."}
```
Les unes de presse sont sous droits et quasi jamais disponibles librement.
Ce panneau en **fabrique** une : il porte le nom du journal et la date comme
des faits énoncés, il ne reproduit aucune mise en page existante. Ne jamais
lui donner le nom d'un titre réel avec une une qu'il n'a pas publiée.

Un plan `motion` prend `"mouvement": "static"` — l'animation est interne.

**Combien ?** Trois à cinq par quart d'heure. Ce sont des respirations et des
moments de structure, pas un habillage. Enchaîner deux panneaux de suite
casse le rythme documentaire.

## Avant de présenter

Vérifier, puis annoncer à l'utilisateur :

- [ ] Chaque beat est couvert.
- [ ] Le nombre de plans correspond à `plans_par_minute`, à peu près.
- [ ] Aucun mouvement répété deux fois de suite.
- [ ] Les requêtes d'archive suivent les pistes de `01-research.md`.
- [ ] Les prompts partagent une direction artistique unique.
- [ ] Aucun nom de personne réelle, aucun texte demandé dans une image.
- [ ] Le compte d'images générées tient dans le budget.

Puis lancer `python -m fresque shots <slug>` pour la validation mécanique, et
s'arrêter. C'est un checkpoint.
