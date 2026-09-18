"""Tests for the deterministic half of the pipeline.

Run with:  PYTHONPATH=pipeline python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def test_every_archive_group_lists_its_file_host():
    """A provider whose API is allowed but whose file host is not looks healthy
    and then fails at download time. Both must be probed."""
    for group in GROUPS:
        if "Archives" in group.label and len(group.hosts) == 1:
            assert "gallica" in group.label.lower(), group.label


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
