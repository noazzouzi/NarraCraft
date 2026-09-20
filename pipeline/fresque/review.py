"""Build `projects/<slug>/review.html` — la page de validation.

Elle ne détient aucune vérité. Elle projette les fichiers du projet, et si
elle les contredit, ce sont les fichiers qui ont raison. C'est la seule
règle qui l'empêche de devenir une seconde source de vérité qui dérive —
et c'est pour ça qu'elle se régénère d'une commande plutôt que de se
mettre à jour toute seule.

Statique, ouvrable en `file://`, sans serveur : le principe fondateur du
projet interdit un état hors des fichiers, et une page qui lancerait des
étapes en aurait un.

CE QU'ELLE SERT À VOIR
======================
Pas à relire un JSON en couleurs. À faire remonter ce que personne ne va
chercher spontanément, et qui coûte cher quand ça passe :

- **L'écart entre l'intention et ce qui est arrivé.** « le mur d'enceinte
  de la Santé » à côté du fichier réellement trouvé. Un humain balaie cent
  quatre-vingts lignes comme ça en deux minutes ; dans un JSON, personne ne
  le fait jamais. Les pires erreurs de ce pipeline sont passées là — la
  colonne Trajane pour « law court columns », un camion à canon à eau pour
  « Nicolas Sarkozy Elysee ».
- Les images revues, et depuis quel plan.
- Les requêtes élargies, qui ont matché plus large que demandé.
- Les licences qui créent une obligation d'attribution à la publication.
- Les plans tenus trop longtemps, mesurés sur l'audio réel.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from . import config, script_parser
from .project import Project
from .shots import Shot, load as load_shots


def _lire(chemin: Path, defaut: Any = None) -> Any:
    if not chemin.is_file():
        return defaut
    return json.loads(chemin.read_text(encoding="utf-8"))


def _titre(brief: Path) -> str:
    if not brief.is_file():
        return ""
    for ligne in brief.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("# "):
            return ligne[2:].strip()
    return ""


def alertes(shots: list[Shot], assets: dict[str, Any],
            timeline: dict[str, Any] | None) -> list[tuple[str, str, list[str]]]:
    """Ce qui mérite un second regard, par ordre de gravité.

    Chaque entrée est (gravité, titre, lignes). Une liste vide est le seul
    résultat qui permette de valider sans rien ouvrir d'autre.
    """
    sorties: list[tuple[str, str, list[str]]] = []

    sans = [s.id for s in shots
            if s.type != "motion" and s.id not in assets]
    if sans:
        sorties.append((
            "grave", f"{len(sans)} plan(s) sans visuel",
            [f"{i} — « {next(s.intention for s in shots if s.id == i)} »"
             for i in sans[:12]],
        ))

    if timeline:
        fps = timeline["fps"]
        longest = float(config.get("montage", "duree_plan_max_s", default=10))
        panneau = float(config.get("montage", "duree_panneau_max_s", default=longest))
        tenus = []
        for clip in timeline["clips"]:
            plafond = panneau if clip["type"] == "motion" else longest
            duree = clip["duree_frames"] / fps
            if duree > plafond:
                tenus.append(f"{clip['id']} — {duree:.1f} s (max {plafond:g}) · "
                             f"{clip['intention'][:56]}")
        if tenus:
            sorties.append((
                "attention", f"{len(tenus)} plan(s) tenus trop longtemps", tenus[:12],
            ))

    elargies = [
        f"{cle} — demandé « {a['requete']} », cherché « {a.get('requete_effective')} » "
        f"→ {a.get('titre', '')[:44]}"
        for cle, a in assets.items() if a.get("requete_relachee")
    ]
    if elargies:
        sorties.append((
            "attention",
            f"{len(elargies)} requête(s) élargies — le résultat peut être plus "
            "large que demandé", elargies[:12],
        ))

    contemporains = [
        f"{cle} — « {a.get('titre', '')[:52]} » ({a.get('source')})"
        for cle, a in sorted(assets.items())
        if "contemporain" in (a.get("nature") or "")
    ]
    if contemporains:
        sorties.append((
            "attention",
            f"{len(contemporains)} plan(s) de banque contemporaine, pas "
            "d'archive — vérifier qu'aucun ne passe pour une image d'époque",
            contemporains[:12],
        ))

    attribution = sorted({
        a.get("credit", "") for a in assets.values()
        if "BY" in (a.get("licence") or "").upper()
        and "CC0" not in (a.get("licence") or "").upper()
    } - {""})
    if attribution:
        sorties.append((
            "info",
            f"{len(attribution)} crédit(s) obligatoires à la publication",
            attribution[:20],
        ))

    return sorties


def _vignette(shot: Shot, asset: dict[str, Any] | None, racine: Path) -> str:
    """Une case de la planche contact.

    L'intention est au-dessus, ce qui a été trouvé en dessous. C'est le seul
    agencement où l'œil compare les deux sans effort — et comparer les deux
    est toute la raison d'être de cette page.
    """
    fichier = (asset or {}).get("fichier")
    existe = bool(fichier) and (racine / fichier).is_file()

    if shot.type == "motion":
        kind = (shot.motion or {}).get("kind", "?")
        media = (f'<div class="panneau"><span>{html.escape(kind)}</span></div>')
        trouve = "panneau graphique, dessiné au rendu"
        licence = ""
    elif existe:
        media = (f'<img loading="lazy" src="{html.escape(fichier)}" alt="">')
        trouve = html.escape((asset or {}).get("titre", "")[:70])
        licence = html.escape((asset or {}).get("licence", ""))
    else:
        media = '<div class="vide"><span>aucun visuel</span></div>'
        trouve = "—"
        licence = ""

    marques = []
    if (asset or {}).get("reutilise_de"):
        marques.append(f'<b class="revu">revu depuis {asset["reutilise_de"]}</b>')
    if (asset or {}).get("requete_relachee"):
        marques.append('<b class="elargi">requête élargie</b>')
    if licence and "BY" in licence.upper() and "CC0" not in licence.upper():
        marques.append('<b class="attribution">attribution due</b>')

    return f"""<figure class="plan">
  {media}
  <figcaption>
    <div class="ids">{shot.id} · {shot.beat} · {html.escape(shot.type)}</div>
    <div class="intention">{html.escape(shot.intention or '—')}</div>
    {f'<div class="requete">{html.escape(shot.requete)}</div>' if shot.requete else ''}
    <div class="trouve">{trouve}</div>
    <div class="marques">{html.escape(licence)} {' '.join(marques)}</div>
  </figcaption>
