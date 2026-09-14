import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from prizehunter_core.fit_evaluation import FitPreferences
from prizehunter_core.user_profile import UserProfile
from pydantic import ValidationError

from prizehunter_aws import pipeline, web
from prizehunter_aws.profile_form import FORM_PATHS, form_options, goal_from_form


def test_blank_browser_form_preserves_core_unknowns():
    fields = {name: "" for name in FORM_PATHS}
    goal = goal_from_form(fields)
    p, f = goal.profile, goal.preferences
    assert type(p) is UserProfile and type(f) is FitPreferences
    assert p.country is None and p.citizenships is None
    assert p.has_reached_age_of_majority is None and p.entrant_statuses is None
    assert p.team_preference == "unknown" and p.intended_team_size is None
    assert p.available_time.total_hours_before_deadline is None
    assert p.entity_profile is None and p.candidate_project is None
    assert f.available_hours_before_deadline is None and f.willingness_to_travel is None
    assert f.willingness_to_build_fresh is None and f.reusable_assets == []
    assert p.skills == [] and p.technical_capability == []


def test_browser_fields_map_to_existing_core_contracts():
    goal = goal_from_form(
        {
            "profile.country": " Taiwan ",
            "profile.citizenships": "Canada, Taiwan",
            "profile.has_reached_age_of_majority": "false",
            "profile.entrant_statuses": ["professional", "student"],
            "profile.team_preference": "either",
            "profile.intended_team_size": "3",
            "profile.skills": "Python, design",
            "profile.technical_capability": "APIs\nPrototyping",
            "preferences.available_hours_before_deadline": "0",
            "preferences.willingness_to_travel": "false",
            "preferences.maximum_travel_days": "0",
            "preferences.interests": "climate, AI",
            "preferences.strategic_goals": "Learn, Portfolio",
            "preferences.reusable_assets": "Prototype\nDataset",
            "preferences.willingness_to_build_fresh": "false",
            "profile.region": "Taipei",
            "profile.age": "30",
            "profile.education_statuses": ["university_student"],
            "profile.graduated_on": "2026-06-01",
            "profile.permanent_resident_countries": "Canada",
            "profile.subject_to_us_sanctions_or_export_controls": "false",
            "profile.candidate_project.is_existing": "true",
            "profile.candidate_project.started_on": "2026-08-01",
            "profile.entity_profile.registered_legal_entity": "true",
            "profile.entity_profile.entity_types": ["startup"],
            "profile.entity_profile.incorporation_country": "Taiwan",
        }
    )
    p, f = goal.profile, goal.preferences
    assert p.country == "Taiwan" and p.citizenships == ["Canada", "Taiwan"]
    assert p.age == 30 and p.has_reached_age_of_majority is False  # Never infer adult from age.
    assert p.entrant_statuses == ["professional", "student"]
    assert p.team_preference == "either" and p.intended_team_size == 3
    assert p.skills == ["Python", "design"] and p.technical_capability == ["APIs", "Prototyping"]
    assert p.available_time.total_hours_before_deadline == f.available_hours_before_deadline == 0
    assert p.available_time.hours_per_week is None
    assert f.willingness_to_travel is False and f.maximum_travel_days == 0
    assert f.interests == ["climate", "AI"] and f.strategic_goals == ["Learn", "Portfolio"]
    assert f.reusable_assets == ["Prototype", "Dataset"] and f.willingness_to_build_fresh is False
    assert p.education_statuses == ["university_student"] and p.graduated_on.isoformat() == "2026-06-01"
    assert (
        p.permanent_resident_countries == ["Canada"] and p.subject_to_us_sanctions_or_export_controls is False
    )
    assert p.candidate_project.started_on.isoformat() == "2026-08-01"
    assert p.entity_profile.entity_types == ["startup"]


@pytest.mark.parametrize(
    "fields",
    [
        {"profile.country": "Canada", "profile.age": "30"},
        {"profile.team_preference": "solo"},
    ],
)
def test_preferences_do_not_invent_eligibility_facts(fields):
    p = goal_from_form(fields).profile
    assert p.citizenships is None and p.has_reached_age_of_majority is None
    assert p.subject_to_us_sanctions_or_export_controls is None and p.intended_team_size is None


@pytest.mark.parametrize(
    "fields",
    [
        {"profile.intended_team_size": "0"},
        {"profile.age": "30.5"},
        {"preferences.available_hours_before_deadline": "NaN"},
        {"preferences.available_hours_before_deadline": "-1"},
        {"profile.entrant_statuses": ["invented_role"]},
        {"profile.has_reached_age_of_majority": "maybe"},
        {"profile.citizenships": "Canada, Canada"},
        {"preferences.willingness_to_travel": "false", "preferences.maximum_travel_days": "4"},
        {
            "profile.entity_profile.registered_legal_entity": "false",
            "profile.entity_profile.incorporation_country": "Canada",
        },
        {"profile.candidate_project.started_on": "2026-08-01"},
        {"profile.country": {"value": "Canada"}},
        {"profile.profile_id": "overwrite"},
    ],
)
def test_invalid_form_values_are_rejected_by_transport_or_core(fields):
    with pytest.raises((ValueError, TypeError, ValidationError)):
        goal_from_form(fields)


