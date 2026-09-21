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


#: Les fournisseurs de voix, nommés ici pour qu'argparse les propose sans
#: importer `voice` — qui tire numpy et le modèle Kokoro au passage.
_FOURNISSEURS = ("kokoro", "edge", "elevenlabs")


# --- Les étapes confiées à Claude --------------------------------------------
#
# Elles ne font rien elles-mêmes : elles vérifient ce qui doit exister,
# lancent le bon skill, et laissent Claude écrire le fichier. Le partage
# tient en une phrase — Claude juge, le code exécute — et ces quatre
# fonctions sont la frontière.

def cmd_nouveau(args: argparse.Namespace) -> int:
    """Un sujet tapé par l'utilisateur devient un dossier. Rien de plus."""
    from .project import slugify

    sujet = (args.sujet or "").strip()
    if not sujet:
        return _fail("un sujet vide ne donne pas de documentaire")
    slug = slugify(sujet)
    if not slug:
        return _fail(f"« {sujet} » ne donne aucun slug utilisable")
    if (config.repo_root() / "projects" / slug).is_dir():
        return _fail(f"projects/{slug} existe déjà")

    project = Project.create(sujet, args.template)
    print(f"✓ projects/{project.slug}/projet.yaml")
    print(f"  sujet : {sujet}")
    if args.template:
        print(f"  template : {args.template}")
    print("  suivant : fresque explorer " + project.slug)
    return 0


def _claude(nom: str, args: argparse.Namespace) -> int:
    from . import claude as claude_mod

    Project.open(args.slug)  # valide le slug et charge le template
    try:
        return claude_mod.lancer(nom, args.slug, getattr(args, "modele", None))
    except claude_mod.ClaudeError as erreur:
        return _fail(str(erreur))


def cmd_explorer(args: argparse.Namespace) -> int:
    return _claude("explorer", args)


def cmd_recherche(args: argparse.Namespace) -> int:
    """Le choix d'une piste, puis la recherche dessus.

    C'est le seul endroit où un clic devient un fait. Le numéro est
    confronté à `pistes.md` avant d'être écrit : une piste 7 dans un
    fichier qui en contient quatre est une erreur, pas une recherche sur un
    angle vide.
    """
    from . import pistes as pistes_mod

    project = Project.open(args.slug)
    if args.piste is not None:
        try:
            catalogue = pistes_mod.lire(project.pistes)
        except FileNotFoundError:
            return _fail("pistes.md manque — lancer `fresque explorer` d'abord")
        except pistes_mod.PistesError as erreur:
            return _fail(str(erreur))
        numeros = [p["numero"] for p in catalogue["pistes"]]
        if args.piste not in numeros:
            return _fail(f"piste {args.piste} inconnue (présentes : "
                         f"{', '.join(str(n) for n in numeros)})")
        retenue = next(p for p in catalogue["pistes"] if p["numero"] == args.piste)
        project.set_valeurs(piste=args.piste, titre=pistes_mod.choisie(retenue))
        print(f"· piste {args.piste} — {retenue['resume']}")
    elif project.piste is None and project.pistes.is_file():
        return _fail("aucune piste retenue — relancer avec --piste N")

    return _claude("recherche", args)


def cmd_ecrire(args: argparse.Namespace) -> int:
    return _claude("ecrire", args)


def cmd_plans(args: argparse.Namespace) -> int:
    return _claude("plans", args)