</figure>"""


_STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#0b0d11; color:#e8eaee;
       font-family:'Inter','Helvetica Neue',Arial,sans-serif; }
main { max-width:1500px; margin:0 auto; padding:44px 26px 110px; }
h1 { font-size:33px; margin:0 0 6px; letter-spacing:-0.02em; }
.sous { color:#8b93a1; margin:0 0 30px; font-size:15px; }
h2 { font-size:13px; letter-spacing:.18em; text-transform:uppercase;
     color:#8b93a1; margin:52px 0 16px; font-weight:600; }
video { width:100%; max-width:900px; border-radius:12px; display:block;
        background:#000; }
.mesures { display:flex; flex-wrap:wrap; gap:10px; margin:22px 0 0; }
.mesure { border:1px solid #232833; border-radius:10px; padding:12px 16px;
          min-width:128px; }
.mesure b { display:block; font-size:25px; font-variant-numeric:tabular-nums; }
.mesure span { color:#8b93a1; font-size:12px; letter-spacing:.05em; }
.alerte { border-left:3px solid #3a4150; background:#0e1117; border-radius:0 10px 10px 0;
          padding:16px 20px; margin-bottom:14px; }
.alerte.grave { border-left-color:#e0524a; }
.alerte.attention { border-left-color:#c9a227; }
.alerte.info { border-left-color:#4b7bd4; }
.alerte h3 { margin:0 0 10px; font-size:15px; font-weight:600; }
.alerte li { color:#aab1bd; font-size:13px; line-height:1.65;
             list-style:none; word-break:break-word; }
.alerte ul { margin:0; padding:0; }
.planche { display:grid; grid-template-columns:repeat(auto-fill,minmax(228px,1fr));
           gap:16px; }
.plan { margin:0; border:1px solid #1b1f28; border-radius:10px; overflow:hidden;
        background:#0e1117; }
.plan img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block;
            background:#14171d; }
.plan .panneau, .plan .vide { aspect-ratio:16/9; display:flex;
            align-items:center; justify-content:center; }
.plan .panneau { background:linear-gradient(135deg,#171b24,#0d1014); color:#c9a227;
                 font-size:13px; letter-spacing:.12em; text-transform:uppercase; }
.plan .vide { background:#1a1013; color:#e0524a; font-size:12px; }
.plan figcaption { padding:11px 13px 13px; font-size:12px; line-height:1.5; }
.ids { color:#6b7280; font-size:11px; letter-spacing:.06em; }
.intention { color:#e8eaee; margin-top:5px; }
.requete { color:#8b93a1; margin-top:5px; font-family:ui-monospace,monospace;
           font-size:11px; }
.trouve { color:#7c8698; margin-top:7px; border-top:1px solid #1b1f28;
          padding-top:7px; }
.marques { margin-top:7px; color:#5f6775; font-size:11px; }
.marques b { display:inline-block; margin-left:5px; padding:2px 7px;
             border-radius:4px; font-weight:600; font-size:10px; }
.revu { background:#1d2735; color:#7fa8e0; }
.elargi { background:#2a2414; color:#c9a227; }
.attribution { background:#221a2c; color:#b18fd8; }
table { width:100%; border-collapse:collapse; font-size:13px; }
td,th { padding:8px 10px; border-bottom:1px solid #1b1f28; text-align:left;
        vertical-align:top; }
th { color:#8b93a1; font-weight:500; font-size:11px; letter-spacing:.1em;
     text-transform:uppercase; }
td.num { font-variant-numeric:tabular-nums; color:#8b93a1; width:82px; }
td.txt { color:#c7ccd6; line-height:1.55; }
.pied { color:#5f6775; font-size:12px; margin-top:44px; line-height:1.7; }
code { background:#151922; padding:2px 7px; border-radius:5px; color:#c7ccd6; }
"""


