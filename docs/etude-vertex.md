# Étude Vertex AI — génération d'images, mode express

Date : 20 septembre 2026. Treize appels réels.

Réglage commun : `visuels.generation.provider: vertex`,
`visuels.generation.vertex.mode: express`, `ratio: "16:9"`.
Modifications locales de `fresque.config.yaml`, non commitées.
Clé lue dans `GOOGLE_CLOUD_KEY`. `VERTEX_PROJECT` absent.

Prompt constant, sauf Q5 :

```
Un couloir de tribunal vide, photographie documentaire, lumière rasante
```

`images.build_prompt()` le préfixe de la direction artistique du projet, qui
contient déjà « sans texte ni inscription visible ». Toutes les mesures
portent donc sur le prompt complet, direction comprise.

Ce fichier remplace `docs/essai-vertex.md`, dont il reprend les constats.

## 1. Ce qui est établi

### Q1 — couverture des modèles

Un appel par modèle, `taille` laissée à la valeur du dépôt (`2K`).

| Modèle | Statut | Dimensions | Format | Poids | Temps |
|---|---|---|---|---|---|
| `gemini-3.1-flash-lite-image` | **400** | — | — | — | 0,8 s |
| `gemini-3.1-flash-image` | succès | 2752 × 1536 | PNG | 8 590 161 o | 17,6 s |
| `gemini-3-pro-image` | succès | 2752 × 1536 | PNG | 8 847 821 o | 24,1 s |
| `gemini-2.5-flash-image` | succès | 1344 × 768 | PNG | 1 290 787 o | 7,0 s |

Erreur du modèle `lite`, corps complet, non tronqué :

```
✗ gemini-3.1-flash-lite-image a répondu 400 : {
  "error": {
    "code": 400,
    "message": "Request contains an invalid argument.",
    "status": "INVALID_ARGUMENT"
  }
}
```

Deux faits qui ne se lisent pas dans la colonne « statut » :

- `gemini-2.5-flash-image` **n'a pas honoré `2K`**. Il a rendu 1344 × 768,
  c'est-à-dire la définition d'un `1K`, sans erreur ni avertissement. Son
  rapport vaut 1,750 au lieu de 1,792 pour les autres.
- Les trois modèles qui réussissent rendent du PNG. `lite` rend du JPEG
  (voir Q4).

### Q2 — effet de `taille`

Sur `gemini-3.1-flash-image` seul. Le cadre du montage fait 1920 px de large
(`montage.resolution`).

| `taille` | Dimensions | Rapport | Poids | Temps | Rapport à 1920 px |
|---|---|---|---|---|---|
| `1K` | 1376 × 768 | 1,792 | 1 862 446 o | 11,7 s | ×0,72 — **il faut agrandir** |
| `2K` | 2752 × 1536 | 1,792 | 8 590 161 o | 17,6 s | ×1,43 |
| `4K` | 5504 × 3072 | 1,792 | 21 232 032 o | 31,0 s | ×2,87 |

La mesure de `2K` est celle de Q1 : même modèle, même réglage, même prompt.

`2K` est la première valeur qui dépasse 1920 px. Chaque palier double
exactement les deux dimensions. Les trois définitions sont des multiples de
32 et le rapport ne bouge pas d'un palier à l'autre.

### Q3 — taille refusée

`gemini-3.1-flash-lite-image` avec `taille: "4K"` :

```
✗ gemini-3.1-flash-lite-image a répondu 400 : {
  "error": {
    "code": 400,
    "message": "Request contains an invalid argument.",
    "status": "INVALID_ARGUMENT"
  }
}
```

C'est **mot pour mot** la réponse obtenue en `2K` (Q1). Le corps ne nomme
aucun champ : ni `imageConfig`, ni `imageSize`, ni une valeur attendue.

Q4 fournit le témoin qui manque : le même modèle, avec le même prompt, en
`1K`, réussit cinq fois de suite. Le 400 vient donc bien de la définition
demandée, et non du modèle, de la clé ou du prompt.

| Réglage | Résultat |
|---|---|
| `lite` + `1K` | succès × 5 |
| `lite` + `2K` | 400 `INVALID_ARGUMENT`, sans champ nommé |
| `lite` + `4K` | 400 `INVALID_ARGUMENT`, sans champ nommé |

### Q4 — limite de débit

Cinq appels consécutifs sans pause, `gemini-3.1-flash-lite-image`, `1K`.

| # | Statut | Temps | Poids | Format |
|---|---|---|---|---|
| 1 | 200 | 3,1 s | 225 679 o | JPEG |
| 2 | 200 | 3,1 s | 185 192 o | JPEG |
| 3 | 200 | 3,0 s | 193 918 o | JPEG |
| 4 | 200 | 3,0 s | 182 672 o | JPEG |
| 5 | 200 | 3,5 s | 207 910 o | JPEG |

**Aucun 429.** Cinq images en un peu moins de 17 secondes de bout en bout.
Les cinq font 1376 × 768.

Aucun corps de 429 n'a donc été observé : ni `quotaId`, ni `retryDelay`, ni
rien d'autre.

### Q5 — forme du prompt

Un appel, `gemini-3.1-flash-image`, `1K`, avec le prompt renforcé :

