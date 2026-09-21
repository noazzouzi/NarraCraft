"""Tests for the deterministic half of the pipeline.

Run with:  PYTHONPATH=pipeline python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Le dépôt, retrouvé depuis CE fichier. Deux tests lisent le moteur de
#: rendu pour vérifier qu'il n'a pas divergé du pipeline ; ils le
#: cherchaient par chemin relatif au répertoire courant, donc ils
#: échouaient dès qu'on lançait la suite depuis `pipeline/`.
RACINE = Path(__file__).resolve().parents[2]
MOTEUR_TSX = RACINE / "remotion" / "src" / "Motion.tsx"

from fresque import align, script_parser, timeline as timeline_mod  # noqa: E402
from fresque.shots import Shot, ShotsError, load as load_shots  # noqa: E402

SCRIPT = """# Script — test

## Acte I — Ouverture

### B001
> intention: un plan large
Première phrase, avec une virgule. Deuxième phrase courte.

### B002
> intention: un gros plan
Une seule phrase ici.

## Acte II — Suite

### B003
> intention: un document
Encore du texte, pour faire bonne mesure.
"""


@pytest.fixture
def script(tmp_path: Path) -> script_parser.Script:
    path = tmp_path / "02-script.md"
    path.write_text(SCRIPT, encoding="utf-8")
    return script_parser.parse(path)


def test_parse_extracts_beats_acts_and_intentions(script):
    assert [b.id for b in script.beats] == ["B001", "B002", "B003"]
    assert script.beats[0].intention == "un plan large"
    assert script.beats[2].act == "II"
    assert "Contrôle" not in script.beats[-1].text


def test_stage_directions_are_refused(tmp_path: Path):
    path = tmp_path / "02-script.md"
    path.write_text(
        "# T\n\n## Acte I — A\n\n### B001\n> intention: x\n"
        "Du texte [ton grave] et la suite.\n",
        encoding="utf-8",
    )
    with pytest.raises(script_parser.ScriptError, match="texte prononcé"):
        script_parser.parse(path)


def test_discontinuous_numbering_is_refused(tmp_path: Path):
    path = tmp_path / "02-script.md"
    path.write_text(
        "# T\n\n## Acte I — A\n\n### B001\n> intention: x\nTexte.\n\n"
        "### B003\n> intention: y\nTexte.\n",
        encoding="utf-8",
    )
    with pytest.raises(script_parser.ScriptError, match="discontinue"):
        script_parser.parse(path)


def test_missing_intention_is_refused(tmp_path: Path):
    path = tmp_path / "02-script.md"
    path.write_text("# T\n\n## Acte I — A\n\n### B001\nTexte seul.\n", encoding="utf-8")
    with pytest.raises(script_parser.ScriptError, match="intention"):
        script_parser.parse(path)


def test_alignment_is_monotonic_and_covers_every_beat(script):
    alignment = align.estimate(script)
    assert alignment["nb_beats"] == 3
    previous = -1.0
    for beat in alignment["beats"]:
        assert beat["debut_s"] >= previous
        for word in beat["mots"]:
            assert word["fin_s"] > word["debut_s"]
            assert word["debut_s"] >= previous
            previous = word["debut_s"]
        assert beat["fin_s"] <= alignment["duree_totale_s"] + 1e-6


def test_alignment_keeps_punctuation_for_display(script):
    alignment = align.estimate(script)
    displays = [w["tx"] for w in alignment["beats"][0]["mots"]]
    assert any(d.endswith(",") for d in displays), displays
    assert any(d.endswith(".") for d in displays), displays
    # The bare form stays clean for the speech engine.
    assert all(not w["t"].endswith((",", ".")) for w in alignment["beats"][0]["mots"])


def test_acts_get_a_longer_breath_than_beats(script):
    alignment = align.estimate(script)
    beats = alignment["beats"]
    within_act = beats[1]["debut_s"] - beats[0]["fin_s"]
    across_acts = beats[2]["debut_s"] - beats[1]["fin_s"]
    assert across_acts > within_act


def _shot(beat: str, index: int, movement: str = "zoom_in", weight: float = 1.0) -> Shot:
    return Shot(index=index, beat=beat, type="archive", requete="q",
                mouvement=movement, poids=weight)


# --- Où tombent les coupes ---------------------------------------------------
#
# Une coupe posée au prorata des poids tombe où le calcul la met, parfois
# au milieu d'un mot. C'est le défaut le plus reconnaissable d'un montage
# automatique. On a la position de chaque mot : il suffit de chercher.

def _mot(texte: str, debut: float, fin: float) -> dict:
    return {"t": texte, "tx": texte, "debut_s": debut, "fin_s": fin}


def test_a_cut_goes_to_the_widest_silence_not_the_nearest():
    """Un blanc de trois cents millisecondes est un meilleur point de coupe
    qu'un blanc de trente, même un peu plus loin."""
    mots = [
        _mot("un", 0.0, 0.5),
        _mot("deux", 0.53, 1.0),     # blanc de 0,03 s, tout près de 1,05
        _mot("trois", 1.30, 1.8),    # blanc de 0,30 s, un peu plus loin
        _mot("quatre", 1.83, 2.3),
    ]
    instant, largeur = timeline_mod._caler_sur_silence(1.05, mots, 0.4)

    assert largeur == pytest.approx(0.30)
    assert instant == pytest.approx(1.15), "le milieu du blanc large"


def test_a_cut_with_no_silence_in_reach_stays_where_it_was():
    mots = [_mot("un", 0.0, 1.0), _mot("deux", 1.0, 2.0)]
    instant, largeur = timeline_mod._caler_sur_silence(1.5, mots, 0.1)
    assert (instant, largeur) == (1.5, 0.0)


def test_only_interior_cuts_count_as_missed():
    """Le dernier plan d'un beat n'a pas de coupe à caler : la sienne est la
    borne du beat suivant, déjà mesurée. Les compter comme des échecs
    faisait dire au contrôle que la moitié des coupes rataient — alors que
    la moitié n'en avait pas."""
    from fresque import timeline as t

    faux = {
        "fps": 30, "clips": [
            {"id": "S000", "debut_frame": 0, "duree_frames": 30, "type": "archive",
             "image": "a.jpg", "coupe_blanc_s": 0.2},
            {"id": "S001", "debut_frame": 30, "duree_frames": 30, "type": "archive",
             "image": "b.jpg", "coupe_blanc_s": None},
        ],
    }
    assert not [p for p in t.check(faux) if "silence" in p]


# --- La livraison ------------------------------------------------------------

def test_a_subtitle_becomes_a_timed_srt_line():
    """Le rendu produisait un mp4 et s'arrêtait là. Les sous-titres
    existaient déjà, à la frame près, dans la timeline."""
    from fresque import cli

    assert cli._horodatage(0) == "00:00:00,000"
    assert cli._horodatage(3661.5) == "01:01:01,500"
    assert cli._horodatage(75.25, ".") == "00:01:15.250"


def test_the_thumbnail_avoids_a_frame_with_a_subtitle_across_it():
    """Le premier plan porte déjà l'accroche et montre le sujet. Mais un
    sous-titre s'y incruste aussi, et une vignette avec un sous-titre en
    travers ne ressemble à rien."""
    from fresque import cli

    donnees = {
        "clips": [{"debut_frame": 0, "duree_frames": 90, "accroche": "Un fait."}],
        "sous_titres": [{"debut_frame": 0, "duree_frames": 45}],
    }
    assert cli._instant_vignette(donnees, 30) == pytest.approx(48 / 30, abs=0.2)

    # Aucune image libre : mieux vaut une vignette avec un sous-titre
    # qu'aucune vignette.
    couvert = {
        "clips": [{"debut_frame": 0, "duree_frames": 60, "accroche": "x"}],
        "sous_titres": [{"debut_frame": 0, "duree_frames": 60}],
    }
    assert cli._instant_vignette(couvert, 30) == 1.0


def test_filling_a_gap_never_erases_what_is_already_sourced(tmp_path):
    """`placeholders` réécrivait le manifeste entier : lancée après `fetch`
    pour boucher quatorze plans, elle détruisait les soixante-six autres,
    leurs licences et leurs crédits. Aucun test ne la couvrait.

    `merge_assets` fusionne et REND le manifeste ; c'est `write_assets` qui
    l'écrit. Jeter le résultat de la première donne le même effet en plus
    discret : les nouveaux visuels n'arrivent jamais.
    """
    from fresque import fetch as fetch_mod

    chemin = tmp_path / "assets.json"
    fetch_mod.write_assets({"S000": {"fichier": "a.jpg", "licence": "CC BY 4.0",
                                     "auteur": "Quelqu'un"}}, chemin)

    fetch_mod.write_assets(
        fetch_mod.merge_assets(chemin, {"S001": {"fichier": "b.jpg",
                                                 "source": "placeholder"}}),
        chemin,
    )

    assets = json.loads(chemin.read_text(encoding="utf-8"))["assets"]
    assert set(assets) == {"S000", "S001"}
    assert assets["S000"]["licence"] == "CC BY 4.0", "l'archive doit survivre"
    assert assets["S001"]["source"] == "placeholder"


def test_replacing_every_visual_has_to_be_asked_for(capsys):
    """Le comportement destructif existe encore — il se nomme, et il se
    lit dans l'aide avant de coûter quarante-six archives."""
    from fresque import cli

    with pytest.raises(SystemExit):
        cli.main(["placeholders", "--help"])
    aide = capsys.readouterr().out
    assert "--tout" in aide and "destructif" in aide


# --- Les familles de sous-titres ---------------------------------------------
#
# Liste close, comme les sept mouvements de caméra et les treize panneaux :
# le moteur sait en dessiner quatre, un template en choisit une, personne
# n'en invente. Une famille inconnue donnerait un film sans sous-titres,
# découvert après vingt minutes de rendu.

def test_an_unknown_subtitle_family_is_refused_before_the_render():
    from fresque import config

    config.use_project_overrides({"montage": {"sous_titres": {"style": "neon"}}})
    try:
        with pytest.raises(timeline_mod.TimelineError) as erreur:
            timeline_mod._famille_sous_titres()
        for connue in timeline_mod.FAMILLES_SOUS_TITRES:
            assert connue in str(erreur.value)
    finally:
        config.use_project_overrides(None)


def test_the_subtitle_settings_reach_the_renderer(script):
    alignment = align.estimate(script)
    shots = [_shot("B001", 0), _shot("B002", 1), _shot("B003", 2)]
    assets = {s.id: {"fichier": f"{s.id}.jpg"} for s in shots}

    reglages = timeline_mod.build(alignment, shots, assets)["style"]["sous_titres"]
    assert reglages["style"] in timeline_mod.FAMILLES_SOUS_TITRES
    for champ in ("majuscules", "position", "couleur_texte", "couleur_mot",
                  "couleur_fond", "ligne_de_base_pct", "voile"):
        assert champ in reglages


def test_the_collage_template_marks_instead_of_colouring():
    """Sur du papier crème, une couleur de TEXTE se distingue mal : le rouge
    des tampons n'a pas le contraste du jaune Frontier sur du noir. Un bloc
    derrière le mot se voit quel que soit le fond."""
    from fresque import config

    try:
        config.use_template("documentaire-collage")
        assert timeline_mod._famille_sous_titres() == "marqueur"
        config.use_template("documentaire-historique")
        assert timeline_mod._famille_sous_titres() == "surligne"
    finally:
        config.use_template(None)


def test_what_the_browser_sends_is_checked_before_it_reaches_projet_yaml():
    """Une famille inventée ou une couleur qui n'en est pas donneraient un
    film sans sous-titres, découvert après le rendu."""
    from fresque import serveur

    for mauvais in ({"style": "neon"},
                    {"couleur_mot": "red"},
                    {"couleur_texte": "#FFF"},
                    {"position": "gauche"},
                    {"ligne_de_base_pct": 150}):
        with pytest.raises(ValueError):
            serveur.choisir_sous_titres("sarkozy-essai-2min", mauvais)


def test_an_empty_colour_is_a_choice_not_an_error():
    """« Vide » veut dire « suis la palette du template ». C'est ce qui
    permet de rendre la main au template après l'avoir débordé."""
    from fresque import serveur

    retenu = serveur.choisir_sous_titres("sarkozy-essai-2min",
                                         {"couleur_mot": ""})
    assert retenu == {"couleur_mot": ""}


# --- Le carton de fin --------------------------------------------------------
#
# `timeline.py` construisait un tableau `credits` depuis toujours, et aucun
# composant ne le lisait. Sur le premier film complet, 258 visuels sur 329
# étaient sous une licence qui exige l'attribution, et aucun n'était
# crédité. Ce n'est pas un défaut de finition : la chaîne est monétisée.

def _credit(licence: str, auteur: str = "Un Auteur") -> dict:
    return {"asset": "x.jpg", "credit": f"{auteur} ({licence})", "url": "u",
            "licence": licence, "auteur": auteur, "source": "wikimedia_commons"}


def test_the_end_card_groups_by_licence_and_counts_the_free_ones():
    credits = ([_credit("CC BY-SA 3.0", f"Auteur {i}") for i in range(5)]
               + [_credit("CC BY 2.0", "Autre")]
               + [_credit("CC0", "Personne"), _credit("Public domain", "")])

    carton = timeline_mod.generique(credits, 30)

    assert [g["licence"] for g in carton["groupes"]] == ["CC BY-SA 3.0", "CC BY 2.0"]
    assert carton["groupes"][0]["nombre"] == 5
    assert carton["libres"] == 2, "CC0 et domaine public n'obligent à rien"
    assert carton["groupes"][0]["fonds"] == ["Wikimedia Commons"], \
        "l'identifiant technique du fonds n'a rien à faire à l'écran"


def test_a_licence_notice_pasted_into_an_author_field_is_cut():
    """Le champ « auteur » de Wikimedia Commons est libre. Un contributeur y
    avait écrit quatre-vingt-dix mots de conditions d'utilisation, qui
    prenaient cinq lignes du carton à eux seuls."""
    tartine = ("This Photo was taken by Wolfgang Moroder. Feel free to use my "
               "photos, but please mention me as the author and send me a "
               "message. This image is not in the public domain.")
    carton = timeline_mod.generique([_credit("CC BY-SA 3.0", tartine)], 30)

    nom = carton["groupes"][0]["auteurs"][0]
    assert len(nom) <= 42 and "public domain" not in nom


def test_the_end_card_extends_the_film_rather_than_covering_it(script):
    """Sa durée entre dans `duree_frames` : sinon le rendu s'arrête avant
    lui, et la musique se tait au milieu des crédits."""
    alignment = align.estimate(script)
    shots = [_shot("B001", 0), _shot("B002", 1), _shot("B003", 2)]
    assets = {s.id: {"fichier": f"{s.id}.jpg", "credit": "A (CC BY 4.0)",
                     "licence": "CC BY 4.0", "auteur": "A",
                     "source": "wikimedia_commons"} for s in shots}

    timeline = timeline_mod.build(alignment, shots, assets)
    carton = timeline["generique"]
    dernier = timeline["clips"][-1]

    assert carton["debut_frame"] == dernier["debut_frame"] + dernier["duree_frames"]
    assert timeline["duree_frames"] == carton["debut_frame"] + carton["duree_frames"]
    assert timeline_mod.check(timeline) == []


def test_a_film_owing_nothing_gets_no_end_card(script):
    """Domaine public d'un bout à l'autre : rien à créditer, pas de carton."""
    alignment = align.estimate(script)
    shots = [_shot("B001", 0), _shot("B002", 1), _shot("B003", 2)]
    assets = {s.id: {"fichier": f"{s.id}.jpg"} for s in shots}

    timeline = timeline_mod.build(alignment, shots, assets)
    assert timeline.get("generique") is None


def test_timeline_is_contiguous_and_matches_alignment(script):
    alignment = align.estimate(script)
    shots = [_shot("B001", 0), _shot("B002", 1), _shot("B003", 2)]
    assets = {s.id: {"fichier": f"{s.id}.jpg"} for s in shots}

    timeline = timeline_mod.build(alignment, shots, assets)

    assert timeline_mod.check(timeline) == []
    assert timeline["clips"][0]["debut_frame"] == 0
    # The montage covers the narration end to end, breaths included.
    expected = round(alignment["duree_totale_s"] * timeline["fps"])
    assert abs(timeline["duree_frames"] - expected) <= 1


def test_weights_split_a_beat_proportionally(script):
    alignment = align.estimate(script)
    shots = [
        _shot("B001", 0, weight=3.0), _shot("B001", 1, "pan_left", weight=1.0),
        _shot("B002", 2), _shot("B003", 3),
    ]
    assets = {s.id: {"fichier": f"{s.id}.jpg"} for s in shots}
    clips = timeline_mod.build(alignment, shots, assets)["clips"]

    first, second = clips[0]["duree_frames"], clips[1]["duree_frames"]
    assert first / second == pytest.approx(3.0, rel=0.05)


def test_uncovered_beat_is_refused(tmp_path: Path, script):
    path = tmp_path / "03-shots.json"
    path.write_text(
        '{"shots":[{"beat":"B001","type":"archive","requete":"q"}]}', encoding="utf-8"
    )
    with pytest.raises(ShotsError, match="sans plan visuel"):
        load_shots(path, [b.id for b in script.beats])


def test_unknown_movement_is_refused(tmp_path: Path, script):
    path = tmp_path / "03-shots.json"
    path.write_text(
        '{"shots":[{"beat":"B001","type":"archive","requete":"q",'
        '"mouvement":"barrel_roll"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ShotsError, match="mouvement"):
        load_shots(path, [b.id for b in script.beats])


def test_movement_varies_between_shots(script):
    """Identical Ken Burns on every shot is what makes a montage look generated."""
    alignment = align.estimate(script)
    shots = [_shot("B001", 0), _shot("B002", 1), _shot("B003", 2)]
    assets = {s.id: {"fichier": f"{s.id}.jpg"} for s in shots}
    clips = timeline_mod.build(alignment, shots, assets)["clips"]

    scales = {(c["mouvement"]["debut"]["scale"], c["mouvement"]["fin"]["scale"])
              for c in clips}
    assert len(scales) == len(clips)


def test_free_licence_detection():
    from fresque.sources.base import is_free_licence

    assert is_free_licence("Public domain")
    assert is_free_licence("CC BY-SA 4.0")
    assert not is_free_licence("Fair use")
    assert not is_free_licence("All rights reserved")
    assert not is_free_licence(None)


# --- Archive sourcing --------------------------------------------------------
#
# The live API is unreachable from the environment this was written in, so the
# parsing and filtering are pinned against a recorded response instead. These
# cover the decisions that actually matter: what gets refused, and why.

import json  # noqa: E402

from fresque.sources.wikimedia import _to_candidates  # noqa: E402

FIXTURE = Path(__file__).with_name("fixtures_wikimedia.json")


def _candidates(limit: int = 10, min_width: int = 1280):
    pages = json.loads(FIXTURE.read_text(encoding="utf-8"))["query"]["pages"]
    return _to_candidates(pages, limit=limit, min_width=min_width)


def test_only_the_usable_candidate_survives():
    found = _candidates()
    assert [c.title for c in found] == ["RMS Titanic 3.jpg"]


def test_non_free_licence_is_refused():
    assert all("poster" not in c.title for c in _candidates())


def test_low_resolution_is_refused():
    assert all(c.width >= 1280 for c in _candidates())
    assert all("Tiny" not in c.title for c in _candidates())


def test_unsupported_format_is_refused():
    assert all(not c.title.endswith(".svg") for c in _candidates())


def test_metadata_is_stripped_of_markup():
    best = _candidates()[0]
    assert best.author == "F. G. O. Stuart"
    assert "<" not in best.credit()
    assert "RMS Titanic departing Southampton" in best.extra["description"]


def test_credit_line_names_work_author_and_licence():
    credit = _candidates()[0].credit()
    assert "RMS Titanic 3.jpg" in credit
    assert "F. G. O. Stuart" in credit
    assert "Public domain" in credit


def test_thumbnail_is_preferred_over_the_original():
    """The originals run to tens of megabytes; the 1920px rendering is enough."""
    assert _candidates()[0].file_url.endswith("1920px.jpg")


# --- Diagnostic --------------------------------------------------------------

from fresque.doctor import GROUPS, allowlist  # noqa: E402


def test_allowlist_collapses_download_subdomains():
    """archive.org serves files from ia######.us.archive.org, never one fixed
    host, so the allowlist has to carry the wildcard rather than the probe."""
    lines = allowlist(["archive.org", "ia800000.us.archive.org"]).splitlines()
    assert lines == ["archive.org", "*.us.archive.org"]


def test_allowlist_deduplicates():
    assert allowlist(["a.example", "a.example", "b.example"]).splitlines() == [
        "a.example", "b.example",
    ]


def test_every_group_probes_its_file_host_or_says_why_not():
    """A provider whose API is allowed but whose file host is not looks healthy
    here and then fails at download time. A single-host group must justify
    itself — Openverse is the real case: its files come from 52 providers."""
    for group in GROUPS:
        if len(group.hosts) == 1:
            assert group.fichiers_ailleurs, group.label


def test_gallica_is_not_probed_anymore():
    """Commercial reuse is paid and licensed even for public-domain works
    (loi 78-753). Probing it would suggest it is an option."""
    hosts = {h.name for g in GROUPS for h in g.hosts}
    assert not any("bnf" in h or "gallica" in h for h in hosts)


# --- Génération d'images -----------------------------------------------------

import base64 as _b64  # noqa: E402

from fresque import images as images_mod  # noqa: E402
from fresque.images import ImageError, _extract_image, build_prompt  # noqa: E402


def test_prompt_carries_the_art_direction():
    """One art direction across the whole video matters more than any single
    image, so it is prefixed mechanically rather than trusted to the skill."""
    shot = Shot(index=0, beat="B001", type="generated", prompt="Un couloir inondé")
    prompt = build_prompt(shot)
    assert "Un couloir inondé" in prompt
    assert "documentaire" in prompt.lower()
    assert prompt.endswith(".")


def test_the_template_decides_what_a_generated_image_looks_like():
    """Claude n'écrit que le sujet du plan. Le style vient du template.

    Le template collage n'avait aucun bloc `generation` : ses images
    sortaient donc en « photographie documentaire, grain argentique », au
    milieu de planches de papier découpé. C'est exactement le « cinq styles
    différents » contre lequel la config met en garde, et il était dans le
    projet.
    """
    from fresque import config

    shot = Shot(index=0, beat="B001", type="generated",
                prompt="un homme de dos devant un restaurant fermé")
    try:
        config.use_template("documentaire-collage")
        collage = build_prompt(shot)
        config.use_template("documentaire-historique")
        historique = build_prompt(shot)
    finally:
        config.use_template(None)

    assert "collage" in collage.lower() and "papier" in collage.lower()
    assert "argentique" in historique.lower()
    assert "argentique" not in collage.lower(), \
        "le template collage ne doit pas hériter du grain de pellicule"
    for prompt in (collage, historique):
        assert "un homme de dos devant un restaurant fermé" in prompt
        assert "sans aucun texte" in prompt, "les interdits suivent partout"


def test_a_template_without_an_art_direction_refuses_to_generate(monkeypatch):
    """Générer sans direction artistique coûte de l'argent pour produire
    une image qui ne ressemblera à aucune autre du film."""
    from fresque import images as images_mod

    monkeypatch.setattr(images_mod, "_art_direction", lambda: "")
    shot = Shot(index=0, beat="B001", type="generated", prompt="x")
    with pytest.raises(images_mod.PromptSansDirection):
        build_prompt(shot)


def test_image_is_extracted_from_inline_data():
    payload = {"candidates": [{"content": {"parts": [
        {"text": "voici"},
        {"inlineData": {"mimeType": "image/png", "data": _b64.b64encode(b"PNGDATA").decode()}},
    ]}}]}
    data, extension = _extract_image(payload)
    assert data == b"PNGDATA"
    assert extension == ".png"


def test_snake_case_inline_data_is_also_accepted():
    payload = {"candidates": [{"content": {"parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": _b64.b64encode(b"JPG").decode()}},
    ]}}]}
    assert _extract_image(payload)[1] == ".jpg"


