---
name: fresque-controle
description: Regarde chaque visuel sourcé d'un projet Fresque et dit s'il montre vraiment ce que le plan demandait. Écrit `05-visuals/controle.jsonl`, append-only et reprenable. À utiliser après `fetch` ou `images`, ou quand l'utilisateur demande de vérifier les visuels, de contrôler les images, ou se plaint qu'une image est hors sujet.
---

# Contrôle des visuels

## RÔLE

Regarder chaque image et dire si elle montre ce que le plan demandait. Rien d'autre.

## POURQUOI CETTE ÉTAPE EXISTE

Le code vérifie déjà la licence, la résolution, le ratio et les doublons. Il ne peut pas vérifier la seule chose qui compte vraiment : **que l'image montre le bon sujet.**

Mesuré sur un film réel : la requête `paper receipt roll` a rendu « Excelsior perforated toilet rolls » — des rouleaux de papier toilette victoriens, sous bonne licence, en bonne résolution, sans doublon. Tout ce que le code sait vérifier était vert. L'image est arrivée dans le montage.

Les fonds d'archive combinent les mots d'une requête sans comprendre ce qu'on cherche. Seul un regard attrape ça.

## ENTRÉE

- `projects/<slug>/03-shots.json` — ce que chaque plan devait montrer : `intention`, `requete`, `prompt`.
- `projects/<slug>/05-visuals/assets.json` — le fichier réellement obtenu, et son titre.
- Les images elles-mêmes, dans `projects/<slug>/05-visuals/`.

## SORTIE

`projects/<slug>/05-visuals/controle.jsonl`, **append-only**. Une ligne par plan contrôlé :

```json
{"shot":"S014","verdict":"refaire","raison":"des rouleaux de papier toilette victoriens ; le plan demande un ticket de caisse"}
{"shot":"S000","verdict":"garde","raison":""}
```

Trois verdicts, et trois seulement :

| verdict | quand |
|---|---|
| `garde` | l'image montre le sujet demandé |
| `refaire` | elle montre autre chose, ou elle est inutilisable |
| `doute` | elle peut passer mais elle est faible — l'humain tranchera |

`raison` est obligatoire pour `refaire` et `doute`, vide pour `garde`. Elle dit **ce qu'on voit**, pas ce qu'on aurait voulu : « une agence bancaire indonésienne » vaut mieux que « pas le bon sujet ».

## PROCÉDURE

**1. Reprendre.** Lire `controle.jsonl` s'il existe et noter les plans déjà jugés. Ne pas les rejuger. `--recommencer` efface le fichier avant de commencer, et c'est le code qui le fait, pas toi.

**2. Par lots de quinze.** Lire les images d'un lot, écrire les quinze lignes, passer au suivant. Quatre-vingts images d'un coup ne tiennent pas, et un plantage au soixantième perdrait tout.

**3. Ne juger que ce qui a un fichier.** Un plan `motion` n'a pas d'image : il est construit au rendu. Un plan sans visuel n'a rien à contrôler. Les sauter tous les deux, sans ligne.

**4. Dire à l'utilisateur**, en trois lignes : combien de `garde`, combien de `refaire`, et les trois pires — le plan, ce qu'il demandait, ce qu'on voit.

## COMMENT JUGER

La question est toujours la même : **un spectateur qui entend la narration de ce beat, et qui voit cette image, comprend-il qu'elle illustre ce qui est dit ?**

**`refaire` sans hésiter :**
- Le sujet est absent. On demande une devanture de restaurant, on a un musée du papier.
- L'objet est le mauvais objet. On demande un ticket de caisse, on a du papier toilette.
- Le lieu est le mauvais pays quand le pays compte. Une agence bancaire à Jakarta pour un réseau américain.
- L'époque est fausse quand l'époque compte. Un reçu de 1890 pour une caisse enregistreuse de 2019.
- C'est une capture de jeu vidéo, un rendu 3D, une affiche de film, une reconstitution.
- Un filigrane, un logo d'agence, une mention de droits incrustée.
- Illisible : flou, tronqué, trop sombre, sujet minuscule au fond du cadre.

**`garde` malgré l'imperfection :**
- Une illustration générique qui fait son travail — une file d'attente pour parler de file d'attente.
- Une image moyenne mais juste. La planche de collage et le duotone rattrapent beaucoup.
- Un cadrage quelconque. Le mouvement de caméra s'en occupe.

**`doute` :**
- Le sujet y est mais noyé.
- L'image est juste mais date visiblement d'une autre décennie, sans que ce soit disqualifiant.
- Tu hésiterais si tu montais le film toi-même.

## RÈGLES

- **Un plan, une ligne.** Jamais deux lignes pour le même plan dans une même passe.
- **Regarder l'image, pas son titre.** Le titre du fichier ment souvent : « Signed Contract between UDC, SCV and Donald » peut être une photo correcte de document signé.
- Juger sur l'`intention` du plan d'abord, sur la `requete` ensuite. L'intention dit ce que le montage attend ; la requête n'est qu'un moyen.
- Une image générée se juge comme les autres. Elle peut rater son sujet aussi.
- Ne jamais modifier `assets.json`, ne jamais supprimer un fichier. Ce n'est pas ton travail : le code s'en charge avec `fresque refaire`.

## REFUS

- Pas de `03-shots.json` ou pas d'`assets.json` → s'arrêter. Il n'y a rien à contrôler.
- Une image qu'on ne peut pas ouvrir → une ligne `refaire`, raison « fichier illisible ». Ne pas s'arrêter pour autant.

## FIN

Annoncer le compte, puis la commande qui répare :

```
python -m fresque refaire <slug> --refuses
```

Elle re-source tous les plans marqués `refaire`, en écartant l'image déjà refusée. Les `doute` restent, et se voient dans la galerie.
