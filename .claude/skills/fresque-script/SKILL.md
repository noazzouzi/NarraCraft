---
name: fresque-script
description: Écrit la narration d'un documentaire Fresque à partir de la piste retenue et de la recherche — découpée en beats numérotés, tenue par des boucles ouvertes, calibrée en durée, optimisée pour la synthèse vocale française. Produit `02-script.md`, premier checkpoint humain. À utiliser après `fresque-recherche`, ou quand l'utilisateur demande d'écrire, réécrire ou retravailler le script d'un projet Fresque.
---

# Script

## RÔLE

Écrire la narration. C'est l'étape qui décide si le film est regardé jusqu'au bout.

## ENTRÉE

- `projects/<slug>/projet.yaml` — `piste` : le numéro retenu. `titre` : le titre publié.
- `projects/<slug>/pistes.md` — la piste N : angle, pivot, preuves.
- `projects/<slug>/01-research.md` — les faits. **Rien d'autre n'est une source.**
- `templates/<template>.yaml` — `meta.registre`, `meta.structure_narrative`, `meta.interdits_specifiques` priment sur ce skill.
- `fresque.config.yaml` — `duree_cible_min`, `hook_s`, `relance_retention_s`, `controle.*`.

## SORTIE

`projects/<slug>/02-script.md`. Format en bas de page, c'est un contrat.

Le fichier contient la narration et rien d'autre. Toutes les métadonnées de contrôle sont dans le tableau de fin.

---

## LA MÉCANIQUE

Un documentaire se regarde jusqu'au bout pour une seule raison : **le spectateur attend une réponse qu'on ne lui a pas encore donnée.**

### Les boucles

Une boucle, c'est une question posée à un beat et répondue bien plus loin.

- Le hook ouvre **L1**, la boucle du film. Elle se ferme au dernier acte.
- Chaque acte ouvre au moins une boucle secondaire.
- Une boucle tient au moins 90 secondes. En dessous, ce n'est pas une boucle, c'est une phrase.
- Jamais plus de trois boucles ouvertes en même temps : au-delà, le spectateur lâche le fil.
- Jamais zéro boucle ouverte, sauf dans les 30 dernières secondes.

Une boucle n'est pas une question posée à voix haute. C'est un fait donné dont la cause manque. « À neuf heures du matin, le médecin a commandé quatre litres de propofol » ouvre une boucle. « Mais pourquoi ? » n'en ouvre pas — ça l'annonce, ce qui la tue.

### `mais` ou `donc`, jamais `et`

Chaque beat s'enchaîne au précédent par l'un des deux :

- **donc** — conséquence. Ce qui précède cause ce qui suit.
- **mais** — retournement. Ce qui suit contredit ce qui précède.

Un beat qui ne peut dire que « et » est un élément de liste. On le fusionne avec son voisin, ou on le coupe. C'est la règle qui sépare un documentaire d'un exposé, et c'est celle qui coupe le plus de texte.

### Le hook

Les quinze premières secondes décident du reste.

- `hook_s` secondes au maximum. Un seul beat.
- Ouvre sur un **fait**, jamais sur une question.
- Contient un nombre, une heure ou une date.
- Contient le trou, pas sa réponse.
- Première phrase de 20 mots au plus : le fait tombe d'un bloc, pas au bout de trois subordonnées.
- **Trois versions écrites.** La retenue devient B001, les deux autres restent en fin de fichier. L'utilisateur peut échanger sans relancer Claude.

### Le rythme

Le texte ne sera jamais lu. Il sera entendu, une fois, sans retour en arrière.

- Une idée par phrase.
- Le sujet avant le verbe, et vite.
- Une phrase de 8 mots ou moins au moins tous les cinq beats. Le silence est un outil : une phrase courte isolée après un paragraphe dense frappe plus fort que n'importe quel adjectif.
- Deux beats consécutifs ne commencent pas par le même mot.
- Les chiffres sont ancrés : « trois mille deux cents tonnes — le poids d'un Airbus à vide ». Un chiffre nu ne laisse aucune trace.
- On ne commente pas les faits, on les ordonne. L'émotion vient du montage des informations, pas des adjectifs posés dessus.