def test_a_refusal_reports_the_api_reason():
    """A silent empty image is the worst failure mode: it looks like a bug in
    our code when the API actually refused the prompt."""
    payload = {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}
    with pytest.raises(ImageError, match="SAFETY"):
        _extract_image(payload)


def test_block_reason_is_reported_when_there_is_no_candidate():
    payload = {"candidates": [], "promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}}
    with pytest.raises(ImageError, match="PROHIBITED_CONTENT"):
        _extract_image(payload)


def test_missing_key_names_both_ways_to_supply_it(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ImageError, match="API credential"):
        images_mod.api_key()


def test_generation_refuses_to_exceed_the_budget_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(
        images_mod.config, "get",
        lambda *keys, default=None: 2 if keys[-1] == "max_images_par_projet" else default,
    )
    shots = [
        Shot(index=i, beat=f"B{i:03d}", type="generated", prompt="p") for i in range(3)
    ]
    with pytest.raises(ImageError, match="plafond"):
        images_mod.generate_all(shots, tmp_path)


# --- Quotas ------------------------------------------------------------------
#
# Pinned against the real 429 bodies the API returned on 2026-09-18. The
# minute/day distinction decides whether waiting helps, so it has to be read
# from the payload rather than guessed from the status code.

from fresque.images import QuotaExhausted, _raise_for_quota, quota_kind  # noqa: E402

DAY_QUOTA = {"error": {"code": 429, "details": [
    {"violations": [{
        "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
        "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
    }]},
]}}

MINUTE_QUOTA = {"error": {"code": 429, "details": [
    {"violations": [{
        "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_input_token_count",
        "quotaId": "GenerateContentInputTokensPerModelPerMinute-FreeTier",
    }]},
]}}


def test_daily_quota_is_recognised():
    kind, quota_id = quota_kind(DAY_QUOTA)
    assert kind == "day"
    assert "PerDay" in quota_id


def test_per_minute_quota_is_recognised():
    assert quota_kind(MINUTE_QUOTA)[0] == "minute"


def test_daily_quota_raises_the_non_retryable_error_and_names_the_fix():
    with pytest.raises(QuotaExhausted, match="facturation"):
        _raise_for_quota(DAY_QUOTA, "gemini-3.1-flash-image")


def test_per_minute_quota_is_not_treated_as_exhausted():
    """It clears on its own, so it must stay a plain ImageError the caller retries."""
    with pytest.raises(ImageError) as caught:
        _raise_for_quota(MINUTE_QUOTA, "m")
    assert not isinstance(caught.value, QuotaExhausted)


def test_unparseable_quota_body_does_not_crash():
    assert quota_kind({}) == ("inconnu", "")
    assert quota_kind({"error": {"details": [None, {"violations": []}]}}) == ("inconnu", "")


def test_exhausted_quota_stops_the_whole_run(monkeypatch, tmp_path):
    """Burning through ninety more shots to collect the same error wastes
    minutes and tells the user nothing new."""
    attempts = []

    def boom(shot, destination_dir, model=None, session=None, report=None):
        attempts.append(shot.id)
        raise QuotaExhausted("quota journalier épuisé")

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(images_mod, "generate", boom)
    shots = [Shot(index=i, beat=f"B{i:03d}", type="generated", prompt="p") for i in range(5)]

    assets, failures = images_mod.generate_all(shots, tmp_path, pause=0)
    assert assets == {}
    assert len(attempts) == 1
    assert len(failures) == 1


# --- Cadrage des archives ----------------------------------------------------

from fresque.sources.base import Candidate  # noqa: E402
from fresque.sources.wikimedia import _prefer_landscape, build_search, variants  # noqa: E402


def _cand(title: str, width: int, height: int) -> Candidate:
    return Candidate(
        provider="wikimedia_commons", title=title, page_url="", file_url="u",
        licence="Public domain", width=width, height=height, mime="image/jpeg",
    )


def test_landscape_candidates_come_first():
    """A 1920x2888 book scan shown in a 16:9 frame is a vertical slice of
    itself — exactly what the first real run produced."""
    ordered = _prefer_landscape([
        _cand("scan de livre", 1920, 2888),
        _cand("photographie", 1920, 1280),
    ])
    assert ordered[0].title == "photographie"


def test_portrait_is_kept_as_a_last_resort():
    only_portrait = [_cand("plaque verticale", 1920, 2560)]
    assert _prefer_landscape(only_portrait) == only_portrait


def test_relevance_order_is_preserved_within_a_group():
    ordered = _prefer_landscape([
        _cand("premier paysage", 1920, 1080),
        _cand("second paysage", 1920, 1200),
    ])
    assert [c.title for c in ordered] == ["premier paysage", "second paysage"]


def test_search_excludes_scanned_documents():
    built = build_search("Titanic boiler room", 1920)
    assert "filetype:bitmap" in built
    assert "filew:>1920" in built


def test_search_respects_an_explicit_filter():
    built = build_search("Titanic filemime:image/png", 1920)
    assert "filetype:bitmap" not in built


def test_variants_go_from_specific_to_loose():
    steps = variants("Titanic boiler room stokers 1912", 1920)
    assert steps[0] == ("Titanic boiler room stokers 1912", 1920)
    assert steps[-1][1] == 800
    assert len(steps) == len(set(steps))


# --- Lint du script ----------------------------------------------------------
#
# Chaque règle correspond à une consigne qui vivait en prose dans un skill,
# où rien ne la vérifiait. Le test prouve qu'elle est désormais contraignante.

from fresque import lint as lint_mod  # noqa: E402


def _script_from(body: str, tmp_path: Path) -> script_parser.Script:
    path = tmp_path / "02-script.md"
    path.write_text(f"# T\n\n## Acte I — A\n\n{body}\n", encoding="utf-8")
    return script_parser.parse(path)


def _beat(identifier: str, text: str) -> str:
    return f"### {identifier}\n> intention: x\n{text}\n"


def _rules_hit(violations) -> set[str]:
    return {v.rule for v in violations}


# --- Ce qui fait rester un spectateur ---------------------------------------
#
# Les boucles ouvertes et l'enchaînement `mais`/`donc` sont les deux seules
# mécaniques de rétention que le script porte. Aucune ne se lit dans le
# texte — un fait dont la cause manque et un fait ordinaire sont les mêmes
# mots. L'auteur les déclare dans le tableau de contrôle, et c'est ce
# tableau que ces tests vérifient.

PHRASE_LONGUE = ("Le contrat prévoyait un versement hebdomadaire calculé sur "
                 "les recettes brutes de chaque établissement franchisé. ")


def _corps(nombre: int, courte: bool = True) -> str:
    """Un script de `nombre` beats, chacun dans la fourchette de mots."""
    morceaux = []
    for index in range(1, nombre + 1):
        texte = PHRASE_LONGUE * 2
        if courte:
            texte += "Personne ne bouge. "
        texte += PHRASE_LONGUE
        morceaux.append(_beat(f"B{index:03d}", texte.strip()))
    return "".join(morceaux)


def _controle(lignes: list[str]) -> str:
    entete = "\n## Contrôle\n\n| beat | lien | boucle | relance |\n|---|---|---|---|\n"
    return entete + "\n".join(lignes) + "\n"


def _table_saine(nombre: int) -> list[str]:
    """Un tableau valide : tout enchaîné, une boucle qui tient tout le film."""
    lignes = [f"| B001 | — | ouvre L1 — pourquoi | hook |"]
    for index in range(2, nombre):
        lignes.append(f"| B{index:03d} | donc | | |")
    lignes.append(f"| B{nombre:03d} | donc | ferme L1 | résolution |")
    return lignes


def test_the_control_table_lands_in_the_beats_and_the_loops(tmp_path):
    """Le tableau est en fin de fichier pour que la narration reste nue au
    checkpoint. Il faut donc que le code sache le ranger."""
    script = _script_from(_corps(10) + _controle(_table_saine(10)), tmp_path)

    assert script.beats[0].lien == ""
    assert script.beats[1].lien == "donc"
    assert script.beats[0].relance == "hook"
    assert [b.nom for b in script.boucles] == ["L1"]
    assert script.boucles[0].ouvre == "B001"
    assert script.boucles[0].ferme == "B010"
    assert script.boucles[0].question == "pourquoi"


def test_a_beat_that_can_only_say_and_is_refused(tmp_path):
    """« et » n'est pas un lien : c'est l'aveu qu'on énumère."""
    table = _table_saine(10)
    table[3] = "| B004 | et | | |"
    with pytest.raises(script_parser.ScriptError, match="donc"):
        _script_from(_corps(10) + _controle(table), tmp_path)


def test_a_beat_without_a_link_is_blocking(tmp_path):
    table = _table_saine(10)
    table[3] = "| B004 | | | |"
    violations = lint_mod.check(_script_from(_corps(10) + _controle(table), tmp_path))
    faute = [v for v in violations if v.rule == "enchaînement"]
    assert faute and faute[0].beat == "B004" and faute[0].blocking


def test_a_script_with_no_control_table_says_it_once(tmp_path):
    """Quarante lignes « aucun lien déclaré » ne sont pas un diagnostic."""
    violations = lint_mod.check(_script_from(_corps(10), tmp_path))
    faute = [v for v in violations if v.rule == "enchaînement"]
    assert len(faute) == 1 and faute[0].beat == "—"
    assert "boucle" in _rules_hit(violations)


def test_a_loop_that_never_closes_is_blocking(tmp_path):
    """Une promesse non tenue se paie en commentaires."""
    table = _table_saine(10)
    table[-1] = "| B010 | donc | | |"
    violations = lint_mod.check(_script_from(_corps(10) + _controle(table), tmp_path))
    faute = [v for v in violations if v.rule == "boucle"]
    assert faute and "jamais fermée" in faute[0].message and faute[0].blocking


def test_a_loop_shorter_than_a_minute_and_a_half_is_not_a_loop(tmp_path):
    """En dessous, ce n'est pas une attente, c'est une phrase."""
    table = _table_saine(12)
    table[1] = "| B002 | donc | ouvre L2 — qui a signé | |"
    table[2] = "| B003 | donc | ferme L2 | |"
    violations = lint_mod.check(_script_from(_corps(12) + _controle(table), tmp_path))
    assert "boucle-courte" in _rules_hit(violations)


def test_closing_the_last_loop_too_early_is_where_viewers_leave(tmp_path):
    """Plus rien en suspens et du film devant : c'est le décrochage."""
    table = _table_saine(12)
    table[-1] = "| B012 | donc | | |"
    table[5] = "| B006 | donc | ferme L1 | |"
    violations = lint_mod.check(_script_from(_corps(12) + _controle(table), tmp_path))
    assert "boucle-vide" in _rules_hit(violations)


def test_a_two_minute_test_montage_is_not_asked_for_loops(tmp_path):
    """Un montage d'essai n'a pas de structure narrative à vérifier. Faire
    échouer son lint apprendrait surtout à passer outre."""
    violations = lint_mod.check(_script_from(_corps(4), tmp_path))
    assert "boucle" not in _rules_hit(violations)
    assert "enchaînement" not in _rules_hit(violations)


def test_a_stretch_without_a_single_short_sentence_is_flagged(tmp_path):
    """Un script entier en phrases de vingt mots respecte toutes les autres
    règles et sonne plat du début à la fin."""
    plat = lint_mod.check(_script_from(_corps(10, courte=False), tmp_path))
    aere = lint_mod.check(_script_from(_corps(10, courte=True), tmp_path))
    assert "souffle" in _rules_hit(plat)
    assert "souffle" not in _rules_hit(aere)


def test_retention_counts_from_the_last_declared_relance(tmp_path):
    """Une relance ne se reconnaît pas au texte : elle se déclare."""
    long = _beat("B001", "mot " * 160) + _beat("B002", "mot " * 160)
    assert "rétention" in _rules_hit(lint_mod.check(_script_from(long, tmp_path)))

    # Le même texte, coupé par une relance déclarée, ne déclenche plus rien.
    coupe = (
        _beat("B001", "mot " * 160)
        + "### B002\n> intention: x\n> relance: révélation\n"
        + "mot " * 160 + "\n"
    )
    assert "rétention" not in _rules_hit(lint_mod.check(_script_from(coupe, tmp_path)))


def test_a_hook_that_opens_on_a_question_is_caught(tmp_path):
    script = _script_from(
        _beat("B001", "Que se passe-t-il quand un président entre en prison ? "
                      + "mot " * 20),
        tmp_path,
    )
    assert "hook-question" in _rules_hit(lint_mod.check(script))


def test_a_hook_whose_first_sentence_runs_long_is_caught(tmp_path):
    longue = " ".join(["mot"] * 28) + ". Court."
    script = _script_from(_beat("B001", longue), tmp_path)
    assert "hook-phrase" in _rules_hit(lint_mod.check(script))


def test_a_hook_over_its_time_budget_is_caught(tmp_path):
    body = _beat("B001", "Court. " * 3 + "mot " * 120)
    script = _script_from(body, tmp_path)
    assert "hook-longueur" in _rules_hit(lint_mod.check(script))


def test_hour_written_in_digits_is_caught(tmp_path):
    script = _script_from(_beat("B001", "Il est 01h23 et " + "mot " * 30), tmp_path)
    assert "synthèse-heure" in _rules_hit(lint_mod.check(script))


def test_percent_sign_is_caught(tmp_path):
    script = _script_from(_beat("B001", "Environ 12% du navire. " + "mot " * 30), tmp_path)
    assert "synthèse-pourcentage" in _rules_hit(lint_mod.check(script))


def test_ellipsis_and_em_dash_are_caught(tmp_path):
    script = _script_from(_beat("B001", "Et puis... plus rien. " + "mot " * 30), tmp_path)
    assert "synthèse-suspension" in _rules_hit(lint_mod.check(script))


def test_unpunctuated_acronym_is_caught(tmp_path):
    script = _script_from(_beat("B001", "L'URSS a nié. " + "mot " * 30), tmp_path)
    hits = [v for v in lint_mod.check(script) if v.rule == "synthèse-acronyme"]
    assert hits and "URSS" in hits[0].message


def test_spoken_acronym_is_allowed(tmp_path):
    script = _script_from(_beat("B001", "L'OTAN a nié. " + "mot " * 30), tmp_path)
    assert "synthèse-acronyme" not in _rules_hit(lint_mod.check(script))


def test_channel_boilerplate_is_caught(tmp_path):
    script = _script_from(_beat("B001", "Abonnez-vous maintenant. " + "mot " * 30), tmp_path)
    assert "interdit" in _rules_hit(lint_mod.check(script))


def test_overlong_sentence_is_caught_with_its_excerpt(tmp_path):
    long_sentence = " ".join(f"mot{i}" for i in range(32)) + "."
    script = _script_from(_beat("B001", long_sentence), tmp_path)
    hits = [v for v in lint_mod.check(script) if v.rule == "longueur-phrase"]
    assert hits and hits[0].excerpt


def test_beat_too_long_is_caught(tmp_path):
    script = _script_from(_beat("B001", "mot " * 80), tmp_path)
    hits = [v for v in lint_mod.check(script) if v.rule == "longueur-beat"]
    assert hits and "maximum" in hits[0].message


def test_budget_is_a_warning_not_a_blocker(tmp_path):
    """La longueur est un arbitrage humain : on le signale, on ne bloque pas."""
    script = _script_from(_beat("B001", "mot " * 40), tmp_path)
    budget = [v for v in lint_mod.check(script) if v.rule == "budget"]
    assert budget and not budget[0].blocking


def test_a_clean_beat_raises_nothing_blocking(tmp_path):
    text = ("La coque s'ouvre sur trois cents pieds. Personne, sur la "
            "passerelle, ne comprend encore ce qui vient de se passer. "
            "Six ponts plus bas, les hommes continuent de pelleter.")
    script = _script_from(_beat("B001", text), tmp_path)
    blocking = [v for v in lint_mod.check(script) if v.blocking]
    assert blocking == [], blocking


def test_blocking_violations_are_listed_first(tmp_path):
    script = _script_from(_beat("B001", "Il est 01h23. " + "mot " * 30), tmp_path)
    found = lint_mod.check(script)
    assert found[0].blocking and not found[-1].blocking


# --- Templates ---------------------------------------------------------------
#
# Un template est une surcouche de données : il redéfinit registre, rythme,
# direction artistique et règles de lint sans qu'une ligne de code ou de
# composant Remotion change. Ces tests vérifient que la surcouche atteint
# bien chaque étage.

import yaml as _yaml  # noqa: E402

from fresque import config as config_mod  # noqa: E402


@pytest.fixture
def base_template(tmp_path, monkeypatch):
    """Un faux dépôt avec une config de base et deux templates."""
    (tmp_path / "templates").mkdir()
    (tmp_path / "fresque.config.yaml").write_text(_yaml.safe_dump({
        "controle": {"mots_par_beat": [25, 60], "interdits": ["a", "b"]},
        "montage": {"palette": {"fond": "#000", "sous_titre": "#fff"}, "fps": 30},
        "narration": {"mots_par_minute": 140},
    }), encoding="utf-8")
    (tmp_path / "templates" / "sobre.yaml").write_text(_yaml.safe_dump({
        "controle": {"mots_par_beat": [28, 65], "interdits": ["c"]},
        "montage": {"palette": {"fond": "#101010"}},
    }), encoding="utf-8")

    monkeypatch.setattr(config_mod, "repo_root", lambda start=None: tmp_path)
    config_mod.use_template(None)
    config_mod.load.cache_clear()
    yield tmp_path
    config_mod.use_template(None)
    config_mod.load.cache_clear()


def test_template_overlays_only_what_it_redefines(base_template):
    config_mod.use_template("sobre")
    assert config_mod.get("controle", "mots_par_beat") == [28, 65]
    # Non redéfini par le template : la valeur de base survit.
    assert config_mod.get("montage", "fps") == 30
    assert config_mod.get("narration", "mots_par_minute") == 140


def test_nested_mappings_merge_rather_than_replace(base_template):
    """Redéfinir `fond` ne doit pas effacer `sous_titre`."""
    config_mod.use_template("sobre")
    palette = config_mod.get("montage", "palette")
    assert palette["fond"] == "#101010"
    assert palette["sous_titre"] == "#fff"


def test_lists_replace_rather_than_append(base_template):
    """Redéfinir un ordre de sources signifie le remplacer, pas y ajouter."""
    config_mod.use_template("sobre")
    assert config_mod.get("controle", "interdits") == ["c"]


def test_selecting_no_template_restores_the_base(base_template):
    config_mod.use_template("sobre")
    config_mod.use_template(None)
    assert config_mod.get("controle", "mots_par_beat") == [25, 60]


def test_unknown_template_is_refused_and_names_the_known_ones(base_template):
    with pytest.raises(config_mod.TemplateError, match="sobre"):
        config_mod.use_template("inexistant")


def test_template_reaches_the_linter(base_template, tmp_path):
    """La preuve que la surcouche traverse jusqu'aux règles d'écriture :
    un beat de 26 mots passe en base et échoue sous le template."""
    body = "### B001\n> intention: x\n" + "mot " * 26 + "\n"
    path = tmp_path / "02-script.md"
    path.write_text(f"# T\n\n## Acte I — A\n\n{body}", encoding="utf-8")
    script = script_parser.parse(path)

    config_mod.use_template(None)
    assert not [v for v in lint_mod.check(script) if v.rule == "longueur-beat"]

    config_mod.use_template("sobre")
    assert [v for v in lint_mod.check(script) if v.rule == "longueur-beat"]


# --- Openverse ---------------------------------------------------------------
#
# Calé sur des réponses réelles de l'API, relevées le 2026-09-19. Le point
# important est la résolution : Openverse indexe une rendition, pas
# l'original, et ses métadonnées annoncent l'original.

from fresque.sources import openverse as ov  # noqa: E402

OV_RESULTS = [
    {   # Flickr : déclaré = servi, mais plafonné à 1024.
        "title": "Courtroom", "url": "https://live.staticflickr.com/x_b.jpg",
        "foreign_landing_url": "https://flickr.com/photos/x",
        "license": "by-sa", "license_version": "3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "creator": "Nitot", "source": "flickr", "filetype": "jpg",
        "width": 1024, "height": 683, "attribution": "\"Courtroom\" by Nitot…",
    },
    {   # Non commercial : refusé avant tout transfert.
        "title": "Interdit", "url": "https://example.org/nc.jpg",
        "license": "by-nc", "license_version": "4.0",
        "source": "flickr", "filetype": "jpg", "width": 4000, "height": 3000,
    },
    {   # Pas de dérivée : un mouvement Ken Burns en est une.
        "title": "Sans dérivée", "url": "https://example.org/nd.jpg",
        "license": "by-nd", "license_version": "4.0",
        "source": "flickr", "filetype": "jpg", "width": 4000, "height": 3000,
    },
    {   # Format non affichable.
        "title": "Vectoriel", "url": "https://example.org/x.svg",
        "license": "cc0", "license_version": "1.0",
        "source": "rawpixel", "filetype": "svg", "width": 4000, "height": 3000,
    },
    {   # Trop petit.
        "title": "Vignette", "url": "https://example.org/small.jpg",
        "license": "cc0", "license_version": "1.0",
        "source": "rawpixel", "filetype": "jpg", "width": 400, "height": 300,
    },
]


def test_only_commercially_usable_results_survive():
    found = ov._to_candidates(OV_RESULTS, limit=10, min_width=900)
    assert [c.title for c in found] == ["Courtroom"]


def test_non_derivative_licence_is_refused():
    """Un mouvement de caméra est une modification : CC BY-ND est inutilisable."""
    assert all("dérivée" not in c.title for c in ov._to_candidates(OV_RESULTS, 10, 900))


def test_licence_code_is_expanded_to_a_readable_label():
    assert ov._licence_label({"license": "by-sa", "license_version": "3.0"}) == "CC BY-SA 3.0"
    assert ov._licence_label({"license": "cc0", "license_version": "1.0"}) == "CC0 1.0"
    assert ov._licence_label({"license": "pdm", "license_version": "1.0"}) == "Public domain 1.0"
    assert ov._licence_label({}) == ""


def test_provider_is_recorded_down_to_the_collection():
    """« openverse » ne suffit pas : il faut savoir si c'est Flickr ou un musée."""
    found = ov._to_candidates(OV_RESULTS, limit=10, min_width=900)
    assert found[0].provider == "openverse:flickr"


def test_wikimedia_is_excluded_server_side():
    """On l'interroge déjà en direct, avec de meilleures vignettes."""
    assert ov.EXCLUDED_SOURCES == "wikimedia"


# --- Garde sur les réponses non-JSON ----------------------------------------

from fresque.sources.base import Throttle, expects_json, is_retryable, retry_delay  # noqa: E402


class _FakeResponse:
    def __init__(self, status=200, headers=None):
        self.status_code = status
        self.headers = headers or {}


def test_html_error_page_is_reported_as_such():
    """Library of Congress sert une page Cloudflare en 429 ; appeler .json()
    dessus lèverait une erreur de décodage qui ne dit rien du problème."""
    with pytest.raises(ValueError, match="non-JSON"):
        expects_json(_FakeResponse(429, {"Content-Type": "text/html"}))


def test_json_response_passes_the_guard():
    expects_json(_FakeResponse(200, {"Content-Type": "application/json"}))


def test_retry_after_is_honoured_when_sent():
    assert retry_delay(_FakeResponse(429, {"Retry-After": "7"}), 0, 1.0) == 7.0


def test_backoff_grows_when_no_retry_after():
    first = retry_delay(_FakeResponse(429), 0, 1.0)
    second = retry_delay(_FakeResponse(429), 1, 1.0)
    assert second > first


def test_retry_delay_is_capped():
    assert retry_delay(_FakeResponse(429, {"Retry-After": "9999"}), 0, 1.0) == 30.0


def test_only_429_and_server_errors_are_retried():
    assert is_retryable(429) and is_retryable(503)
    assert not is_retryable(404) and not is_retryable(200)


def test_throttle_spaces_successive_calls():
    import time
    throttle = Throttle(0.05)
    start = time.monotonic()
    for _ in range(3):
        throttle.wait()
    assert time.monotonic() - start >= 0.1


def test_non_commercial_and_no_derivative_licences_are_refused():
    """Régression. Un simple test de sous-chaîne lisait « cc by-nc 4.0 » comme
    contenant « cc by » et le laissait passer : le filtre a accepté du non
    commercial pendant toute la première moitié du projet."""
    from fresque.sources.base import is_free_licence as free
    assert not free("CC BY-NC 4.0")
    assert not free("CC BY-NC-SA 3.0")
    assert not free("CC BY-ND 4.0")
    assert not free("CC BY-NC-ND 4.0")
    assert not free("Creative Commons Non-Commercial")
    assert not free("CC BY-SA 3.0 NoDerivatives")
    # Et ce qui reste autorisé le reste.
    assert free("CC BY-SA 3.0")
    assert free("CC BY 4.0")
    assert free("CC0 1.0")
    assert free("Public domain")
    assert free("No restrictions")


# --- Motion graphics ---------------------------------------------------------
#
# La forme est validée au checkpoint du plan visuel, pas dans le moteur : un
# champ manquant doit arrêter le pipeline là, pas produire un panneau vide
# vingt minutes après le début d'un rendu.

def _shots_file(tmp_path, shots: list) -> Path:
    path = tmp_path / "03-shots.json"
    path.write_text(json.dumps({"shots": shots}), encoding="utf-8")
    return path


def _motion_shot(motion: dict | None) -> dict:
    return {"beat": "B001", "type": "motion", "motion": motion} if motion is not None \
        else {"beat": "B001", "type": "motion"}


def test_motion_without_object_is_refused(tmp_path):
    with pytest.raises(ShotsError, match="objet `motion`"):
        load_shots(_shots_file(tmp_path, [_motion_shot(None)]), ["B001"])


def test_unknown_motion_kind_is_refused_and_lists_the_known_ones(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({"kind": "hologramme"})])
    with pytest.raises(ShotsError, match="chronologie"):
        load_shots(path, ["B001"])


