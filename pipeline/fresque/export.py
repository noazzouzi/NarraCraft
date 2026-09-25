"""`fresque export` — l'atelier figé dans un dossier, ouvrable sans rien lancer.

Le serveur ne sert que la machine qui le fait tourner. Quand il faut montrer
un montage à quelqu'un — un relecteur, un client, soi-même sur un autre
poste — il faut un dossier qu'on envoie et qui s'ouvre en double-clic.

C'est le même atelier, avec deux différences assumées, toutes deux visibles
sur la page plutôt que découvertes à l'usage :

- **Rien ne se lance.** Sans serveur il n'y a pas de sous-processus, donc
  pas de pilote. Les pages sont celles qu'on lit, pas celles qui agissent.
- **Les images sont réduites.** Un projet de quinze minutes pèse 99 Mo de
  visuels en pleine définition, pour une planche contact qui les affiche à
  228 pixels de large. On les redimensionne à la largeur où on les regarde,
  ce qui divise le poids par plus de vingt sans qu'on voie la différence.

Le dossier produit ne contient aucun chemin absolu et ne charge rien depuis
le réseau : il reste lisible dans dix ans, et hors ligne.
"""
from __future__ import annotations

import re
import shutil
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import apercu, config, review, serveur

#: La planche contact affiche les vignettes à 228 px de large, et la carte
#: d'un projet à 310. Le double couvre les écrans à forte densité — au-delà,
#: on paie des octets que personne ne voit.
LARGEUR_VIGNETTE = 620

#: Les images passent en JPEG à cette qualité. 82 est le point où l'artefact
#: cesse d'être visible sur une photo d'archive.
QUALITE = 82

_BALISE_VIDEO = re.compile(r"<video\b[^>]*></video>", re.IGNORECASE)


@dataclass
class Bilan:
    fichiers: int = 0
    octets_source: int = 0
    octets_export: int = 0
    projets: int = 0
    videos: int = 0

    @property
    def gain(self) -> float:
        if not self.octets_source:
            return 1.0
        return self.octets_source / max(self.octets_export, 1)


#: Exporté, un lien pointe sur un fichier voisin plutôt que sur une route.
#: L'index d'un projet est sa page de validation : c'est la seule des deux
#: qui ait encore un sens sans serveur derrière.
LIENS = serveur.Liens(
    accueil="index.html",
    projet=lambda slug: f"p/{urllib.parse.quote(slug)}/review.html",
    fichier=lambda slug, rel: f"p/{urllib.parse.quote(slug)}/{urllib.parse.quote(rel)}",
    template=lambda nom: f"t/{urllib.parse.quote(nom)}.html",
)


def _reduire(source: Path, destination: Path, largeur: int) -> int:
    """Copie une image en la ramenant à la largeur où elle est regardée.

    Retourne la taille écrite. Une image déjà plus petite est copiée telle
    quelle : la réencoder ne ferait que lui retirer de la qualité.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            if image.width <= largeur:
                shutil.copy2(source, destination)
                return destination.stat().st_size
            hauteur = round(image.height * largeur / image.width)
            reduite = image.convert("RGB").resize((largeur, hauteur), Image.LANCZOS)
            reduite.save(destination, "JPEG", quality=QUALITE, optimize=True)
    except OSError:
        # Un fichier que Pillow ne sait pas ouvrir reste un fichier du
        # projet : on le copie plutôt que de le faire disparaître de la
        # planche sans le dire.
        shutil.copy2(source, destination)
    return destination.stat().st_size


def _greffer_bandeau(page: str, actif: str, fin: str, remonte: str) -> str:
    """Ajoute à une page autonome le bandeau qui la relie aux autres.

    `review.html` et l'aperçu d'un template sont écrits pour s'ouvrir seuls.
    Placés dans un export, ils deviennent des culs-de-sac : on y entre et
    on ne sait plus revenir. Seules les règles du bandeau sont greffées —
    verser toute la feuille du serveur réécrirait leur mise en page.
    """
    bandeau = serveur._entete(actif, serveur.Liens(accueil=remonte), fin)
    return page.replace(
        "</head><body>",
        f"<style>{serveur._BARRE}</style></head><body>{bandeau}",
        1,
    )


def _index_export(bilan: Bilan, videos: bool) -> str:
    """L'atelier, plus l'avertissement qui empêche de le confondre."""
    page = serveur.page_atelier(LIENS)
    note = (
        '<p class="pied" style="border-left:3px solid #c9a227;padding-left:14px">'
        "<b>Copie figée.</b> Cet atelier est un export : les pages se lisent, "
        "rien ne s'y lance. Les images sont réduites à la largeur où elles sont "
        f"affichées ({LARGEUR_VIGNETTE} px), soit {bilan.gain:.0f} fois plus "
        "légères que les originales."
        + ("" if videos else " Les vidéos ne sont pas incluses.")
        + " Pour l'atelier complet : <code>python -m fresque serve</code> "
        "dans le dépôt.</p>"
    )
    return page.replace('<p class="pied">', note + '<p class="pied">', 1)


def exporter(destination: Path, videos: bool = False,
             largeur: int = LARGEUR_VIGNETTE) -> Bilan:
    """Écrit l'atelier complet dans `destination`, et rend ce qu'il a coûté."""
    destination.mkdir(parents=True, exist_ok=True)
    bilan = Bilan()

    for projet in serveur.projets():
        slug = projet["slug"]
        source = config.repo_root() / "projects" / slug
        cible = destination / "p" / slug
        cible.mkdir(parents=True, exist_ok=True)

        # La page de validation est une projection : on la refait à partir
        # des fichiers, plutôt que de recopier une version qui peut dater.
        page = review.construire(slug).read_text(encoding="utf-8")

        # En profondeur : un visuel peut vivre dans un sous-dossier, et une
        # image manquante ne se verrait qu'en ouvrant la planche contact.
        for image in sorted((source / "05-visuals").rglob("*")):
            if image.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            relatif = image.relative_to(source)
            bilan.octets_source += image.stat().st_size
            bilan.octets_export += _reduire(image, cible / relatif, largeur)
            bilan.fichiers += 1

        if videos:
            lecture = source / "07-out" / "apercu-720p.mp4"
            if not lecture.is_file():
                lecture = source / "07-out" / "video.mp4"
            if lecture.is_file():
                (cible / "07-out").mkdir(exist_ok=True)
                shutil.copy2(lecture, cible / "07-out" / lecture.name)
                bilan.octets_export += lecture.stat().st_size
                bilan.videos += 1
        else:
            # Sans le fichier, la balise afficherait un lecteur cassé. La
            # retirer dit la vérité : il n'y a pas de vidéo ici.
            page = _BALISE_VIDEO.sub(
                '<p class="pied">La vidéo n\'est pas incluse dans cet export.</p>',
                page)

        (cible / "review.html").write_text(
            _greffer_bandeau(page, "Atelier", slug, "../../index.html"),
            encoding="utf-8")
        bilan.projets += 1

    dossier_t = destination / "t"
    dossier_t.mkdir(exist_ok=True)
    for nom in config.available_templates():
        chemin = apercu.page(nom, dossier_t / f"{nom}.html")
        chemin.write_text(
            _greffer_bandeau(chemin.read_text(encoding="utf-8"),
                             "Templates", nom, "../index.html"),
            encoding="utf-8")

    (destination / "index.html").write_text(
        _index_export(bilan, videos), encoding="utf-8")
    return bilan