---

## PROCÉDURE

**1. Le budget.** Il n'y a pas de formule : aucun débit n'est visé, et un compte de mots ne prédit pas une durée — c'est le moteur de voix qui décide du débit et des silences. Partir du dernier film mesuré s'il y en a un (`04-audio/alignment.json`, `nb_mots` et `duree_totale_s`), sinon écrire et mesurer.

**2. La colonne vertébrale.** Avant d'écrire une seule phrase : lister 8 à 12 retournements, une ligne chacun, avec leur lien `mais`/`donc` et les boucles qu'ils ouvrent ou ferment. Le pivot de la piste est l'un d'eux, aux deux tiers environ. Si la chaîne ne tient pas ici, elle ne tiendra pas non plus en 2000 mots.

**3. Le hook.** Trois versions, avant le reste.

**4. Les beats**, acte par acte, budget en main.

**5. La passe de coupe.** Relire en retirant chaque beat mentalement. Si son absence ne casse aucune chaîne `mais`/`donc` et ne laisse aucune boucle béante, le retirer pour de bon. La coupe est le meilleur outil de rétention qui existe.

**6. Le tableau de contrôle**, en fin de fichier. Il n'est pas décoratif : le lint le lit.

**7. `python -m fresque lint <slug>`**, jusqu'à zéro violation bloquante. Recommencer autant de fois que nécessaire. L'utilisateur ne doit relire qu'un script qui passe déjà cette barre.

**8. `python -m fresque voice <slug>`**, puis le lint une dernière fois. La voix donne la durée réelle du film, et cinq règles ne tournent pas sans elle : durée, air, rétention, longueur du hook, tenue des boucles. Tant qu'elle n'a pas tourné, le script est vérifié sur son texte seul.

**9. Présenter** : la durée mesurée contre la cible, les boucles et leur tenue, les deux ou trois passages les moins sûrs. Puis s'arrêter — c'est un checkpoint.

---

## ÉCRIRE POUR LA SYNTHÈSE VOCALE FRANÇAISE

Chaque violation produit une erreur audible dans le fichier final.

| Ne pas écrire | Écrire |
|---|---|
| `01h23` | `une heure vingt-trois` |
| `%` | `pour cent` |
| `km/h`, `m²`, `°C` | `kilomètres-heure`, `mètres carrés`, `degrés` |
| `M. Dupont`, `Dr Faure` | `Monsieur Dupont`, `le docteur Faure` |
| `n°4`, `§3` | `numéro quatre`, `paragraphe trois` |
| `1er`, `2e` | `premier`, `deuxième` |
| `&`, `+`, `=` | `et`, `plus`, `égale` |

- **Les années en chiffres sont bien lues** (`1986`, `2004`). Les garder ainsi.
- **Acronymes** : ceux qui se lisent comme un mot s'écrivent normalement (`OTAN`, `SIDA`). Ceux qui s'épellent se ponctuent : `U.R.S.S.`, `F.B.I.`
- **Noms propres étrangers** : quand la prononciation française attendue diffère de l'orthographe, écrire la forme phonétique et le signaler au checkpoint.
- **Ponctuation = respiration.** Le point produit une vraie pause, la virgule une courte. Points de suspension et tiret cadratin donnent des résultats imprévisibles : les éviter. Pour un silence appuyé, une phrase de trois mots sur sa propre ligne.
- **Pas de parenthèses.** Lues à plat. Ce qui est entre parenthèses est soit une phrase entière, soit à supprimer.
- **Citations** : chacune dans son propre beat, en annonçant qui parle avant. La voix ne changera pas — c'est la phrase qui doit le faire comprendre.

---

## LES FAITS

