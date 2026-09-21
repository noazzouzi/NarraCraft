---
name: fresque-plan-visuel
description: Établit le plan visuel d'un documentaire Fresque — un ou plusieurs plans par beat, arbitrage entre archives libres et images générées, mouvement de caméra, prompts de génération. Produit `03-shots.json`, deuxième checkpoint humain. À utiliser après validation du script, ou quand l'utilisateur demande le plan visuel, les images, les plans ou le découpage visuel d'un projet Fresque.
---

# Plan visuel

Produire `projects/<slug>/03-shots.json` à partir de `pistes.md` (la
piste retenue), `01-research.md` et `02-script.md`.

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

Viser `plans_par_minute` plans par minute de montage. **Calculer, ne pas
estimer** : la durée d'un beat vaut `mots_du_beat / mots_par_minute × 60`, et
le nombre de plans à lui donner vaut cette durée divisée par
`montage.duree_plan_max_s`, arrondi au supérieur. Un beat de 40 mots à
170 mots/min dure quatorze secondes : il lui faut **trois plans**, pas un.

Ce rythme n'est pas cosmétique, et c'est l'erreur qui a rendu le premier
documentaire de ce pipeline monotone : il tournait à 8 plans par minute, une
image toutes les sept secondes et demie. Une image tenue aussi longtemps sur
une narration continue fait décrocher, même avec un mouvement de caméra.

**Il n'y a pas de limite basse crédible.** Ce skill a longtemps affirmé que
sous deux secondes par plan un documentaire devenait une bande-annonce. La
mesure dit le contraire : sur deux documentaires Frontier, la durée médiane
d'un plan est de 1,7 et 2,4 secondes, et le plan le plus court tient cinq
images — un sixième de seconde (`docs/analyse-frontier.md`). Un plan très
court est un outil, pas un défaut ; ce qui fatigue, c'est un plan long sur
une narration qui avance.

Le vrai contrepoids est ailleurs : **si le montage accélère, la narration
ralentit.** Frontier coupe deux fois plus vite que nous et parle deux fois
moins vite — environ 70 mots par minute, en phrases de trois à six mots
séparées par du silence. C'est l'image qui porte le rythme ; la voix lui
laisse la place. Un plan de 1,7 seconde sur une narration à 170 mots par
minute ne donne pas du rythme, il donne du bruit.

Répartir les plans d'un beat avec `poids`. Un plan de poids 2 occupe deux
fois plus de temps qu'un plan de poids 1 dans le même beat. **Attention au
poids sur un beat long** : un beat de quatorze secondes découpé 1/1/4 tient
quand même sa dernière image neuf secondes. C'est le plan le plus lourd qui
décide, pas la moyenne — et c'est celui-là que le pipeline vérifie.

`python -m fresque shots <slug>` affiche les plans par minute obtenus et
liste les beats qui tiennent une image trop longtemps. **Corriger jusqu'à ce
que la liste soit vide** avant de présenter le plan.

## L'ouverture

**Le premier plan du fichier décide si le deuxième est vu.** Deux règles,
refusées mécaniquement par `fresque shots` :

1. **Il montre le sujet lui-même** — le visage, l'objet, la personne que la
   voix nomme. Jamais son décor, jamais un panneau graphique. Le premier
   documentaire de ce pipeline ouvrait sur une façade de prison pendant que
   la narration nommait un ancien président : rien à quoi accrocher la phrase.
2. **Il porte une `accroche`** : la phrase choc incrustée en grand à l'écran,
   `accroche_mots_max` mots au plus. Le titre de la piste retenue en est
   la matière première.

```json
{"beat":"B001","type":"archive","intention":"le visage, plan serré",
 "requete":"Nicolas Sarkozy portrait","mouvement":"zoom_in",
 "accroche":"Condamné, et toujours présumé innocent."}
```

L'accroche n'est pas un sous-titre : elle apparaît pendant que la voix dit
autre chose, en haut du cadre, mot par mot. La lecture va plus vite que
l'écoute, et c'est tout l'intérêt.

Le champ est disponible sur n'importe quel plan, pas seulement le premier.
S'en servir avec parcimonie — deux ou trois par documentaire, en tête d'acte
ou sur la révélation du pivot. Au-delà, c'est un diaporama de citations.

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
- **Le premier plan n'est pas un `motion` et porte une `accroche`.**
- Une `accroche` fait au plus `accroche_mots_max` mots.
- Les beats sont référencés par leur identifiant exact (`B001`…).
- `type` vaut `archive`, `collage`, `generated`, `motion` ou `video`.
- Un plan `archive`, `collage` ou `video` a une `requete` ; un plan
  `generated` a un `prompt`.
- `poids` est strictement positif.
- `mouvement` appartient à la liste ci-dessus.