def cmd_pistes(args: argparse.Namespace) -> int:
    """Relit `pistes.md` et le contrôle — le même contrôle que l'interface."""
    from . import pistes as pistes_mod

    project = Project.open(args.slug)
    try:
        catalogue = pistes_mod.lire(project.pistes)
    except FileNotFoundError:
        return _fail("pistes.md manque — lancer `fresque explorer` d'abord")
    except pistes_mod.PistesError as erreur:
        return _fail(str(erreur))

    retenue = project.piste
    for piste in catalogue["pistes"]:
        marque = "▸" if piste["numero"] == retenue else " "
        print(f"{marque} {piste['numero']}. {piste['resume']}")
        print(f"    {piste['angle']}")
        print(f"    pivot : {piste['pivot']}")
        for titre in piste["titres"]:
            print(f"    « {titre['texte']} »  (preuve {titre['preuve']})")
        print(f"    {len(piste['preuves'])} preuves · risque : "
              f"{piste['risque'] or '—'}")
    return 0


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
    # La fiche du moteur n'a pas les mêmes champs d'un moteur à l'autre :
    # on l'affiche telle qu'elle vient plutôt que d'en nommer un.
    fiche = alignment["voix"]
    print("  " + " · ".join(f"{cle} {valeur}" for cle, valeur in fiche.items()))
    mots = alignment["nb_mots"]
    duree = alignment["duree_totale_s"]
    if duree:
        print(f"  {mots / duree * 60:.0f} mots/min, silences compris")
    print("  durées de beat mesurées sur l'audio réel")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """Faire entendre un beat, sans synthétiser tout le film.

    Un script se valide en le lisant, alors qu'il sera entendu — une seule
    fois, sans retour en arrière. Un hook qui ne marche pas s'entend en
    quinze secondes ; en markdown il peut passer trois relectures.

    C'est `_say_beat` qui travaille, la fonction même de la passe voix :
    ce qu'on entend ici est exactement ce qui sortira, pauses comprises.
    """
    from . import voice as voice_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)

    vise = (args.beat or script.beats[0].id).upper()
    beat = next((b for b in script.beats if b.id == vise), None)
    if beat is None:
        return _fail(f"{vise} n'est pas un beat de ce script "
                     f"({script.beats[0].id} à {script.beats[-1].id})")

    try:
        machine = voice_mod.moteur()
        samples, rate = voice_mod._say_beat(
            machine, beat.text,
            float(config.get("narration", "pause_phrase_s", default=0.45)),
        )
    except voice_mod.VoiceError as erreur:
        return _fail(str(erreur))

    sortie = project.audio_dir / f"essai-{beat.id}.wav"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    voice_mod._write_wav(sortie, samples, rate)

    duree = len(samples) / rate
    cible = float(config.get("structure", "hook_s", default=20))
    print(f"✓ {sortie.relative_to(project.root)}")
    ligne = (f"{beat.id} · {duree:.1f} s · {beat.word_count} mots · "
             f"{beat.word_count / duree * 60:.0f} mots/min")
    if beat.id == script.beats[0].id:
        ligne += f" · cible {cible:.0f} s"
    print(ligne)
    if beat.id == script.beats[0].id and duree > cible:
        print(f"  ⚠ {duree - cible:.1f} s de trop — la suite appartient au "
              "beat suivant")
    return 0


