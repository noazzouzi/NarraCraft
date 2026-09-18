"""`python -m fresque <commande> <slug>` — the mechanical half of the pipeline.

Each command reads the files that precede it and writes exactly one artefact.
Nothing is held in memory between commands.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import align, script_parser, shots as shots_mod, timeline as timeline_mod
from .project import Project


def _fail(message: str) -> int:
    print(f"✗ {message}", file=sys.stderr)
    return 1


def cmd_align(args: argparse.Namespace) -> int:
    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    alignment = align.estimate(script)
    align.write(alignment, project.alignment)

    target_min = float(args.target or 0)
    duration = alignment["duree_totale_s"]
    print(f"✓ {project.alignment.relative_to(project.root.parent.parent)}")
    print(f"  {alignment['nb_beats']} beats · {alignment['nb_mots']} mots")
    print(f"  durée estimée : {align.format_duration(duration)}")
    if target_min:
        drift = (duration / 60 - target_min) / target_min * 100
        print(f"  écart à la cible de {target_min:g} min : {drift:+.1f} %")
    print("  ⚠ timings estimés — seront remplacés par l'alignement forcé")
    return 0


def cmd_shots(args: argparse.Namespace) -> int:
    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])
    kinds: dict[str, int] = {}
    for shot in plan:
        kinds[shot.type] = kinds.get(shot.type, 0) + 1
    print(f"✓ {len(plan)} plans sur {len(script.beats)} beats")
    for kind, count in sorted(kinds.items()):
        print(f"  {kind:<10} {count}")
    return 0


def cmd_placeholders(args: argparse.Namespace) -> int:
    from .placeholders import card

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])

    assets: dict[str, dict] = {}
    for shot in plan:
        name = f"{shot.id}.jpg"
        card(shot, project.visuals_dir / name)
        assets[shot.id] = {
            "fichier": name,
            "source": "placeholder",
            "licence": "n/a",
            "credit": None,
        }
    project.assets.write_text(
        json.dumps({"assets": assets}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✓ {len(assets)} visuels de substitution → {project.visuals_dir.name}/")
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])

    if not project.alignment.is_file():
        return _fail("alignment.json manquant — lancer `align` d'abord.")
    alignment = align.load(project.alignment)

    assets = {}
    if project.assets.is_file():
        assets = json.loads(project.assets.read_text(encoding="utf-8")).get("assets", {})

    timeline = timeline_mod.build(alignment, plan, assets)
    timeline_mod.write(timeline, project.timeline)

    problems = timeline_mod.check(timeline)
    print(f"✓ {project.timeline.name}")
    print(f"  {len(timeline['clips'])} plans · "
          f"{len(timeline['sous_titres'])} lignes de sous-titres")
    print(f"  {timeline['duree_frames']} frames à {timeline['fps']} fps "
          f"= {align.format_duration(timeline['duree_s'])}")
    if timeline["source_timings"] == "estimate":
        print("  ⚠ construit sur des timings estimés")
    if problems:
        print(f"  ✗ {len(problems)} problème(s) :")
        for problem in problems[:10]:
            print(f"    · {problem}")
        return 1
    print("  aucun trou, aucun chevauchement")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    import shutil
    import subprocess

    project = Project.open(args.slug)
    if not project.timeline.is_file():
        return _fail("06-timeline.json manquant — lancer `timeline` d'abord.")

    from . import config
    remotion = config.repo_root() / "remotion"
    if not (remotion / "node_modules").is_dir():
        return _fail(f"dépendances Remotion absentes — `npm install` dans {remotion}")
    if not shutil.which("npx"):
        return _fail("npx introuvable — Node est requis pour le rendu.")

    output = project.out_dir / "video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "npx", "remotion", "render", "Documentaire", str(output),
        f"--props={project.timeline}",
        f"--public-dir={project.visuals_dir}",
        f"--concurrency={args.concurrency}",
    ]
    if args.browser:
        command.append(f"--browser-executable={args.browser}")

    print(f"→ rendu vers {output}")
    result = subprocess.run(command, cwd=remotion)
    if result.returncode != 0:
        return _fail(f"le rendu a échoué (code {result.returncode}).")
    size_mb = output.stat().st_size / 1_048_576
    print(f"✓ {output.name} · {size_mb:.1f} Mo")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project = Project.open(args.slug)
    steps = [
        ("00-brief.md", project.brief),
        ("01-research.md", project.research),
        ("02-script.md", project.script),
        ("03-shots.json", project.shots),
        ("04-audio/alignment.json", project.alignment),
        ("05-visuals/assets.json", project.assets),
        ("06-timeline.json", project.timeline),
        ("07-out/video.mp4", project.out_dir / "video.mp4"),
    ]
    print(f"Projet : {project.slug}")
    for label, path in steps:
        print(f"  {'✓' if path.exists() else '·'} {label}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fresque", description="Étapes déterministes du pipeline Fresque."
    )
    sub = parser.add_subparsers(dest="commande", required=True)

    def add(name: str, help_text: str, handler):
        node = sub.add_parser(name, help=help_text)
        node.add_argument("slug")
        node.set_defaults(handler=handler)
        return node

    align_cmd = add("align", "Estimer les timings depuis le script", cmd_align)
    align_cmd.add_argument("--target", type=float, help="durée cible en minutes")
    add("shots", "Valider le plan visuel", cmd_shots)
    add("placeholders", "Générer des visuels de substitution", cmd_placeholders)
    add("timeline", "Construire 06-timeline.json", cmd_timeline)
    render_cmd = add("render", "Rendre la vidéo avec Remotion", cmd_render)
    render_cmd.add_argument("--concurrency", type=int, default=4)
    render_cmd.add_argument(
        "--browser", default=None,
        help="chemin d'un Chromium existant (évite un téléchargement)",
    )
    add("status", "État d'avancement du projet", cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (script_parser.ScriptError, shots_mod.ShotsError) as error:
        return _fail(str(error))
    except FileNotFoundError as error:
        return _fail(str(error))