def construire(slug: str) -> Path:
    projet = Project.open(slug)
    racine = projet.root

    script = script_parser.parse(projet.script) if projet.script.is_file() else None
    shots = load_shots(projet.shots, [b.id for b in script.beats]) \
        if script and projet.shots.is_file() else []
    assets = (_lire(projet.assets, {}) or {}).get("assets", {})
    timeline = _lire(projet.timeline)

    video = projet.out_dir / "video.mp4"
    apercu = projet.out_dir / "apercu-720p.mp4"
    lecture = apercu if apercu.is_file() else video

    # --- Mesures : ce qui se compte, compté ici plutôt qu'estimé à l'œil.
    mesures = []
    if script:
        mesures += [("beats", len(script.beats)), ("mots", script.word_count)]
    if shots:
        mesures.append(("plans", len(shots)))
        mesures.append(("panneaux", sum(1 for s in shots if s.type == "motion")))
        planches = sum(1 for s in shots if s.type == "collage")
        if planches:
            mesures.append(("planches collage", planches))
    if assets:
        distinctes = len({a.get("url") for a in assets.values() if a.get("url")})
        mesures.append(("images distinctes", distinctes))
        mesures.append(("reprises", sum(1 for a in assets.values()
                                        if a.get("reutilise_de"))))
    if timeline:
        mesures.append(("durée", f"{timeline['duree_s'] / 60:.1f} min"))
        if timeline["duree_s"]:
            mesures.append(("plans/min",
                            f"{len(timeline['clips']) / timeline['duree_s'] * 60:.1f}"))

    bloc_mesures = "".join(
        f'<div class="mesure"><b>{html.escape(str(v))}</b>'
        f'<span>{html.escape(nom)}</span></div>'
        for nom, v in mesures
    )

    bloc_alertes = "".join(
        f'<div class="alerte {gravite}"><h3>{html.escape(titre)}</h3><ul>'
        + "".join(f"<li>{html.escape(l)}</li>" for l in lignes)
        + "</ul></div>"
        for gravite, titre, lignes in alertes(shots, assets, timeline)
    ) or ('<div class="alerte info"><h3>Rien à signaler</h3>'
          "<ul><li>Aucun plan sans visuel, aucun plan tenu trop longtemps, "
          "aucune requête élargie.</li></ul></div>")

    planche = "".join(_vignette(s, assets.get(s.id), racine) for s in shots)

    # --- Le script, avec la durée réelle de chaque beat.
    lignes_script = ""
    if script and timeline:
        par_beat: dict[str, float] = {}
        for clip in timeline["clips"]:
            par_beat[clip["beat"]] = par_beat.get(clip["beat"], 0) + clip["duree_frames"]
        for beat in script.beats:
            secondes = par_beat.get(beat.id, 0) / timeline["fps"]
            lignes_script += (
                f'<tr><td class="num">{beat.id}<br>{secondes:.1f} s</td>'
                f'<td class="txt">{html.escape(beat.text)}</td></tr>'
            )

    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Review — {html.escape(slug)}</title>
<style>{_STYLE}</style></head><body><main>
<h1>{html.escape(_titre(projet.brief) or slug)}</h1>
<p class="sous">{html.escape(slug)} · template {html.escape(projet.template or '—')}
 · page régénérée par <code>fresque review {html.escape(slug)}</code></p>

{f'<video controls preload="metadata" src="{html.escape(lecture.relative_to(racine).as_posix())}"></video>' if lecture.is_file() else ''}
<div class="mesures">{bloc_mesures}</div>

<h2>À regarder</h2>
{bloc_alertes}

<h2>Les {len(shots)} plans — intention, puis ce qui est arrivé</h2>
<div class="planche">{planche}</div>

{f'<h2>Narration</h2><table><tr><th>Beat</th><th>Texte prononcé</th></tr>{lignes_script}</table>' if lignes_script else ''}

<p class="pied">
Cette page ne détient aucune vérité : elle projette les fichiers du projet.
Si elle les contredit, ce sont les fichiers qui ont raison — relancer
<code>fresque review {html.escape(slug)}</code> pour la remettre à jour.<br>
Statique et sans serveur, comme le veut le principe fondateur : aucun état
ne vit en dehors de <code>projects/{html.escape(slug)}/</code>.
</p>
</main></body></html>
"""
    sortie = racine / "review.html"
    sortie.write_text(page, encoding="utf-8")
    return sortie