def cmd_refaire(args: argparse.Namespace) -> int:
    """Remplacer le visuel d'un plan, et d'un seul.

    C'est le bouton « Remplacer » de la galerie. Le refus est écrit dans
    `05-visuals/rejets.jsonl` avant la nouvelle recherche : sans ce
    registre, le second clic relance la même requête et retombe sur le même
    candidat — on aurait un bouton qui ne fait rien.
    """
    from . import fetch as fetch_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])

    vise = args.plan.upper()
    shot = next((s for s in plan if s.id == vise), None)
    if shot is None:
        return _fail(f"{vise} n'est pas un plan de ce projet "
                     f"({plan[0].id} à {plan[-1].id})")
    if shot.type == "motion":
        return _fail(f"{vise} est un panneau graphique : il n'a pas de "
                     "fichier à remplacer. Corriger son contenu dans "
                     "03-shots.json.")

    assets = {}
    if project.assets.is_file():
        assets = json.loads(project.assets.read_text(encoding="utf-8")).get(
            "assets", {})
    actuel = assets.get(vise)

    if actuel:
        fetch_mod.noter_rejet(project.visuals_dir, vise, actuel, args.raison or "")
        ancien = project.root / actuel.get("fichier", "")
        # Le fichier peut servir à un autre plan : une archive revient, et
        # le manifeste l'enregistre deux fois. On ne le supprime que s'il
        # n'est plus référencé nulle part.
        assets.pop(vise, None)
        encore = any(a.get("fichier") == actuel.get("fichier")
                     for a in assets.values())
        if ancien.is_file() and not encore:
            ancien.unlink()
        print(f"· {vise} refusé : {actuel.get('titre', '—')[:60]}")
    else:
        print(f"· {vise} n'avait pas de visuel")

    if shot.type == "generated":
        from . import images as images_mod

        try:
            assets[vise] = images_mod.generate(
                shot, project.visuals_dir, report=lambda ligne: print(ligne))
        except images_mod.ImageError as erreur:
            fetch_mod.write_assets(assets, project.assets)
            return _fail(str(erreur))
    else:
        nouveaux, manquants = fetch_mod.fetch_archives(
            [shot], project.visuals_dir, report=lambda ligne: print(ligne),
            deja={k: v for k, v in assets.items()},
            refuses=fetch_mod.lire_rejets(project.visuals_dir),
        )
        if manquants:
            fetch_mod.write_assets(assets, project.assets)
            return _fail(f"{vise} : plus aucun candidat pour « "
                         f"{shot.requete} » — changer la requête dans "
                         "03-shots.json")
        assets.update(nouveaux)

    fetch_mod.write_assets(assets, project.assets)
    nouveau = assets[vise]
    print(f"✓ {vise} · {nouveau.get('titre', '')[:60]}")
    print(f"  {nouveau.get('source', '')} · {nouveau.get('licence', '')}")
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

    # L'ouverture décide si le deuxième plan est vu. La variété décide si
    # le film se regarde. Les deux font échouer le checkpoint, avant la
    # moindre dépense.
    opening = shots_mod.ouverture(plan)
    for line in opening:
        print(f"\n✗ ouverture : {line}", file=sys.stderr)

    varie = shots_mod.variete(plan, script.beats)
    for line in varie:
        print(f"✗ variété : {line}", file=sys.stderr)

    return 1 if (opening or varie) else 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from . import fetch as fetch_mod

    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])

    # Une planche de collage se source exactement comme une archive : c'est
    # une photographie libre. Ce qui change vient après, au montage.
    archives = [s for s in plan if s.type in shots_mod.SOURCEES]
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


def _porte() -> str:
    """Par quelle porte on passe, et sur quel compte ça se facture.

    Deux fournisseurs servent les mêmes modèles ; se tromper de porte coûte
    de l'argent sur le mauvais projet, ou échoue après coup. Autant le dire
    avant, en une ligne.
    """
    from . import images as images_mod, vertex as vertex_mod

    try:
        nom = images_mod.fournisseur()
    except images_mod.ImageError as error:
        return f"⚠ {error}"
    if nom != "vertex":
        return "Fournisseur : AI Studio (GEMINI_API_KEY)"
    try:
        etat = vertex_mod.etat()
    except vertex_mod.VertexError as error:
        return f"Fournisseur : Vertex AI — ⚠ {error}"
    # On nomme la variable qui porte la clé, jamais son contenu : savoir
    # LAQUELLE a été lue est ce qui manque quand trois noms sont acceptés.
    papiers = (f"clé {etat['cle']}" if etat["cle"] else "jeton OAuth")
    projet = etat["projet"] or "déduit du justificatif"
    return (f"Fournisseur : Vertex AI · {papiers} · projet {projet} "
            f"· région {etat['region']}")


