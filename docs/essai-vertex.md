# Essai Vertex AI — mode express

Date : 20 septembre 2026.
Réglage : `visuels.generation.provider: vertex`,
`visuels.generation.vertex.mode: express`. Modification locale de
`fresque.config.yaml`, non commitée.
Clé : présente dans `GOOGLE_CLOUD_KEY`. Ni `VERTEX_API_KEY` ni `GOOGLE_API_KEY`
n'étaient posées. `VERTEX_PROJECT` non plus — le mode express n'en demande pas.

**Vertex AI en mode express produit une image.** Le format demandé est honoré,
à la grille de définition du modèle près.

## Premier passage

Deux défauts relevés, tous deux corrigés sur cette branche avant ce second
passage :

1. `generateContent` répondait 400 — `Please use a valid role: user, model` :
   le corps de requête n'émettait pas de champ `role` sur `contents`. Vertex
   l'exige, AI Studio s'en passe.
2. `fresque images --list-models` attribuait un 401 à des identifiants de
   modèle périmés. Un 401 dit que la requête n'est pas identifiée, pas que le
   modèle est inconnu.

## Second passage — la commande

```
$ PYTHONPATH=pipeline python3 -m fresque essai-image "Photographie documentaire d'archive, un couloir de tribunal vide, lumière naturelle contrastée, grain argentique" --sortie /tmp/essai
Fournisseur : Vertex AI · mode express · clé lue dans GOOGLE_CLOUD_KEY
→ gemini-3.1-flash-image · « Photographie documentaire d'archive, un couloir de tribunal vide, lumière naturelle contrastée, grain argentique »
✓ /tmp/essai/S000.png · 1960 Ko · 11.5 s

real	0m11.840s
RETURN_CODE=0
```

Un seul modèle a été appelé, celui de la config : `gemini-3.1-flash-image`.
Aucun autre n'a été essayé — le premier a réussi.

## L'image obtenue

| | |
|---|---|
| Chemin | `/tmp/essai/S000.png` (hors dépôt, non commitée) |
| Taille | 2 007 215 octets |
| Dimensions | 1376 × 768 |
| Format | PNG, 8 bits par canal, RVB, non entrelacé |
| Temps | 11,5 s mesurés par la commande, 11,84 s de bout en bout |
| Modèle | `gemini-3.1-flash-image` |

Le contenu correspond au prompt : couloir vide, dallage, portes sombres,
lumière rasante, noir et blanc granuleux. La direction artistique préfixée
demande « sans texte ni inscription visible » ; l'image porte deux inscriptions
gravées sur des portes (« PORTE 14 », « 15 »). Relevé, pas creusé.

## `imageConfig` : honoré

La config demandait `ratio: "16:9"` et `taille: "1K"`.

| | |
|---|---|
| Ratio demandé | 16:9 = 1,7778 |
| Ratio obtenu | 1376 / 768 = 1,7917 |
| Écart | +0,8 % |

Deux constats appuient la conclusion :

- **Le champ est passé.** `images.generate()` ne réessaie sans `imageConfig`
  que sur un 400 nommant ce champ, et le signale alors sur la sortie
  (`pipeline/fresque/images.py:279`). Ce message n'est pas apparu : la seule
  requête envoyée portait `aspectRatio: "16:9"` et `imageSize: "1K"`, et elle a
  été acceptée.
- **La sortie n'est pas un carré.** 1376 × 768 est un format paysage, et 768 de
  haut est la définition attendue d'un « 1K » en paysage.

L'écart de 0,8 % s'explique par une grille : 1376 = 43 × 32 et 768 = 24 × 32.
Un 16:9 exact sur 768 de haut ferait 1365,33 px, qui n'est pas un multiple de
32. Le modèle semble arrondir au multiple de 32 le plus proche. C'est une
lecture des deux nombres obtenus, pas une règle vérifiée sur plusieurs
définitions.

Conséquence pour le montage : le cadre fait 1920 de large, l'image en fait
1376 — elle sera agrandie d'environ ×1,40 avant le Ken Burns, qui monte lui
jusqu'à ×1,18. Non mesuré ici.

## Non testé

- Le mode `projet` (jeton OAuth). Rien de ce passage ne dit s'il fonctionne.
- `fresque images --list-models`, qui rendait quatre 401 au premier passage. La
  commande n'a pas été relancée : on ne sait pas si elle répond autrement
  aujourd'hui, ni pourquoi les fiches de modèle refusaient la clé alors que
  `generateContent` l'accepte.
- Un appel témoin sans `imageConfig`, qui aurait donné les dimensions par
  défaut du modèle.
- Toute autre valeur de `ratio` ou de `taille` : la grille des 32 px n'est
  déduite que de ce seul couple de nombres.
- Le coût réel de l'appel. Aucune facturation n'a été consultée.