def test_citation_requires_its_source(tmp_path):
    """Une citation sans source, sur un sujet judiciaire, est inutilisable."""
    path = _shots_file(tmp_path, [_motion_shot({"kind": "citation", "texte": "x"})])
    with pytest.raises(ShotsError, match="source"):
        load_shots(path, ["B001"])


def test_chiffre_requires_a_label(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({"kind": "chiffre", "valeur": "20"})])
    with pytest.raises(ShotsError, match="libelle"):
        load_shots(path, ["B001"])


def test_a_single_dated_event_is_not_a_timeline(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "chronologie", "evenements": [{"date": "2024", "texte": "x"}],
    })])
    with pytest.raises(ShotsError, match="deux événements"):
        load_shots(path, ["B001"])


def test_too_many_events_are_refused_as_unreadable(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "chronologie",
        "evenements": [{"date": str(y), "texte": "x"} for y in range(2010, 2019)],
    })])
    with pytest.raises(ShotsError, match="illisible"):
        load_shots(path, ["B001"])


def test_event_without_a_date_is_refused(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "chronologie",
        "evenements": [{"date": "2024", "texte": "x"}, {"texte": "sans date"}],
    })])
    with pytest.raises(ShotsError, match=r"evenements\[1\]"):
        load_shots(path, ["B001"])


def test_a_well_formed_timeline_passes(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "chronologie", "titre": "Trois affaires",
        "evenements": [
            {"date": "déc. 2024", "texte": "Bismuth"},
            {"date": "sept. 2025", "texte": "Financement libyen"},
        ],
    })])
    shots = load_shots(path, ["B001"])
    assert shots[0].motion["kind"] == "chronologie"


def test_motion_clip_needs_no_image_in_the_timeline(tmp_path):
    """`check` signale un plan sans visuel — sauf un motion, qui se dessine."""
    body = "### B001\n> intention: x\n" + "mot " * 20 + "\n"
    script_path = tmp_path / "02-script.md"
    script_path.write_text(f"# T\n\n## Acte I — A\n\n{body}", encoding="utf-8")
    script = script_parser.parse(script_path)

    shot = Shot(index=0, beat="B001", type="motion",
                motion={"kind": "chiffre", "valeur": "20", "libelle": "jours"})
    timeline = timeline_mod.build(align.estimate(script), [shot], {})
    assert timeline_mod.check(timeline) == []


def _timeline_de(tmp_path, actes: list[tuple[str, list[str]]], shots: list[Shot],
                 **kwargs):
    """Build a timeline from a script described as [(acte, [beats])]."""
    lignes = ["# T", ""]
    numero = 1
    for titre, beats in actes:
        lignes += [f"## Acte {titre} — A", ""]
        for _ in beats:
            lignes += [f"### B{numero:03d}", "> intention: x", "mot " * 20, ""]
            numero += 1
    script_path = tmp_path / "02-script.md"
    script_path.write_text("\n".join(lignes), encoding="utf-8")
    script = script_parser.parse(script_path)
    return timeline_mod.build(align.estimate(script), shots, {}, **kwargs)


def test_transitions_follow_the_structure_of_the_story():
    """Le code choisit d'après la place du plan, pas au hasard ni à l'identique."""
    from fresque.timeline import _transition

    assert _transition(0, "B001", "I", None, "archive", None) == "ouverture"

    # Même beat, même acte : l'idée continue, la coupe est nue.
    precedent = {"beat": "B001", "acte": "I", "type": "archive"}
    assert _transition(1, "B001", "I", precedent, "archive", "archive") == "coupe"

    # Beat suivant : nouvelle idée.
    assert _transition(2, "B002", "I", precedent, "archive", "archive") == "flash"

    # Acte suivant : une respiration, qui prime sur le changement de beat.
    assert _transition(3, "B009", "II", precedent, "archive", "archive") == "fondu_noir"

    # Un panneau graphique est un autre médium qui arrive.
    assert _transition(4, "B001", "I", precedent, "motion", "archive") == "glisse"
    assert _transition(4, "B001", "I", {**precedent, "type": "motion"},
                       "archive", "motion") == "glisse"


def test_transition_sounds_lead_their_cut(tmp_path):
    """Le son précède la coupe : l'oreille annonce à l'oeil ce qui arrive."""
    shots = [
        Shot(index=0, beat="B001", type="archive", requete="x"),
        Shot(index=1, beat="B002", type="archive", requete="y"),
    ]
    timeline = _timeline_de(tmp_path, [("I", ["B001", "B002"])], shots,
                            sons_dir="04-audio/sons")

    sons = timeline["sons"]
    assert sons, "des transitions sonores sont attendues"
    # L'ouverture est calée à zéro, faute de pouvoir démarrer avant le film.
    assert sons[0]["debut_frame"] == 0
    coupe = timeline["clips"][1]["debut_frame"]
    assert 0 < sons[1]["debut_frame"] < coupe

    # Aucun son n'est produit quand aucun dossier n'est fourni : la timeline
    # reste lisible par un moteur qui n'en veut pas.
    muet = _timeline_de(tmp_path, [("I", ["B001", "B002"])], shots)
    assert muet["sons"] == []


def test_every_transition_names_a_sound_that_exists(tmp_path):
    """Un nom de son inventé ne casserait qu'au rendu, une heure plus tard."""
    from fresque import sons as sons_mod
    from fresque.timeline import TRANSITIONS

    attendus = {n for n in TRANSITIONS.values() if n}
    assert attendus <= set(sons_mod.SONS)

    produits = sons_mod.build(tmp_path / "sons")
    assert attendus <= set(produits)

    # Idempotent : un fichier déjà là est conservé, sinon Remotion le
    # recopierait dans son bundle à chaque rendu.
    avant = (tmp_path / "sons" / "souffle.wav").stat().st_mtime_ns
    sons_mod.build(tmp_path / "sons")
    assert (tmp_path / "sons" / "souffle.wav").stat().st_mtime_ns == avant


def test_a_shot_held_too_long_is_reported(tmp_path):
    """Le plafond de durée est vérifié sur la timeline, donc sur l'audio réel.

    C'est le seul endroit où un montage lent peut être attrapé : le plan
    visuel ne connaît que des estimations."""
    body = "### B001\n> intention: x\n" + "mot " * 60 + "\n"
    script_path = tmp_path / "02-script.md"
    script_path.write_text(f"# T\n\n## Acte I — A\n\n{body}", encoding="utf-8")
    script = script_parser.parse(script_path)

    shot = Shot(index=0, beat="B001", type="motion",
                motion={"kind": "chiffre", "valeur": "20", "libelle": "jours"})
    timeline = timeline_mod.build(align.estimate(script), [shot], {})
    problems = timeline_mod.check(timeline)
    assert any("plan tenu" in p for p in problems)


def test_density_catches_a_beat_planned_with_too_few_shots(tmp_path):
    """Le même contrôle, mais au checkpoint : avant de payer les images."""
    from fresque.shots import density

    body = "### B001\n> intention: x\n" + "mot " * 60 + "\n"
    script_path = tmp_path / "02-script.md"
    script_path.write_text(f"# T\n\n## Acte I — A\n\n{body}", encoding="utf-8")
    beats = script_parser.parse(script_path).beats

    seul = [Shot(index=0, beat="B001", type="archive", requete="x")]
    assert density(seul, beats), "un plan pour soixante mots doit être signalé"

    # Le plan le plus lourd décide, pas la moyenne : découper sans corriger
    # les poids ne résout rien.
    desequilibre = [
        Shot(index=0, beat="B001", type="archive", requete="x", poids=1),
        Shot(index=1, beat="B001", type="archive", requete="y", poids=9),
    ]
    assert density(desequilibre, beats)


def test_a_run_of_identical_shots_is_refused():
    """Ce qui a produit le diaporama.

    Le premier film complet tenait quatorze archives d'affilée au même
    endroit. Le skill disait « varier les types ». Personne ne comptait,
    donc rien ne variait : le montage était conforme à toutes les règles
    écrites et visuellement mort.
    """
    from fresque.shots import variete

    suite = [Shot(index=i, beat=f"B{i // 3 + 1:03d}", type="archive",
                  requete="x") for i in range(30)]
    problemes = variete(suite)
    assert any("de suite" in p for p in problemes)
    assert any("%" in p for p in problemes), \
        "trente plans d'un seul type dépassent aussi la part maximale"


def test_variety_says_nothing_about_a_test_montage():
    """Un plan d'essai de trois images n'a pas de variété à tenir."""
    from fresque.shots import variete

    assert variete([Shot(index=i, beat="B001", type="archive", requete="x")
                    for i in range(3)]) == []


def test_an_act_without_a_single_panel_is_reported(tmp_path):
    """Un panneau graphique par acte : c'est ce qui coupe une suite
    d'images, et ce qui porte les chiffres de la recherche."""
    from fresque.shots import variete

    corps = "".join(
        f"### B{i:03d}\n> intention: x\n" + "mot " * 30 + "\n" for i in range(1, 6))
    chemin = tmp_path / "02-script.md"
    chemin.write_text(f"# T\n\n## Acte I — A\n\n{corps}", encoding="utf-8")
    beats = script_parser.parse(chemin).beats

    melange = []
    for i in range(24):
        melange.append(Shot(index=i, beat=f"B{i % 5 + 1:03d}",
                            type="archive" if i % 2 else "collage",
                            requete="x"))
    assert any("panneau" in p for p in variete(melange, beats))


def test_the_opening_shot_must_carry_a_hook_sentence():
    from fresque.shots import ouverture

    panneau = Shot(index=0, beat="B001", type="motion",
                   motion={"kind": "chiffre", "valeur": "20", "libelle": "j"})
    assert ouverture([panneau]), "ouvrir sur un panneau graphique est refusé"

    nu = Shot(index=0, beat="B001", type="archive", requete="x")
    assert ouverture([nu]), "un premier plan sans accroche est refusé"

    tenu = Shot(index=0, beat="B001", type="archive", requete="x",
                accroche="Il est entré en prison présumé innocent.")
    assert ouverture([tenu]) == []


def test_a_hook_sentence_longer_than_the_card_is_refused(tmp_path):
    path = _shots_file(tmp_path, [{
        "beat": "B001", "type": "archive", "requete": "x",
        "accroche": "mot " * 30,
    }])
    with pytest.raises(ShotsError, match="accroche"):
        load_shots(path, ["B001"])


def test_map_needs_named_markers_with_coordinates(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "carte", "marqueurs": [{"nom": "Paris"}],
    })])
    with pytest.raises(ShotsError, match="coord"):
        load_shots(path, ["B001"])


def test_map_coordinates_are_longitude_then_latitude(tmp_path):
    """Le piège classique : on lit « 48,85 / 2,35 » mais GeoJSON veut la
    longitude d'abord. Inversé, Paris tombe dans l'océan Indien — ou, ici,
    hors limites."""
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "carte", "marqueurs": [{"nom": "Paris", "coord": [48.85, 200.0]}],
    })])
    with pytest.raises(ShotsError, match="longitude, latitude"):
        load_shots(path, ["B001"])


def test_too_many_markers_are_refused(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "carte",
        "marqueurs": [{"nom": f"V{i}", "coord": [i, i]} for i in range(6)],
    })])
    with pytest.raises(ShotsError, match="chevauchent"):
        load_shots(path, ["B001"])


def test_a_well_formed_map_passes(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "carte", "titre": "Deux capitales",
        "marqueurs": [
            {"nom": "Paris", "coord": [2.35, 48.85]},
            {"nom": "Tripoli", "coord": [13.19, 32.89]},
        ],
        "relier": True, "pays": ["France", "Libya"],
    })])
    shots = load_shots(path, ["B001"])
    assert len(shots[0].motion["marqueurs"]) == 2


def test_front_page_requires_paper_date_and_headline(tmp_path):
    for manquant in ("journal", "date", "titre"):
        motion = {"kind": "journal", "journal": "Le Quotidien",
                  "date": "26 septembre 2025", "titre": "Titre"}
        del motion[manquant]
        path = _shots_file(tmp_path, [_motion_shot(motion)])
        with pytest.raises(ShotsError, match=manquant):
            load_shots(path, ["B001"])


# --- Métrage d'archive ------------------------------------------------------

from fresque.sources.loc import Clip as LocClip, _to_clips as loc_clips, point_de_depart  # noqa: E402

LOC_RESULTS = [
    {   # Utilisable.
        "title": "Charleston chain-gang", "date": "1902",
        "access_restricted": False,
        "resources": [{"video": "https://tile.loc.gov/a.mp4", "duration": 62,
                       "width": 1440, "height": 1080, "url": "https://loc.gov/a"}],
    },
    {   # Un long métrage, pas un plan.
        "title": "Court of human relations", "access_restricted": False,
        "resources": [{"video": "https://tile.loc.gov/b.mp4", "duration": 1628,
                       "width": 1440, "height": 1080}],
    },
    {   # Accès restreint : jamais sourcé.
        "title": "Restreint", "access_restricted": True,
        "resources": [{"video": "https://tile.loc.gov/c.mp4", "duration": 40,
                       "width": 1440, "height": 1080}],
    },
    {   # Définition trop basse.
        "title": "Basse def", "access_restricted": False,
        "resources": [{"video": "https://tile.loc.gov/d.mp4", "duration": 40,
                       "width": 640, "height": 480}],
    },
]


def test_only_short_unrestricted_hd_footage_is_kept():
    clips, vus, longs = loc_clips(LOC_RESULTS, collection="nsr", max_duree_s=420)
    assert [c.title for c in clips] == ["Charleston chain-gang"]
    assert longs == 1


def test_licence_is_declared_from_the_collection_not_the_item():
    """LOC ne publie aucun champ de licence exploitable : la confiance vient
    de la whitelist de collections, et doit se lire dans l'asset."""
    clips, _, _ = loc_clips(LOC_RESULTS, collection="national-screening-room",
                            max_duree_s=420)
    assert "Domaine public" in clips[0].licence
    assert "national-screening-room" in clips[0].licence


def test_rejected_for_length_is_counted_separately():
    """« rien trouvé » et « douze films trouvés, tous de vingt minutes »
    appellent des corrections différentes."""
    _, _, longs = loc_clips(LOC_RESULTS, collection="nsr", max_duree_s=30)
    assert longs == 2


def test_in_point_skips_the_leader():
    """Les films d'archive ouvrent sur des amorces et des cartons."""
    assert point_de_depart(100, 8, rang=0, saut_pct=0.1) == pytest.approx(10.0)


