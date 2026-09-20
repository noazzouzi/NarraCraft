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

    source = Path("remotion/src/Motion.tsx").read_text(encoding="utf-8")
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

    class FauxKokoro:
        def create(self, texte, voice, speed, lang):
            appels.append(texte)
            # Une seconde de « parole » par phrase, à amplitude non nulle.
            return np.ones(voice_mod.SAMPLE_RATE, dtype="float32"), voice_mod.SAMPLE_RATE

    samples, rate = voice_mod._say_beat(
        FauxKokoro(), "Trois mots. Puis trois. Et fin.",
        "ff_siwis", 0.75, "fr-fr", 0.70)

    assert appels == ["Trois mots.", "Puis trois.", "Et fin."]
    # Trois secondes de parole, plus deux silences amputés de ce que le
    # moteur fournit déjà.
    attendu = 3 + 2 * (0.70 - voice_mod._PAUSE_KOKORO_S)
    assert abs(len(samples) / rate - attendu) < 0.02
    assert (samples == 0).sum() > 0, "aucun silence n'a été inséré"


def test_a_single_sentence_beat_is_not_split():
    """Découper là où il n'y a rien à découper ferait payer un appel de plus
    au moteur, et changerait la prosodie sans raison."""
    import numpy as np

    from fresque import voice as voice_mod

    appels = []

    class FauxKokoro:
        def create(self, texte, voice, speed, lang):
            appels.append(texte)
            return np.ones(100, dtype="float32"), voice_mod.SAMPLE_RATE

    texte = "Une seule phrase, avec une virgule."
    voice_mod._say_beat(FauxKokoro(), texte, "ff_siwis", 0.75, "fr-fr", 0.70)
    assert appels == [texte]


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

    mesure = {"source": "kokoro",
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