- **Ne jamais introduire un fait absent de `01-research.md`.** En cas de manque, s'arrêter et le signaler plutôt que combler. C'est ainsi qu'un documentaire se fait démonter en commentaires.
- Ce que la recherche marque contesté est énoncé comme contesté, avec la formulation exacte de sa colonne « Comment le script doit traiter ».
- Les trous s'assument à voix haute. « On ne sait pas ce qui s'est dit dans cette pièce » est une phrase de documentaire. L'inventer ne l'est pas.
- **Le titre est agressif, la narration ne l'est pas.** Le titre vit en dehors du script. Aucun superlatif, aucun suspense artificiel, aucune spéculation au même ton que les faits.

---

## REFUS

Mieux vaut échouer que deviner.

- Pas de `01-research.md` → s'arrêter. Pas de script sans faits.
- Un beat qui ne s'enchaîne ni par `mais` ni par `donc` → le couper, pas le garder avec un « et ».
- Une boucle qu'on ne sait pas fermer → ne pas l'ouvrir.
- Un fait qui manque pour tenir le pivot → le dire, et proposer de relancer la recherche sur ce point. Ne pas écrire autour du trou en faisant comme s'il n'existait pas.

---

## Format de `02-script.md`

```markdown
# Script — <titre publié>

- **mots** : <réel> / <budget> · **durée estimée** : <n> min <n> s
- **statut** : brouillon | validé

---

## Acte I — <titre>

### B001
> intention: <une ligne — ce qu'on VOIT pendant ce beat>
Le texte de la narration, tel qu'il sera prononcé, mot pour mot.

### B002
> intention: <...>
...

---

## Contrôle

| beat | lien | boucle | relance |
|---|---|---|---|
| B001 | — | ouvre L1 — pourquoi quatre litres de propofol | hook |
| B002 | donc | | |
| B003 | mais | ouvre L2 — qui a signé l'ordonnance | révélation |
| ... | | | |
| B031 | donc | ferme L2 | |
| B047 | donc | ferme L1 | résolution |

## Hooks écartés

- <version 2, telle qu'elle aurait été prononcée>
- <version 3>

## Points fragiles

- <ce dont on est le moins sûr, et pourquoi>
```

Règles de format, strictes :

- Beats numérotés `B001`, `B002`… en continu à travers tout le document, sans trou et sans reprise à chaque acte.
- Un beat = un plan visuel = 10 à 25 secondes, soit ~25 à 60 mots. Plus long, l'image ne tient pas ; plus court, le montage devient haché.
- La ligne `> intention:` est obligatoire et fait **une seule ligne**. Elle décrit ce que le spectateur voit, pas ce qu'il entend.
- Le corps d'un beat ne contient **que le texte prononcé**. Aucune didascalie, aucun crochet, aucune indication de mise en scène — tout partirait tel quel dans la voix.
- Le tableau `## Contrôle` porte **une ligne par beat**, dans l'ordre. `lien` vaut `—` pour B001, `donc` ou `mais` ensuite. `boucle` vaut `ouvre L<n> — <la question>`, `ferme L<n>`, ou rien. `relance` nomme le changement d'état, ou rien.

---

## Ce que le lint vérifie

Lancer `python -m fresque lint` plutôt que de vérifier à l'œil. Il ne passe rien :

longueur des beats et des phrases · pièges de synthèse vocale · formules proscrites · budget de mots · part de silence · longueur du hook · espacement des relances · présence d'un lien par beat · boucles ouvertes et jamais fermées · boucles trop courtes · trop de boucles simultanées · phrase courte tous les cinq beats.

Le reste reste ton travail, parce qu'aucune machine ne le voit :

- [ ] Le hook pose un fait, et le fait est le bon.
- [ ] Chaque `mais` est un vrai retournement, pas un `et` déguisé.
- [ ] Le pivot est audible : on entend le moment où l'histoire bascule.
- [ ] Chaque acte se termine sur une boucle ouverte, sauf le dernier.
- [ ] Aucune phrase ne demande de reprendre son souffle en cours de route.
- [ ] Aucun interdit du template n'a été enfreint.