def test_successive_shots_from_one_film_start_at_different_points():
    """Sans cela, réutiliser un rush montre deux fois les mêmes secondes —
    pire que de ne pas le réutiliser."""
    departs = [point_de_depart(62, 8, rang=r, saut_pct=0.1) for r in range(4)]
    assert len(set(round(d, 1) for d in departs)) == 4


def test_in_point_never_runs_past_the_end():
    for duree in (10, 30, 62, 900):
        depart = point_de_depart(duree, 8, rang=3, saut_pct=0.1)
        assert 0 <= depart <= max(duree - 8, 0) + 1e-6


def test_video_shot_requires_a_query(tmp_path):
    path = _shots_file(tmp_path, [{"beat": "B001", "type": "video",
                                   "mouvement": "static"}])
    with pytest.raises(ShotsError, match="requete"):
        load_shots(path, ["B001"])


def test_video_shot_refuses_a_camera_move(tmp_path):
    """Le métrage bouge déjà : lui ajouter un travelling donne deux
    mouvements qui se contrarient."""
    path = _shots_file(tmp_path, [{"beat": "B001", "type": "video",
                                   "requete": "prison", "mouvement": "zoom_in"}])
    with pytest.raises(ShotsError, match="static"):
        load_shots(path, ["B001"])


def test_footage_reuse_keys_on_the_source_url():
    from fresque.rushes import _cle
    a = LocClip("loc:nsr", "A", "", "https://tile.loc.gov/a.mp4", "PD", 62, 1440, 1080, "nsr")
    b = LocClip("loc:nsr", "B", "", "https://tile.loc.gov/a.mp4", "PD", 62, 1440, 1080, "nsr")
    c = LocClip("loc:nsr", "C", "", "https://tile.loc.gov/z.mp4", "PD", 62, 1440, 1080, "nsr")
    assert _cle(a) == _cle(b) != _cle(c)


# --- Document d'archive ------------------------------------------------------

def test_document_requires_lines(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({"kind": "document"})])
    with pytest.raises(ShotsError, match="lignes"):
        load_shots(path, ["B001"])


def test_a_full_page_is_refused(tmp_path):
    """Un spectateur ne lit pas une page entière en huit secondes."""
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "document", "lignes": [f"ligne {i}" for i in range(9)],
    })])
    with pytest.raises(ShotsError, match="huit secondes"):
        load_shots(path, ["B001"])


def test_highlight_index_must_exist(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "document", "lignes": ["a", "b"], "surligne": 5,
    })])
    with pytest.raises(ShotsError, match="entre 0 et 1"):
        load_shots(path, ["B001"])


def test_unknown_handwriting_style_is_refused(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "document", "lignes": ["a"], "ecriture": "gothique",
    })])
    with pytest.raises(ShotsError, match="dactylographie"):
        load_shots(path, ["B001"])


def test_a_well_formed_document_passes(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "document", "ecriture": "officiel",
        "entete": "Tribunal correctionnel de Paris",
        "lignes": ["DÉCLARE coupable ;", "LE CONDAMNE à cinq années ;"],
        "surligne": 1,
    })])
    shots = load_shots(path, ["B001"])
    assert shots[0].motion["surligne"] == 1


def test_highlight_is_optional(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "document", "lignes": ["une seule ligne"],
    })])
    assert load_shots(path, ["B001"])[0].motion.get("surligne") is None


def test_every_motion_kind_is_dispatched_by_the_renderer():
    """Le pipeline valide des formes que le moteur doit savoir dessiner :
    si les deux listes divergent, un plan validé produit un panneau vide."""
    from fresque.shots import MOTION_FIELDS
    source = MOTEUR_TSX.read_text(encoding="utf-8")
    for kind in MOTION_FIELDS:
        assert f'case "{kind}":' in source, kind


def test_staging_exposes_every_media_the_timeline_references(tmp_path, monkeypatch):
    """Le rendu ne copie que ce qu'on lui liste. Oublier un type de média ne
    se voit qu'au tiers du rendu, quand le moteur réclame un fichier absent —
    c'est arrivé avec les rushes vidéo sur le premier documentaire complet."""
    from fresque import cli as cli_mod
    from fresque.project import Project

    racine = tmp_path / "projects" / "p"
    for rel in ("05-visuals/S000.jpg", "05-visuals/rushes/a.mp4", "04-audio/voix.wav"):
        chemin = racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(b"x")
    (racine / "06-timeline.json").write_text(json.dumps({
        "audio": "04-audio/voix.wav",
        "clips": [
            {"image": "05-visuals/S000.jpg", "video": None},
            {"image": None, "video": "05-visuals/rushes/a.mp4"},
            {"image": None, "video": None},
        ],
    }), encoding="utf-8")

    staging = cli_mod._stage_public_dir(Project(slug="p", root=racine))
    exposes = {str(f.relative_to(staging)) for f in staging.rglob("*") if f.is_file()}
    assert exposes == {
        "05-visuals/S000.jpg", "05-visuals/rushes/a.mp4", "04-audio/voix.wav",
    }


def test_two_shots_sharing_a_query_get_two_different_files(tmp_path):
    """À quinze plans la minute, un documentaire revient au même tribunal.

    Il ne doit pas en revenir avec la même photographie : c'est le signe le
    plus visible qu'un montage a épuisé sa matière."""
    from fresque import fetch as fetch_mod
    from fresque.sources.base import Candidate

    def _candidat(nom):
        return Candidate(
            provider="wikimedia_commons", title=nom, page_url=f"https://c/{nom}",
            file_url=f"https://c/{nom}.jpg", licence="CC BY-SA 4.0",
            licence_url="", author="a", width=2000, height=1200, mime="image/jpeg",
        )

    appels = []

    def faux_search(query, session):
        appels.append(query)
        return [_candidat("un"), _candidat("deux")], query, 1920

    def faux_download(candidate, destination):
        destination.write_bytes(b"\x00")

    monkey = {"wikimedia_commons": (faux_search, faux_download)}
    origine = fetch_mod.PROVIDERS
    fetch_mod.PROVIDERS = monkey
    try:
        shots = [
            Shot(index=0, beat="B001", type="archive", requete="palais de justice"),
            Shot(index=1, beat="B002", type="archive", requete="palais de justice"),
        ]
        assets, absents = fetch_mod.fetch_archives(
            shots, tmp_path / "05-visuals", cascade=("wikimedia_commons",),
            dry_run=True,
        )
    finally:
        fetch_mod.PROVIDERS = origine

    assert absents == []
    assert assets["S000"]["url"] != assets["S001"]["url"]
    # Et la recherche n'a été lancée qu'une fois pour les deux plans.
    assert appels == ["palais de justice"]


def test_relevance_requires_every_word_of_the_query():
    """Un seul mot commun était trop faible d'un ordre de grandeur.

    Chacun de ces cas est réel, relevé sur un plan visuel de cent
    soixante-seize plans où le filtre précédent les avait tous acceptés."""
    from fresque.sources.wikimedia import est_pertinent

    assert not est_pertinent("law court columns", "Inside the cast of Trajan's column")
    assert not est_pertinent("code penal France", "Speyer Kaiserdom 2010")
    assert not est_pertinent("prison window bars", "Museo di Via Tasso - first floor hall")
    assert not est_pertinent("cash banknotes", "Cash Cash - Club Sutra")
    assert not est_pertinent("Nicolas Sarkozy Elysee", "Camion canon à eau Police-CRS à Paris")

    # Et ce qui doit passer passe, pluriel et composé compris.
    assert est_pertinent("prison de la Santé", "Facade Nord de la prison de la Santé")
    assert est_pertinent("courthouse interior", "Bytom courthouse interior stairs")
    assert est_pertinent("law court columns", "Court of the Thousand Columns, law")


def _faux_fournisseur(titres, appels=None):
    """Un fournisseur d'archives en mémoire, pour tester la réutilisation."""
    from fresque.sources.base import Candidate

    def candidat(nom):
        return Candidate(
            provider="wikimedia_commons", title=nom, page_url=f"https://c/{nom}",
            file_url=f"https://c/{nom}.jpg", licence="CC BY-SA 4.0",
            licence_url="", author="a", width=2000, height=1200, mime="image/jpeg",
        )

    def search(query, session):
        if appels is not None:
            appels.append(query)
        return [candidat(t) for t in titres], query, 1920

    def download(candidate, destination):
        destination.write_bytes(b"\x00")

    return {"wikimedia_commons": (search, download)}


def test_an_image_comes_back_only_far_from_itself(tmp_path, monkeypatch):
    """Les fonds libres sont finis : refuser toute reprise laisserait un
    tiers du montage sans visuel. Ce qui la rend acceptable, c'est la
    distance — jamais dans le même beat, jamais trop tôt."""
    from fresque import config as config_mod, fetch as fetch_mod

    vrai_get = config_mod.get

    def get_court(*cles, default=None):
        if cles[-1] == "ecart_min_plans":
            return 3
        return vrai_get(*cles, default=default)

    monkeypatch.setattr(fetch_mod.config, "get", get_court)

    origine = fetch_mod.PROVIDERS
    fetch_mod.PROVIDERS = _faux_fournisseur(["un"])
    try:
        # Un seul fichier disponible, six plans répartis sur six beats.
        shots = [
            Shot(index=i, beat=f"B{i:03d}", type="archive", requete="q")
            for i in range(6)
        ]
        assets, absents = fetch_mod.fetch_archives(
            shots, tmp_path / "05-visuals", cascade=("wikimedia_commons",),
            dry_run=True,
        )
    finally:
        fetch_mod.PROVIDERS = origine

    # Le premier plan prend le fichier ; les deux suivants sont trop proches
    # et restent sans image ; le quatrième est assez loin pour le reprendre —
    # et la reprise repousse d'autant la suivante.
    assert "S000" in assets
    assert absents == ["S001", "S002", "S004", "S005"]
    assert assets["S003"]["reutilise_de"] == "S000"
    # La reprise pointe le fichier déjà sur disque, sans second téléchargement.
    assert assets["S003"]["fichier"] == assets["S000"]["fichier"]


def test_two_shots_of_the_same_beat_never_share_an_image(tmp_path):
    from fresque import fetch as fetch_mod

    origine = fetch_mod.PROVIDERS
    fetch_mod.PROVIDERS = _faux_fournisseur(["un"])
    try:
        shots = [
            Shot(index=0, beat="B001", type="archive", requete="q"),
            Shot(index=1, beat="B001", type="archive", requete="q"),
        ]
        assets, absents = fetch_mod.fetch_archives(
            shots, tmp_path / "05-visuals", cascade=("wikimedia_commons",),
            dry_run=True,
        )
    finally:
        fetch_mod.PROVIDERS = origine

    assert list(assets) == ["S000"]
    assert absents == ["S001"]


def test_the_music_loop_joins_seamlessly():
    """La boucle tourne pendant un quart d'heure : un raccord audible
    deviendrait le seul événement de la bande."""
    import numpy as np

    from fresque import sons as sons_mod

    for mode in sons_mod.MODES:
        piste = sons_mod.musique(6.0, 55.0, mode)
        # Le raccord se mesure à la marche entre la dernière et la première
        # valeur : au-delà d'un millième de la pleine échelle, ça claque.
        assert abs(piste[0] - piste[-1]) < 0.01, mode
        assert np.abs(piste).max() <= 1.0


def test_each_mode_lands_on_its_own_interval():
    """Le mode est ce qui fait qu'un template ne sonne pas comme un autre."""
    import numpy as np

    from fresque import sons as sons_mod

    def pics(mode):
        x = sons_mod.musique(8.0, 55.0, mode)
        f = np.fft.rfftfreq(len(x), 1 / sons_mod.RATE)
        m = np.abs(np.fft.rfft(x))
        return {round(p) for p in f[np.argsort(m)[-6:]]}

    # Tierce mineure à 65 Hz pour « sombre », majeure à 69 pour « clair ».
    assert 65 in pics("sombre")
    assert 69 in pics("clair")
    assert 65 not in pics("sobre") and 69 not in pics("sobre")


def test_an_unknown_musical_mode_is_refused():
    from fresque import sons as sons_mod

    with pytest.raises(ValueError, match="mode musical"):
        sons_mod.musique(1.0, 55.0, "disco")


def test_template_overview_says_where_each_value_comes_from():
    """Un template dit ce qui change, jamais ce que ça donne. C'est
    précisément ce que cette vue répare."""
    from fresque import apercu as apercu_mod

    donnees = apercu_mod.resume("documentaire-historique")
    plat = {chemin: source
            for _, lignes in donnees["axes"] for chemin, _, source in lignes}

    assert plat["narration.mots_par_minute"] == "template"
    assert plat["montage.musique.source"] == "template"
    # Hérité : le template ne parle ni de résolution ni de fréquence d'images.
    assert plat["montage.fps"] == "base"


def test_template_page_is_static_and_self_contained(tmp_path):
    from fresque import apercu as apercu_mod

    sortie = apercu_mod.page("documentaire-historique", tmp_path / "t.html")
    page = sortie.read_text(encoding="utf-8")
    assert "<script" not in page, "la page doit être statique"
    # Autonome veut dire : rien à aller chercher au chargement. Une URL
    # citée dans le texte — le crédit d'une musique, par exemple — n'est
    # pas une ressource, c'est de l'information.
    for attribut in ('src="http', "src='http", 'href="http', "href='http",
                     "@import"):
        assert attribut not in page, attribut
    # Les couleurs du template y figurent comme pastilles.
    assert "#c9a227" in page


def test_a_project_can_override_its_template(tmp_path, monkeypatch):
    """Tester un montage sur deux minutes doit coûter une ligne dans le
    projet, pas une modification du template qu'on oubliera de défaire."""
    from fresque import config as config_mod
    from fresque.project import Project

    racine = tmp_path / "projects" / "essai"
    racine.mkdir(parents=True)
    (racine / "projet.yaml").write_text(
        "template: documentaire-historique\n"
        "reglages:\n  production:\n    duree_cible_min: 2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_mod, "repo_root", lambda *a, **k: tmp_path)
    # Le dépôt réel fournit la config de base et les templates.
    vrai = Path(__file__).resolve().parents[2]
    for nom in (config_mod.CONFIG_NAME,):
        (tmp_path / nom).write_text((vrai / nom).read_text(encoding="utf-8"),
                                    encoding="utf-8")
    (tmp_path / "templates").mkdir()
    for gabarit in (vrai / "templates").glob("*.yaml"):
        (tmp_path / "templates" / gabarit.name).write_text(
            gabarit.read_text(encoding="utf-8"), encoding="utf-8")

    # Ce test porte sur la surcouche, pas sur un réglage : figer la valeur du
    # template ici le ferait échouer chaque fois qu'on ajuste le débit, et
    # pour une raison qui n'a rien à voir avec ce qu'il vérifie.
    import yaml

    attendu = yaml.safe_load(
        (vrai / "templates" / "documentaire-historique.yaml").read_text(
            encoding="utf-8")
    )["narration"]["mots_par_minute"]

    try:
        Project.open("essai")
        # Le projet a le dernier mot…
        assert config_mod.get("production", "duree_cible_min") == 2
        # …sans écraser ce que le template dit par ailleurs.
        assert config_mod.get("narration", "mots_par_minute") == attendu
    finally:
        config_mod.use_project_overrides({})
        config_mod.use_template(None)


def test_the_bed_gain_is_measured_against_the_voice(tmp_path):
    """Un même gain est inaudible sur un bourdon à 49 Hz et envahissant sur
    un lit à 300. Il se mesure, il ne se règle pas."""
    import numpy as np

    from fresque import sons as sons_mod

    voix = tmp_path / "voix.wav"
    t = np.arange(int(sons_mod.RATE * 2)) / sons_mod.RATE
    # Une « voix » à 200 Hz, là où la pondération A ne retire presque rien.
    sons_mod._write(voix, 0.5 * np.sin(2 * np.pi * 200 * t), np)

    gains = {}
    for tonique in (49.0, 110.0):
        piste = sons_mod.build_musique(
            tmp_path / f"m{tonique:.0f}.wav", 4.0, tonique, "sombre", force=True)
        gains[tonique] = sons_mod.gain_pour(piste, voix, -24.0)

    # Plus le lit est grave, plus il faut de gain pour le même niveau perçu.
    assert gains[49.0] > gains[110.0] * 2
    # Et le rapport demandé est bien tenu.
    piste = tmp_path / "m110.wav"
    x, r = sons_mod.lire_wav(piste)
    v, vr = sons_mod.lire_wav(voix)
    obtenu = (sons_mod.niveau_pondere_a(x * gains[110.0], r)
              / sons_mod.niveau_pondere_a(v, vr))
    assert 20 * np.log10(obtenu) == pytest.approx(-24, abs=0.5)


def test_the_bed_lives_where_speakers_can_reproduce_it():
    """Deux réglages ont échoué faute de cette vérification.

    Un lit dont l'énergie vit sous 120 Hz est parfaitement mesurable et
    parfaitement inaudible : ni un haut-parleur d'ordinateur ni celui d'un
    téléphone ne descend là. Et il ne doit pas pour autant monter dans la
    zone d'intelligibilité de la parole, qu'il masquerait."""
    import numpy as np

    from fresque import config as config_mod, sons as sons_mod

    tonique = float(config_mod.get("montage", "musique", "tonique_hz", default=131))
    for mode in sons_mod.MODES:
        x = sons_mod.musique(8.0, tonique, mode)
        f = np.fft.rfftfreq(len(x), 1 / sons_mod.RATE)
        m = np.abs(np.fft.rfft(x))

        def part(lo, hi):
            return m[(f >= lo) & (f < hi)].sum() / m.sum()

        assert part(0, 120) < 0.10, f"{mode} : trop d'énergie sous 120 Hz"
        assert part(250, 900) > 0.25, f"{mode} : pas assez entre 250 et 900 Hz"
        assert part(900, 4000) < 0.15, f"{mode} : empiète sur la parole"


def test_a_downloaded_track_is_folded_into_a_seamless_loop(tmp_path):
    """Un enregistrement ne boucle pas tout seul : sa fin et son début n'ont
    aucune raison de se raccorder. Sans fondu croisé, une piste de cinquante
    secondes claque toutes les cinquante secondes."""
    import numpy as np
    import soundfile as sf

    from fresque import musiques as musiques_mod

    # Un morceau dont la fin ne raccorde pas du tout avec le début : une
    # rampe, qui part de -0,9 pour finir à +0,9. Un sinus ne ferait pas
    # l'affaire, il passe par zéro aux deux bouts et la marche s'y cache.
    rate = 44100
    rampe = np.linspace(-0.9, 0.9, rate * 10)
    brut = np.stack([rampe, rampe], axis=1)
    source = tmp_path / "source.wav"
    sf.write(str(source), brut, rate)

    avant = abs(brut[0, 0] - brut[-1, 0])
    boucle = musiques_mod.preparer_boucle(source, tmp_path / "loop.wav", 2.0, force=True)
    x, r = sf.read(str(boucle), always_2d=True)

    assert len(x) / r == pytest.approx(8.0, abs=0.01), "la boucle perd le fondu"
    assert abs(x[0, 0] - x[-1, 0]) < avant / 4
    assert np.abs(x).max() <= 1.0


def test_a_track_too_short_for_its_crossfade_is_refused(tmp_path):
    import numpy as np
    import soundfile as sf

    from fresque import musiques as musiques_mod

    sf.write(str(tmp_path / "court.wav"), np.zeros((4410, 2)), 44100)
    with pytest.raises(musiques_mod.MusiqueError, match="trop court"):
        musiques_mod.preparer_boucle(
            tmp_path / "court.wav", tmp_path / "l.wav", 4.0, force=True)


def test_a_non_commercial_track_is_refused():
    """Le filtre serveur porte sur la licence déclarée ; on le double."""
    from fresque.musiques import Piste

    def piste(licence):
        return Piste(titre="t", auteur="a", licence=licence, licence_url="",
                     page_url="p", fichier_url="f", duree_s=100.0,
                     source="s", credit="c")

    assert piste("CC BY 4.0").utilisable
    assert piste("CC0 1.0").utilisable
    assert not piste("CC BY-NC 4.0").utilisable
    assert not piste("CC BY-ND 4.0").utilisable
    assert not piste("Tous droits réservés").utilisable


def test_every_motion_kind_reaches_the_renderer():
    """Un `kind` validé par le pipeline mais absent du routeur ne se voit
    qu'au rendu, une heure plus tard, sous la forme d'un panneau vide."""
    from fresque.shots import MOTION_FIELDS

    source = MOTEUR_TSX.read_text(encoding="utf-8")
    for kind in MOTION_FIELDS:
        assert f'case "{kind}":' in source, kind


def test_a_table_row_must_match_its_columns(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "tableau",
        "colonnes": ["Chef", "Décision"],
        "lignes": [["Corruption passive", "Relaxé"], ["Association"]],
    })])
    with pytest.raises(ShotsError, match="cellules pour"):
        load_shots(path, ["B001"])


def test_a_proportion_larger_than_its_total_is_refused(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "proportion", "valeur": 2000, "total": 20, "libelle": "jours",
    })])
    with pytest.raises(ShotsError, match="n'est pas une"):
        load_shots(path, ["B001"])


def test_a_network_link_must_point_at_a_node(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "reseau",
        "noeuds": [{"nom": "A"}, {"nom": "B"}],
        "liens": [{"de": 0, "a": 7}],
    })])
    with pytest.raises(ShotsError, match="index de nœud"):
        load_shots(path, ["B001"])


