---
name: fresque-plan-visuel
description: Établit le plan visuel d'un documentaire Fresque — un ou plusieurs plans par beat, arbitrage entre archives libres, planches de collage, métrage et images générées, panneaux graphiques tirés de la recherche. Produit `03-shots.json`, deuxième checkpoint humain. À utiliser après validation du script, ou quand l'utilisateur demande le plan visuel, les images, les plans, les graphiques ou le découpage visuel d'un projet Fresque.
---

# Plan visuel

## RÔLE

Décider ce que le spectateur voit, plan par plan. Rien n'est encore téléchargé ni payé.

## ENTRÉE

- `projects/<slug>/02-script.md` — les beats. Chacun aura au moins un plan.
- `projects/<slug>/01-research.md` — les faits, les chiffres, les archives repérées. **Tout contenu de panneau vient d'ici.**
- `projects/<slug>/pistes.md` — le titre retenu : la matière de l'accroche.
- `templates/<template>.yaml` — la direction artistique. On ne la réécrit pas, on s'y conforme.
- `fresque.config.yaml` — `plans_par_minute`, `variete.*`, `max_images_par_projet`.

## SORTIE

`projects/<slug>/03-shots.json`. Format en bas de page.

C'est le **checkpoint 2** : le dernier point avant que le pipeline ne dépense. Tout ce qui est validé ici sera payé.

---

## LES CINQ TYPES

| Type | Ce que c'est | Coût |
|---|---|---|
| `archive` | une photographie libre, plein cadre | gratuit |
| `collage` | la même photographie, composée sur une planche de papier | gratuit |
| `video` | du vrai métrage qui bouge | gratuit |
| `motion` | un panneau graphique construit — voir `panneaux.md` | gratuit |
| `generated` | une image inventée par un modèle | **payant** |

**Une archive chaque fois qu'il en existe une.** Sur un sujet documentaire, une photographie d'époque imparfaite est plus convaincante qu'une illustration générée impeccable, et le spectateur fait la différence sans savoir l'expliquer. La section « Archives repérées » de `01-research.md` a déjà fait le repérage : ne pas la contourner.

On ne génère que dans trois cas :

1. Rien de réel n'existe — intérieur détruit, scène sans témoin, abstraction.
2. Ce qui existe est inutilisable — licence non libre, résolution trop faible.
3. Le plan est un raccord, pas un document — une texture, une ambiance.

**Le métrage est ce qui distingue le plus un documentaire d'un diaporama.** Quinze minutes d'images fixes, même bien animées, se reconnaissent immédiatement. Chercher du `video` avant de se rabattre sur du fixe.

---

## LA VARIÉTÉ

Le premier film complet de ce pipeline tenait 288 photographies sur 348 plans, dont quatorze archives d'affilée au même endroit. Le skill disait « varier ». Personne ne comptait.

`fresque shots` refuse maintenant le fichier si :

- un type dépasse `variete.part_max_par_type` du montage ;
- plus de `variete.suite_max` plans consécutifs partagent le même type ;
- un acte n'a aucun panneau graphique.

Ce n'est pas une contrainte esthétique, c'est le rythme. Alterner est le travail.

## LE DÉCOUPAGE

Viser `plans_par_minute`. **Calculer, ne pas estimer** : la durée d'un beat vaut `mots_du_beat / mots_par_minute × 60`, et le nombre de plans vaut cette durée divisée par `montage.duree_plan_max_s`, arrondi au supérieur. Un beat de 40 mots à 140 mots/min dure dix-sept secondes : il lui faut **cinq plans**, pas un.

**Il n'y a pas de limite basse.** Mesuré sur deux documentaires Frontier : durée médiane d'un plan 1,7 et 2,4 s, le plus court tient cinq images. Un plan très court est un outil. Ce qui fatigue, c'est un plan long sur une narration qui avance.

`poids` répartit le temps dans un beat. Attention au poids sur un beat long : un beat de quatorze secondes découpé 1/1/4 tient quand même sa dernière image neuf secondes. C'est le plan le plus lourd qui décide.

## L'OUVERTURE

**Le premier plan décide si le deuxième est vu.** Deux règles, refusées mécaniquement :

1. **Il montre le sujet lui-même** — le visage, l'objet, le lieu que la voix nomme. Jamais son décor, jamais un panneau graphique. Le premier film ouvrait sur une façade de prison pendant que la narration nommait un ancien président : rien à quoi accrocher la phrase.
2. **Il porte une `accroche`** — la phrase incrustée en grand, `accroche_mots_max` mots au plus, tirée du titre de la piste.

L'accroche apparaît pendant que la voix dit autre chose. La lecture va plus vite que l'écoute, c'est tout l'intérêt. Deux ou trois par documentaire au plus, en tête d'acte ou sur le pivot.

## LE MOUVEMENT

`zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up`, `pan_down`, `static`.

| Contenu | Mouvement |
|---|---|
| Visage, détail, objet isolé | `zoom_in` |
| Scène large, paysage, foule | `pan_*` |
| Révélation, élargissement | `zoom_out` |
| Document, carte, portrait officiel | `static` |
| `motion` et `video` | `static` — obligatoire |

**Jamais le même mouvement sur deux plans consécutifs.** C'est ce qui fait qu'un montage automatique se voit immédiatement.

## LES REQUÊTES D'ARCHIVE

Le champ `requete` part dans l'API des fonds libres.

**Trois ou quatre termes, pas plus.** C'est la règle la plus importante et elle est contre-intuitive : les fonds combinent les termes en ET, donc plus la requête est précise, plus elle a de chances de ne **rien** renvoyer. Mesuré : `Titanic boiler room stokers 1912` renvoie zéro fichier, `Titanic engineers memorial Southampton` en renvoie trois excellents.

