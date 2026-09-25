---
description: Démarre un nouveau documentaire Fresque — exploration, recherche, script — jusqu'au premier checkpoint
---

Démarrer un nouveau projet de documentaire Fresque sur le sujet suivant :

$ARGUMENTS

Créer le projet avec `python -m fresque nouveau "<sujet>"`, puis enchaîner
les trois étapes d'écriture :

1. `fresque-exploration` → `pistes.md`
2. **S'arrêter.** Présenter les quatre pistes et demander laquelle retenir.
   Écrire le choix avec `python -m fresque recherche <slug> --piste N`.
3. `fresque-recherche` → `01-research.md`
4. `fresque-script` → `02-script.md`

Si la recherche contredit la piste retenue, le dire avant d'écrire le
script.

T'arrêter après le script : c'est le checkpoint 1. Présenter alors, de
façon compacte :

- le slug du projet et le chemin de ses fichiers
- la piste retenue en une phrase
- le compte de mots réel contre la cible
- ce qui est solide dans la recherche, et ce qui est fragile
- les deux ou trois passages du script dont tu es le moins sûr

Ne rien générer de payant. Aucune voix, aucune image.