def test_a_mockup_without_its_source_is_refused(tmp_path):
    """Même règle que le journal : fabriquer une page au nom d'un média réel
    sans dire d'où vient l'information est l'écart le plus grave possible."""
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "maquette", "site": "Mediapart", "titre": "Un document",
    })])
    with pytest.raises(ShotsError, match="source"):
        load_shots(path, ["B001"])


def test_a_bar_chart_with_one_series_is_refused(tmp_path):
    path = _shots_file(tmp_path, [_motion_shot({
        "kind": "barres", "series": [{"libelle": "requis", "valeur": 7}],
    })])
    with pytest.raises(ShotsError, match="deux séries"):
        load_shots(path, ["B001"])


def test_a_panel_inherits_the_texture_of_a_neighbouring_shot(script):
    """Un panneau sur fond noir plat se lit comme une diapositive posée à
    côté du film. L'image du plan voisin, floutée dessous, le rattache."""
    alignment = align.estimate(script)
    shots = [
        Shot(index=0, beat="B001", type="archive", requete="q"),
        Shot(index=1, beat="B002", type="motion",
             motion={"kind": "chiffre", "valeur": "5", "libelle": "ans"}),
        Shot(index=2, beat="B003", type="archive", requete="q"),
    ]
    assets = {"S000": {"fichier": "05-visuals/S000.jpg"},
              "S002": {"fichier": "05-visuals/S002.jpg"}}
    clips = timeline_mod.build(alignment, shots, assets)["clips"]

    assert clips[1]["fond_image"] == "05-visuals/S000.jpg"
    # Un plan photographique ne reçoit pas de texture : il EST l'image.
    assert clips[0]["fond_image"] is None


def test_a_panel_that_opens_the_film_borrows_the_shot_that_follows(script):
    """Sinon il s'ouvrirait sur du noir, faute de plan précédent."""
    alignment = align.estimate(script)
    shots = [
        Shot(index=0, beat="B001", type="motion",
             motion={"kind": "chiffre", "valeur": "5", "libelle": "ans"}),
        Shot(index=1, beat="B002", type="archive", requete="q"),
        Shot(index=2, beat="B003", type="archive", requete="q"),
    ]
    assets = {"S001": {"fichier": "05-visuals/S001.jpg"}}
    clips = timeline_mod.build(alignment, shots, assets)["clips"]
    assert clips[0]["fond_image"] == "05-visuals/S001.jpg"


def test_review_reports_what_nobody_would_look_for(tmp_path):
    """La page existe pour faire remonter ce qu'on ne va pas chercher :
    plans sans visuel, requêtes élargies, attributions dues."""
    from fresque.review import alertes

    shots = [
        Shot(index=0, beat="B001", type="archive", requete="q",
             intention="une façade"),
        Shot(index=1, beat="B002", type="archive", requete="r", intention="un mur"),
    ]
    assets = {
        "S001": {"fichier": "05-visuals/S001.jpg", "requete": "r",
                 "requete_effective": "r élargi", "requete_relachee": True,
                 "licence": "CC BY-SA 3.0", "credit": "un auteur", "titre": "t"},
    }
    textes = " ".join(t for _, t, _ in alertes(shots, assets, None))

    assert "sans visuel" in textes          # S000 n'a pas d'asset
    assert "élargies" in textes
    assert "crédit" in textes
    # Une licence CC0 ne crée aucune obligation, elle ne doit pas alerter.
    assets["S001"]["licence"] = "CC0 1.0"
    assert "crédit" not in " ".join(t for _, t, _ in alertes(shots, assets, None))


def test_review_is_a_projection_not_a_source(tmp_path):
    """Elle se régénère et n'écrit rien d'autre : aucun état ne doit vivre
    en dehors des fichiers du projet."""
    from fresque import review as review_mod
    from fresque.project import Project

    projet = Project.open("sarkozy-essai-2min")
    avant = {p.name for p in projet.root.iterdir()}
    sortie = review_mod.construire("sarkozy-essai-2min")
    apres = {p.name for p in projet.root.iterdir()}

    assert sortie.name == "review.html"
    assert apres - avant <= {"review.html"}
    page = sortie.read_text(encoding="utf-8")
    assert "<script" not in page, "la page doit être statique"


# --- Les pistes --------------------------------------------------------------
#
# `pistes.md` est écrit par Claude et lu par le code. C'est la seule
# frontière où une sortie de modèle devient une interface cliquable : ce
# qui est vérifié ici, c'est qu'elle ne passe pas à moitié remplie.

PISTES_TYPE = """# Pistes — La faillite de Subway

> 17 recherches · 2026-09-21

## Piste 1 — La redevance sur les recettes

- **angle** : Le contrat payait le siège sur le chiffre d'affaires.
- **pivot** : Ce n'était pas une croissance ratée, c'était un modèle.
- **risque** : Les documents varient d'une année à l'autre.

**Preuves**
1. Huit pour cent du chiffre d'affaires hebdomadaire — [FDD 2019](https://exemple.org/fdd)
2. Six mille cinq cents fermetures entre 2015 et 2021 — [Rapport](https://exemple.org/r)
3. Aucune clause de protection territoriale — [FDD 2019](https://exemple.org/fdd)

**Titres**
- Pourquoi Subway a fermé 6 500 restaurants — preuve 2
- 8 % sur tout ce que vous vendez, bénéfice ou pas — preuve 1
"""


def test_a_piste_keeps_its_source_out_of_its_text():
    """La carte affiche le fait d'un côté et le lien de l'autre. Laisser le
    markdown du lien dans le texte donnait « … — [FDD 2019](https://… ) »
    en clair au milieu de la phrase."""
    from fresque import pistes as pistes_mod

    catalogue = pistes_mod.analyser(PISTES_TYPE)
    preuve = catalogue["pistes"][0]["preuves"][0]

    assert preuve["texte"] == "Huit pour cent du chiffre d'affaires hebdomadaire"
    assert preuve["url"] == "https://exemple.org/fdd"
    assert preuve["source"] == "FDD 2019"
    assert catalogue["sujet"] == "La faillite de Subway"


def test_the_most_aggressive_title_is_the_last_one():
    """Le format classe les titres du plus sobre au plus agressif. C'est
    ce qui permet à l'interface de mettre le dernier en grand sans demander
    à un modèle lequel est lequel."""
    from fresque import pistes as pistes_mod

    piste = pistes_mod.analyser(PISTES_TYPE)["pistes"][0]
    assert pistes_mod.choisie(piste) == "8 % sur tout ce que vous vendez, bénéfice ou pas"


def test_a_title_whose_proof_is_missing_is_refused():
    """« Un titre dont la preuve manque n'est pas proposé » est la règle du
    skill. Une règle qu'aucun code ne vérifie est une suggestion : un titre
    agressif sans rien dessous est exactement ce qu'on ne veut pas voir
    arriver jusqu'au navigateur."""
    from fresque import pistes as pistes_mod

    with pytest.raises(pistes_mod.PistesError, match="preuve 9"):
        pistes_mod.analyser(PISTES_TYPE.replace("— preuve 2", "— preuve 9"))


def test_a_piste_with_two_proofs_is_refused():
    from fresque import pistes as pistes_mod

    ampute = PISTES_TYPE.replace(
        "3. Aucune clause de protection territoriale — [FDD 2019](https://exemple.org/fdd)\n",
        "",
    )
    with pytest.raises(pistes_mod.PistesError, match="2 preuve"):
        pistes_mod.analyser(ampute)


def test_a_file_without_a_piste_says_so():
    """Claude peut écrire un fichier hors format. Mieux vaut une erreur
    nette qu'une page de cartes vides."""
    from fresque import pistes as pistes_mod

    with pytest.raises(pistes_mod.PistesError):
        pistes_mod.analyser("# Pistes — Subway\n\nJe n'ai rien trouvé.\n")


# --- Le serveur d'atelier ----------------------------------------------------
#
# Ce qui est vérifié ici n'est pas que les pages s'affichent — un coup d'œil
# le dit mieux — mais les deux propriétés qui rendent un serveur acceptable
# dans un projet dont le principe fondateur l'interdit : il ne lance que des
# commandes connues, et il ne garde aucun état qui ne soit dans un fichier.

def test_the_server_only_launches_commands_it_knows():
    """La liste des commandes est close. Rien de ce que le navigateur
    envoie ne devient un `argv` sans avoir été reconnu d'abord."""
    from fresque import serveur

    with pytest.raises(KeyError):
        serveur.lancer("sarkozy-essai-2min", "rm", {})
    with pytest.raises(FileNotFoundError):
        serveur.lancer("../../etc", "status", {})


def test_a_text_option_is_matched_before_it_reaches_an_argv():
    """Une option textuelle arrive du navigateur. Elle est confrontée à un
    motif, jamais concaténée : `0-450; rm -rf /` doit être refusé."""
    from fresque import serveur

    with pytest.raises(ValueError):
        serveur.lancer("sarkozy-essai-2min", "render", {"frames": "0-450; rm -rf /"})
    with pytest.raises(ValueError):
        serveur.lancer("sarkozy-essai-2min", "render", {"frames": "$(whoami)"})


def test_the_hook_is_heard_the_way_it_will_be_rendered(tmp_path, monkeypatch):
    """Écouter le hook n'a de valeur que si c'est le vrai hook.

    Une synthèse à part — le texte passé tel quel au moteur — donnerait un
    fichier sans les silences entre phrases, alors que le silence est la
    moitié du rythme. La commande passe donc par `_say_beat`, la fonction
    même de la passe voix.
    """
    import numpy as np

    from fresque import voice as voice_mod

    appels: list[str] = []

    class Faux(voice_mod.Moteur):
        nom = "faux"
        pause_naturelle_s = 0.0

        def dire(self, phrase: str):
            appels.append(phrase)
            return np.zeros(int(0.5 * voice_mod.SAMPLE_RATE), "float32"), \
                voice_mod.SAMPLE_RATE

        def fiche(self):
            return {"moteur": "faux"}

    monkeypatch.setattr(voice_mod, "moteur", Faux)
    samples, rate = voice_mod._say_beat(Faux(), "Une phrase. Puis une autre.", 0.45)

    assert appels == ["Une phrase.", "Puis une autre."], \
        "le beat doit être dit phrase par phrase"
    assert len(samples) / rate == pytest.approx(0.5 + 0.45 + 0.5, abs=0.01), \
        "le silence entre phrases doit être dans le fichier qu'on écoute"


def test_a_refused_visual_never_comes_back_for_the_same_shot(tmp_path):
    """Le bouton « Remplacer » sans registre de refus est un bouton qui ne
    fait rien : le second clic relance la même requête et retombe sur le
    même candidat."""
    from fresque import fetch as fetch_mod
    from fresque.sources.base import Candidate

    visuels = tmp_path / "05-visuals"
    fetch_mod.noter_rejet(
        visuels, "S002",
        {"url": "https://exemple.org/a", "titre": "Une façade"},
        "montre le décor, pas le sujet",
    )
    refuses = fetch_mod.lire_rejets(visuels)
    assert refuses == {"S002": {"https://exemple.org/a"}}

    def _candidat(url: str) -> Candidate:
        return Candidate(
            provider="wikimedia_commons", title="t", author="a",
            licence="CC BY 4.0", licence_url="", page_url=url,
            file_url=url, width=2000, height=1200, mime="image/jpeg",
        )

    neufs, _ = fetch_mod._eligibles(
        [_candidat("https://exemple.org/a"), _candidat("https://exemple.org/b")],
        {}, 0, 25, "B002", refuses["S002"],
    )
    assert [c.page_url for c in neufs] == ["https://exemple.org/b"]


def test_a_shot_name_from_the_browser_is_matched_before_it_reaches_an_argv():
    from fresque import serveur

    with pytest.raises(ValueError):
        serveur.remplacer("sarkozy-essai-2min", "S002; rm -rf /")


def test_a_beat_name_from_the_browser_is_matched_before_it_reaches_an_argv():
    """Le nom d'un beat arrive d'une requête. Il est confronté à un motif,
    comme toute option textuelle."""
    from fresque import serveur

    with pytest.raises(ValueError):
        serveur.dire_beat("sarkozy-essai-2min", "B001; rm -rf /")


def test_an_integer_option_does_not_reach_argparse_as_a_float():
    """Le numéro d'une piste arrive du navigateur comme texte. Converti en
    flottant, il donne `--piste 2.0`, et `argparse --piste type=int` refuse
    la commande : choisir une piste échouait sans rien dire d'utile."""
    from fresque import serveur

    argv = serveur._argv("recherche", "sarkozy-essai-2min", {"piste": "2"})
    assert argv[-2:] == ["--piste", "2"]


def test_every_step_claude_holds_writes_the_file_the_chain_waits_for():
    """Trois listes décrivent les mêmes étapes : les skills dans `claude`,
    les commandes lançables dans `serveur`, et les fichiers de la chaîne.
    Si elles divergent, un bouton lance un skill dont personne ne lit la
    sortie — et l'étape reste éternellement « pas encore écrite »."""
    from fresque import claude as claude_mod, serveur

    fichiers = {relatif for _, relatif in serveur.ETAPES}
    for nom, etape in claude_mod.ETAPES.items():
        assert nom in serveur.COMMANDES, f"{nom} n'est pas lançable"
        assert serveur.COMMANDES[nom].produit == etape.produit
        assert etape.produit in fichiers, f"{etape.produit} n'est pas dans la chaîne"
        skill = RACINE / ".claude" / "skills" / etape.skill / "SKILL.md"
        assert skill.is_file(), f"skill introuvable : {etape.skill}"


def test_a_run_interrupted_by_a_restart_is_not_a_success():
    """Une fiche restée sans code de sortie, sans processus vivant, signale
    un serveur arrêté en cours de commande. La confondre avec un succès
    ferait croire qu'une étape est faite alors qu'elle ne l'est pas."""
    from fresque import serveur

    assert serveur._issue({"code": 0}) == "ok"
    assert serveur._issue({"code": 2}) == "code 2"
    assert serveur._issue({"code": None, "vivant": True}) == "en cours"
    assert serveur._issue({"code": None, "vivant": False}) == "interrompu"


def test_the_thumbnail_is_the_opening_shot_not_the_first_file(tmp_path):
    """Prendre le premier fichier du dossier donnait la même vignette à
    trois projets, parce qu'une image réutilisée peut arriver en tête du
    tri. La vignette doit être le visuel du plan d'ouverture."""
    from fresque import serveur

    projet = tmp_path / "essai"
    (projet / "05-visuals").mkdir(parents=True)
    for nom in ("S000.jpg", "aaa-reutilisee.jpg"):
        (projet / "05-visuals" / nom).write_bytes(b"\xff\xd8\xff")
    (projet / "05-visuals" / "assets.json").write_text(json.dumps({"assets": {
        "S000": {"fichier": "05-visuals/S000.jpg"},
        "S001": {"fichier": "05-visuals/aaa-reutilisee.jpg"},
    }}), encoding="utf-8")

    assert serveur._vignette(projet) == "05-visuals/S000.jpg"


def test_the_workshop_page_holds_no_state_of_its_own():
    """L'atelier se lit à chaud. Rien n'y est mis en cache, et il ne dépend
    d'aucune ressource extérieure — comme `review.html`."""
    from fresque import serveur

    page = serveur.page_atelier()
    assert "http://" not in page and "https://" not in page, \
        "aucune ressource ne doit être chargée depuis l'extérieur"
    for projet in serveur.projets():
        assert not projet["slug"].startswith("."), \
            "un dossier caché n'est pas un projet"


def test_an_export_carries_no_path_off_the_machine_that_made_it(tmp_path):
    """Un export s'ouvre ailleurs, des années plus tard, hors ligne. Un
    chemin absolu ou une ressource distante l'en empêche."""
    import re

    from fresque import export as export_mod

    bilan = export_mod.exporter(tmp_path / "atelier")
    assert bilan.projets > 0 and bilan.fichiers > 0

    for page in (tmp_path / "atelier").rglob("*.html"):
        texte = page.read_text(encoding="utf-8")
        # On cherche ce qui est *chargé*, pas ce qui est *écrit* : une page
        # de template affiche l'URL de licence de sa musique en toutes
        # lettres, et cette attribution est obligatoire.
        for attribut in ('src="', 'href="'):
            for cible in re.findall(re.escape(attribut) + r'([^"]*)', texte):
                assert not cible.startswith(("http://", "https://", "file://")), \
                    f"{page.name} charge {cible} depuis l'extérieur"
                assert not cible.startswith("/"), \
                    f"{page.name} garde le chemin absolu {cible}"


def test_an_export_without_videos_says_so_rather_than_showing_a_broken_player(tmp_path):
    """Retirer le fichier sans retirer la balise laisserait un lecteur
    cassé, qu'on prendrait pour une panne plutôt que pour un choix."""
    from fresque import export as export_mod

    export_mod.exporter(tmp_path / "atelier", videos=False)
    page = (tmp_path / "atelier" / "p" / "sarkozy-essai-2min" / "review.html")
    texte = page.read_text(encoding="utf-8")

    assert "<video" not in texte
    assert "pas incluse" in texte


def test_export_images_are_reduced_to_the_width_they_are_shown_at(tmp_path):
    """Un projet de quinze minutes pèse 99 Mo de visuels pour une planche
    qui les affiche à 228 px. Les envoyer en pleine définition rendrait
    l'export inutilisable."""
    from PIL import Image

    from fresque import export as export_mod

    bilan = export_mod.exporter(tmp_path / "atelier", largeur=320)
    assert bilan.octets_export < bilan.octets_source

    for image in (tmp_path / "atelier").rglob("05-visuals/*.jpg"):
        with Image.open(image) as ouverte:
            assert ouverte.width <= 320, f"{image.name} n'a pas été réduite"


# --- Rythme du montage -------------------------------------------------------
#
# Deux propriétés qui viennent d'une mesure, pas d'un goût : voir
# `docs/analyse-frontier.md`. Elles se perdent au premier réglage changé
# sans y penser, d'où ces tests.

def test_camera_speed_does_not_depend_on_how_long_the_shot_lasts():
    """Le mouvement est une vitesse, pas une amplitude.

    L'ancien réglage parcourait 1,06 → 1,30 quelle que soit la durée : un
    plan de 6,5 s valait 3,5 %/s, mais le même réglage sur un plan de 2,4 s
    en valait 9,4. Accélérer le montage aurait donc transformé chaque plan
    en zoom avant brutal, sans qu'aucun réglage de zoom n'ait bougé.
    """
    from fresque.timeline import _movement

    shot = Shot(index=0, beat="B001", type="archive", requete="q",
                intention="i", mouvement="zoom_in")
    vitesses = []
    for duree in (1.5, 2.5, 3.5, 6.0, 10.0):
        mouvement = _movement(shot, duree)
        debut = mouvement["debut"]["scale"]
        fin = mouvement["fin"]["scale"]
        vitesses.append((fin / debut - 1) * 100 / duree)

    assert max(vitesses) - min(vitesses) < 0.05, \
        f"la vitesse varie avec la durée : {vitesses}"
    # Et elle reste dans la plage relevée sur les documentaires Frontier.
    assert 1.8 <= vitesses[0] <= 3.4, vitesses[0]


def test_a_long_shot_never_zooms_past_the_ceiling():
    """Une vitesse constante sur un plan très long finirait en gros plan."""
    from fresque import config as config_mod
    from fresque.timeline import _movement

    shot = Shot(index=0, beat="B001", type="archive", requete="q",
                intention="i", mouvement="zoom_in")
    plafond = float(config_mod.get("montage", "ken_burns", "zoom_max",
                                   default=1.18))
    assert _movement(shot, 120.0)["fin"]["scale"] <= plafond + 1e-6


def test_the_cut_only_style_leaves_nothing_but_cuts():
    """Sur vingt et une transitions relevées dans deux documentaires
    Frontier, toutes étaient des coupes d'une image. `style: coupe` retire
    le flash et la glisse — donc leurs souffles, qui n'existent pas non plus
    dans les échantillons mesurés.

    Le fondu au noir de changement d'acte survit : rien de ce qui a été
    mesuré ne dit de l'enlever.
    """
    from fresque.timeline import _transition

    precedent = {"beat": "B001", "acte": "I", "type": "archive"}
    # Changement de beat : un flash en style `effets`, rien en style `coupe`.
    assert _transition(2, "B002", "I", precedent, "archive", "archive") == "flash"
    assert _transition(2, "B002", "I", precedent, "archive", "archive",
                       "coupe") == "coupe"
    # Un panneau graphique ne glisse plus non plus.
    assert _transition(3, "B001", "I", precedent, "motion", "archive",
                       "coupe") == "coupe"
    # Mais l'acte qui tourne garde sa respiration.
    assert _transition(4, "B009", "II", precedent, "archive", "archive",
                       "coupe") == "fondu_noir"


def test_the_historical_template_cuts_hard_and_fast():
    """Le template porte le rythme mesuré, et c'est lui qu'on livre."""
    from fresque import apercu

    effectif = apercu.resume("documentaire-historique")["effectif"]
    montage = effectif["montage"]

    assert effectif["visuels"]["plans_par_minute"] >= 24
    assert montage["duree_plan_max_s"] <= 3.5
    assert montage["duree_panneau_max_s"] <= 5.5
    assert montage["transitions"]["style"] == "coupe"
    assert 2.0 <= montage["ken_burns"]["vitesse_pct_s"] <= 3.1, \
        "hors de la plage relevée chez Frontier"


# --- Narration : le silence compte ------------------------------------------

def _script(texte: str):
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(texte)
        chemin = Path(f.name)
    return script_parser.parse(chemin)


