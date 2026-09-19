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

    def boom(shot, destination_dir, model=None, session=None):
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
    source = Path("remotion/src/Motion.tsx").read_text(encoding="utf-8")
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
    assert plat["montage.musique.mode"] == "template"
    # Hérité : le template ne parle ni de résolution ni de fréquence d'images.
    assert plat["montage.fps"] == "base"


def test_template_page_is_static_and_self_contained(tmp_path):
    from fresque import apercu as apercu_mod

    sortie = apercu_mod.page("documentaire-historique", tmp_path / "t.html")
    page = sortie.read_text(encoding="utf-8")
    assert "<script" not in page, "la page doit être statique"
    assert "http://" not in page and "https://" not in page
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

    try:
        Project.open("essai")
        # Le projet a le dernier mot…
        assert config_mod.get("production", "duree_cible_min") == 2
        # …sans écraser ce que le template dit par ailleurs.
        assert config_mod.get("narration", "mots_par_minute") == 170
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