def cmd_essai_image(args: argparse.Namespace) -> int:
    """Générer UNE image, sans projet, pour vérifier qu'une porte s'ouvre.

    Changer de fournisseur ou de modèle se vérifiait jusqu'ici en lançant un
    projet entier : on découvrait un jeton refusé après avoir attendu la
    voix et le sourcing. Une image seule coûte trois centimes et répond en
    quelques secondes.
    """
    import time

    from . import images as images_mod
    from .shots import Shot

    print(_porte())
    destination = Path(args.sortie or ".")
    shot = Shot(index=0, beat="ESSAI", type="generated", prompt=args.prompt)

    modele = args.modele or str(
        config.get("visuels", "generation", "model", default=""))
    print(f"→ {modele or 'modèle par défaut'} · « {args.prompt} »")

    debut = time.monotonic()
    try:
        asset = images_mod.generate(shot, destination, model=args.modele or None,
                                    report=print)
    except images_mod.ImageError as error:
        return _fail(str(error))

    chemin = destination / Path(asset["fichier"]).name
    octets = chemin.stat().st_size
    print(f"✓ {chemin} · {octets / 1024:.0f} Ko · "
          f"{time.monotonic() - debut:.1f} s")
    # Les dimensions disent si `imageConfig` a été honoré : l'API ne le
    # confirme nulle part, et un carré rendu là où la config demande du 16:9
    # est exactement le défaut qu'on vient de corriger.
    try:
        from PIL import Image

        with Image.open(chemin) as vue:
            attendu = str(config.get("visuels", "generation", "ratio", default=""))
            reel = vue.width / vue.height
            print(f"  {vue.width} × {vue.height} (rapport {reel:.2f})"
                  + (f" · demandé {attendu}" if attendu else ""))
    except ImportError:
        pass
    return 0


def cmd_images(args: argparse.Namespace) -> int:
    from . import fetch as fetch_mod, images as images_mod

    # Lister les modèles ne regarde aucun projet : ouvrir celui-ci d'abord
    # obligeait à en nommer un pour vérifier une installation, et à en avoir
    # un avant d'avoir vérifié qu'on pouvait générer quoi que ce soit.
    if args.list_models:
        # Sur Vertex, cette commande ne se contente pas de lister : chaque
        # fiche interrogée vérifie le jeton, le projet, la région et
        # l'identifiant du modèle, gratuitement. C'est donc la commande à
        # lancer d'abord, avant d'avoir dépensé quoi que ce soit.
        print(_porte())
        try:
            names = images_mod.image_models()
        except (images_mod.ImageError, Exception) as error:  # noqa: BLE001
            return _fail(str(error))
        print("Modèles d'image servis :")
        for name in names:
            print(f"  {name}")
        return 0

    if not args.slug:
        return _fail("slug manquant — `fresque images <slug>`.")
    project = Project.open(args.slug)
    script = script_parser.parse(project.script)
    plan = shots_mod.load(project.shots, [b.id for b in script.beats])
    todo = [s for s in plan if s.type == "generated"]
    if not todo:
        print("Aucun plan `generated` — rien à produire.")
        return 0

    # Dit avant de dépenser sur quel compte la dépense va tomber.
    print(_porte())
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
        # Sans ça, Remotion lance l'exécutable comme un « headless shell »,
        # un binaire réduit qui n'accepte pas les mêmes arguments. Un
        # Chromium complet — celui de Playwright, par exemple — meurt
        # immédiatement, et le message dit seulement « Failed to launch the
        # browser process », ce qui envoie chercher le problème ailleurs.
        command.append("--chrome-mode=chrome-for-testing")

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