def test_the_word_budget_is_measured_in_time_not_in_words():
    """La cible est une durée. `mots_par_minute` est le débit PARLÉ, et les
    silences s'ajoutent par-dessus : multiplier l'un par l'autre sous-estime
    la durée dès qu'on laisse de l'air, et un script « dans le budget »
    dépasse sa cible d'un tiers.
    """
    from fresque import align as align_mod, config as config_mod, lint as lint_mod

    texte = "# Script — essai\n\n## Acte I — Ouverture\n\n"
    for i in range(1, 9):
        texte += (f"### B{i:03d}\n> intention: un plan\n"
                  "Une phrase courte. Puis une autre. Et encore une ici.\n\n")
    script = _script(texte)

    config_mod.use_template(None)
    config_mod.use_project_overrides({"production": {"duree_cible_min": 1}})
    try:
        plan = align_mod.estimate(script)
        parlee_s = script.word_count / float(
            config_mod.get("narration", "mots_par_minute")) * 60
        assert plan["duree_totale_s"] > parlee_s, \
            "les pauses doivent allonger la durée au-delà du temps parlé"

        message = " ".join(
            v.message for v in lint_mod.rule_word_budget(script, plan))
        assert "estimées" in message
        # La durée annoncée est celle du plan, pas un produit mots × débit.
        assert align_mod.format_duration(plan["duree_totale_s"]) in message
    finally:
        config_mod.use_project_overrides({})


def test_a_script_without_air_is_flagged():
    """Un beat fait d'une seule longue phrase ne respire nulle part, quelles
    que soient les pauses configurées : c'est la ponctuation qui les crée."""
    from fresque import align as align_mod, config as config_mod, lint as lint_mod

    entete = "# Script — essai\n\n## Acte I — Ouverture\n\n"
    dense = entete + "".join(
        f"### B{i:03d}\n> intention: un plan\n"
        "Une seule très longue phrase qui avance sans jamais reprendre son "
        "souffle et ne laisse donc aucun silence au montage\n\n"
        for i in range(1, 6))
    aere = entete + "".join(
        f"### B{i:03d}\n> intention: un plan\n"
        "Trois mots. Puis trois. Encore trois. Et fin.\n\n"
        for i in range(1, 6))

    config_mod.use_template(None)
    config_mod.use_project_overrides({"controle": {"part_silence_min": 0.25}})
    try:
        def part(script):
            return list(lint_mod.rule_air(script, align_mod.estimate(script)))

        assert part(_script(dense)), "un pavé sans ponctuation doit être signalé"
        assert not part(_script(aere)), "un script ponctué ne doit pas l'être"
    finally:
        config_mod.use_project_overrides({})


def test_the_voice_speed_matches_the_words_per_minute_it_claims():
    """`mots_par_minute` et `voix.kokoro.speed` disent la même chose à deux
    endroits : l'un sert à convertir mots <-> durée dans tout le pipeline,
    l'autre pilote le moteur. Les changer séparément fait dériver toutes les
    estimations de durée sans qu'aucun test ne tombe.

    La table vient d'une mesure sur un extrait réel du script Sarkozy avec
    la voix ff_siwis, la seule voix française de Kokoro v1.0.
    """
    from fresque import apercu

    MESURE = {0.62: 107, 0.69: 117, 0.75: 124, 0.82: 146, 0.95: 167}

    effectif = apercu.resume("documentaire-historique")["effectif"]
    vitesse = float(effectif["voix"]["kokoro"]["speed"])
    annonce = float(effectif["narration"]["mots_par_minute"])

    plus_proche = min(MESURE, key=lambda v: abs(v - vitesse))
    assert abs(plus_proche - vitesse) < 0.01, (
        f"speed {vitesse} n'est pas dans la table mesurée {sorted(MESURE)} — "
        "mesurer avant de changer")
    assert abs(MESURE[plus_proche] - annonce) <= 4, (
        f"speed {vitesse} produit {MESURE[plus_proche]} mots/min, "
        f"mais la config en annonce {annonce}")


def test_the_historical_template_speaks_slowly_and_leaves_air():
    from fresque import apercu

    effectif = apercu.resume("documentaire-historique")["effectif"]
    assert effectif["narration"]["mots_par_minute"] <= 130
    assert effectif["controle"]["mots_par_phrase_max"] <= 12
    assert effectif["controle"]["part_silence_min"] >= 0.20
    assert effectif["controle"]["mots_par_beat"][1] <= 20
    # Les pauses portent le rythme : elles doivent dépasser celles de la base.
    base = apercu._charger("documentaire-historique")[0]["narration"]
    for cle in ("pause_phrase_s", "pause_entre_beats_s"):
        assert effectif["narration"][cle] > base[cle], cle


def test_a_beat_is_spoken_sentence_by_sentence_with_real_silence():
    """Kokoro ne marque qu'un dixième de seconde après un point. Le silence
    qui porte le rythme est donc inséré par nous, entre les phrases — sinon
    `pause_phrase_s` ne servirait qu'à estimer, et jamais à produire.

    Le moteur est remplacé par un faux : ce qui est vérifié ici est le
    découpage et le silence, pas la synthèse.
    """
    import numpy as np

    from fresque import voice as voice_mod

    appels = []

    class FauxMoteur(voice_mod.Moteur):
        nom = "faux"
        pause_naturelle_s = 0.10

        def dire(self, phrase):
            appels.append(phrase)
            # Une seconde de « parole » par phrase, à amplitude non nulle.
            return np.ones(voice_mod.SAMPLE_RATE, dtype="float32"), voice_mod.SAMPLE_RATE

    machine = FauxMoteur()
    samples, rate = voice_mod._say_beat(
        machine, "Trois mots. Puis trois. Et fin.", 0.70)

    assert appels == ["Trois mots.", "Puis trois.", "Et fin."]
    # Trois secondes de parole, plus deux silences amputés de ce que le
    # moteur fournit déjà.
    attendu = 3 + 2 * (0.70 - machine.pause_naturelle_s)
    assert abs(len(samples) / rate - attendu) < 0.02
    assert (samples == 0).sum() > 0, "aucun silence n'a été inséré"


def test_a_single_sentence_beat_is_not_split():
    """Découper là où il n'y a rien à découper ferait payer un appel de plus
    au moteur, et changerait la prosodie sans raison."""
    import numpy as np

    from fresque import voice as voice_mod

    appels = []

    class FauxMoteur(voice_mod.Moteur):
        def dire(self, phrase):
            appels.append(phrase)
            return np.ones(100, dtype="float32"), voice_mod.SAMPLE_RATE

    texte = "Une seule phrase, avec une virgule."
    voice_mod._say_beat(FauxMoteur(), texte, 0.70)
    assert appels == [texte]


def test_edge_trims_the_silence_it_wraps_each_sentence_in():
    """Mesuré sur trois phrases courtes, Edge laisse 0,21 s avant et 0,92 s
    après — plus d'une seconde de vide par phrase. Sur les quatre cents
    phrases d'un quart d'heure, c'est plusieurs minutes de blanc que
    personne n'a demandées, et qu'aucun réglage ne rattrape ensuite."""
    import numpy as np

    from fresque import voice as voice_mod

    rate = voice_mod.SAMPLE_RATE
    parole = np.ones(rate, dtype="float32")          # une seconde
    avant = np.zeros(int(0.21 * rate), dtype="float32")
    apres = np.zeros(int(0.92 * rate), dtype="float32")

    rogne = voice_mod._rogner(np.concatenate([avant, parole, apres]), rate)

    marge = voice_mod._MARGE_ROGNAGE_S
    assert abs(len(rogne) / rate - (1 + 2 * marge)) < 0.01
    # La marge existe pour ne pas couper une occlusive initiale.
    assert marge > 0


def test_trimming_a_silent_take_returns_it_whole():
    """Rogner ce qui ne contient rien ne doit pas rendre un tableau vide :
    un beat muet vaut mieux qu'un beat de longueur nulle, qui décalerait
    tout le montage derrière lui."""
    import numpy as np

    from fresque import voice as voice_mod

    muet = np.zeros(1000, dtype="float32")
    assert len(voice_mod._rogner(muet, voice_mod.SAMPLE_RATE)) == 1000


def test_an_unknown_voice_provider_says_which_ones_exist():
    from fresque import config, voice as voice_mod

    config.use_project_overrides({"voix": {"provider": "festival"}})
    try:
        with pytest.raises(voice_mod.VoiceError) as erreur:
            voice_mod.moteur()
        message = str(erreur.value)
        for connu in ("edge", "kokoro", "elevenlabs"):
            assert connu in message
    finally:
        config.use_project_overrides(None)


# --- La bibliothèque de voix -------------------------------------------------
#
# Les trois fournisseurs décrivent leur catalogue de façon incompatible :
# deux lettres de préfixe chez Kokoro, du JSON Microsoft chez Edge, des
# étiquettes libres chez ElevenLabs. Ce qui est vérifié ici, c'est qu'ils
# en sortent tous sous la même forme — sans quoi l'interface aurait trois
# bibliothèques au lieu d'une.

def test_kokoro_reads_its_catalogue_without_loading_the_model(monkeypatch):
    """Lister les voix ne doit pas charger trois cent vingt-cinq
    mégaoctets d'ONNX : le fichier de voix est un npz, ses clés sont les
    noms, et les lire coûte onze millisecondes."""
    from fresque import voice as voice_mod

    def jamais():
        raise AssertionError("le modèle ONNX ne doit pas être chargé")

    monkeypatch.setattr(voice_mod, "_engine", jamais)
    catalogue = voice_mod.MoteurKokoro.catalogue()
    assert len(catalogue) > 40


def test_a_kokoro_voice_name_carries_its_language_and_gender():
    """`ff_siwis` est française et féminine. C'est la seule description que
    Kokoro donne de ses voix — il n'y a pas de catalogue ailleurs."""
    from fresque import voice as voice_mod

    par_id = {v.id: v for v in voice_mod.MoteurKokoro.catalogue()}
    siwis = par_id["ff_siwis"]
    assert (siwis.langue, siwis.genre, siwis.code_langue) == ("fr-FR", "femme", "fr")
    assert par_id["am_adam"].langue == "en-US"
    assert par_id["am_adam"].genre == "homme"


def test_the_library_filters_on_language_and_gender():
    from fresque.voice import Voix, filtrer

    catalogue = [
        Voix(id="a", nom="A", langue="fr-FR", genre="homme"),
        Voix(id="b", nom="B", langue="fr-CA", genre="femme"),
        Voix(id="c", nom="C", langue="en-US", genre="homme"),
    ]
    # « fr » retient les francophones, pas seulement la France : une voix
    # québécoise reste une voix française.
    assert [v.id for v in filtrer(catalogue, langue="fr")] == ["a", "b"]
    assert [v.id for v in filtrer(catalogue, genre="homme")] == ["a", "c"]
    assert [v.id for v in filtrer(catalogue, "fr", "homme")] == ["a"]
    assert len(filtrer(catalogue)) == 3


def test_elevenlabs_names_the_variable_that_holds_the_key_never_its_value(
        monkeypatch):
    """Une clé absente est un état normal d'installation, pas une panne.
    Le message dit où la poser — et ne peut pas divulguer ce qu'elle vaut,
    puisqu'il n'y en a pas."""
    from fresque import voice as voice_mod

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(voice_mod.VoiceError) as erreur:
        voice_mod.MoteurElevenLabs.catalogue()
    assert "ELEVENLABS_API_KEY" in str(erreur.value)


def test_a_voice_name_from_the_browser_is_matched_before_it_reaches_an_argv():
    from fresque import serveur

    with pytest.raises(ValueError):
        serveur.choisir_voix("sarkozy-essai-2min", "edge", "fr-FR; rm -rf /")
    with pytest.raises(ValueError):
        serveur.essayer_voix("sarkozy-essai-2min", "festival", "x")


# --- Alignement forcé --------------------------------------------------------
#
# Le modèle pèse 1,2 Go : ce qui est testé ici est tout ce qui l'entoure —
# la préparation du texte, et la règle qui décide qu'un mot est mal posé.

def test_french_numbers_are_spelled_the_way_the_voice_said_them():
    """L'aligneur ne connaît que `a-z`. Un nombre doit donc être écrit en
    lettres — et en français, pas en calquant l'anglais : il n'y a ni
    dizaine à 70 ni à 90."""
    from fresque.aligner import en_lettres

    assert en_lettres(16) == "seize"
    assert en_lettres(17) == "dix sept"
    assert en_lettres(21) == "vingt et un"
    assert en_lettres(71) == "soixante onze"
    assert en_lettres(80) == "quatre vingt"
    assert en_lettres(81) == "quatre vingt un"      # pas « quatre vingt et un »
    assert en_lettres(93) == "quatre vingt treize"
    assert en_lettres(99) == "quatre vingt dix neuf"
    assert en_lettres(1986) == "mille neuf cent quatre vingt six"
    assert en_lettres(2025) == "deux mille vingt cinq"


def test_a_number_becomes_several_alignment_tokens():
    """« 2025 » occupe quatre mots d'audio. Lui donner un seul jeton — ou un
    joker — jetterait presque une seconde de son."""
    from fresque.aligner import jetons

    assert jetons("2025") == ["deux", "mille", "vingt", "cinq"]
    assert jetons("l'exécution") == ["l'execution"]   # accents dépouillés
    assert jetons("après-midi") == ["apres", "midi"]
    assert jetons("Sarkozy") == ["sarkozy"]


def test_the_model_score_is_not_used_to_detect_errors():
    """Mesuré : « Le vingt-cinq septembre » écrit en toutes lettres score
    0,250 sur « vingt », aussi bas que la version en chiffres (0,278), alors
    que les deux sont parfaitement placées. Le modèle aligne des lettres, et
    le g et le t de « vingt » sont muets.

    Un seuil absolu signalait donc du français normal. Ce module ne doit
    plus en exposer un.
    """
    from fresque import aligner as aligner_mod

    assert not hasattr(aligner_mod, "SEUIL_CONFIANCE")
    assert aligner_mod.DUREE_MIN_S < 0.05
    bas, haut = aligner_mod.SECONDES_PAR_SYLLABE
    # La médiane relevée sur un montage réel, 0,14 s/syllabe, doit passer.
    assert bas < 0.14 < haut


def test_forced_alignment_refuses_an_estimate_it_cannot_trust():
    """`forced` promet des bornes de beat mesurées. Les prendre dans un
    alignement estimé rendrait cette promesse fausse sans rien dire."""
    from fresque.aligner import AlignError, bases_depuis

    with pytest.raises(AlignError, match="estimées"):
        bases_depuis({"source": "estimate", "beats": []})

    mesure = {"source": "mesure",
              "beats": [{"id": "B001", "debut_s": 0.0},
                        {"id": "B002", "debut_s": 4.25}]}
    assert bases_depuis(mesure) == {"B001": 0.0, "B002": 4.25}


# --- Sous-titres mot à mot ---------------------------------------------------

def _mots(paires):
    """(texte, début) -> des mots d'alignement, chacun long de 0,2 s."""
    return [{"t": t.strip(".,!?"), "tx": t, "debut_s": d, "fin_s": d + 0.2}
            for t, d in paires]


def test_a_subtitle_line_is_a_sentence():
    """Une ligne qui commence par les deux mots d'après le point fait lire le
    début d'une idée dont la suite n'est pas affichée. Vu au rendu :
    « cinq ans de prison. Il est »."""
    from fresque.timeline import _subtitle_lines

    mots = _mots([("Nicolas", 0.0), ("Sarkozy", 0.3), ("est", 0.6),
                  ("condamné.", 0.9), ("Il", 1.4), ("entre", 1.7),
                  ("en", 2.0), ("cellule.", 2.3)])
    lignes = [" ".join(m["tx"] for m in l) for l in _subtitle_lines(mots, 6)]

    assert lignes == ["Nicolas Sarkozy est condamné.", "Il entre en cellule."]
    for ligne in lignes:
        assert ". " not in ligne, f"{ligne!r} coupe une phrase"


def test_a_sentence_too_long_for_a_line_breaks_on_a_comma():
    from fresque.timeline import _subtitle_lines

    mots = _mots([("Le", 0.0), ("tribunal", 0.2), ("de", 0.4), ("Paris,", 0.6),
                  ("ce", 0.8), ("jour", 1.0), ("de", 1.2), ("septembre,", 1.4),
                  ("rend", 1.6), ("son", 1.8), ("jugement.", 2.0)])
    lignes = [" ".join(m["tx"] for m in l) for l in _subtitle_lines(mots, 4)]

    assert lignes[0] == "Le tribunal de Paris,"
    assert lignes[-1].endswith("jugement.")


def test_a_word_stays_highlighted_until_the_next_one_starts():
    """Sinon le surlignage s'éteint pendant la respiration entre deux mots,
    et le texte clignote. Ça règle aussi les mots avalés : l'aligneur pose
    « a » et « à » à une seule trame de 20 ms."""
    from fresque.timeline import _fenetres

    chunk = _mots([("a", 1.00), ("été", 1.02), ("condamné.", 1.40)])
    fenetres = _fenetres(chunk, fin_ligne=60, fps=30, plancher=3)

    # Jamais de trou : une fenêtre court au moins jusqu'au départ de la
    # suivante. Elle peut la dépasser un peu quand le plancher mord sur un
    # mot avalé — un chevauchement d'une ou deux images vaut mieux qu'un
    # surlignage invisible — mais jamais s'arrêter avant.
    for cette, suivante in zip(fenetres, fenetres[1:]):
        assert cette["fin_frame"] >= suivante["debut_frame"], "trou"
        depassement = cette["fin_frame"] - suivante["debut_frame"]
        assert depassement <= 3, f"chevauchement de {depassement} frames"
    # Le dernier mot tient jusqu'à la fin de la ligne.
    assert fenetres[-1]["fin_frame"] == 60
    # Et aucune fenêtre n'est trop courte pour être vue.
    for f in fenetres:
        assert f["fin_frame"] - f["debut_frame"] >= 3


def test_a_swallowed_word_still_gets_a_visible_window():
    """Un mot posé à une trame — mesuré sept fois sur trois cent dix-sept —
    doit quand même se surligner assez longtemps pour se voir."""
    from fresque.timeline import _fenetres

    chunk = _mots([("à", 2.000), ("la", 2.005), ("Santé.", 2.010)])
    fenetres = _fenetres(chunk, fin_ligne=200, fps=30, plancher=4)
    for f in fenetres:
        assert f["fin_frame"] - f["debut_frame"] >= 4


def test_only_artefact_gaps_between_lines_are_closed():
    """Le blanc entre deux phrases est voulu — c'est la pause que `voice`
    insère. Celui entre deux moitiés d'une même phrase est un artefact."""
    from fresque.timeline import _recoller

    lignes = [
        {"debut_frame": 0, "duree_frames": 10},    # trou de 5 -> artefact
        {"debut_frame": 15, "duree_frames": 10},   # trou de 40 -> vrai silence
        {"debut_frame": 65, "duree_frames": 10},
    ]
    recollees = _recoller(lignes, seuil_frames=21)

    assert recollees[0]["duree_frames"] == 15      # tient jusqu'à la suivante
    assert recollees[1]["duree_frames"] == 10      # le silence est gardé


def test_the_renderer_is_told_the_measured_colours():
    from fresque import apercu

    montage = apercu.resume("documentaire-historique")["effectif"]["montage"]
    assert montage["palette"]["sous_titre"].lower() == "#fafafa"
    assert montage["sous_titres"]["surlignage"]["couleur"].upper() == "#F5BC4D"
    assert montage["sous_titres"]["surlignage"]["actif"] is True
    assert montage["sous_titres"]["voile"] is False
    assert 90 <= montage["sous_titres"]["ligne_de_base_pct"] <= 92


# --- Surligneur calé sur la narration ---------------------------------------

def test_a_highlight_fires_when_the_voice_says_the_line():
    """Le balayage partait à un instant fixe après l'arrivée du panneau —
    1,2 s, quel que soit le texte. Il s'allumait donc rarement au moment où
    la voix disait la ligne. Le plan visuel déclare QUOI ; le code calcule
    QUAND, depuis `alignment.json`."""
    from fresque.timeline import _instant_de

    mots = [{"t": "Le", "debut_s": 26.28}, {"t": "tribunal", "debut_s": 26.44},
            {"t": "ordonne", "debut_s": 26.90}, {"t": "l'exécution", "debut_s": 27.30}]

    assert _instant_de("Le tribunal ordonne", mots) == 26.28
    assert _instant_de("tribunal ordonne", mots) == 26.44
    # Les accents et la casse ne doivent pas faire échouer un rapprochement.
    assert _instant_de("LE TRIBUNAL", mots) == 26.28
    # Introuvable -> None, jamais un instant inventé.
    assert _instant_de("la cour d'appel", mots) is None


def test_an_unresolved_highlight_is_reported_not_guessed():
    """Une phrase qui ne se retrouve pas est presque toujours une faute de
    frappe du plan visuel. On le dit au checkpoint."""
    from fresque.timeline import _motion_calee, check

    shot = Shot(index=5, beat="B003", type="motion", intention="i",
                motion={"kind": "document", "lignes": ["a"],
                        "surligne_a": "la cour d'appel"})
    beat = {"id": "B003", "mots": [{"t": "Le", "debut_s": 1.0}]}
    introuvables: list[str] = []

    motion = _motion_calee(shot, beat, debut_frame=0, fps=30,
                           introuvables=introuvables)
    assert "surligne_frame" not in motion
    assert introuvables and "S005" in introuvables[0]

    problemes = check({"clips": [], "fps": 30, "duree_frames": 0,
                       "surligne_introuvables": introuvables})
    assert any("surligne_a" in p for p in problemes)


