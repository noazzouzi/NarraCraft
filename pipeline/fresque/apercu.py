"""Show what a template actually contains.

A template is a thin overlay over `fresque.config.yaml`, which is exactly
what makes it cheap to write and hard to read: the file says what changes,
never what the result is. Answering "what does this template look like"
meant opening two files and merging them in your head.

So this module answers it twice, for two different questions:

- `resume()` — the effective settings, key by key, saying for each whether
  it comes from the template or from the base. That is the question you ask
  when you are about to change a value.
- `page()` — a static HTML page showing the art direction as it will look:
  the palette as swatches, the typography as a subtitle, the graphic panel
  colours, the camera amplitude as a rectangle, the sound bed as a player.
  That is the question you ask when you are choosing between templates.

The page is static and opens from the filesystem, like `review.html`. No
server, in keeping with the rest of the project.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import yaml

from . import config

#: Blocs de prose destinés aux skills, affichés tels quels plutôt que
#: comme des valeurs de réglage.
META = "meta"

#: Ce qui décide de l'allure du film, et qu'un template redéfinit en
#: priorité. L'ordre est celui de la page.
AXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Écriture", ("narration", "controle", "structure")),
    ("Voix", ("voix",)),
    ("Visuels", ("visuels",)),
    ("Montage", ("montage",)),
)


def _plat(node: Any, prefixe: str = "") -> dict[str, Any]:
    """Aplatit un arbre de réglages en chemins pointés."""
    sortie: dict[str, Any] = {}
    if isinstance(node, dict):
        for cle, valeur in node.items():
            sortie.update(_plat(valeur, f"{prefixe}.{cle}" if prefixe else str(cle)))
    else:
        sortie[prefixe] = node
    return sortie


def _charger(nom: str) -> tuple[dict[str, Any], dict[str, Any]]:
    racine = config.repo_root()
    base = yaml.safe_load((racine / config.CONFIG_NAME).read_text(encoding="utf-8"))
    chemin = racine / config.TEMPLATES_DIR / f"{nom}.yaml"
    if not chemin.is_file():
        connus = ", ".join(config.available_templates()) or "aucun"
        raise config.TemplateError(f"Template inconnu : {nom!r} (connus : {connus})")
    overlay = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return base, overlay


def resume(nom: str) -> dict[str, Any]:
    """Réglages effectifs du template, avec leur provenance.

    Retourne `{"meta": …, "reglages": [(chemin, valeur, "template"|"base")]}`.
    """
    base, overlay = _charger(nom)
    effectif = config._merge(base, overlay)

    propres = set(_plat({k: v for k, v in overlay.items() if k != META}))
    reglages = []
    for titre, blocs in AXES:
        lignes = []
        for bloc in blocs:
            for chemin, valeur in _plat({bloc: effectif.get(bloc, {})}).items():
                lignes.append((chemin, valeur,
                               "template" if chemin in propres else "base"))
        reglages.append((titre, lignes))

    return {
        "nom": nom,
        "meta": overlay.get(META, {}),
        "axes": reglages,
        "nb_propres": len(propres),
        "effectif": effectif,
    }


def texte(nom: str, tout: bool = False) -> str:
    """Le résumé, pour un terminal. `tout` inclut les valeurs héritées."""
    donnees = resume(nom)
    lignes = [f"Template — {donnees['meta'].get('nom', nom)}",
              f"  {donnees['nb_propres']} réglage(s) propres, le reste hérité "
              f"de {config.CONFIG_NAME}", ""]

    for cle in ("description", "registre", "structure_narrative",
                "interdits_specifiques", "sourcing"):
        valeur = donnees["meta"].get(cle)
        if valeur:
            lignes.append(f"{cle} :")
            lignes.extend(f"  {morceau}" for morceau in _replier(str(valeur), 74))
            lignes.append("")

    for titre, entrees in donnees["axes"]:
        visibles = [e for e in entrees if tout or e[2] == "template"]
        if not visibles:
            continue
        lignes.append(f"--- {titre}")
        for chemin, valeur, source in visibles:
            marque = "◆" if source == "template" else " "
            lignes.append(f"  {marque} {chemin:<44} {_bref(valeur)}")
        lignes.append("")

    if not tout:
        lignes.append("◆ = défini par le template. `--tout` pour voir l'hérité.")
    return "\n".join(lignes)


def _bref(valeur: Any) -> str:
    if isinstance(valeur, list):
        rendu = ", ".join(str(v) for v in valeur)
        return rendu if len(rendu) <= 60 else rendu[:57] + "…"
    rendu = str(valeur)
    return rendu if len(rendu) <= 60 else rendu[:57] + "…"


def _replier(texte_source: str, largeur: int) -> list[str]:
    mots, ligne, sorties = texte_source.split(), "", []
    for mot in mots:
        if len(ligne) + len(mot) + 1 > largeur:
            sorties.append(ligne)
            ligne = mot
        else:
            ligne = f"{ligne} {mot}".strip()
    if ligne:
        sorties.append(ligne)
    return sorties


# --- Page statique -----------------------------------------------------------

_GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Template — {nom}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b0d11; color:#e8eaee;
         font-family:'Inter','Helvetica Neue',Arial,sans-serif; }}
  main {{ max-width:1080px; margin:0 auto; padding:48px 24px 96px; }}
  h1 {{ font-size:34px; margin:0 0 6px; letter-spacing:-0.02em; }}
  .sous {{ color:#8b93a1; margin:0 0 40px; }}
  h2 {{ font-size:13px; letter-spacing:.18em; text-transform:uppercase;
       color:#8b93a1; margin:44px 0 14px; font-weight:600; }}
  .prose {{ line-height:1.62; color:#c7ccd6; max-width:66ch; margin:0 0 18px; }}
  .prose b {{ color:#e8eaee; font-weight:600; }}
  .grille {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
            gap:14px; }}
  .pastille {{ border-radius:10px; overflow:hidden; border:1px solid #232833; }}
  .pastille .aire {{ height:74px; }}
  .pastille .nom {{ padding:9px 11px; font-size:12px; color:#8b93a1;
                   display:flex; justify-content:space-between; gap:8px; }}
  .pastille .nom code {{ color:#c7ccd6; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  td {{ padding:7px 10px; border-bottom:1px solid #1b1f28; vertical-align:top; }}
  td.cle {{ color:#8b93a1; width:46%; }}
  td.val {{ color:#e8eaee; font-variant-numeric:tabular-nums; }}
  tr.propre td.cle::before {{ content:"◆ "; color:{accent}; }}
  tr.heritee {{ opacity:.45; }}
  .cadre {{ border:1px solid #232833; border-radius:12px; padding:20px;
           background:#0e1117; }}
  .scene {{ position:relative; height:190px; border-radius:8px; overflow:hidden;
           background:linear-gradient(135deg,#1a1f2b,#0d1014); }}
  .scene .interieur {{ position:absolute; inset:0; border:2px dashed {accent};
                      opacity:.75; }}
  .legende {{ color:#8b93a1; font-size:12px; margin-top:10px; }}
  audio {{ width:100%; margin-top:10px; }}
  .soustitre {{ text-align:center; padding:26px 10px 34px;
               background:linear-gradient(to top,{voile},rgba(0,0,0,0)); }}
</style></head><body><main>
<h1>{nom}</h1>
<p class="sous">{description}</p>
{prose}
<h2>Palette</h2><div class="grille">{palette}</div>
<h2>Panneaux graphiques</h2><div class="grille">{motion}</div>
<h2>Sous-titres</h2>
<div class="cadre" style="background:{fond}">
  <div class="soustitre"><span style="{soustitre_style}">{exemple}</span></div>
</div>
<h2>Amplitude de caméra</h2>
<div class="cadre"><div class="scene">
  <div class="interieur" style="{cadre_style}"></div>
</div><p class="legende">{legende_kb}</p></div>
<h2>Lit sonore</h2>
<div class="cadre">
  <p class="legende">{legende_musique}</p>{lecteur}
</div>
{tables}
<p class="legende" style="margin-top:34px">◆ défini par le template · le reste
est hérité de <code>fresque.config.yaml</code>.</p>
</main></body></html>
"""