def test_arbitrary_form_reaches_core_fit_without_reusing_scripted_preferences(monkeypatch, tmp_path):
    captured = {}
    original = pipeline.evaluate_fit

    def capture(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(pipeline, "evaluate_fit", capture)
    fields = {
        "profile.country": "Canada",
        "profile.citizenships": "Taiwan",
        "profile.skills": "Rust",
        "preferences.strategic_goals": "Explore robotics",
        "preferences.available_hours_before_deadline": "1.5",
    }
    status, _, body = web.dispatch("POST", "/api/profile-analysis", json.dumps(fields).encode(), tmp_path)
    r = json.loads(body)
    assert status == 200 and r["eligibility"]["overall_status"] == "uncertain"
    assert captured["profile"].skills == ["Rust"]
    assert captured["preferences"].strategic_goals == ["Explore robotics"]
    assert captured["preferences"].available_hours_before_deadline == 1.5
    assert captured["profile"].citizenships == ["Taiwan"]
    assert r["fit"] is None and r["plan"] is None and "require live inference" in r["decision_limitation"]
    assert r["execution"]["model_calls"] == 2  # Research only; no scripted Fit/Plan consumed.
    assert not list(tmp_path.iterdir())  # Entered profiles are not persisted.


def test_residence_change_affects_core_blocker_without_citizenship_inference(tmp_path):
    fields = {"profile.country": "Taiwan", "profile.citizenships": "Canada"}
    _, _, body = web.dispatch("POST", "/api/profile-analysis", json.dumps(fields).encode(), tmp_path)
    r = json.loads(body)
    assert r["eligibility"]["overall_status"] == "ineligible"
    assert r["fit"]["recommendation"] == "not_eligible" and r["fit"]["inference_skipped"]
    assert r["plan"]["inference_skipped"] and r["execution"]["model_calls"] == 2


def test_saved_example_remains_available_and_does_not_absorb_custom_profile(tmp_path):
    web.dispatch("POST", "/api/profile-analysis", b'{"profile.country":"Taiwan"}', tmp_path)
    _, _, body = web.dispatch("GET", "/api/example-result", b"", tmp_path)
    r = json.loads(body)
    assert r["goal"]["profile"]["country"] == "Canada"
    assert r["execution"]["model_calls"] == 4 and r["fit"] is not None


def test_html_form_uses_only_core_paths_and_enum_options():
    class Controls(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = set()

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            path = (
                values.get("name")
                if tag in {"input", "select", "textarea"}
                else values.get("data-checkboxes")
            )
            if path:
                self.paths.add(path)

    parser = Controls()
    parser.feed((web.ASSETS / "index.html").read_text())
    assert parser.paths == set(FORM_PATHS)
    assert form_options()["profile.team_preference"] == ["solo", "team", "either", "unknown"]
    assert "professional" in form_options()["profile.entrant_statuses"]


def test_live_harness_defaults_in_region_without_calling_aws(monkeypatch, tmp_path):
    import runpy
    import sys
    from types import SimpleNamespace

    import boto3

    monkeypatch.setattr(boto3, "Session", lambda **kwargs: SimpleNamespace(get_credentials=lambda: None))
    monkeypatch.setattr(sys, "argv", ["live_validation.py", "--output-dir", str(tmp_path)])
    script = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/live_validation.py"))
    assert script["main"]() == 2
    assert json.loads((tmp_path / "live-blocker.json").read_text())["model"] == "amazon.nova-lite-v1:0"


@pytest.mark.parametrize("arguments", [["--model", "us.amazon.nova-lite-v1:0"], []])
def test_live_harness_prevents_unsupported_cross_region_and_pending_account_retries(
    monkeypatch, tmp_path, arguments
):
    import runpy
    import sys

    import boto3

    ledger = tmp_path / "live-attempt-ledger.json"
    ledger.write_text('[{"error_type":"AccessDeniedException"}]')
    before = ledger.read_bytes()
    monkeypatch.setattr(
        boto3, "Session", lambda **kwargs: pytest.fail("Must not resolve credentials or call AWS")
    )
    monkeypatch.setattr(sys, "argv", ["live_validation.py", "--output-dir", str(tmp_path), *arguments])
    script = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/live_validation.py"))
    with pytest.raises(SystemExit) as error:
        script["main"]()
    assert error.value.code == 2 and ledger.read_bytes() == before