def test_the_highlight_frame_is_relative_to_its_shot():
    """Une séquence Remotion compte à partir de zéro : la frame absolue de
    la narration doit être ramenée au début du plan."""
    from fresque.timeline import _motion_calee

    shot = Shot(index=5, beat="B003", type="motion", intention="i",
                motion={"kind": "document", "lignes": ["a"],
                        "surligne_a": "Le tribunal"})
    beat = {"id": "B003", "mots": [{"t": "Le", "debut_s": 26.28},
                                   {"t": "tribunal", "debut_s": 26.44}]}

    motion = _motion_calee(shot, beat, debut_frame=644, fps=30, introuvables=[])
    assert motion["surligne_frame"] == round(26.28 * 30) - 644


def test_a_highlight_cue_only_belongs_on_a_panel_that_can_use_it(tmp_path, script):
    from fresque.shots import ShotsError, load as load_shots

    def fichier(motion):
        chemin = tmp_path / f"s{abs(hash(str(motion)))}.json"
        chemin.write_text(json.dumps({"shots": [
            {"beat": b.id, "type": "motion", "intention": "i",
             "mouvement": "static", "motion": motion}
            for b in script.beats
        ]}, ensure_ascii=False), encoding="utf-8")
        return chemin

    ids = [b.id for b in script.beats]
    # Un chiffre n'a pas de ligne à surligner.
    with pytest.raises(ShotsError, match="surligne_a"):
        load_shots(fichier({"kind": "chiffre", "valeur": "5", "libelle": "ans",
                            "surligne_a": "Le tribunal"}), ids)
    # Un mot seul se retrouve trop souvent ailleurs dans le beat.
    with pytest.raises(ShotsError, match="deux mots"):
        load_shots(fichier({"kind": "document", "lignes": ["a"],
                            "surligne_a": "tribunal"}), ids)
    # Et un document correctement annoté passe.
    load_shots(fichier({"kind": "document", "lignes": ["a"],
                        "surligne_a": "Le tribunal"}), ids)


# --- Pexels ------------------------------------------------------------------

def test_a_stock_clip_is_credited_to_its_own_source():
    """`Clip.credit()` écrivait « Library of Congress » en dur. C'était vrai
    tant qu'il n'y avait qu'un fonds, et devenait un faux crédit au second."""
    from fresque.sources.loc import Clip

    stock = Clip(provider="pexels", title="Aerial view of central paris",
                 page_url="", file_url="", licence="Pexels License",
                 duree_s=12, width=1920, height=1080,
                 collection="stock contemporain", author="Florian Delée")
    archive = Clip(provider="loc", title="A trip to the moon", page_url="",
                   file_url="", licence="No known restrictions", duree_s=10,
                   width=640, height=480, collection="films")

    assert "Library of Congress" not in stock.credit()
    assert "Florian Delée" in stock.credit()
    assert "Library of Congress" in archive.credit()
    # La licence ne disparaît jamais, même quand le fonds porte le même nom.
    assert "Pexels License" in stock.credit()
    assert stock.credit().count("Pexels") == 1


def test_a_stock_title_too_long_is_shortened_in_the_credit():
    from fresque.sources.loc import Clip

    clip = Clip(provider="pexels", title="A stirring portrayal of justice " * 6,
                page_url="", file_url="", licence="Pexels License",
                duree_s=12, width=1920, height=1080, collection="stock")
    assert len(clip.credit().split(" — ")[0]) <= 90


def test_a_readable_title_is_derived_from_the_page_url():
    """Pexels ne renvoie aucun titre : `alt` est nul sur toutes les vidéos
    essayées. Sans le slug de l'URL, `review.html` afficherait dix fois la
    même requête et on ne distinguerait aucun plan."""
    from fresque.sources.pexels import _titre

    video = {"url": "https://www.pexels.com/video/aerial-view-of-central-"
                    "paris-skyline-38835028/", "alt": None}
    assert _titre(video, "défaut") == "Aerial view of central paris skyline"
    assert _titre({"url": ""}, "défaut") == "défaut"


def test_stock_footage_is_marked_and_surfaced_at_the_checkpoint():
    """Le code ne sait pas de quelle époque parle un beat. Il ne tranche donc
    pas entre archive et banque contemporaine — il marque, et la page de
    validation le montre. Sans ça, un plan tourné cette année passerait pour
    de l'archive sans que personne ne l'ait décidé."""
    from fresque.review import alertes

    shots = [Shot(index=0, beat="B001", type="video", requete="q",
                  intention="la façade du tribunal")]
    assets = {"S000": {"fichier": "05-visuals/rushes/a.mp4",
                       "titre": "Bashkia tirane municipality of tirana",
                       "source": "pexels", "licence": "Pexels License",
                       "nature": "stock contemporain"}}
    textes = " ".join(t for _, t, _ in alertes(shots, assets, None))
    assert "contemporaine" in textes

    assets["S000"]["nature"] = "films"
    assert "contemporaine" not in " ".join(
        t for _, t, _ in alertes(shots, assets, None))


# --- Planches de collage ------------------------------------------------------
#
# La mise en page est calculée par le pipeline et voyage dans la timeline :
# c'est ce qui la rend inspectable et corrigeable à la main. Ce qui se teste
# ici, ce sont donc les invariants de cette mise en page — pas le dessin, qui
# appartient au moteur.

from fresque import collage as collage_mod  # noqa: E402


#: Les coordonnées sont arrondies à quatre décimales avant d'entrer dans la
#: timeline, pour qu'elle reste lisible à l'œil nu. Recalculer une géométrie
#: à partir des valeurs arrondies décale donc de quelques 10⁻⁵. Un millième
#: de cadre vaut un pixel sur 1080 : la marge est large pour l'arrondi et
#: reste trop fine pour laisser passer une pièce qui dépasse vraiment.
ARRONDI = 1e-3


def _collage_shot(accroche: str = "") -> Shot:
    return Shot(index=7, beat="B001", type="collage", requete="q",
                accroche=accroche)


def test_collage_layout_is_deterministic():
    """Deux rendus du même plan doivent donner la même planche.

    C'est la contrepartie de la variation : sans elle, un re-rendu d'une
    seule séquence ne raccorderait pas avec le reste du film.
    """
    premier = collage_mod.compose(_collage_shot(), 1.5)
    second = collage_mod.compose(_collage_shot(), 1.5)
    assert premier == second


def test_two_shots_do_not_get_the_same_plate():
    """Une mise en page identique d'un plan à l'autre se lit comme un
    gabarit — exactement ce qu'on reproche aux vidéos générées."""
    a = collage_mod.compose(Shot(index=1, beat="B001", type="collage",
                                 requete="q"), 1.5)
    b = collage_mod.compose(Shot(index=2, beat="B001", type="collage",
                                 requete="q"), 1.5)
    assert a["pieces"][1]["x"] != b["pieces"][1]["x"]


def test_pieces_stay_inside_the_frame_once_rotated():
    """Borner une pièce sur sa hauteur nominale ne suffit pas.

    Une feuille large inclinée de quatre degrés lève un coin bien au-dessus
    de son bord haut. Relevé au rendu : le tampon rouge remontait dans la
    deuxième ligne de l'accroche alors que son centre respectait la bande.
    """
    for ratio in (0.6, 1.0, 1.5, 2.4):
        for index in range(40):
            shot = Shot(index=index, beat="B001", type="collage", requete="q")
            for piece in collage_mod.compose(shot, ratio)["pieces"]:
                demi = collage_mod._demi_hauteur(
                    piece["w"], piece["h"], piece["rotation_deg"])
                assert piece["y"] - demi >= -ARRONDI, (index, ratio, piece)
                assert piece["y"] + demi <= 1 + ARRONDI, (index, ratio, piece)


def test_the_title_band_is_left_clear():
    """L'accroche est composée par Remotion plutôt que cuite dans une image :
    accents français fiables, typographie du template, et un titre qu'un
    surligneur peut balayer. Encore faut-il qu'aucune pièce n'y monte."""
    for index in range(40):
        shot = Shot(index=index, beat="B001", type="collage", requete="q",
                    accroche="Condamné, et toujours présumé innocent")
        planche = collage_mod.compose(shot, 1.5)
        bande = planche["bande_titre"]
        assert bande > 0
        for piece in planche["pieces"]:
            demi = collage_mod._demi_hauteur(
                piece["w"], piece["h"], piece["rotation_deg"])
            assert piece["y"] - demi >= bande - ARRONDI, (index, piece)


def test_pieces_are_ordered_from_back_to_front():
    """L'ordre de la liste EST l'ordre de superposition. Le moteur ne trie
    rien, sans quoi une correction à la main dans `06-timeline.json` ne
    servirait à rien."""
    pieces = collage_mod.compose(_collage_shot(), 1.5)["pieces"]
    profondeurs = [p["profondeur"] for p in pieces]
    assert profondeurs == sorted(profondeurs)
    assert pieces[0]["role"] == "bloc"


def test_a_plate_never_repeats_an_accent_shape_before_using_the_others():
    """Un tirage indépendant par accent est uniforme et reste pourtant
    capable de poser trois demi-cercles sur la même planche — relevé sur
    S001. À l'œil, ça ne se lit pas comme du hasard mais comme une panne."""
    for index in range(60):
        shot = Shot(index=index, beat="B001", type="collage", requete="q")
        formes = [p["forme"] for p in collage_mod.compose(shot, 1.5)["pieces"]
                  if p["role"] == "accent"]
        assert len(formes) == len(set(formes)), (index, formes)


def test_collage_requires_a_query_like_an_archive(tmp_path):
    """Une planche se source comme une archive : c'est une photographie
    libre, et ce qui change vient après, au montage."""
    with pytest.raises(ShotsError, match="`collage` exige une `requete`"):
        load_shots(_shots_file(tmp_path, [{"beat": "B001", "type": "collage"}]),
                   ["B001"])


def test_collage_holds_the_screen_as_long_as_a_panel():
    """Une photographie se périme : passé quelques secondes le mouvement de
    caméra est le seul événement, et il ne dit rien. Une planche dont les
    pièces glissent à des vitesses différentes est toujours en train de dire
    quelque chose."""
    from fresque.shots import plafond_s

    assert plafond_s("collage") == plafond_s("motion")
    assert plafond_s("archive") <= plafond_s("collage")


# --- Vertex AI ----------------------------------------------------------------
#
# Une seule adresse, deux façons de présenter ses papiers. Il y a eu deux
# « modes » ici — `express` et `projet` — sur la supposition qu'une clé d'API
# ne pouvait pas porter de projet. Cinq sondes contre l'API réelle l'ont
# démentie (`docs/etude-vertex.md`), et la moitié de ces tests décrivait donc
# une architecture qui n'avait pas lieu d'être.
#
# Ce qui se teste ici : la couture entre `images.py` et Vertex, et le fait que
# le reste du module ne sache ni quel projet, ni quels papiers, ni quelle
# porte.

import time as _time  # noqa: E402

from fresque import vertex as vertex_mod  # noqa: E402


@pytest.fixture
def par_vertex(monkeypatch):
    """Bascule le fournisseur sans toucher au dépôt, et neutralise le jeton."""
    reel = images_mod.config.get

    def truque(*keys, default=None):
        if keys == ("visuels", "generation", "provider"):
            return "vertex"
        return reel(*keys, default=default)

    monkeypatch.setattr(images_mod.config, "get", truque)
    monkeypatch.setattr(vertex_mod, "jeton", lambda force=False: "JETON")
    monkeypatch.setenv("VERTEX_PROJECT", "mon-projet")
    # Sans clé : la fixture décrit une machine qui s'identifie par jeton. Une
    # clé laissée par un autre test changerait les en-têtes sous nos pieds.
    for nom in vertex_mod.NOMS_CLE:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(vertex_mod, "_cache", None)
    yield
    monkeypatch.setattr(vertex_mod, "_cache", None)


@pytest.fixture
def sans_papiers(monkeypatch):
    """Ni clé ni projet dans l'environnement, et rien qui traîne du test
    précédent."""
    for nom in (*vertex_mod.NOMS_CLE, "VERTEX_PROJECT",
                "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(vertex_mod, "_cache", None)


def test_the_global_region_has_no_host_prefix(monkeypatch):
    """`global` couvre le monde et s'adresse à l'hôte nu ; une région, non.
    Se tromper là-dessus donne un DNS qui ne résout pas, et le message ne dit
    pas que la région en est la cause."""
    monkeypatch.setattr(vertex_mod.config, "get",
                        lambda *k, default=None: "global")
    assert vertex_mod.racine() == "https://aiplatform.googleapis.com/v1"
    monkeypatch.setattr(vertex_mod.config, "get",
                        lambda *k, default=None: "europe-west4")
    assert vertex_mod.racine() == "https://europe-west4-aiplatform.googleapis.com/v1"


def test_the_project_comes_from_the_environment_never_from_the_repo(sans_papiers,
                                                                    monkeypatch):
    """`fresque.config.yaml` est versionné : un identifiant de compte n'y a
    pas sa place. Et son absence n'est pas une erreur — mesuré, l'adresse
    globale marche sans lui."""
    monkeypatch.setitem(sys.modules, "google.auth", None)
    assert vertex_mod.projet() is None

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "depuis-gcloud")
    assert vertex_mod.projet() == "depuis-gcloud"
    monkeypatch.setenv("VERTEX_PROJECT", "explicite")
    assert vertex_mod.projet() == "explicite"


def test_a_valid_token_is_not_fetched_again(monkeypatch):
    """Sur cent images, redemander un jeton à chaque appel ferait cent
    aller-retours pour rien — et ne jamais le redemander ferait échouer la
    soixantième."""
    appels = []

    def source():
        appels.append(1)
        return "T", _time.time() + 3600

    monkeypatch.setattr(vertex_mod, "_cache", None)
    monkeypatch.setattr(vertex_mod, "_par_bibliotheque", source)
    monkeypatch.setattr(vertex_mod, "_par_gcloud", lambda: None)

    assert vertex_mod.jeton() == "T"
    assert vertex_mod.jeton() == "T"
    assert len(appels) == 1

    # Un jeton dans la marge d'expiration est renouvelé plutôt que servi.
    monkeypatch.setattr(vertex_mod, "_cache", ("VIEUX", _time.time() + 10))
    assert vertex_mod.jeton() == "T"
    assert len(appels) == 2


def test_missing_credentials_name_both_remedies(monkeypatch):
    monkeypatch.setattr(vertex_mod, "_cache", None)
    monkeypatch.setattr(vertex_mod, "_par_bibliotheque", lambda: None)
    monkeypatch.setattr(vertex_mod, "_par_gcloud", lambda: None)
    with pytest.raises(vertex_mod.VertexError) as capture:
        vertex_mod.jeton()
    message = str(capture.value)
    assert "application-default login" in message
    assert "GOOGLE_APPLICATION_CREDENTIALS" in message


def test_without_a_key_the_token_is_used(par_vertex):
    acces = images_mod._acces("gemini-3.1-flash-image")
    assert acces.url == (
        "https://aiplatform.googleapis.com/v1/projects/mon-projet"
        "/locations/global/publishers/google/models"
        "/gemini-3.1-flash-image:generateContent"
    )
    assert acces.entetes["Authorization"] == "Bearer JETON"
    # Rien dans l'URL : un secret en paramètre est recopié par chaque journal
    # de proxy sur le trajet.
    assert acces.params == {}


def test_the_aspect_ratio_is_actually_sent(monkeypatch):
    """`visuels.generation.ratio` existait depuis le début et n'était jamais
    envoyé : le modèle rendait du carré pendant que la config annonçait 16:9,
    et le montage recadrait sans que personne ne l'ait décidé."""
    corps = images_mod._corps("un prompt", avec_image_config=True)
    assert corps["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    assert corps["contents"][0]["parts"][0]["text"] == "un prompt"

    nu = images_mod._corps("un prompt", avec_image_config=False)
    assert "imageConfig" not in nu["generationConfig"]


class _Reponse:
    def __init__(self, code, charge=None, texte=""):
        self.status_code = code
        self._charge = charge or {}
        self.text = texte
        self.content = b"x"

    def json(self):
        return self._charge


def _png(largeur: int = 32, hauteur: int = 18) -> bytes:
    """Un vrai PNG, pas trois octets.

    `images.generate()` mesure désormais le fichier qu'il vient d'écrire —
    un modèle peut ignorer la définition demandée sans le dire. Un faux
    contenu ne passe donc plus, et c'est tant mieux : le test exerce le même
    chemin que la production.
    """
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (largeur, hauteur), (12, 12, 12)).save(tampon, format="PNG")
    return tampon.getvalue()


def _reponse_image(largeur: int = 32, hauteur: int = 18):
    return _Reponse(200, {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png",
                        "data": _b64.b64encode(_png(largeur, hauteur)).decode()}}]}}]})


class _Session:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.envois = []

    def post(self, url, params=None, headers=None, json=None, timeout=None):
        self.envois.append({"url": url, "headers": headers or {}, "json": json})
        return self.reponses.pop(0)


def test_a_model_that_refuses_image_config_is_retried_without_it(par_vertex, tmp_path):
    """Tous les modèles ne l'acceptent pas, et l'API le dit en nommant le
    champ. Faire échouer le premier plan d'une série payante sur une option
    de confort serait une mauvaise affaire — mais le silence en serait une
    pire, donc on le signale."""
    session = _Session([
        _Reponse(400, texte='Unknown name "imageConfig" at generation_config'),
        _reponse_image(),
    ])
    dits: list[str] = []
    actif = images_mod.generate(
        Shot(index=0, beat="B001", type="generated", prompt="p"),
        tmp_path, session=session, report=dits.append)

    assert len(session.envois) == 2
    assert "imageConfig" in session.envois[0]["json"]["generationConfig"]
    assert "imageConfig" not in session.envois[1]["json"]["generationConfig"]
    assert any("imageConfig" in ligne for ligne in dits)
    assert actif["source"] == "vertex"
    assert (tmp_path / "S000.png").is_file()


def test_a_vertex_429_without_a_quota_id_is_waited_out(par_vertex, tmp_path, monkeypatch):
    """Vertex ne détaille pas ses quotas comme AI Studio : sa réponse ne porte
    pas de `quotaId`. Un 429 y est le plus souvent une saturation passagère,
    et l'échec sec d'AI Studio y serait le mauvais réflexe."""
    dodos: list[float] = []
    monkeypatch.setattr(images_mod.time, "sleep", dodos.append)
    session = _Session([_Reponse(429, {}), _reponse_image()])

    images_mod.generate(Shot(index=0, beat="B001", type="generated", prompt="p"),
                        tmp_path, session=session)
    assert len(session.envois) == 2
    assert dodos == [images_mod.BACKOFF_S]


def test_a_daily_quota_still_fails_loudly_on_vertex(par_vertex, tmp_path):
    """Un quota journalier ne se vide pas en attendant : attendre une heure
    dessus est la seule chose à ne pas faire."""
    charge = {"error": {"details": [
        {"violations": [{"quotaId": "GenerateContentPerDayPerProject"}]}]}}
    session = _Session([_Reponse(429, charge)])
    with pytest.raises(QuotaExhausted):
        images_mod.generate(Shot(index=0, beat="B001", type="generated", prompt="p"),
                            tmp_path, session=session)


def test_an_unknown_provider_is_refused_by_name(monkeypatch):
    monkeypatch.setattr(
        images_mod.config, "get",
        lambda *keys, default=None: "midjourney"
        if keys == ("visuels", "generation", "provider") else default)
    with pytest.raises(ImageError, match="midjourney"):
        images_mod.fournisseur()


def test_the_probe_paths_are_the_ones_the_api_actually_routes(sans_papiers,
                                                              monkeypatch):
    """Épinglé contre l'API réelle, sondée sans jeton le 2026-09-20.

    Deux formes que j'avais écrites de mémoire rendaient un 404 en HTML,
    c'est-à-dire une route inexistante qu'on aurait lue comme un modèle
    introuvable ou un projet fermé :

        v1/publishers/google/models                        → 404 HTML
        v1beta1/projects/p/locations/…/publishers/…/gemini → 404 HTML

    Ce qui répond 401 — donc ce qui existe et demande seulement un jeton :

        v1/projects/p/locations/global                     → 401 JSON
        v1beta1/publishers/google/models/gemini-…          → 401 JSON
        v1/projects/p/locations/global/…:generateContent   → 401 JSON (POST)

    La fiche d'un modèle n'est pas portée par le projet et n'existe qu'en
    `v1beta1` : les deux sont contre-intuitifs, et aucun test unitaire ne les
    aurait trouvés — seul un appel réel le pouvait.
    """
    hote = "https://aiplatform.googleapis.com"
    monkeypatch.setenv("VERTEX_PROJECT", "p")
    assert vertex_mod._url_region() == f"{hote}/v1/projects/p/locations/global"
    assert vertex_mod._url_fiche("gemini-3.1-flash-image") == (
        f"{hote}/v1beta1/publishers/google/models/gemini-3.1-flash-image")
    assert vertex_mod.url_modele("gemini-3.1-flash-image") == (
        f"{hote}/v1/projects/p/locations/global/publishers/google/models"
        "/gemini-3.1-flash-image:generateContent")


