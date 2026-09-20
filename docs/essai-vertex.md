# Essai Vertex AI — mode express

Date : 20 septembre 2026.
Mode : `visuels.generation.provider: vertex`, `visuels.generation.vertex.mode: express`.
Modèle demandé : `gemini-3.1-flash-image` (valeur de `visuels.generation.model`).
Clé : présente dans `GOOGLE_CLOUD_KEY`, 53 caractères. Ni `VERTEX_API_KEY` ni
`GOOGLE_API_KEY` n'étaient posées. La modification de `fresque.config.yaml` était
locale et n'est pas commitée.

## Aucune image n'est sortie

Les deux commandes ont échoué, et pas pour la même raison.

## `fresque images --list-models`

```
$ PYTHONPATH=pipeline python3 -m fresque images --list-models
Fournisseur : Vertex AI · mode express · clé lue dans GOOGLE_CLOUD_KEY
✗ le projet répond, mais aucun des modèles d'image connus n'a de fiche.
  gemini-3.1-flash-lite-image → 401
  gemini-3.1-flash-image → 401
  gemini-3-pro-image → 401
  gemini-2.5-flash-image → 401
  · les identifiants de `vertex.MODELES_CANDIDATS` ont peut-être changé.
RETURN_CODE=1
```

Les quatre fiches publiques de modèle
(`v1beta1/publishers/google/models/<modèle>`, sondées avec `?key=`) rendent 401.
Le message de sortie attribue l'échec à des identifiants de modèle périmés ;
un 401 dit autre chose — la requête n'est pas identifiée. Non testé : si ces
mêmes fiches répondent 200 avec un jeton OAuth (mode `projet`).

## `fresque essai-image`

```
$ PYTHONPATH=pipeline python3 -m fresque essai-image "Photographie documentaire d'archive, un couloir de tribunal vide, lumière naturelle contrastée, grain argentique" --sortie /tmp/essai
Fournisseur : Vertex AI · mode express · clé lue dans GOOGLE_CLOUD_KEY
→ gemini-3.1-flash-image · « Photographie documentaire d'archive, un couloir de tribunal vide, lumière naturelle contrastée, grain argentique »
✗ gemini-3.1-flash-image a répondu 400 : {
  "error": {
    "code": 400,
    "message": "Please use a valid role: user, model.",
    "status": "INVALID_ARGUMENT"
  }
}

real	0m0.825s
RETURN_CODE=1
```

Rien n'a été écrit : `/tmp/essai` n'existe pas.

## Ce que les deux codes de retour disent

`generateContent` répond 400, pas 401. La clé a donc été acceptée sur cet
appel, et c'est le corps de la requête qui est refusé : Vertex exige un champ
`role` sur chaque entrée de `contents`, que `images._corps()` n'émet pas
(`{"contents": [{"parts": [{"text": prompt}]}]}`, `pipeline/fresque/images.py:218`).
AI Studio, l'autre porte, s'en passe — c'est la seule divergence de corps
observée ici, alors que le module `vertex.py` annonce un corps identique sur
les deux portes.

Le 401 des fiches de modèle et le 400 de la génération ne se contredisent pas
nécessairement : ce ne sont ni la même version d'API (`v1beta1` contre `v1`),
ni le même verbe (GET contre POST). Je n'ai pas cherché laquelle de ces
différences explique le 401, et je n'ai pas vérifié si la clé porte une
restriction d'API.

## `imageConfig` et le ratio 16:9

Non testé. Le 400 reçu ne nomme pas `imageConfig`, donc la reprise sans ce
champ (`images._sans_image_config()`) ne s'est pas déclenchée, et aucune image
n'a été produite. On ne sait donc pas si Vertex honore `aspectRatio: "16:9"` et
`imageSize: "1K"`, ni quelles dimensions il rendrait.
