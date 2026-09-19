"""`python -m fresque <commande> <slug>` — the mechanical half of the pipeline.

Each command reads the files that precede it and writes exactly one artefact.
Nothing is held in memory between commands.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import align, config, script_parser, shots as shots_mod, timeline as timeline_mod
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


def cmd_voice(args: argparse.Namespace) -> int:
    from . import align as align_mod, voice as voice_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)

    def progress(done: int, total: int, seconds: float) -> None:
        print(f"\r  {done}/{total} beats · {align.format_duration(seconds)}",
              end="", flush=True)

    try:
        alignment = voice_mod.synthesize(script, project.audio_dir, progress)
    except voice_mod.VoiceError as error:
        print()
        return _fail(str(error))

    print()
    align_mod.write(alignment, project.alignment)
    print(f"✓ {project.audio_dir.name}/voix.wav")
    print(f"  {alignment['nb_beats']} beats · "
          f"{align.format_duration(alignment['duree_totale_s'])}")
    print(f"  voix {alignment['voix']['voice']} · vitesse {alignment['voix']['speed']}")
    print("  durées de beat mesurées sur l'audio réel")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    from . import lint as lint_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    violations = lint_mod.check(script)

    blocking = [v for v in violations if v.blocking]
    warnings = [v for v in violations if not v.blocking]

    if not violations:
        print(f"✓ {script.word_count} mots · {len(script.beats)} beats · "
              "aucune violation")
        return 0

    for violation in violations:
        mark = "✗" if violation.blocking else "·"
        print(f"{mark} {violation.beat:<5} [{violation.rule}] {violation.message}")
        if violation.excerpt:
            print(f"        « {violation.excerpt} »")

    print()
    print(f"{len(blocking)} bloquante(s), {len(warnings)} avertissement(s)")
    return 1 if blocking else 0


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

    par_minute = len(plan) / (script.word_count / float(
        config.get("narration", "mots_par_minute", default=140)))
    vise = float(config.get("visuels", "plans_par_minute", default=8))
    print(f"  {par_minute:.1f} plans/min (visé : {vise:g})")

    slow = shots_mod.density(plan, script.beats)
    if slow:
        print(f"\n  ⚠ {len(slow)} beat(s) tiennent une image trop longtemps :")
        for line in slow[:12]:
            print(f"    {line}")
        if len(slow) > 12:
            print(f"    … et {len(slow) - 12} autre(s)")

    # The opening is the one thing worth failing the checkpoint over: every
    # other shot only matters to viewers who got past it.
    opening = shots_mod.ouverture(plan)
    for line in opening:
        print(f"\n✗ ouverture : {line}", file=sys.stderr)
    return 1 if opening else 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from . import fetch as fetch_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])

    archives = [s for s in plan if s.type == "archive"]
    generated = [s for s in plan if s.type == "generated"]
    print(f"→ {len(archives)} plans d'archive, {len(generated)} à générer")

    try:
        deja = {}
        if project.assets.is_file() and not args.force:
            deja = json.loads(project.assets.read_text(encoding="utf-8")).get("assets", {})
        assets, unsourced = fetch_mod.fetch_archives(
            archives, project.visuals_dir, report=print,
            dry_run=args.dry_run, deja=deja,
        )
    except fetch_mod.FetchError as error:
        return _fail(str(error))

    if not args.dry_run:
        merged = fetch_mod.merge_assets(project.assets, assets)
        fetch_mod.write_assets(merged, project.assets)
        print(f"✓ {len(assets)} archives → {project.assets.name}")
    else:
        print(f"(simulation) {len(assets)} archives trouvées, rien téléchargé")

    if unsourced:
        print(f"  ⚠ {len(unsourced)} plan(s) sans archive : {', '.join(unsourced)}")
        print("    → reformuler la requête, ou basculer le plan en `generated`")
    if generated:
        print(f"  · {len(generated)} plan(s) `generated` en attente du jalon 4c")
    return 0


def cmd_rushes(args: argparse.Namespace) -> int:
    from . import align as align_mod, fetch as fetch_mod, rushes as rushes_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])
    todo = [s for s in plan if s.type == "video"]
    if not todo:
        print("Aucun plan `video` — rien à sourcer.")
        return 0

    if not project.alignment.is_file():
        return _fail("alignment.json manquant — lancer `align` ou `voice` d'abord.")
    alignment = align_mod.load(project.alignment)

    # Screen time per shot decides how far into a film we may start.
    fenetres = _fenetres(alignment, plan)

    print(f"→ {len(todo)} plan(s) de métrage d'archive")
    assets, manquants = rushes_mod.fetch_videos(
        todo, project.root, fenetres, report=print
    )
    merged = fetch_mod.merge_assets(project.assets, assets)
    fetch_mod.write_assets(merged, project.assets)
    print(f"✓ {len(assets)} plan(s) vidéo → {project.assets.name}")
    if manquants:
        print(f"  ⚠ {len(manquants)} sans métrage : {', '.join(manquants)}")
    return 0


def _fenetres(alignment: dict, plan: list) -> dict[str, float]:
    """Seconds of screen time per shot, from the beat windows."""
    beats = alignment["beats"]
    total = float(alignment["duree_totale_s"])
    grouped = shots_mod.by_beat(plan)
    fenetres: dict[str, float] = {}
    for index, beat in enumerate(beats):
        fin = float(beats[index + 1]["debut_s"]) if index + 1 < len(beats) else total
        largeur = fin - float(beat["debut_s"])
        lot = grouped.get(beat["id"], [])
        poids = sum(s.poids for s in lot) or 1
        for shot in lot:
            fenetres[shot.id] = largeur * shot.poids / poids
    return fenetres


def cmd_images(args: argparse.Namespace) -> int:
    from . import fetch as fetch_mod, images as images_mod

    project = Project.open(args.slug)

    if args.list_models:
        try:
            names = images_mod.image_models()
        except (images_mod.ImageError, Exception) as error:  # noqa: BLE001
            return _fail(str(error))
        print("Modèles d'image servis par l'API :")
        for name in names:
            print(f"  {name}")
        return 0

    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])
    todo = [s for s in plan if s.type == "generated"]
    if not todo:
        print("Aucun plan `generated` — rien à produire.")
        return 0

    print(f"→ {len(todo)} image(s) à générer")
    try:
        assets, failures = images_mod.generate_all(todo, project.visuals_dir, report=print)
    except images_mod.ImageError as error:
        return _fail(str(error))

    merged = fetch_mod.merge_assets(project.assets, assets)
    fetch_mod.write_assets(merged, project.assets)
    print(f"✓ {len(assets)} image(s) → {project.assets.name}")
    if failures:
        print(f"  ✗ {len(failures)} échec(s) : {', '.join(s for s, _ in failures)}")
        return 1
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
            "fichier": f"05-visuals/{name}",
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

    # Generated here rather than in their own command: they are deterministic
    # and cost nothing, so a step that can be forgotten is a step that should
    # not exist.
    from . import sons as sons_mod

    sons_dir = "04-audio/sons"
    sons_mod.build(project.root / sons_dir)

    voix = project.audio_dir / "voix.wav"

    musique = None
    if config.get("montage", "musique", "actif", default=True):
        relatif = f"{sons_dir}/musique.wav"
        if config.get("montage", "musique", "source", default="synthese") == "fichier":
            from . import musiques as musiques_mod

            chemin = config.get("montage", "musique", "fichier")
            if not chemin:
                return _fail("montage.musique.source vaut `fichier` mais "
                             "`montage.musique.fichier` n'est pas renseigné.")
            source = config.repo_root() / chemin
            if not source.is_file():
                return _fail(f"musique introuvable : {source}")
            # Un enregistrement ne boucle pas tout seul : sa fin et son début
            # n'ont aucune raison de se raccorder. On replie l'un sur l'autre.
            piste = musiques_mod.preparer_boucle(
                source, project.root / relatif,
                fondu_s=float(config.get(
                    "montage", "musique", "boucle_fondu_s", default=4.0)),
                force=True,
            )
        else:
            piste = sons_mod.build_musique(
                project.root / relatif,
                duree_s=float(config.get("montage", "musique", "boucle_s", default=40)),
                tonique_hz=float(config.get(
                    "montage", "musique", "tonique_hz", default=131)),
                mode=str(config.get("montage", "musique", "mode", default="sobre")),
                force=True,
            )
        # Le gain se mesure, il ne se règle pas : le même 0,06 est inaudible
        # sur un bourdon à 49 Hz et envahissant sur un lit à 300.
        niveau_db = float(config.get(
            "montage", "musique", "niveau_relatif_db", default=-24))
        if voix.is_file():
            gain = sons_mod.gain_pour(piste, voix, niveau_db)
        else:
            gain = float(config.get("montage", "musique", "gain", default=0.1))
        musique = {"fichier": relatif, "gain": round(gain, 4),
                   "niveau_relatif_db": niveau_db}

    timeline = timeline_mod.build(
        alignment, plan, assets,
        audio="04-audio/voix.wav" if voix.is_file() else None,
        sons_dir=sons_dir,
        musique=musique,
    )
    timeline_mod.write(timeline, project.timeline)

    problems = timeline_mod.check(timeline)
    print(f"✓ {project.timeline.name}")
    print(f"  {len(timeline['clips'])} plans · "
          f"{len(timeline['sous_titres'])} lignes de sous-titres")
    print(f"  {timeline['duree_frames']} frames à {timeline['fps']} fps "
          f"= {align.format_duration(timeline['duree_s'])}")
    print(f"  audio : {timeline['audio'] or 'aucun (muet)'}")

    arrivees: dict[str, int] = {}
    for clip in timeline["clips"]:
        kind = clip["entree"]["type"]
        arrivees[kind] = arrivees.get(kind, 0) + 1
    print("  transitions : " + " · ".join(
        f"{kind} {count}" for kind, count in sorted(arrivees.items())
    ))
    print(f"  {len(timeline['sons'])} son(s) de transition")
    if timeline.get("musique"):
        mus = timeline["musique"]
        print(f"  lit sonore : {mus['niveau_relatif_db']:+g} dB sous la voix "
              f"(pondéré A) · gain {mus['gain']:g}")
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

    remotion = config.repo_root() / "remotion"
    if not (remotion / "node_modules").is_dir():
        return _fail(f"dépendances Remotion absentes — `npm install` dans {remotion}")
    if not shutil.which("npx"):
        return _fail("npx introuvable — Node est requis pour le rendu.")

    output = Path(args.output) if args.output else project.out_dir / "video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.scale != 1.0:
        # Remotion refuses non-integer dimensions, and says so only after
        # bundling and launching the browser — two minutes in.
        timeline = json.loads(project.timeline.read_text(encoding="utf-8"))
        for nom, valeur in (("largeur", timeline["width"]), ("hauteur", timeline["height"])):
            mis = valeur * args.scale
            if abs(mis - round(mis)) > 1e-9:
                entiers = [e for e in (0.25, 0.5, 0.75) if (valeur * e).is_integer()]
                return _fail(
                    f"--scale={args.scale} donne une {nom} de {mis:g} px, "
                    f"et le moteur exige un entier. Essayer : "
                    + ", ".join(str(e) for e in entiers)
                )

    public_dir = _stage_public_dir(project)

    command = [
        "npx", "remotion", "render", "Documentaire", str(output),
        f"--props={project.timeline}",
        f"--public-dir={public_dir}",
        f"--concurrency={args.concurrency}",
        f"--crf={args.crf if args.crf else config.get('montage', 'crf', default=22)}",
    ]
    if args.scale != 1.0:
        command.append(f"--scale={args.scale}")
    if args.frames:
        command.append(f"--frames={args.frames}")
    if args.browser:
        command.append(f"--browser-executable={args.browser}")

    print(f"→ rendu vers {output}")
    result = subprocess.run(command, cwd=remotion)
    if result.returncode != 0:
        return _fail(f"le rendu a échoué (code {result.returncode}).")
    size_mb = output.stat().st_size / 1_048_576
    print(f"✓ {output.name} · {size_mb:.1f} Mo")
    return 0


def _stage_public_dir(project: Project) -> Path:
    """Assemble exactly the files the renderer needs, and nothing else.

    Remotion copies its whole public directory into the bundle. Pointing it at
    the project root meant copying the per-beat audio, the previous render and
    every archive alternative — ninety megabytes to draw a ten-megabyte film.
    """
    import shutil

    timeline = json.loads(project.timeline.read_text(encoding="utf-8"))
    # Every media path the timeline references: stills, footage, and the
    # voice track. Missing one is not caught until the renderer is a third
    # of the way in and asks for a file that was never copied.
    wanted: set[str] = set()
    for clip in timeline["clips"]:
        # `fond_image` compte : un panneau graphique s'appuie dessus, et elle
        # n'est pas forcément l'image d'un autre plan retenu.
        for cle in ("image", "video", "fond_image"):
            if clip.get(cle):
                wanted.add(clip[cle])
    if timeline.get("audio"):
        wanted.add(timeline["audio"])
    for son in timeline.get("sons", []):
        wanted.add(son["fichier"])
    if (timeline.get("musique") or {}).get("fichier"):
        wanted.add(timeline["musique"]["fichier"])

    staging = project.root / ".render"
    if staging.exists():
        shutil.rmtree(staging)

    for relative in sorted(wanted):
        source = project.root / relative
        if not source.is_file():
            continue
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    total = sum(f.stat().st_size for f in staging.rglob("*") if f.is_file())
    print(f"  {len(wanted)} fichier(s) exposés au rendu · {total / 1_048_576:.1f} Mo")
    return staging


def cmd_review(args: argparse.Namespace) -> int:
    from . import review as review_mod

    sortie = review_mod.construire(args.slug)
    taille = sortie.stat().st_size / 1024
    print(f"✓ {sortie.relative_to(config.repo_root())} · {taille:.0f} ko")
    print(f"  ouvrir : file://{sortie}")
    return 0


def cmd_template(args: argparse.Namespace) -> int:
    from . import apercu as apercu_mod

    connus = config.available_templates()
    if not args.nom:
        print(f"{len(connus)} template(s) :")
        for nom in connus:
            resume = apercu_mod.resume(nom)
            meta = resume["meta"]
            print(f"  {nom:<28} {meta.get('nom', '')} "
                  f"· {resume['nb_propres']} réglages propres")
        print("\n`fresque template <nom>` pour le détail, `--html` pour la page.")
        return 0

    try:
        if args.html:
            # La boucle sonore n'existe qu'une fois un projet monté ; on la
            # copie à côté de la page pour qu'elle soit écoutable.
            sortie = Path(args.html)
            musique = None
            if args.projet:
                project = Project.open(args.projet)
                source = project.root / "04-audio/sons/musique.wav"
                if source.is_file():
                    import shutil
                    sortie.parent.mkdir(parents=True, exist_ok=True)
                    musique = sortie.parent / "musique.wav"
                    shutil.copy2(source, musique)
            apercu_mod.page(args.nom, sortie, musique)
            print(f"✓ {sortie}")
            return 0
        print(apercu_mod.texte(args.nom, tout=args.tout))
    except config.TemplateError as error:
        return _fail(str(error))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from . import doctor as doctor_mod

    print("Diagnostic Fresque\n")
    essentials_ok, blocked = doctor_mod.run()

    if not blocked:
        print("\n✓ Tout est joignable.")
        return 0

    print(f"\n{len(blocked)} hôte(s) injoignable(s).")
    print(
        "\nSi tu es dans une session Claude Code cloud, c'est le niveau d'accès\n"
        "réseau de l'environnement. Ouvre le sélecteur d'environnement sur\n"
        "claude.ai/code (l'icône nuage au-dessus de la zone de message), édite\n"
        "l'environnement, passe « Network access » sur **Custom**, coche\n"
        "« Also include default list of common package managers », et colle :\n"
    )
    for line in doctor_mod.allowlist(blocked).splitlines():
        print(f"    {line}")
    print(
        "\nLe changement ne s'applique qu'aux sessions démarrées ensuite :\n"
        "il faut en ouvrir une nouvelle."
    )
    return 0 if essentials_ok else 1


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
    add("lint", "Vérifier le script contre les règles d'écriture", cmd_lint)
    add("shots", "Valider le plan visuel", cmd_shots)
    add("voice", "Synthétiser la voix off (Kokoro)", cmd_voice)
    fetch_cmd = add("fetch", "Sourcer les archives libres", cmd_fetch)
    fetch_cmd.add_argument(
        "--dry-run", action="store_true",
        help="chercher et afficher sans rien télécharger",
    )
    fetch_cmd.add_argument(
        "--force", action="store_true",
        help="re-sourcer même les plans déjà acquis",
    )
    images_cmd = add("images", "Générer les images manquantes (Gemini)", cmd_images)
    images_cmd.add_argument(
        "--list-models", action="store_true",
        help="interroger l'API pour connaître les modèles d'image disponibles",
    )
    add("rushes", "Sourcer le métrage d'archive (Library of Congress)", cmd_rushes)
    add("placeholders", "Générer des visuels de substitution", cmd_placeholders)
    add("timeline", "Construire 06-timeline.json", cmd_timeline)
    render_cmd = add("render", "Rendre la vidéo avec Remotion", cmd_render)
    render_cmd.add_argument("--concurrency", type=int, default=4)
    render_cmd.add_argument(
        "--browser", default=None,
        help="chemin d'un Chromium existant (évite un téléchargement)",
    )
    render_cmd.add_argument(
        "--output", default=None, help="chemin de sortie (défaut : 07-out/video.mp4)"
    )
    render_cmd.add_argument(
        "--scale", type=float, default=1.0,
        help="facteur de résolution, par ex. 0.5 pour une copie de visionnage",
    )
    render_cmd.add_argument(
        "--frames", default=None, metavar="DEBUT-FIN",
        help="ne rendre qu'un intervalle, par ex. 0-450 — de quoi vérifier "
             "une ouverture ou une transition sans rendre le film entier",
    )
    render_cmd.add_argument(
        "--crf", type=int, default=None, help="qualité d'encodage (défaut : config)"
    )
    add("status", "État d'avancement du projet", cmd_status)
    add("review", "Construire la page de validation du projet", cmd_review)

    # No slug: these two describe the installation, not a project.
    doctor_cmd = sub.add_parser(
        "doctor", help="Vérifier accès réseau, modèles et dépendances"
    )
    doctor_cmd.set_defaults(handler=cmd_doctor)

    template_cmd = sub.add_parser(
        "template", help="Voir ce qu'un template contient, et d'où vient chaque valeur"
    )
    template_cmd.set_defaults(handler=cmd_template)
    template_cmd.add_argument("nom", nargs="?", help="sans nom : liste les templates")
    template_cmd.add_argument(
        "--tout", action="store_true",
        help="afficher aussi les valeurs héritées de la config de base",
    )
    template_cmd.add_argument(
        "--html", metavar="FICHIER", default=None,
        help="écrire une page statique montrant la direction artistique",
    )
    template_cmd.add_argument(
        "--projet", default=None,
        help="slug d'un projet monté, pour joindre sa boucle sonore à la page",
    )

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (script_parser.ScriptError, shots_mod.ShotsError) as error:
        return _fail(str(error))
    except FileNotFoundError as error:
        return _fail(str(error))