def cmd_aligner(args: argparse.Namespace) -> int:
    from . import align as align_mod, aligner as aligner_mod

    project = Project.open(args.slug)
    if not project.alignment.is_file():
        return _fail("alignment.json manquant — lancer `voice` d'abord.")
    script = script_parser.parse(project.script)
    precedent = align_mod.load(project.alignment)

    try:
        bases = aligner_mod.bases_depuis(precedent)
        resultat = aligner_mod.force(
            script, project.audio_dir, bases,
            report=print if args.verbeux else None,
        )
    except aligner_mod.AlignError as erreur:
        return _fail(str(erreur))

    align_mod.write(resultat, project.alignment)
    print(f"✓ {project.alignment.relative_to(config.repo_root())} · "
          f"source `{resultat['source']}`")
    print(f"  {resultat['nb_mots']} mots sur {resultat['nb_beats']} beats · "
          f"{align_mod.format_duration(resultat['duree_totale_s'])}")
    print(f"  confiance la plus basse : {resultat['confiance_min']:.2f}")

    suspects = resultat["mots_invraisemblables"]
    if suspects:
        print(f"\n  {len(suspects)} mot(s) posé(s) à une durée invraisemblable — "
              "soit le texte ne correspond pas à ce qui a été dit, soit la "
              "voix a avalé le mot :")
        for entree in suspects[:10]:
            print(f"    {entree['beat']}  {entree['mot']:<22} "
                  f"{entree['duree_s']:.2f} s / {entree['syllabes']} syll "
                  f"= {entree['s_par_syllabe']:.3f}")
    else:
        print("  aucun mot posé à une durée invraisemblable.")
    for ligne in resultat["beats_non_alignes"]:
        print(f"  ⚠ {ligne}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from . import export as export_mod

    destination = Path(args.destination)
    bilan = export_mod.exporter(
        destination, args.videos,
        args.largeur or export_mod.LARGEUR_VIGNETTE)
    print(f"✓ {destination} — {bilan.projets} projet(s), {bilan.fichiers} image(s)"
          + (f", {bilan.videos} vidéo(s)" if bilan.videos else ""))
    print(f"  {bilan.octets_source / 1e6:.0f} Mo de visuels ramenés à "
          f"{bilan.octets_export / 1e6:.0f} Mo ({bilan.gain:.0f}× plus léger)")
    print(f"  ouvrir : file://{destination.resolve()}/index.html")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from . import serveur as serveur_mod

    serveur_mod.servir(args.hote, args.port)
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
        ("pistes.md", project.pistes),
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


def cmd_voix(args: argparse.Namespace) -> int:
    """La bibliothèque d'un fournisseur, filtrable par langue et par sexe.

    Les trois moteurs décrivent leur catalogue de façon incompatible.
    `voice.catalogue` les normalise, donc cette commande — et l'interface
    qui l'appelle — n'en connaît qu'un seul format.
    """
    from . import voice

    fournisseur = args.provider or str(
        config.get("voix", "provider", default="kokoro"))
    try:
        toutes = voice.catalogue(fournisseur)
    except voice.VoiceError as erreur:
        return _fail(str(erreur))

    retenues = voice.filtrer(toutes, args.langue or "", args.genre or "")
    if not retenues:
        filtres = " ".join(f for f in (args.langue, args.genre) if f)
        return _fail(f"aucune voix chez {fournisseur} pour « {filtres} » "
                     f"({len(toutes)} voix au catalogue)")

    actuelle = str(config.get("voix", fournisseur, "voice", default=""))
    print(f"{fournisseur} · {len(retenues)} voix sur {len(toutes)}")
    for v in retenues:
        marque = "→" if v.id == actuelle else " "
        print(f" {marque} {v.id:34} {v.langue:7} {v.genre:7} {v.detail[:38]}")
    return 0


def cmd_voix_essai(args: argparse.Namespace) -> int:
    """Écouter une voix avant de la choisir.

    N'écrit rien dans `projet.yaml` : écouter et décider sont deux gestes.
    La phrase d'essai est le hook du script quand il existe — c'est sur lui
    qu'une voix se juge, pas sur une phrase neutre.
    """
    from . import voice

    project = Project.open(args.slug)
    fournisseur = args.provider or str(
        config.get("voix", "provider", default="kokoro"))

    texte = args.texte
    if not texte and project.script.is_file():
        texte = script_parser.parse(project.script).beats[0].text
    texte = texte or ("Le vingt-cinq septembre, le tribunal a prononcé une "
                      "peine de cinq ans. Personne ne s'y attendait.")

    try:
        machine = voice.moteur(fournisseur, args.voix or "")
        samples, rate = voice._say_beat(
            machine, texte,
            float(config.get("narration", "pause_phrase_s", default=0.45)),
        )
    except voice.VoiceError as erreur:
        return _fail(str(erreur))

    nom = (args.voix or machine.voice or fournisseur).replace("/", "-")
    sortie = project.audio_dir / f"essai-voix-{nom}.wav"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    voice._write_wav(sortie, samples, rate)

    duree = len(samples) / rate
    mots = len(texte.split())
    print(f"✓ {sortie.relative_to(project.root)}")
    print(f"{fournisseur} · {machine.voice} · {duree:.1f} s · "
          f"{mots / duree * 60:.0f} mots/min")
    return 0


def cmd_voix_choix(args: argparse.Namespace) -> int:
    """Retenir une voix pour ce projet.

    Le choix s'écrit dans les `reglages` du projet, pas dans la config du
    dépôt : deux documentaires côte à côte n'ont aucune raison de parler
    avec la même voix, et la config du dépôt est suivie par git.
    """
    from . import voice

    project = Project.open(args.slug)
    try:
        toutes = voice.catalogue(args.provider)
    except voice.VoiceError as erreur:
        return _fail(str(erreur))

    retenue = next((v for v in toutes if v.id == args.voix), None)
    if retenue is None:
        return _fail(f"« {args.voix} » n'est pas une voix de {args.provider} "
                     f"({len(toutes)} au catalogue)")

    reglages = project.reglages
    voix = dict(reglages.get("voix") or {})
    voix["provider"] = args.provider
    bloc = dict(voix.get(args.provider) or {})
    bloc["voice"] = retenue.id
    voix[args.provider] = bloc
    reglages["voix"] = voix
    project.set_valeurs(reglages=reglages)

    print(f"✓ {args.provider} · {retenue.id}")
    print(f"  {retenue.nom} · {retenue.langue} · {retenue.genre}")
    print(f"  écrit dans projects/{project.slug}/projet.yaml")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fresque", description="Étapes déterministes du pipeline Fresque."
    )
    sub = parser.add_subparsers(dest="commande", required=True)

    def add(name: str, help_text: str, handler, slug: bool = True):
        node = sub.add_parser(name, help=help_text)
        if slug:
            node.add_argument("slug")
        node.set_defaults(handler=handler)
        return node

    # Les étapes que Claude tient. Toutes acceptent --modele : la recherche
    # coûte cher en tours, et on veut pouvoir l'essayer plus bas.
    nouveau_cmd = sub.add_parser(
        "nouveau", help="Créer un projet à partir d'un sujet"
    )
    nouveau_cmd.set_defaults(handler=cmd_nouveau)
    nouveau_cmd.add_argument("sujet", help="quelques mots-clés, entre guillemets")
    nouveau_cmd.add_argument(
        "--template", default=None,
        choices=config.available_templates() or None,
        help="direction artistique (défaut : la config de base)",
    )

    explorer_cmd = add(
        "explorer", "Proposer quatre pistes à partir du sujet", cmd_explorer)
    add("pistes", "Relire et contrôler pistes.md", cmd_pistes)
    recherche_cmd = add(
        "recherche", "Mener la recherche sur la piste retenue", cmd_recherche)
    recherche_cmd.add_argument(
        "--piste", type=int, default=None,
        help="numéro de la piste choisie dans pistes.md",
    )
    ecrire_cmd = add("ecrire", "Écrire le script", cmd_ecrire)
    plans_cmd = add("plans", "Écrire le plan visuel", cmd_plans)
    for node in (explorer_cmd, recherche_cmd, ecrire_cmd, plans_cmd):
        node.add_argument(
            "--modele", default=None, help="modèle Claude (défaut : opus)")

    align_cmd = add("align", "Estimer les timings depuis le script", cmd_align)
    align_cmd.add_argument("--target", type=float, help="durée cible en minutes")
    add("lint", "Vérifier le script contre les règles d'écriture", cmd_lint)
    refaire_cmd = add("refaire", "Remplacer le visuel d'un seul plan", cmd_refaire)
    refaire_cmd.add_argument("plan", help="identifiant du plan, ex. S012")
    refaire_cmd.add_argument(
        "--raison", default=None, help="pourquoi ce visuel est refusé")
    hook_cmd = add("hook", "Entendre un beat sans synthétiser le film", cmd_hook)
    hook_cmd.add_argument(
        "--beat", default=None, metavar="B00N",
        help="beat à entendre (défaut : le premier, c'est-à-dire le hook)",
    )
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
    images_cmd = add("images", "Générer les images manquantes", cmd_images,
                     slug=False)
    images_cmd.add_argument(
        "slug", nargs="?", default=None,
        help="le projet (inutile avec --list-models)",
    )
    images_cmd.add_argument(
        "--list-models", action="store_true",
        help="interroger l'API pour connaître les modèles d'image disponibles",
    )
    essai_cmd = add("essai-image", "Générer une seule image, pour vérifier "
                    "qu'un fournisseur répond", cmd_essai_image, slug=False)
    essai_cmd.add_argument("prompt")
    essai_cmd.add_argument("--modele", default=None,
                           help="forcer un modèle (défaut : celui de la config)")
    essai_cmd.add_argument("--sortie", default=None,
                           help="dossier de destination (défaut : courant)")
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
    aligner_cmd = add(
        "aligner", "Mesurer la position de chaque mot dans l'audio", cmd_aligner)
    aligner_cmd.add_argument(
        "--verbeux", action="store_true", help="afficher beat par beat")
    add("status", "État d'avancement du projet", cmd_status)
    add("review", "Construire la page de validation du projet", cmd_review)

    export_cmd = sub.add_parser(
        "export", help="Figer l'atelier dans un dossier ouvrable sans serveur"
    )
    export_cmd.set_defaults(handler=cmd_export)
    export_cmd.add_argument("destination")
    export_cmd.add_argument(
        "--videos", action="store_true",
        help="inclure une copie de visionnage par projet (lourd)",
    )
    export_cmd.add_argument(
        "--largeur", type=int, default=None,
        help="largeur des images en pixels (défaut : celle de la planche)",
    )

    serve_cmd = sub.add_parser(
        "serve", help="Ouvrir l'atelier dans un navigateur (aucun état gardé)"
    )
    serve_cmd.set_defaults(handler=cmd_serve)
    serve_cmd.add_argument("--port", type=int, default=4321)
    serve_cmd.add_argument(
        "--hote", default="127.0.0.1",
        help="0.0.0.0 pour ouvrir sur le réseau local — le serveur lance des "
             "commandes, ne l'exposer qu'à un réseau de confiance",
    )

    # No slug: these two describe the installation, not a project.
    doctor_cmd = sub.add_parser(
        "doctor", help="Vérifier accès réseau, modèles et dépendances"
    )
    doctor_cmd.set_defaults(handler=cmd_doctor)

    # La bibliothèque : sans slug, elle décrit l'installation, pas un projet.
    voix_cmd = sub.add_parser(
        "voix", help="La bibliothèque de voix d'un fournisseur"
    )
    voix_cmd.set_defaults(handler=cmd_voix)
    voix_cmd.add_argument(
        "--provider", default=None, choices=sorted(_FOURNISSEURS),
        help="kokoro, edge ou elevenlabs (défaut : celui de la config)",
    )
    voix_cmd.add_argument(
        "--langue", default="fr",
        help="préfixe de locale, par ex. fr ou fr-FR (défaut : fr) — "
             "vide pour toutes",
    )
    voix_cmd.add_argument(
        "--genre", default=None, choices=("homme", "femme"),
        help="filtrer par sexe de la voix",
    )

    essai_voix_cmd = add(
        "voix-essai", "Écouter une voix avant de la choisir", cmd_voix_essai)
    essai_voix_cmd.add_argument(
        "--provider", default=None, choices=sorted(_FOURNISSEURS))
    essai_voix_cmd.add_argument(
        "--voix", default=None, help="identifiant de la voix à essayer")
    essai_voix_cmd.add_argument(
        "--texte", default=None,
        help="phrase d'essai (défaut : le hook du script)")

    choix_voix_cmd = add(
        "voix-choix", "Retenir une voix pour ce projet", cmd_voix_choix)
    choix_voix_cmd.add_argument(
        "--provider", required=True, choices=sorted(_FOURNISSEURS))
    choix_voix_cmd.add_argument("--voix", required=True)

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