```
Un couloir de tribunal vide, photographie documentaire, lumière rasante,
sans aucun texte ni inscription visible, aucune lettre, aucun chiffre
```

**L'image ne porte aucun texte.** Les portes sont nues : pas de plaque, pas
de numéro, pas de glyphe, y compris en agrandissant ×3 les zones de portes.

Témoin gratuit, tiré de l'image de Q2 (`1K`, même modèle, même définition,
prompt court) : la porte du premier plan droit porte **deux petites plaques
avec des glyphes**, illisibles à cette définition mais nettement lus comme
des inscriptions. C'est le même défaut que celui relevé dans l'essai
précédent (« PORTE 14 »).

Une image par condition. C'est une observation, pas une conclusion.

## 2. Ce que ça implique pour l'implémentation

**Modèle par défaut : `gemini-3.1-flash-image`.** C'est le seul des quatre
qui honore `2K` en moins de vingt secondes. `gemini-3-pro-image` rend
exactement les mêmes dimensions pour 6,5 s de plus (24,1 s contre 17,6 s) :
rien dans ces mesures ne justifie son coût supplémentaire pour du fond
documentaire. `gemini-2.5-flash-image` plafonne à 1344 px, sous le cadre.
C'est le réglage actuel du dépôt : ces mesures le confirment, elles ne le
changent pas.

**Garder `taille: "2K"`.** `1K` rend 1376 px pour un cadre de 1920 : il faut
agrandir de ×1,40 avant même le Ken Burns, qui monte à ×1,18 d'après le
commentaire de `fresque.config.yaml` — soit un besoin réel d'environ 2266 px.
`2K` (2752 px) couvre les deux. `4K` (5504 px) coûte 21 Mo et 31 s pour 2,87
fois la largeur du cadre : de la définition jetée au premier redimensionnement.

**`images._sans_image_config()` ne se déclenchera jamais sur ce refus.** Il
teste `"imageConfig" in reponse.text` (`pipeline/fresque/images.py:232`). Les
deux 400 mesurés (Q1, Q3) ne contiennent que `Request contains an invalid
argument.` La reprise automatique sans `imageConfig` est donc morte sur cette
porte : un modèle qui refuse la définition demandée fait échouer le plan au
lieu de retomber sur le format du modèle. Deux réponses possibles, et le choix
n'est pas à moi — soit élargir la détection à tout 400 `INVALID_ARGUMENT`
quand `imageConfig` a été envoyé, soit plafonner la définition par modèle. La
première a un défaut à peser : un 400 dû au prompt serait alors réessayé pour
rien, donc payé deux fois. *(Signalé, non corrigé : aucun fichier de
`pipeline/` n'a été touché.)*

**Le message d'erreur rendu à l'utilisateur ne dit pas ce qui est fautif.**
`{model} a répondu 400 : Request contains an invalid argument.` n'indique
nulle part que c'est la définition. Le diagnostic a demandé un appel témoin.

**Rien ne permet de conclure sur la logique de réessai.** Zéro 429 sur cinq
appels consécutifs. Le commentaire de `images.generate()` (lignes 269-274)
suppose qu'un 429 Vertex ne porte pas de `quotaId` et mérite la même attente
qu'un quota à la minute : cette étude ne le vérifie ni ne l'infirme. Ne pas
toucher au code sur la foi de ces mesures.

**Le format de sortie varie selon le modèle.** `lite` rend du JPEG, les trois
autres du PNG. `images.IMAGE_MIMES` couvre déjà les deux et l'extension du
fichier suit le type réel : rien à changer. À savoir si un jour un traitement
aval suppose du PNG.

## 3. Non testé

- **La clé sur une adresse portée par un projet.** `VERTEX_PROJECT` est absent
  de l'environnement, donc les routes
  `v1/projects/{id}/locations/{region}/...` — c'est-à-dire tout le mode
  `projet`, celui de production — n'ont pas pu être appelées. Question
  ouverte, et la plus importante : seul le mode `express` est mesuré ici.
- **Le coût réel.** Aucune facturation consultée. Les treize appels ne sont
  chiffrés nulle part dans cette étude.
- **La qualité comparée des modèles.** Une image par modèle, un seul sujet.
  Rien ne dit lequel rend le meilleur plan ; on ne mesure ici que des
  dimensions, des poids et des temps.
- **Le corps d'un 429 sur Vertex.** Aucun n'a été provoqué (Q4).
- **La variance des temps.** Un appel par point de mesure, sauf Q4. Les 17,6 s
  de `2K` sont un tirage, pas une moyenne.
- **`fresque images --list-models` en mode express.** Non relancé. L'essai
  précédent rendait quatre 401 sur les fiches publiques de modèle, ce que
  `vertex.modeles_image()` explique déjà par le fait qu'une clé d'API n'a pas
  cours sur cette route. Non revérifié.
- **`taille: "512px"`**, quatrième valeur annoncée par la config, et toute
  autre valeur de `ratio` que `16:9`.
- **La reprise sans `imageConfig`** elle-même : puisqu'elle ne se déclenche
  pas (section 2), on ne sait pas ce que `lite` rendrait sans le champ.