def test_a_refused_project_names_the_two_usual_causes(sans_papiers, monkeypatch):
    """Un 403 sur Vertex veut dire, neuf fois sur dix, que l'API n'est pas
    activée sur le projet ou que le compte n'a pas le rôle. Les nommer
    épargne une demi-heure dans la console."""
    monkeypatch.setenv("VERTEX_PROJECT", "p")
    monkeypatch.setattr(vertex_mod, "entetes", lambda: {})

    class _S:
        def get(self, url, headers=None, timeout=None):
            return _Reponse(403, texte="SERVICE_DISABLED")

    with pytest.raises(vertex_mod.VertexError) as capture:
        vertex_mod.modeles_image(_S())
    message = str(capture.value)
    assert "aiplatform.googleapis.com" in message
    assert "roles/aiplatform.user" in message


def test_model_sheets_are_probed_only_once_the_project_answered(sans_papiers,
                                                                monkeypatch):
    """Sonder quatre modèles alors que le jeton est mauvais rend quatre fois
    la même erreur, et aucune ne nomme la vraie cause."""
    monkeypatch.setenv("VERTEX_PROJECT", "p")
    monkeypatch.setattr(vertex_mod, "entetes", lambda: {})
    vus: list[str] = []

    class _S:
        def get(self, url, headers=None, timeout=None):
            vus.append(url)
            if "/locations/" in url:
                return _Reponse(200, {})
            return _Reponse(200 if "flash-lite" in url else 404, {})

    assert vertex_mod.modeles_image(_S()) == ["gemini-3.1-flash-lite-image"]
    assert vus[0].endswith("/projects/p/locations/global")
    assert len(vus) == 1 + len(vertex_mod.MODELES_CANDIDATS)


def test_a_key_travels_in_a_header_and_still_names_the_project(par_vertex, monkeypatch):
    """Mesuré : `projects/{id}/locations/global/...` rend 200 avec la seule
    clé, en paramètre comme en en-tête. C'est ce qui a supprimé la notion de
    mode — une clé porte un projet.

    L'en-tête est préféré au `?key=` : les deux rendent 200, mais un secret
    dans une URL est recopié par chaque journal de proxy sur le trajet."""
    monkeypatch.setenv("VERTEX_API_KEY", "CLE")

    acces = images_mod._acces("gemini-3.1-flash-image")
    assert acces.url == (
        "https://aiplatform.googleapis.com/v1/projects/mon-projet"
        "/locations/global/publishers/google/models"
        "/gemini-3.1-flash-image:generateContent")
    assert acces.entetes["x-goog-api-key"] == "CLE"
    assert "Authorization" not in acces.entetes
    assert acces.params == {}


def test_a_key_beats_an_ambient_token(par_vertex, monkeypatch):
    """L'explicite l'emporte sur l'ambiant : poser une clé dans
    l'environnement est un geste, alors qu'un jeton peut venir d'un `gcloud
    auth login` oublié ou du serveur de métadonnées d'une machine."""
    monkeypatch.setenv("GOOGLE_CLOUD_KEY", "CLE")
    entetes = vertex_mod.entetes()
    assert entetes["x-goog-api-key"] == "CLE"
    assert "Authorization" not in entetes


def test_without_a_project_the_global_address_is_used(sans_papiers, monkeypatch):
    """Mesuré : l'adresse globale rend 200 avec une clé — le serveur retrouve
    le projet depuis le justificatif. Ne pas connaître le projet n'est donc
    pas une erreur, et exiger `VERTEX_PROJECT` refuserait un appel qui marche."""
    monkeypatch.setenv("VERTEX_API_KEY", "CLE")
    assert vertex_mod.projet() is None
    assert vertex_mod.url_modele("gemini-3.1-flash-image") == (
        "https://aiplatform.googleapis.com/v1/publishers/google/models"
        "/gemini-3.1-flash-image:generateContent")


def test_the_state_never_shows_the_key(sans_papiers, monkeypatch):
    """`fresque images` imprime l'état avant de dépenser. Une clé recopiée là
    finirait dans `journal/`, qui est un fichier du projet."""
    monkeypatch.setenv("VERTEX_API_KEY", "SECRET-À-NE-PAS-ÉCRIRE")
    rendu = str(vertex_mod.etat())
    assert "SECRET" not in rendu
    # On nomme la variable qui la porte, ce qui est l'information utile
    # quand plusieurs noms sont acceptés.
    assert "VERTEX_API_KEY" in rendu


def test_the_key_is_accepted_under_the_names_people_actually_use(sans_papiers,
                                                                 monkeypatch):
    """Un nom qui ne correspond pas rendrait « clé absente » alors que la clé
    est là — le pire message possible, parce qu'il envoie la chercher du côté
    de Google. Relevé en vrai : la clé avait été nommée GOOGLE_CLOUD_KEY."""
    assert vertex_mod.cle() is None
    assert vertex_mod.porteur_de_cle() is None
    monkeypatch.setenv("GOOGLE_CLOUD_KEY", "CLE")
    assert vertex_mod.cle() == "CLE"
    assert vertex_mod.porteur_de_cle() == "GOOGLE_CLOUD_KEY"


def test_every_request_carries_a_role():
    """Épinglé contre le premier appel Vertex réel, le 2026-09-20.

    Sans `role`, la génération rend « Please use a valid role: user, model »
    en 400 — un message qui nomme les valeurs attendues et pas le champ
    manquant, donc difficile à rattacher à un `contents` sans rôle. AI Studio
    s'en passe, Vertex l'exige ; on l'émet pour les deux, parce qu'un corps
    unique est ce qui rend les deux portes interchangeables.
    """
    corps = images_mod._corps("un prompt", avec_image_config=True)
    assert corps["contents"][0]["role"] == "user"


def test_a_key_cannot_verify_anything_for_free(sans_papiers, monkeypatch):
    """Mesuré : la route des fiches de modèle rend 401 `CREDENTIALS_MISSING`
    avec une clé — elle n'accepte qu'un jeton OAuth. C'est une propriété de
    cette route, pas un défaut de la clé, et la conséquence mérite d'être
    dite plutôt que laissée à deviner : avec une clé, la seule vérification
    est une génération."""
    monkeypatch.setenv("VERTEX_API_KEY", "CLE")

    class _S:
        def get(self, url, headers=None, timeout=None):
            raise AssertionError("aucune sonde ne devrait partir")

    with pytest.raises(vertex_mod.VertexError) as capture:
        vertex_mod.modeles_image(_S())
    message = str(capture.value)
    assert "essai-image" in message
    assert "MODELES_CANDIDATS" not in message


def test_a_401_on_model_sheets_is_not_reported_as_a_stale_model_id(sans_papiers,
                                                                   monkeypatch):
    """Relevé au premier essai réel : quatre 401 étaient rendus comme « les
    identifiants de modèle ont peut-être changé ». Un 401 ne dit rien des
    identifiants — il dit que la requête n'est pas identifiée, et le message
    envoyait chercher au mauvais endroit."""
    monkeypatch.setattr(vertex_mod, "entetes", lambda: {})

    class _S:
        def get(self, url, headers=None, timeout=None):
            return _Reponse(401, texte="UNAUTHENTICATED")

    with pytest.raises(vertex_mod.VertexError) as capture:
        vertex_mod.modeles_image(_S())
    assert "MODELES_CANDIDATS" not in str(capture.value)


def test_a_404_on_model_sheets_still_points_at_the_identifiers(sans_papiers,
                                                               monkeypatch):
    """L'autre moitié de la distinction : une route qui répond mais ne
    connaît pas le modèle, c'est bien l'identifiant qui est en cause."""
    monkeypatch.setattr(vertex_mod, "entetes", lambda: {})

    class _S:
        def get(self, url, headers=None, timeout=None):
            return _Reponse(404, texte="NOT_FOUND")

    with pytest.raises(vertex_mod.VertexError, match="MODELES_CANDIDATS"):
        vertex_mod.modeles_image(_S())


def test_the_real_dimensions_are_recorded(par_vertex, tmp_path):
    """Un modèle peut ignorer la définition demandée sans le dire. Mesuré :
    `gemini-2.5-flash-image` rend 1344 px quand on lui demande du `2K`, sans
    erreur ni avertissement. Sans ce relevé, la dégradation ne se verrait
    qu'au montage — et le montage s'en sert aussi pour son `ratio`."""
    session = _Session([_reponse_image(2752, 1536)])
    asset = images_mod.generate(
        Shot(index=0, beat="B001", type="generated", prompt="p"),
        tmp_path, session=session)
    assert (asset["largeur"], asset["hauteur"]) == (2752, 1536)


def test_an_unnamed_400_names_the_size_as_the_likely_cause(par_vertex, tmp_path):
    """Mesuré le 2026-09-20 : `gemini-3.1-flash-lite-image` rend
    `400 · Request contains an invalid argument.` pour `2K` comme pour `4K`,
    et réussit cinq fois de suite en `1K`. Le corps ne nomme rien — il est
    identique à celui d'une requête malformée. Sans le témoin en `1K`, rien
    ne désignait la définition."""
    session = _Session([_Reponse(400, texte="Request contains an invalid argument.")])
    with pytest.raises(ImageError) as capture:
        images_mod.generate(Shot(index=0, beat="B001", type="generated", prompt="p"),
                            tmp_path, session=session)
    message = str(capture.value)
    assert "taille" in message
    assert "gemini-3.1-flash-image" in message
    # Un seul appel : on ne réessaie pas. Cent images au mauvais cadrage
    # coûtent plus qu'un échec net, et une définition refusée est une erreur
    # de réglage — elle échouerait de la même façon sur les cent.
    assert len(session.envois) == 1


import re  # noqa: E402

# --------------------------------------------------------------------------
# CLAUDE.md
#
# Le fichier est rechargé dans chaque session : une phrase fausse s'y applique
# à toutes. Il a déjà dérivé — un tableau de skills annonçait « à venir » un
# skill livré, et la section des rôles contredisait celle de l'alignement.
# Ces quatre tests sont à CLAUDE.md ce que
# `test_every_motion_kind_is_dispatched_by_the_renderer` est au moteur : ils
# ne jugent pas la prose, ils empêchent deux artefacts de diverger.
# --------------------------------------------------------------------------

#: Le fichier est reparti de zéro, une consigne à la fois. Le budget est haut
#: pour laisser la reconstruction se faire ; le resserrer quand elle sera finie.
BUDGET_MOTS_CLAUDE_MD = 1600

#: Les dossiers du dépôt qu'un chemin cité peut désigner. `projects/` en est
#: absent à dessein : il est ignoré par git, et son contenu varie.
RACINES_CITABLES = ("pipeline/", "docs/", "templates/", "remotion/",
                    ".claude/", "assets/")
FICHIERS_RACINE = {"README.md", "CLAUDE.md", "fresque.config.yaml",
                   ".env.example", "package.json"}
EXTENSIONS = (".py", ".md", ".json", ".yaml", ".tsx", ".ts", ".html")


def _claude_md() -> str:
    return (RACINE / "CLAUDE.md").read_text(encoding="utf-8")


def _codes_inline(texte: str) -> list[str]:
    """Les mots entre backticks, hors blocs clôturés.

    Les blocs sont exclus parce qu'ils portent l'arbre d'un projet, dont les
    chemins sont relatifs à `projects/<slug>/` et n'existent pas ici.
    """
    hors_blocs = re.sub(r"```.*?```", "", texte, flags=re.S)
    return [t for t in re.findall(r"`([^`\n]+)`", hors_blocs) if " " not in t]


def _section(texte: str, titre: str) -> str:
    """Le contenu d'une section, ou une chaîne vide si elle n'existe pas.

    Absente n'est pas une erreur : le fichier se reconstruit une consigne à
    la fois, et un test qui exige une section fige le plan du fichier.
    """
    bloc = re.search(rf"^## {re.escape(titre)}\n(.*?)(?=^## |\Z)",
                     texte, flags=re.S | re.M)
    return bloc.group(1) if bloc else ""


def test_claude_md_ne_cite_que_des_chemins_qui_existent():
    """Un renvoi vers un fichier disparu envoie la session dans le vide."""
    for token in _codes_inline(_claude_md()):
        if "<" in token:  # un gabarit, pas un chemin : `templates/<nom>.yaml`
            continue
        if token in FICHIERS_RACINE or token.startswith(RACINES_CITABLES):
            assert (RACINE / token).exists(), \
                f"CLAUDE.md cite `{token}`, qui n'existe pas"


def test_claude_md_ne_cite_que_des_commandes_qui_existent():
    """Le tableau des commandes est le doublon le plus exposé du fichier :
    il vieillit à chaque ajout au CLI, et personne ne le relit."""
    source = (RACINE / "pipeline" / "fresque" / "cli.py").read_text(encoding="utf-8")
    reelles = set(re.findall(r'\badd\(\s*"([a-z][a-z-]*)"', source))
    reelles |= set(re.findall(r'add_parser\(\s*\n?\s*"([a-z][a-z-]*)"', source))
    assert len(reelles) >= 15, "extraction des commandes cassée, pas le fichier"

    cites = {t for t in _codes_inline(_section(_claude_md(), "Commandes"))
             if re.fullmatch(r"[a-z][a-z-]*", t)}
    assert cites - reelles == set(), \
        f"CLAUDE.md cite des commandes absentes du CLI : {sorted(cites - reelles)}"


def test_claude_md_ne_cite_que_des_reglages_qui_existent():
    """Nommer un réglage mort — `budget.max_eur_par_projet` l'était en tant
    que garde-fou — fait croire à une protection qui n'existe pas."""
    import yaml

    config = yaml.safe_load((RACINE / "fresque.config.yaml").read_text(encoding="utf-8"))
    for token in _codes_inline(_claude_md()):
        if token.endswith(EXTENSIONS) or "/" in token or "<" in token:
            continue
        if not re.fullmatch(r"[a-z_]+(\.[a-z_]+)+", token):
            continue
        if token.startswith("fresque."):
            module = token.split(".", 1)[1]
            assert Path(f"pipeline/fresque/{module}.py").exists(), \
                f"CLAUDE.md cite le module `{token}`, qui n'existe pas"
            continue
        noeud = config
        for cle in token.split("."):
            assert isinstance(noeud, dict) and cle in noeud, \
                f"CLAUDE.md cite le réglage `{token}`, absent de fresque.config.yaml"
            noeud = noeud[cle]


def test_claude_md_tient_sous_son_budget():
    """Le fichier a triplé en dix commits sans que personne ne le mesure.
    Le budget n'est pas une élégance : c'est du contexte payé à chaque tour."""
    texte = re.sub(r"^\s*\|", "", _claude_md(), flags=re.M).replace("|", " ")
    mots = [m for m in texte.split() if m != "---"]
    assert len(mots) <= BUDGET_MOTS_CLAUDE_MD, (
        f"CLAUDE.md fait {len(mots)} mots pour un budget de "
        f"{BUDGET_MOTS_CLAUDE_MD}. Déplacer avant d'ajouter."
    )


def test_a_plate_without_a_title_fills_the_frame():
    """Le défaut mesuré sur le premier documentaire complet : la photo était
    dimensionnée par une largeur fixe, calibrée pour une planche surmontée
    d'une accroche. Or une seule planche par film en porte une — sur les 141
    de ce montage, les 141 avaient `bande_titre: 0`. La photo couvrait 25,6 %
    de l'écran, et le film se regardait comme un diaporama."""
    aires = []
    for index in range(60):
        shot = Shot(index=index, beat="B001", type="collage", requete="q")
        planche = collage_mod.compose(shot, 1.5)
        assert planche["bande_titre"] == 0
        bloc = next(p for p in planche["pieces"] if p["role"] == "bloc")
        aires.append(bloc["w"] * bloc["h"])

    moyenne = sum(aires) / len(aires)
    assert moyenne > 0.42, f"la planche ne remplit que {moyenne:.0%} du cadre"


def test_a_running_command_survives_a_server_restart():
    """Le serveur gardait en mémoire la seule preuve qu'un processus vivait.
    Redémarré pendant un rendu de trente minutes, il déclarait « interrompu »
    une commande qui tournait toujours. Le pid est maintenant dans le fichier
    — un processus long se surveille par son pid."""
    import os

    from fresque import serveur as serveur_mod

    assert serveur_mod._tourne_encore(os.getpid()) is True
    assert serveur_mod._tourne_encore(None) is False
    assert serveur_mod._tourne_encore("4456") is False
    # Un pid qui n'existe plus. 2^22 est au-dessus du plafond habituel de
    # Linux, donc aucun processus ne peut le porter.
    assert serveur_mod._tourne_encore(4_194_304) is False


def test_the_workshop_can_run_every_step_the_pipeline_has():
    """`aligner` manquait : la seule étape que le projet chiffre comme
    indispensable — 305 ms d'écart médian sans elle — n'était lançable qu'au
    terminal. Une commande qui écrit un fichier du projet et qu'on ne peut
    pas lancer depuis l'atelier est une commande qui ne sera pas lancée."""
    from fresque import serveur as serveur_mod

    for nom in ("voice", "aligner", "fetch", "timeline", "render"):
        assert nom in serveur_mod.COMMANDES, nom

    # Le libellé ne nomme aucun moteur : il en existe deux, et le réglage
    # peut changer sans que ce fichier le sache.
    assert "Kokoro" not in serveur_mod.COMMANDES["voice"].libelle


def test_the_source_field_names_the_method_not_the_engine():
    """`source` valait « kokoro », du temps où il n'y avait qu'un moteur.
    Un film synthétisé avec Edge annonçait donc Kokoro dans son propre
    fichier d'alignement — et le nom du moteur était déjà ailleurs, dans
    `voix.provider`. Ce champ dit d'où viennent les nombres."""
    from fresque import aligner as aligner_mod

    bases = {"beats": [{"id": "B001", "debut_s": 0.0}]}
    for mesure in ("mesure", "kokoro", aligner_mod.SOURCE):
        aligner_mod.bases_depuis({**bases, "source": mesure})

    with pytest.raises(aligner_mod.AlignError):
        aligner_mod.bases_depuis({**bases, "source": "estimate"})


def test_the_step_that_completes_a_file_holds_its_line():
    """Trois commandes écrivent `alignment.json`. La ligne « voix » de la
    chaîne doit porter celle qui la remplit vraiment : `align` n'écrit que
    des durées estimées, et cliquer dessus remplissait l'étape sans
    qu'aucun son existe."""
    from fresque import serveur

    memes = [c for c in serveur.COMMANDES.values()
             if c.produit == "04-audio/alignment.json"]
    principales = [c for c in memes if c.principale]

    assert len(memes) > 1, "le cas ne se pose que si plusieurs écrivent le fichier"
    assert [c.libelle for c in principales] == ["Générer l'audio"]


def test_an_estimated_alignment_is_not_a_voice(tmp_path):
    """`align` et `voice` écrivent le même fichier. La jauge de l'atelier
    testait sa seule présence, donc elle affichait la voix comme faite après
    une simple estimation — et l'étape suivante partait sur des chiffres
    devinés au lieu de durées mesurées."""
    from fresque import serveur as serveur_mod

    dossier = tmp_path
    (dossier / "04-audio").mkdir()
    cible = dossier / "04-audio" / "alignment.json"

    cible.write_text(json.dumps({"source": "estimate"}), encoding="utf-8")
    assert serveur_mod._etape_faite(dossier, "04-audio/alignment.json") is False

    for vraie in ("mesure", "kokoro", "forced"):
        cible.write_text(json.dumps({"source": vraie}), encoding="utf-8")
        assert serveur_mod._etape_faite(dossier, "04-audio/alignment.json") is True

    # Un fichier illisible ne vaut pas mieux qu'un fichier absent.
    cible.write_text("{cassé", encoding="utf-8")
    assert serveur_mod._etape_faite(dossier, "04-audio/alignment.json") is False

    # Tous les autres fichiers : exister suffit.
    (dossier / "02-script.md").write_text("x", encoding="utf-8")
    assert serveur_mod._etape_faite(dossier, "02-script.md") is True
    assert serveur_mod._etape_faite(dossier, "07-out/video.mp4") is False


def test_the_checkpoint_estimate_counts_the_silence_it_will_insert():
    """`mots_par_minute` est le débit du FILM : il compte les blancs entre
    beats et entre actes, qui ne sont pas dans le beat. Estimer un beat avec
    ce chiffre le raccourcit — mesuré sur les 168 beats du premier
    documentaire complet, 9,1 % sous la durée réelle en médiane.

    C'est la mauvaise direction : ce contrôle existe pour attraper un plan
    trop long AVANT de payer les images. Sous-estimer laisse passer au
    checkpoint ce que la timeline refusera après la dépense."""
    from fresque import config, shots as shots_mod

    class FauxBeat:
        id = "B001"
        word_count = 40
        text = "Trois mots ici. Puis trois autres. Et une fin."

    config.use_project_overrides({
        "narration": {"mots_par_minute": 120, "pause_phrase_s": 1.0},
        "montage": {"duree_plan_max_s": 20},
    })
    try:
        plan = [Shot(index=0, beat="B001", type="archive", requete="q")]
        # 40 mots à 120 mots/min = 20 s de parole, plus deux pauses d'une
        # seconde : 22 s. Sans les pauses, 20 s passerait tout juste sous le
        # plafond de 20 s ; avec elles, le plan est signalé.
        assert shots_mod.density(plan, [FauxBeat()]) != []
    finally:
        config.use_project_overrides(None)

    config.use_project_overrides({
        "narration": {"mots_par_minute": 120, "pause_phrase_s": 0},
        "montage": {"duree_plan_max_s": 20},
    })
    try:
        plan = [Shot(index=0, beat="B001", type="archive", requete="q")]
        assert shots_mod.density(plan, [FauxBeat()]) == []
    finally:
        config.use_project_overrides(None)