Le pipeline élargit tout seul une requête trop longue, en coupant par la queue : **les termes déterminants en premier**.

- **Chercher en anglais**, et dans la langue d'origine du sujet. Les fonds sont catalogués ainsi, rarement en français.
- Des termes de catalogue, pas de la prose : `Titanic boiler room`, pas `des hommes qui pellettent du charbon`.
- Pour `video`, **un ou deux mots**. Mesuré : `prison` donne cinq clips utilisables sur huit, `courtroom judge` zéro.

## LES PROMPTS DE GÉNÉRATION

**Tu n'écris que le sujet du plan. Jamais le style.**

```json
{"type": "generated",
 "prompt": "un homme seul, de dos, devant un restaurant aux rideaux baissés"}
```

La direction artistique — médium, palette, traitement, interdits — vient de `visuels.generation` dans le template, et le code l'ajoute autour de ta phrase. C'est ce qui garantit que cent vingt images partagent un seul style, et c'est ce qui permet de changer de template sans réécrire un prompt.

Écrire du style dans le `prompt` est une erreur : il entre en conflit avec le préfixe du template, et le résultat n'est cohérent ni avec l'un ni avec l'autre.

Ne jamais écrire non plus :
- **un nom de personne réelle** — droit à l'image, et la chaîne est monétisée ;
- **du texte à faire figurer dans l'image** — les modèles le rendent mal ;
- un ratio ou une indication de qualité — la configuration s'en charge.

## LES PANNEAUX

Treize types, détaillés dans **`panneaux.md`**, à lire avant d'en écrire un.

**Leur contenu vient de `01-research.md`, jamais d'ailleurs.** Un `barres` avec des chiffres inventés est pire qu'une illustration générique : il a l'air d'une preuve. Les tables de la recherche correspondent aux panneaux une à une — Chronologie, Chiffres, Contesté, Citations, Personnes.

Trois à cinq panneaux par quart d'heure, et au moins un par acte. Ce sont des respirations et des moments de structure. Deux panneaux de suite cassent le rythme.

## LE BUDGET

Compter les plans `generated` contre `max_images_par_projet`. Si ça dépasse, **arbitrer avant d'écrire le fichier** : convertir des plans générés en archives ou en panneaux, ou augmenter le `poids` de plans existants. Annoncer le compte au checkpoint.

---

## REFUS

- Un fait, un chiffre ou une citation absents de `01-research.md` → ne pas en faire un panneau.
- Une une de presse réelle, une capture d'écran réelle → les panneaux `journal` et `maquette` en **construisent** une. Jamais le nom d'un média réel avec un titre qu'il n'a pas publié.
- Une reconstitution générée présentée comme une archive → jamais, quel que soit le template.
- Pas d'archive repérée sur un beat entier → le dire, plutôt que de générer quatre images pour boucher.

## Format de `03-shots.json`

```json
{
  "version": 1,
  "shots": [
    {"beat": "B001", "type": "archive",
     "intention": "le visage, plan serré",
     "requete": "Nicolas Sarkozy portrait",
     "mouvement": "zoom_in",
     "accroche": "Condamné, et toujours présumé innocent.",
     "poids": 1},

    {"beat": "B002", "type": "collage",
     "intention": "le tribunal, le jour du verdict",
     "requete": "palais justice Paris", "mouvement": "pan_right"},

    {"beat": "B003", "type": "video",
     "intention": "une prison filmée",
     "requete": "prison", "mouvement": "static"},

    {"beat": "B004", "type": "motion", "mouvement": "static",
     "intention": "la frise des trois affaires",
     "motion": {"kind": "chronologie", "titre": "Trois affaires",
                "evenements": [{"date": "déc. 2024", "texte": "…"},
                               {"date": "sept. 2025", "texte": "…"}]}},

    {"beat": "B005", "type": "generated",
     "intention": "l'eau entre deux plaques de coque",
     "prompt": "de l'eau qui force entre deux plaques de coque rivetées",
     "mouvement": "pan_right", "poids": 2}
  ]
}
```

Vérifié par le pipeline, qui refuse le fichier sinon :

- Tout beat du script a au moins un plan. Aucune exception.
- Le premier plan n'est pas un `motion` et porte une `accroche`.
- `archive`, `collage`, `video` ont une `requete` ; `generated` a un `prompt` ; `motion` a un objet `motion`.
- `poids` strictement positif, `mouvement` dans la liste.
- Les plafonds de variété.

### Un mot sur `collage`

Un plan `collage` se déclare **exactement comme une `archive`** : même requête, mêmes fonds, même licence. Quelles pièces, où, dans quel ordre, à quelle profondeur : tout est calculé par `fresque.collage` depuis `montage.collage` du template. Il n'y a rien à décrire ici, et c'est voulu — une mise en page écrite au fil de cent plans ne tiendrait pas.

Une planche relance l'œil là où une suite de photographies s'endort, et elle rattrape une image moyenne. Mais elle met la photographie à moins de la moitié du cadre : jamais pour un visage qui porte le beat.

## AVANT DE PRÉSENTER

Lancer `python -m fresque shots <slug>` et corriger jusqu'à zéro refus. Puis annoncer :

- le nombre de plans, leur répartition par type, les plans par minute obtenus ;
- le compte d'images générées et ce qu'il représente contre le budget ;
- les beats pour lesquels aucune archive n'a été repérée ;
- les deux ou trois plans dont tu es le moins sûr.

Puis s'arrêter. C'est un checkpoint.