def _pastille(nom: str, couleur: str) -> str:
    return (f'<div class="pastille"><div class="aire" style="background:{couleur}">'
            f'</div><div class="nom"><span>{html.escape(nom)}</span>'
            f'<code>{html.escape(str(couleur))}</code></div></div>')


def page(nom: str, destination: Path, musique: Path | None = None) -> Path:
    """Écrit la page statique de présentation du template."""
    donnees = resume(nom)
    eff = donnees["effectif"]
    meta = donnees["meta"]
    palette = eff.get("montage", {}).get("palette", {})
    motion = eff.get("montage", {}).get("motion", {})
    typo = eff.get("montage", {}).get("typographie", {})
    kb = eff.get("montage", {}).get("ken_burns", {})
    mus = eff.get("montage", {}).get("musique", {})

    prose = "".join(
        f'<p class="prose"><b>{cle.replace("_", " ")}</b> — '
        f'{html.escape(str(meta[cle]))}</p>'
        for cle in ("registre", "structure_narrative", "interdits_specifiques",
                    "sourcing")
        if meta.get(cle)
    )

    tables = []
    for titre, entrees in donnees["axes"]:
        lignes = "".join(
            f'<tr class="{"propre" if src == "template" else "heritee"}">'
            f'<td class="cle">{html.escape(chemin)}</td>'
            f'<td class="val">{html.escape(_bref(val))}</td></tr>'
            for chemin, val, src in entrees
        )
        tables.append(f"<h2>{html.escape(titre)}</h2><table>{lignes}</table>")

    # Le zoom maximal, dessiné à l'échelle : un rectangle qui montre ce que
    # la caméra garde du cadre au plus serré.
    zoom_max = float(kb.get("zoom_max", 1.18))
    part = 100 / zoom_max
    derive = float(kb.get("derive_max_pct", 6))
    vitesse = float(kb.get("vitesse_pct_s", 2.5))
    depart = float(kb.get("echelle_depart", 1.04))

    lecteur = ""
    if musique and musique.is_file():
        lecteur = (f'<audio controls src="{html.escape(musique.name)}"></audio>')

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_GABARIT.format(
        nom=html.escape(meta.get("nom", nom)),
        description=html.escape(str(meta.get("description", ""))),
        accent=motion.get("accent", "#c9a227"),
        voile=palette.get("voile", "rgba(0,0,0,0.72)"),
        fond=palette.get("fond", "#000"),
        prose=prose,
        palette="".join(_pastille(k, v) for k, v in palette.items()),
        motion="".join(_pastille(k, v) for k, v in motion.items()
                       if isinstance(v, str) and v.startswith("#")),
        exemple="Le tribunal ordonne l'exécution provisoire de la peine.",
        soustitre_style=(
            f"color:{palette.get('sous_titre', '#fff')};"
            f"font-family:{typo.get('famille', 'sans-serif')};"
            f"font-size:{float(typo.get('taille', 52)) * 0.62:.0f}px;"
            f"font-weight:{typo.get('graisse', 500)};"
            f"letter-spacing:{typo.get('interlettrage', '0')};"
        ),
        cadre_style=(f"left:{(100 - part) / 2:.1f}%;top:{(100 - part) / 2:.1f}%;"
                     f"width:{part:.1f}%;height:{part:.1f}%;"),
        legende_kb=(
            f"Départ ×{depart:g} · +{vitesse:g} %/s, plafonné à ×{zoom_max:g} · "
            f"dérive {kb.get('derive_pct_s', 3)} %/s, au plus {derive:g} % · "
            f"micro-rotation {kb.get('micro_rotation_deg')}° · "
            f"{kb.get('easing')}. Le mouvement est une vitesse : un plan de "
            f"{(zoom_max / depart - 1) * 100 / vitesse:.0f} s atteint le "
            "plafond, un plan plus court en fait moins. Le pointillé montre "
            "ce que la caméra garde du cadre au plus serré."),
        legende_musique=(
            f"Mode {mus.get('mode')} · tonique {mus.get('tonique_hz')} Hz · "
            f"boucle {mus.get('boucle_s')} s · gain {mus.get('gain')} · "
            f"fondu {mus.get('fondu_s')} s."
            + ("" if lecteur else " Lancer `fresque timeline` sur un projet "
               "pour entendre la boucle.")),
        lecteur=lecteur,
        tables="".join(tables),
    ), encoding="utf-8")
    return destination
