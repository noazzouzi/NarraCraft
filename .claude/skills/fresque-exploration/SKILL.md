---
name: fresque-exploration
description: Transforme quelques mots-clés en quatre pistes de documentaire, chacune avec un angle, un pivot, ses preuves et trois titres agressifs. Produit `pistes.md`. Première étape du pipeline Fresque — à utiliser dès que l'utilisateur entre un sujet ("la faillite de Subway", "la mort de Michael Jackson") et avant `fresque-recherche`.
---

# Exploration

## RÔLE

Transformer des mots-clés en quatre pistes de documentaire, et laisser l'utilisateur choisir.

## ENTRÉE

- `projects/<slug>/projet.yaml` — son champ `sujet` porte les mots-clés
  tapés par l'utilisateur. C'est le point de départ, et il est dans le
  fichier, pas dans la conversation. Le champ `template` donne la direction
  artistique visée.
- Le web. 10 à 20 recherches, pas plus. On cherche des angles, pas des faits.

## SORTIE

`projects/<slug>/pistes.md`, exactement ce format :

```markdown
# Pistes — <mots-clés>

> <n> recherches · <AAAA-MM-JJ>

## Piste 1 — <angle en cinq mots>

- **angle** : <une phrase. La tension, pas le sujet.>
- **pivot** : <le moment où le spectateur comprend qu'il s'était trompé.>
- **risque** : <ce qui peut faire tomber la piste : archives absentes, fait contesté, sujet sensible.>

**Preuves**
1. <fait précis, chiffré ou daté> — [source](url)
2. <...> — [source](url)
3. <...> — [source](url)

**Titres**
- <sobre> — preuve 1
- <plus tendu> — preuve 2
- <le plus agressif> — preuve 2

## Piste 2 — ...
```

Quatre pistes. Trois preuves minimum par piste. Trois titres par piste.

## RÈGLES

- Les quatre pistes racontent quatre histoires différentes, pas quatre découpages de la même.
- Un angle est une tension : une contradiction, un écart entre ce qu'on croit et ce qui s'est passé. « Subway » est un sujet. « Le contrat qui payait le siège même quand le restaurant perdait de l'argent » est un angle.
- Pas de pivot, pas de piste. Un documentaire sans pivot est un exposé.
- Chaque preuve est un fait précis avec une URL. Pas de généralité, pas de « il est connu que ».
- Le risque est rempli honnêtement, même quand il condamne la piste. C'est ce que l'utilisateur lit en premier.
- Classer les pistes de la plus solide à la plus fragile.

## TITRE

Il doit faire cliquer, pas informer.

- Trois titres par piste, du plus sobre au plus agressif.
- Moins de 60 caractères. Une majuscule d'emphase au maximum.
- Ancré sur un nombre ou une date. Un titre sans chiffre ni date ne tient pas.
- Le cadrage est libre. Le fait dessous ne l'est pas : chaque titre cite la preuve qui le tient, par son numéro. Un titre dont la preuve manque n'est pas proposé.

Le titre vit en dehors de la narration. Le script, lui, garde ses interdits : titre agressif, narration sobre.

## REFUS

Mieux vaut échouer que deviner.

- Moins de trois preuves sourcées pour une piste → ne pas la proposer, et le dire.
- Moins de deux pistes tenables → s'arrêter, dire pourquoi, demander d'autres mots-clés.
- Un titre qu'aucune preuve ne tient → le supprimer, pas l'adoucir.
- Sujet vivant et accusation pénale sans condamnation → le dire dans `risque`, ne jamais l'affirmer dans un titre.

## FIN

Présenter les quatre pistes à l'utilisateur en quatre lignes — une par piste, le titre le plus agressif et le pivot. Puis s'arrêter. C'est lui qui choisit.

Son choix lance directement la recherche : `python -m fresque recherche <slug> --piste N`. Il n'y a pas d'étape entre les deux — l'angle et le pivot sont déjà ici.
