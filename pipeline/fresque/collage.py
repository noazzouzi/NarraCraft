"""Compose une planche de collage — le style « Vox » relevé chez Frontier.

POURQUOI UN MOTEUR DE COMPOSITION, ET PAS UNE IMAGE GÉNÉRÉE
===========================================================
L'analyse du concurrent est formelle sur ce point (`docs/analyse-frontier.md`) :

> Fond papier beige, photos **découpées au contour avec un liseré blanc**,
> tampons rouges en papier déchiré [...] Il ne demande aucune image générée :
> il demande un **moteur de composition**.

L'essai de génération l'a confirmé par l'autre bout. Quatre modèles, quatre
mesures (`docs/essai-collage.md`, `PROMPT-V2.md`) : le meilleur rendu coûtait
0,0336 $ l'image et restait **un aplat cuit dans des pixels**. On ne peut ni
animer ses couches séparément, ni changer sa palette quand le template change,
ni corriger la position d'une pièce. Trois choses qu'un template est censé
pouvoir faire.

Ici, les pièces existent séparément jusqu'au rendu. Elles se déplacent donc à
des vitesses différentes — c'est la parallaxe, et c'est précisément ce qu'une
affiche générée ne fera jamais. Le fond de papier bouge à peine, la photo
suit, les accents passent devant.

QUI DÉCIDE QUOI
===============
Le pipeline décide **quelles pièces et où** ; le moteur décide **comment les
dessiner**. C'est la même frontière que partout ailleurs : `timeline` calcule
les frames, Remotion les joue ; ici `collage` calcule une mise en page, et
Remotion trace un bord déchiré et une trame d'impression.

Conséquence voulue : la mise en page atterrit dans `06-timeline.json`, donc
elle est **inspectable et corrigeable à la main**. Déplacer une flèche, c'est
éditer un nombre et relancer `fresque render`. C'est le principe de l'atelier,
appliqué à une image.

Et comme le Ken Burns, la variation est tirée d'un grain **déterministe** :
deux rendus du même plan donnent la même planche, mais deux plans ne se
ressemblent pas. Une mise en page identique d'un plan à l'autre se lit comme
un gabarit ; c'est exactement ce qu'on reproche aux vidéos générées.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

from . import config
from .shots import Shot


def jitter(seed: str, salt: str) -> float:
    """Pseudo-aléatoire stable dans [0, 1).

    Deux appels avec les mêmes arguments rendent toujours la même valeur, sur
    n'importe quelle machine — c'est ce qui permet de varier sans renoncer à
    un rendu reproductible. Le mouvement de caméra s'en sert aussi.
    """
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def _entre(seed: str, salt: str, bas: float, haut: float) -> float:
    return bas + (haut - bas) * jitter(seed, salt)


#: Rapport du cadre. Sert à convertir une largeur normalisée en hauteur
#: normalisée sans déformer une photo : les deux axes n'ont pas la même
#: échelle en pixels.
def _ratio_cadre() -> float:
    largeur, hauteur = config.get("montage", "resolution", default=[1920, 1080])
    return float(largeur) / float(hauteur)


#: Bande haute laissée libre quand le plan porte une accroche. Le titre y est
#: composé par Remotion — accents fiables, typographie du template, et un
#: titre qu'un surligneur peut balayer. Un titre cuit dans une image ne permet
#: aucune des trois.
#:
#: Réglable par template, parce que c'est une question de typographie : un
#: template qui compose ses accroches plus grandes en a besoin de plus. La
#: valeur par défaut tient une accroche de deux lignes à la taille du
#: `fresque.config.yaml` de base.
BANDE_TITRE_DEFAUT = 0.46

#: Marge basse. Les sous-titres se posent à 90,8 % ; on ne réserve pas cette
#: bande pour autant — la planche continue dessous, comme chez Frontier — mais
#: rien ne doit toucher le bord du cadre.
MARGE_BAS = 0.03
MARGE_HAUT = 0.05

#: De quoi laisser le tampon déborder au-dessus de la photo sans entrer dans
#: la bande du titre. Sans cette réserve, le tampon montait dans l'accroche —
#: vu au rendu : un aplat rouge derrière la première ligne du texte.
DEBORD_BLOC = 0.03

#: Le vocabulaire de formes. Volontairement court : ce sont les pièces
#: relevées sur les planches Frontier, et rien d'autre. Une forme de plus
#: qu'on n'a pas vue chez eux est une invention, pas une reproduction.
ACCENTS = ("triangle", "cercle", "demi_cercle", "zigzag", "fleche")

#: Profondeurs. Elles ne servent qu'à une chose : donner à chaque pièce sa
#: part du mouvement de caméra. Le fond bouge à peine, l'avant-plan glisse.
PROFONDEUR_BLOC = 0.12
PROFONDEUR_PHOTO = 0.50
PROFONDEUR_ACCENT = (0.70, 1.00)
PROFONDEUR_RUBAN = 0.58


def _demi_hauteur(largeur: float, hauteur: float, rotation_deg: float) -> float:
    """La demi-hauteur d'une pièce UNE FOIS TOURNÉE, en fraction du cadre.

    Borner une pièce sur sa hauteur nominale ne suffit pas : une feuille
    large inclinée de quatre degrés lève un coin bien au-dessus de son bord
    haut. Relevé au rendu — le tampon rouge remontait dans la deuxième ligne
    de l'accroche alors que son centre respectait la bande.

    La largeur est une fraction de la LARGEUR du cadre ; sa contribution à la
    hauteur passe donc par le rapport du cadre.
    """
    angle = math.radians(abs(rotation_deg))
    return (hauteur * math.cos(angle)
            + largeur * _ratio_cadre() * math.sin(angle)) / 2


def _photo(shot: Shot, ratio_photo: float | None, haut: float) -> dict[str, Any]:
    """La photo, posée sur son papier.

    Elle est cadrée en largeur puis ramenée dans la zone utile si elle
    déborde — une photo en portrait sort du cadre autrement, et l'archive en
    est pleine (pages, portraits, affiches).
    """
    cadre = _ratio_cadre()
    ratio = ratio_photo or 1.4

    largeur = _entre(shot.id, "photo_w", 0.40, 0.52)
    hauteur = largeur * cadre / ratio

    # La photo se cadre dans une zone déjà rétrécie du débord du tampon :
    # c'est le tampon qui doit tenir sous le titre, pas seulement la photo.
    plafond = haut + DEBORD_BLOC
    plancher = 1.0 - MARGE_BAS - DEBORD_BLOC
    dispo = plancher - plafond
    if hauteur > dispo:
        hauteur = dispo
        largeur = hauteur * ratio / cadre

    rotation = _entre(shot.id, "photo_rot", -3.0, 3.0)
    demi = _demi_hauteur(largeur, hauteur, rotation)
    if demi * 2 > dispo:
        reduction = dispo / (demi * 2)
        largeur, hauteur, demi = largeur * reduction, hauteur * reduction, dispo / 2

    cx = _entre(shot.id, "photo_x", 0.38, 0.60)
    cy = plafond + dispo / 2 + _entre(shot.id, "photo_y", -0.03, 0.03)
    # Garde la pièce entière dans le cadre, quelle que soit la dérive.
    cx = min(max(cx, largeur / 2 + 0.04), 1 - largeur / 2 - 0.04)
    cy = min(max(cy, plafond + demi), plancher - demi)

    return {
        "role": "photo",
        "forme": "papier",
        "bords": "dechire" if jitter(shot.id, "bords") < 0.6 else "coupe",
        "x": round(cx, 4),
        "y": round(cy, 4),
        "w": round(largeur, 4),
        "h": round(hauteur, 4),
        "rotation_deg": round(rotation, 2),
        "profondeur": PROFONDEUR_PHOTO,
        "graine": f"{shot.id}:photo",
    }


def _bloc(shot: Shot, photo: dict[str, Any], haut: float) -> dict[str, Any]:
    """Le tampon de papier déchiré posé sous la photo.

    C'est lui qui fait la planche. Sans lui, une photo avec un liseré blanc
    sur du papier beige est une photo avec un cadre ; avec lui, elle est
    collée sur quelque chose.

    Il est borné par la bande du titre comme la photo, et pour la même
    raison : c'est la pièce la plus grande de la planche, donc la première à
    déborder. Au premier rendu, elle passait derrière la première ligne de
    l'accroche.
    """
    echelle = _entre(shot.id, "bloc_k", 1.10, 1.26)
    largeur, hauteur = photo["w"] * echelle, photo["h"] * echelle
    rotation = _entre(shot.id, "bloc_rot", -4.0, 4.0)

    dispo = 1.0 - haut - MARGE_BAS
    demi = _demi_hauteur(largeur, hauteur, rotation)
    if demi * 2 > dispo:
        reduction = dispo / (demi * 2)
        largeur, hauteur, demi = largeur * reduction, hauteur * reduction, dispo / 2

    cx = photo["x"] + _entre(shot.id, "bloc_x", -0.05, 0.05)
    cy = photo["y"] + _entre(shot.id, "bloc_y", -0.03, 0.03)
    cx = min(max(cx, largeur / 2 + 0.01), 1 - largeur / 2 - 0.01)
    cy = min(max(cy, haut + demi), 1 - MARGE_BAS - demi)

    return {
        "role": "bloc",
        "forme": "papier",
        "bords": "dechire",
        "couleur": "accent",
        "x": round(cx, 4),
        "y": round(cy, 4),
        "w": round(largeur, 4),
        "h": round(hauteur, 4),
        "rotation_deg": round(rotation, 2),
        "profondeur": PROFONDEUR_BLOC,
        "graine": f"{shot.id}:bloc",
    }


def _emplacements(photo: dict[str, Any]) -> list[tuple[float, float]]:
    """Les places possibles pour un accent, autour de la photo.

    Elles suivent la photo au lieu d'être fixes dans le cadre : une photo
    étroite rapproche ses accents, une photo large les écarte. Sans quoi une
    planche sur un portrait laisserait deux trous sur les côtés.
    """
    hw, hh = photo["w"] / 2, photo["h"] / 2
    x, y = photo["x"], photo["y"]
    return [
        (x - hw - 0.065, y - hh + 0.10),
        (x - hw - 0.075, y),
        (x - hw - 0.055, y + hh - 0.09),
        (x + hw + 0.065, y - hh + 0.10),
        (x + hw + 0.075, y),
        (x + hw + 0.055, y + hh - 0.09),
        (x - hw * 0.45, y - hh - 0.065),
        (x + hw * 0.45, y - hh - 0.065),
        (x - hw * 0.55, y + hh + 0.055),
        (x + hw * 0.55, y + hh + 0.055),
    ]


def _accents(shot: Shot, photo: dict[str, Any], haut: float) -> list[dict[str, Any]]:
    """Trois à six pièces géométriques autour de la photo.

    Le nombre et les places sont tirés du grain, donc stables. Ce qui tombe
    hors cadre ou dans la bande du titre est écarté plutôt que replacé : une
    planche à quatre accents vaut mieux qu'une planche à six dont deux sont
    poussés là où il reste de la place.
    """
    places = _emplacements(photo)
    ordre = sorted(range(len(places)),
                   key=lambda i: jitter(shot.id, f"ordre{i}"))
    # Plafonné au nombre de formes disponibles : au-delà, l'une d'elles
    # reviendrait forcément sur la même planche, et un doublon se lit comme
    # une panne plutôt que comme du hasard.
    voulus = min(3 + int(jitter(shot.id, "nb_accents") * 4), len(ACCENTS))

    # Les formes sont distribuées, pas tirées une par une. Un tirage
    # indépendant par accent est uniforme et reste pourtant capable de poser
    # trois demi-cercles sur la même planche — relevé sur S001. À l'œil, ça
    # ne se lit pas comme du hasard mais comme une panne. En parcourant un
    # ordre mélangé par plan, aucune forme ne revient tant que les autres
    # n'ont pas servi, et deux plans n'ont toujours pas la même planche.
    formes = sorted(ACCENTS, key=lambda f: jitter(shot.id, f"forme:{f}"))

    pieces: list[dict[str, Any]] = []
    for rang, index in enumerate(ordre):
        if len(pieces) >= voulus:
            break
        cx, cy = places[index]
        graine = f"{shot.id}:a{index}"

        taille = _entre(graine, "taille", 0.028, 0.062)
        hauteur = taille * _ratio_cadre()
        if not (MARGE_HAUT + hauteur / 2 <= cy <= 1 - MARGE_BAS - hauteur / 2):
            continue
        if cy - hauteur / 2 < haut:
            continue
        if not (0.03 + taille / 2 <= cx <= 0.97 - taille / 2):
            continue

        forme = formes[len(pieces) % len(formes)]
        # Une flèche qui ne désigne rien n'est qu'un chevron. Celle-ci pointe
        # vers la photo, et l'angle est de la géométrie — pas un choix.
        if forme == "fleche":
            rotation = math.degrees(math.atan2(photo["y"] - cy, photo["x"] - cx)) + 90
        else:
            rotation = _entre(graine, "rot", -20.0, 20.0)

        pieces.append({
            "role": "accent",
            "forme": forme,
            "couleur": "accent" if jitter(graine, "teinte") < 0.55 else "encre",
            "x": round(cx, 4),
            "y": round(cy, 4),
            "w": round(taille, 4),
            "h": round(hauteur, 4),
            "rotation_deg": round(rotation, 2),
            "profondeur": round(
                _entre(graine, "prof", *PROFONDEUR_ACCENT), 3),
            "graine": graine,
        })
    return pieces


def _rubans(shot: Shot, photo: dict[str, Any], haut: float) -> list[dict[str, Any]]:
    """Un ou deux morceaux d'adhésif, en travers d'un coin de la photo.

    C'est le détail qui dit « collé » plutôt que « superposé ». Il tient à
    deux coins au plus : sur les quatre, la photo a l'air encadrée.

    Un adhésif chevauche son coin — c'est ce qui le fait tenir — donc il
    dépasse de la photo par construction. Il est borné comme les autres
    pièces : sur une photo qui remplit la zone, le morceau du haut sortait
    du cadre, ou montait dans la bande du titre.
    """
    hw, hh = photo["w"] / 2, photo["h"] / 2
    coins = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    choisis = sorted(range(4), key=lambda i: jitter(shot.id, f"ruban{i}"))
    combien = 1 + int(jitter(shot.id, "nb_rubans") * 2)

    pieces: list[dict[str, Any]] = []
    for index in choisis[:combien]:
        sx, sy = coins[index]
        largeur = _entre(f"{shot.id}:r{index}", "w", 0.045, 0.075)
        hauteur = largeur * _ratio_cadre() * 0.42
        # En travers du coin : c'est ce qui tient une photo, un adhésif
        # parallèle au bord ne tient rien.
        rotation = -45 * sx * sy + _entre(f"{shot.id}:r{index}", "rot", -8.0, 8.0)
        demi = _demi_hauteur(largeur, hauteur, rotation)

        cy = photo["y"] + sy * hh
        cy = min(max(cy, haut + demi), 1 - MARGE_BAS - demi)
        cx = photo["x"] + sx * hw
        cx = min(max(cx, largeur / 2), 1 - largeur / 2)

        pieces.append({
            "role": "ruban",
            "forme": "ruban",
            "couleur": "adhesif",
            "x": round(cx, 4),
            "y": round(cy, 4),
            "w": round(largeur, 4),
            "h": round(hauteur, 4),
            "rotation_deg": round(rotation, 2),
            "profondeur": PROFONDEUR_RUBAN,
            "graine": f"{shot.id}:r{index}",
        })
    return pieces


def compose(shot: Shot, ratio_photo: float | None) -> dict[str, Any]:
    """La planche d'un plan : une liste de pièces, du fond vers l'avant.

    L'ordre de la liste **est** l'ordre de superposition. Le moteur les
    dessine dans l'ordre reçu et ne trie rien — trier dans le moteur voudrait
    dire qu'une correction à la main dans `06-timeline.json` ne servirait à
    rien.
    """
    bande = float(config.get("montage", "collage", "bande_titre",
                             default=BANDE_TITRE_DEFAUT))
    haut = bande if shot.accroche else MARGE_HAUT

    photo = _photo(shot, ratio_photo, haut)
    pieces = [_bloc(shot, photo, haut), photo,
              *_rubans(shot, photo, haut), *_accents(shot, photo, haut)]
    pieces.sort(key=lambda p: p["profondeur"])

    return {
        "bande_titre": round(haut, 4) if shot.accroche else 0.0,
        "pieces": pieces,
    }


def style() -> dict[str, Any]:
    """La direction artistique de la planche, telle que le template la donne.

    Rien ici n'est décidé par le moteur de rendu, et rien n'est en dur dans
    un composant : c'est la condition posée par CLAUDE.md pour qu'une
    quatrième thématique n'amène pas un quatrième moteur.
    """
    bloc = config.get("montage", "collage", default={}) or {}
    return {
        "papier": str(bloc.get("papier", "#F2EDE1")),
        "encre": str(bloc.get("encre", "#1C1B19")),
        "accent": str(bloc.get("accent", "#8C2230")),
        "lisere": str(bloc.get("lisere", "#FBF8F1")),
        "adhesif": str(bloc.get("adhesif", "rgba(226,214,186,0.72)")),
        # Le voile posé sous l'accroche. Nul par défaut, et c'est une mesure :
        # sur une planche claire, le texte est en encre sombre et n'a besoin
        # d'aucun fond. Le premier rendu portait un voile crème à 90 %, qui
        # délavait la moitié haute de la planche — le tampon rouge virait au
        # rose, la photo perdait ses noirs. Un template à papier sombre le
        # rallume.
        #
        # Déclaré plutôt que dérivé du papier : dériver voudrait dire
        # concaténer une transparence à une chaîne hexadécimale, ce qui casse
        # le jour où un template écrit une couleur en `rgb()` ou par son nom.
        "voile_titre": str(bloc.get("voile_titre", "transparent")),
        "ombre": str(bloc.get("ombre", "rgba(60,44,28,0.30)")),
        "trame": float(bloc.get("trame", 0.35)),
        "grain": float(bloc.get("grain", 0.05)),
        "photo": str(bloc.get("photo", "duotone")),
        # Part du mouvement de caméra que reçoit la pièce la plus au fond.
        # À 1,0 toutes les pièces bougent ensemble et la planche redevient
        # une image plate — c'est-à-dire exactement ce qu'on cherchait à ne
        # pas faire.
        "parallaxe_min": float(bloc.get("parallaxe_min", 0.25)),
        "cascade_s": float(bloc.get("cascade_s", 0.05)),
        "lisere_px": int(bloc.get("lisere_px", 14)),
    }
