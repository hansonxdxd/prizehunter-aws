"""Browser transport conversion into the existing Core contracts, never a second schema."""

import json
import math
import re

from prizehunter_core.fit_evaluation import FitPreferences
from prizehunter_core.user_profile import UserProfile

from .contracts import Goal

# UI exposure only. Types, enums, constraints and defaults come from Core JSON Schema.
FORM_PATHS = (
    "profile.country",
    "profile.citizenships",
    "profile.has_reached_age_of_majority",
    "profile.entrant_statuses",
    "profile.team_preference",
    "profile.intended_team_size",
    "profile.skills",
    "profile.technical_capability",
    "profile.willingness_to_learn_new_tech",
    "preferences.available_hours_before_deadline",
    "preferences.willingness_to_travel",
    "preferences.maximum_travel_days",
    "preferences.interests",
    "preferences.strategic_goals",
    "preferences.reusable_assets",
    "preferences.willingness_to_build_fresh",
    "profile.region",
    "profile.age",
    "profile.permanent_resident_countries",
    "profile.subject_to_us_sanctions_or_export_controls",
    "profile.education_statuses",
    "profile.graduated_on",
    "profile.entity_profile.registered_legal_entity",
    "profile.entity_profile.entity_types",
    "profile.entity_profile.incorporation_country",
    "profile.entity_profile.incorporated_on",
    "profile.entity_profile.primary_business_country",
    "profile.entity_profile.operating",
    "profile.entity_profile.qualifies_as_sme",
    "profile.candidate_project.is_existing",
    "profile.candidate_project.started_on",
    "profile.candidate_project.publicly_released",
    "profile.candidate_project.previously_submitted",
    "profile.candidate_project.will_be_materially_modified",
)
SCHEMAS = {"profile": UserProfile.model_json_schema(), "preferences": FitPreferences.model_json_schema()}


def unwrap(node, root):
    if "anyOf" in node:
        node = next(n for n in node["anyOf"] if n.get("type") != "null")
    if "$ref" in node:
        node = root["$defs"][node["$ref"].split("/")[-1]]
    return node


def field_schema(path):
    group, *parts = path.split(".")
    root = SCHEMAS[group]
    node = root
    for part in parts:
        node = unwrap(node, root)["properties"][part]
    return node, root


def form_options():
    options = {}
    for path in FORM_PATHS:
        raw, root = field_schema(path)
        node = unwrap(raw, root)
        if node.get("type") == "array":
            node = unwrap(node["items"], root)
        if "enum" in node:
            options[path] = node["enum"]
    return options


def convert(path, value):
    raw, root = field_schema(path)
    schema = unwrap(raw, root)
    if not isinstance(value, (str, list)) or (
        isinstance(value, list) and not all(isinstance(v, str) for v in value)
    ):
        raise ValueError(f"{path}: expected form text")
    if len(json.dumps(value)) > 4000:
        raise ValueError(f"{path}: field too long")
    if schema.get("type") == "array":
        parts = value if isinstance(value, list) else re.split(r"[\n,]", value)
        values = [v.strip() for v in parts if v.strip()]
        if len(values) > 40:
            raise ValueError(f"{path}: too many values")
        return values or (None if "anyOf" in raw else [])
    if not isinstance(value, str):
        raise TypeError(f"{path}: expected one value")
    value = value.strip()
    if not value:
        return raw.get("default")  # Core owns unknown/null/default semantics.
    kind = schema.get("type")
    if kind == "boolean":
        if value not in {"true", "false"}:
            raise ValueError(f"{path}: expected yes, no or unknown")
        return value == "true"
    if kind == "integer":
        if not re.fullmatch(r"[+-]?\d+", value):
            raise ValueError(f"{path}: expected a whole number")
        return int(value)
    if kind == "number":
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{path}: expected a finite number")
        return number
    return value


def goal_from_form(fields):
    if not isinstance(fields, dict) or set(fields) - set(FORM_PATHS):
        raise ValueError("Unknown profile form field")
    payload = {
        "profile": {"profile_id": "browser-profile", "version": 1},
        "preferences": {"preferences_id": "browser-preferences", "version": 1},
    }
    for path, value in fields.items():
        parts = path.split(".")
        parent = payload
        for part in parts[:-1]:
            parent = parent.setdefault(part, {})
        parent[parts[-1]] = convert(path, value)
    for name in ("entity_profile", "candidate_project"):
        nested = payload["profile"].get(name)
        if nested and all(value is None or value == [] for value in nested.values()):
            payload["profile"][name] = None
    # One explicit total-hours answer feeds both Core contracts; no weekly-hour inference.
    hours = payload["preferences"].get("available_hours_before_deadline")
    payload["profile"]["available_time"] = {"total_hours_before_deadline": hours}
    profile = UserProfile.model_validate_json(json.dumps(payload["profile"]))
    preferences = FitPreferences.model_validate_json(json.dumps(payload["preferences"]))
    return Goal(
        goal_id="browser-goal",
        description="Evaluate the curated evidence for my entered profile.",
        profile=profile,
        preferences=preferences,
    )