## Plans `collage` — une archive composée sur du papier

Le style relevé chez Frontier sur ses documentaires « Vox » : la photographie
d'archive n'est pas montrée plein cadre, elle est **collée sur une planche de
papier** — un tampon déchiré dessous, un liseré blanc autour, des accents
découpés, un ou deux morceaux d'adhésif.

```json
{"beat":"B006","type":"collage","intention":"le tribunal, le jour du verdict",
 "requete":"palais justice Paris","mouvement":"zoom_in"}
```

Le plan se déclare **exactement comme une `archive`** : même `requete`, mêmes
fonds, même licence à respecter. Tout le reste — quelles pièces, où, dans
quel ordre, à quelle profondeur — est calculé par `fresque.collage`, écrit
dans `06-timeline.json` et corrigeable à la main. Il n'y a rien à décrire
ici, et c'est voulu : une mise en page écrite par un LLM serait une décision
de plus qu'il ne peut pas tenir d'un plan à l'autre.

**Quand s'en servir.** Une planche relance l'œil là où une suite de
photographies plein cadre s'endort, et elle rattrape une image moyenne — le
duotone et le liseré la remettent dans la direction artistique. Elle vaut
donc pour les beats explicatifs, les changements d'acte, et les archives dont
le cadrage est quelconque.

**Quand s'en passer.** Un visage qui porte le beat se montre en grand. Une
planche met la photographie à moins de la moitié du cadre : c'est le bon
choix pour illustrer une idée, jamais pour un regard.

**Elle tient l'écran plus longtemps** qu'une photographie — `duree_panneau_max_s`
plutôt que `duree_plan_max_s` — parce que ses pièces bougent à des vitesses
différentes tout du long. Ce n'est pas une licence pour ralentir : c'est la
même règle que pour un panneau graphique.

**Le style est celui du template.** Papier, encres, trame, adhésif,
profondeur de parallaxe : tout vient de `montage.collage`. Le template
`documentaire-collage` est construit autour, sous-titres en encre sombre
compris — un sous-titre blanc sur du papier crème est illisible.

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

**`document`** — une pièce officielle, avec un passage surligné.
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
Sur un sujet judiciaire ou administratif, c'est souvent **le plan le plus
fort disponible** : les mots exacts d'un jugement disent ce qu'aucune façade
de tribunal ne dira.

Huit lignes maximum — un spectateur ne lit pas une page entière en huit
secondes. `surligne` désigne l'index de la ligne qui compte, et un
surligneur la balaie à l'écran : c'est ce qui dit où regarder avant qu'il
ait fini de décider lui-même.

**`surligne_a` décide de l'instant, et c'est ce qui fait la différence.**
Y mettre deux ou trois mots de la narration du beat, copiés mot pour mot.
`timeline` y retrouve la frame dans `alignment.json` et le surligneur passe
**au moment exact où la voix dit la ligne**. Sans ce champ, le balayage part
une seconde et demie après l'arrivée du panneau, donc presque jamais au bon
moment — un ornement au lieu d'une démonstration.

Le même champ marche sur `journal`, où il surligne le titre.

Deux mots au minimum : un mot seul se retrouve trop souvent ailleurs dans
le beat. S'il ne se retrouve pas du tout, `fresque timeline` le signale et
le surligneur garde son retard par défaut — il ne devine jamais.

`ecriture` vaut `dactylographie` (machine à écrire) ou `officiel` (papier
administratif). Aucune police n'est embarquée, ces familles existent partout.

**Ne jamais inventer le contenu d'une pièce réelle.** Le texte doit venir
mot pour mot de `01-research.md`, avec sa source. Un document fabriqué qui
ressemble à une pièce authentique est le pire écart possible sur un sujet
judiciaire.

Un plan `motion` prend `"mouvement": "static"` — l'animation est interne.

**Combien ?** Trois à cinq par quart d'heure. Ce sont des respirations et des
moments de structure, pas un habillage. Enchaîner deux panneaux de suite
casse le rythme documentaire.

## Avant de présenter

Vérifier, puis annoncer à l'utilisateur :

- [ ] Le premier plan montre le sujet et porte son `accroche`.
- [ ] Chaque beat est couvert.
- [ ] `fresque shots` ne signale plus aucun beat trop tenu.
- [ ] Le nombre de plans par minute affiché est proche de `plans_par_minute`.
- [ ] Aucun mouvement répété deux fois de suite.
- [ ] Les requêtes d'archive suivent les pistes de `01-research.md`.
- [ ] Les prompts partagent une direction artistique unique.
- [ ] Aucun nom de personne réelle, aucun texte demandé dans une image.
- [ ] Le compte d'images générées tient dans le budget.

Puis lancer `python -m fresque shots <slug>` pour la validation mécanique, et
s'arrêter. C'est un checkpoint.
