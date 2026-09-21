---
name: fresque-brief
description: Transforme un sujet ou un titre en brief de documentaire narré — angle, promesse, structure en actes, hook. Première étape du pipeline Fresque, produit `00-brief.md`. À utiliser dès que l'utilisateur veut lancer une nouvelle vidéo, propose un sujet de documentaire, ou demande à démarrer un projet Fresque.
---

# Brief de documentaire

Produire `projects/<slug>/00-brief.md`. C'est le contrat que toutes les
étapes suivantes respecteront.

Lire `projet.yaml` pour connaître le template, puis `templates/<template>.yaml` : ses champs `meta.registre`, `meta.structure_narrative` et `meta.interdits_specifiques` priment sur les consignes génériques de ce skill.

Lire `fresque.config.yaml` avant de commencer : durée cible, nombre d'actes
et débit de narration en dépendent.

## Ce qu'il faut comprendre d'abord

Un sujet n'est pas un angle. « Tchernobyl » est un sujet ; « les treize
secondes pendant lesquelles trois hommes ont su que le réacteur allait
exploser, et ce qu'ils ont fait » est un angle.

Un documentaire de 15 minutes ne tient pas sur un sujet. Il tient sur **une
tension** : une contradiction, une question sans réponse évidente, un écart
entre ce qu'on croit savoir et ce qui s'est passé. Sans tension identifiée
dans le brief, le script sera une liste de faits, et une liste de faits perd
le spectateur en quatre minutes.

## Procédure

**1. Lire la piste retenue.** `projet.yaml` porte `piste: N` — le numéro
que l'utilisateur a choisi. Ouvrir `pistes.md` et prendre la piste N : son
angle, son pivot, ses preuves et son titre sont déjà décidés. Le brief les
développe, il ne les rediscute pas.

Pas de `pistes.md`, ou pas de `piste` dans `projet.yaml` : partir du champ
`sujet`, et faire une recherche web rapide (3-5 requêtes) pour repérer les
angles disponibles. Ne pas faire la recherche documentaire complète — c'est
le travail de `fresque-recherche`.

**2. Vérifier que l'angle tient.** Les preuves de la piste sont lues, pas
crues sur parole. Si l'une d'elles ne dit pas ce que la piste lui fait
dire, le signaler et proposer de reprendre l'exploration, plutôt que
d'écrire un brief sur un angle vide.

**3. Écrire le brief** au format ci-dessous. Le titre de travail est le
titre le plus agressif de la piste. Les interdits du script restent entiers :
le titre fait cliquer, la narration reste sobre.

**4. Écrire `projects/<slug>/00-brief.md`.** Le dossier existe déjà : il a
été créé avec le sujet. Ne pas en créer un autre.

**5. Annoncer la suite** : une ligne indiquant que `fresque-recherche` est
l'étape suivante. Ne pas l'enchaîner automatiquement.

## Format de `00-brief.md`

```markdown
# <Titre de travail>

- **slug** : <kebab-case-sans-accent>
- **durée cible** : <n> min (~<n×mots_par_minute> mots de narration)
- **créé le** : <AAAA-MM-JJ>

## Angle
<Deux à trois phrases. La tension précise, pas le sujet général.>

## Promesse
<Une phrase : ce que le spectateur saura ou ressentira à la fin, qu'il
ne savait pas au début. S'il n'y a rien, l'angle est mauvais — recommencer.>

## Audience
<Qui regarde ça un mardi soir, et pourquoi il ne passe pas à autre chose.>

## Hook (~<hook_s> s)
<Le texte réel des premières secondes. Pas « on présente le sujet » : la
phrase d'ouverture elle-même.>

**Accroche** : <la même chose en huit mots, telle qu'elle sera incrustée
à l'écran.>
**Premier plan** : <qui ou quoi est à l'image pendant cette phrase.>

## Structure
### Acte I — <titre> (~<n> min)
<Ce qui est établi, et la question ouverte à la fin de l'acte.>
### Acte II — <titre> (~<n> min)
...

## Le pivot
<Le moment exact où le spectateur comprend qu'il s'était trompé, ou que
l'histoire n'était pas celle qu'il croyait. Situer dans quel acte.>

## Registre
<Ton, rythme, vocabulaire. Deux ou trois lignes concrètes.>

## Interdits
<Ce que ce documentaire ne fera pas. Voir la liste ci-dessous, adaptée
au sujet.>

## Zones de risque
<Faits contestés, sujets sensibles, questions de droits, points de
modération YouTube. Vide si aucun — mais y réfléchir vraiment.>
```

## Règles de fond

**La durée se calcule, elle ne s'estime pas.** Durée cible × `mots_par_minute`
= budget de mots. Répartir ce budget entre les actes dans le brief. Le skill
script s'y tiendra.

**Chaque acte finit sur une question ouverte.** C'est ce qui fait passer le
spectateur à l'acte suivant. Un acte qui se referme proprement est un acte
où l'on arrête de regarder.

**Le pivot est obligatoire.** S'il n'y en a pas, le documentaire est un
exposé. Un exposé de 15 minutes ne se regarde pas.

**Le hook nomme et montre ce dont il parle.** Trois contraintes, et elles
sont vérifiées mécaniquement par `fresque lint` et `fresque shots` :

- **La première phrase pose un fait, en vingt mots au plus.** Pas une
  question : une question d'ouverture est la signature sonore du contenu
  générique, et elle ne promet rien de vérifiable.
- **Le fait est le plus dérangeant dont on dispose**, pourvu qu'il soit
  sourcé et exact. Un fait tiède ne tient personne.
- **Le premier plan montre le sujet lui-même**, pas son décor. Un visage,
  l'objet, la personne nommée dans la phrase. Le premier documentaire de ce
  pipeline ouvrait sur une façade de prison pendant que la voix nommait un
  ancien président : le spectateur n'avait rien sur quoi accrocher la
  phrase. Décrire le premier plan dans le brief — le plan visuel s'y tiendra.

L'**accroche** est la même idée en huit mots, qui sera incrustée en grand à
l'écran pendant que la voix dit autre chose. La lecture est plus rapide que
l'écoute : ce qui est écrit à l'image est lu avant que la phrase soit finie.

**Vérifier la faisabilité visuelle avant de valider l'angle.** Un angle
magnifique sur un sujet sans aucune archive disponible coûtera cher en
génération d'images et paraîtra faux. Le noter dans les zones de risque.

## Interdits par défaut

À reprendre dans le brief, en les adaptant :

- Aucune formule de chaîne YouTube : pas de « abonnez-vous », « dans cette
  vidéo », « mais avant ça ».
- Aucun superlatif non justifié : « incroyable », « choquant », « personne ne
  sait ». Si c'est vraiment incroyable, les faits le montreront.
- Aucune question rhétorique creuse en ouverture (« Et si je vous disais
  que… »). C'est la signature sonore du contenu IA.
- Aucun suspense artificiel sur une information qu'on pourrait donner
  immédiatement.
- Aucune spéculation présentée sur le même ton que les faits établis.
