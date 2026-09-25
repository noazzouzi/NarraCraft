# Essai alignement — ce que l'estimation syllabique coûtait vraiment

Mesuré le 19 septembre 2026, sur les 317 mots du montage d'essai.
Source : commit `75e6fd1`, qui a introduit `fresque aligner`.

Ce document existe parce que le chiffre vivait à trois endroits — `CLAUDE.md`,
la docstring de `pipeline/fresque/aligner.py`, et `README.md` — et qu'une
donnée à trois exemplaires se corrige à un seul le jour où elle change.

## Les deux états de `alignment.json`

Le champ `source` dit toujours d'où viennent les nombres.

| `source` | Bornes de beat | Position des mots | Écrit par | Coût |
|---|---|---|---|---|
| `mesure` | **données par le moteur** | estimées par syllabes | `fresque voice` | selon le moteur |
| `forced` | idem | **mesurées** | `fresque aligner` | nul, local |

Il y en avait un troisième, `estimate`, écrit par une commande `fresque
align` qui déduisait toutes les durées d'un débit annoncé en mots par
minute. Les deux ont été supprimés : un débit visé n'a jamais décrit ce que
le moteur fait vraiment, et l'écart se payait en aval.

Les bornes de beat de `mesure` ne sont pas non plus une mesure de notre
part. Le film est **une seule prise** — un appel au moteur pour toute la
narration — et c'est le moteur qui dit où tombe chaque phrase dedans
(évènements `SentenceBoundary` chez Edge). On recoupe ce qu'il annonce
contre le texte qu'on lui a envoyé, et on s'arrête si les deux divergent.

Ce champ décrit **d'où viennent les nombres, pas quel moteur a parlé**.
Qui a parlé est dans `voix.provider`. La valeur s'appelait `kokoro` du
temps où il n'y avait qu'un moteur, si bien qu'un fichier produit avec Edge
annonçait Kokoro ; les projets montés avant le renommage gardent l'ancienne
valeur, que le code accepte toujours.

Ce qui restait faux, c'est la position d'un mot *à l'intérieur* d'un beat —
donc les sous-titres, et tout surlignage mot à mot.

## L'écart mesuré

Estimation syllabique contre alignement forcé, sur les 317 mots :

| | Écart |
|---|---|
| médiane | **305 ms** |
| 9ᵉ décile | 816 ms |
| maximum | 1 709 ms |
| mots décalés de plus de 150 ms | **80 %** |

Quatre mots sur cinq tombaient à plus d'un sixième de seconde de leur place.
Un surlignage mot à mot ne tient pas là-dessus : sur une phrase de six mots,
l'erreur cumulée se voit immédiatement.

## Ce que ça a demandé

**Les nombres sont écrits en lettres avant alignement.** Le dictionnaire du
modèle ne connaît que `a-z` et l'apostrophe. « 2025 » a été prononcé « deux
mille vingt cinq » par la voix — vérifié, 3,31 s contre 1,54 s sans la
conversion. Aligner un joker à cet endroit reviendrait à jeter deux secondes
d'audio. Le convertisseur gère les irrégularités françaises : ni dizaine à
70 ni à 90, et « quatre vingt un » sans « et ».

**Le seuil de confiance a été retiré.** À 0,40, il signalait douze mots.
Test contrôlé : « Le vingt-cinq septembre » écrit en toutes lettres score
0,250 sur « vingt », aussi bas que la version en chiffres, alors que les deux
sont parfaitement placées — le modèle aligne des lettres, et le `g` et le `t`
de « vingt » sont muets. Le seuil signalait donc du français normal.

C'était la troisième fois qu'une règle criait au loup dans ce projet. C'est
de là que vient la règle de `CLAUDE.md` : *une règle automatique qui se
déclenche sur du contenu normal vaut moins que pas de règle.*

## Coût et dépendances

Modèle CTC multilingue MMS (1 100 langues), 1,2 Go, téléchargé une fois. Tout
tourne en local, sans clé ni réseau, gratuitement.

`torch` et `torchaudio` restent **optionnels** : sans eux, le pipeline garde
les positions estimées et tout le reste fonctionne.

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```
