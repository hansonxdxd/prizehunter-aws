"""Conservative, deterministic hard-eligibility checks with no model calls."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile


class EligibilityStatus(StrEnum):
    """The only permitted outcomes for a hard-eligibility check."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNCERTAIN = "uncertain"


class EligibilityCheck(BaseModel):
    """One deterministic conclusion with explicit input-field references."""

    model_config = ConfigDict(extra="forbid")

    criterion: Literal["country", "age", "team_size"]
    status: EligibilityStatus
    reason: str
    competition_fields: list[str] = Field(default_factory=list)
    profile_fields: list[str] = Field(default_factory=list)


class HardEligibilityResult(BaseModel):
    """Combined deterministic result; it is not an AI FitEvaluation."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    profile_version: int
    competition_name: str | None
    status: EligibilityStatus
    checks: list[EligibilityCheck]


_COUNTRY_ALIASES = {
    "taiwan": {"taiwan"},
    "united states": {"united states", "united states of america", "usa"},
    "united states of america": {
        "united states",
        "united states of america",
        "usa",
    },
    "usa": {"united states", "united states of america", "usa"},
    "canada": {"canada"},
    "italy": {"italy"},
}

_GENERAL_MIN_AGE = re.compile(
    r"(?:entrants?|participants?|applicants?|individuals?|people|you)\s+"
    r"(?:must|need(?:s)?\s+to)\s+be\s+at\s+least\s+(\d{1,3})"
)
_GENERAL_OR_OLDER = re.compile(
    r"(?:entrants?|participants?|applicants?|individuals?|people|you)\s+"
    r"(?:must|need(?:s)?\s+to)\s+be\s+(\d{1,3})\s+"
    r"(?:years?\s+old\s+)?or\s+older"
)
_GENERAL_UNDER_AGE = re.compile(
    r"(?:entrants?|participants?|applicants?|individuals?|people|you)\s+"
    r"(?:must|need(?:s)?\s+to)\s+be\s+under\s+(\d{1,3})"
)
_GENERAL_OR_YOUNGER = re.compile(
    r"(?:entrants?|participants?|applicants?|individuals?|people|you)\s+"
    r"(?:must|need(?:s)?\s+to)\s+be\s+(\d{1,3})\s+"
    r"(?:years?\s+old\s+)?or\s+younger"
)
_TEAM_NUMBER_TOKEN = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b"
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_NUMBER_PATTERN = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _profile_field_uncertain(profile: UserProfile, fields: set[str]) -> bool:
    return any(item.field in fields for item in profile.profile_uncertainties)


def _competition_field_uncertain(
    competition: CompetitionRecord, fields: set[str]
) -> bool:
    return any(item.field in fields for item in competition.uncertainties)


def _country_terms(country: str) -> set[str]:
    normalized = _normalize(country)
    return _COUNTRY_ALIASES.get(normalized, {normalized})


def _country_check(
    competition: CompetitionRecord, profile: UserProfile
) -> EligibilityCheck:
    fields = ["eligibility", "geographic_restrictions"]
    profile_fields = ["country", "region"]
    if profile.country is None or _profile_field_uncertain(profile, {"country"}):
        return EligibilityCheck(
            criterion="country",
            status=EligibilityStatus.UNCERTAIN,
            reason="User country is missing or not confirmed.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    if _competition_field_uncertain(competition, set(fields)):
        return EligibilityCheck(
            criterion="country",
            status=EligibilityStatus.UNCERTAIN,
            reason="Competition geographic or eligibility rules are marked uncertain.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    rules = [
        _normalize(item)
        for item in [*competition.geographic_restrictions, *competition.eligibility]
    ]
    if not rules:
        return EligibilityCheck(
            criterion="country",
            status=EligibilityStatus.UNCERTAIN,
            reason="No explicit geographic rule is available.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    terms = _country_terms(profile.country)
    direct_exclusion_markers = (
        "may not enter",
        "not eligible",
        "are excluded",
        "is excluded",
        "are prohibited",
        "is prohibited",
    )
    for rule in rules:
        present_terms = [term for term in terms if _contains_phrase(rule, term)]
        if not present_terms:
            continue
        if any(
            _contains_phrase(rule, f"excluding {term}")
            or _contains_phrase(rule, f"except {term}")
            for term in present_terms
        ) or any(marker in rule for marker in direct_exclusion_markers):
            return EligibilityCheck(
                criterion="country",
                status=EligibilityStatus.INELIGIBLE,
                reason=f"The rules explicitly exclude {profile.country}.",
                competition_fields=fields,
                profile_fields=profile_fields,
            )

    allowed_only_markers = (
        "open only to",
        "only open to",
        "legal residents of",
        "must be legal residents of",
        "limited to residents of",
    )
    for rule in rules:
        if not any(marker in rule for marker in allowed_only_markers):
            continue
        matching_terms = [term for term in terms if _contains_phrase(rule, term)]
        if not matching_terms:
            return EligibilityCheck(
                criterion="country",
                status=EligibilityStatus.INELIGIBLE,
                reason=f"The allowed-country list does not include {profile.country}.",
                competition_fields=fields,
                profile_fields=profile_fields,
            )
        excluded_country_term = next(
            (term for term in matching_terms if f"{term} excluding" in rule), None
        )
        if excluded_country_term is not None:
            if profile.region is None or _profile_field_uncertain(profile, {"region"}):
                return EligibilityCheck(
                    criterion="country",
                    status=EligibilityStatus.UNCERTAIN,
                    reason=(
                        f"The rule has a sub-country exception for {profile.country}, "
                        "but the user region is missing or not confirmed."
                    ),
                    competition_fields=fields,
                    profile_fields=profile_fields,
                )
            excluded_regions = rule.split(
                f"{excluded_country_term} excluding", maxsplit=1
            )[1]
            if _contains_phrase(excluded_regions, _normalize(profile.region)):
                return EligibilityCheck(
                    criterion="country",
                    status=EligibilityStatus.INELIGIBLE,
                    reason=(
                        f"The rules explicitly exclude {profile.region}, "
                        f"{profile.country}."
                    ),
                    competition_fields=fields,
                    profile_fields=profile_fields,
                )
            return EligibilityCheck(
                criterion="country",
                status=EligibilityStatus.ELIGIBLE,
                reason=(
                    f"The allowed-country rule includes {profile.country}, and the "
                    f"stated exception does not match {profile.region}."
                ),
                competition_fields=fields,
                profile_fields=profile_fields,
            )
        return EligibilityCheck(
            criterion="country",
            status=EligibilityStatus.ELIGIBLE,
            reason=f"The allowed-country rule explicitly includes {profile.country}.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    for rule in rules:
        if "open worldwide" not in rule:
            continue
        conditional_markers = (
            "except",
            "excluding",
            "where lawful",
            "where prohibited",
            "sanctioned",
        )
        if any(marker in rule for marker in conditional_markers):
            return EligibilityCheck(
                criterion="country",
                status=EligibilityStatus.UNCERTAIN,
                reason="Worldwide eligibility has an exception that needs verification.",
                competition_fields=fields,
                profile_fields=profile_fields,
            )
        return EligibilityCheck(
            criterion="country",
            status=EligibilityStatus.ELIGIBLE,
            reason="The rules explicitly state that entry is open worldwide.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    return EligibilityCheck(
        criterion="country",
        status=EligibilityStatus.UNCERTAIN,
        reason="The geographic wording is outside the conservative baseline patterns.",
        competition_fields=fields,
        profile_fields=profile_fields,
    )


def _age_check(
    competition: CompetitionRecord, profile: UserProfile
) -> EligibilityCheck:
    fields = ["eligibility"]
    profile_fields = ["age", "country"]
    if profile.age is None or _profile_field_uncertain(profile, {"age"}):
        return EligibilityCheck(
            criterion="age",
            status=EligibilityStatus.UNCERTAIN,
            reason="User age is missing or not confirmed.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    if _competition_field_uncertain(competition, set(fields)):
        return EligibilityCheck(
            criterion="age",
            status=EligibilityStatus.UNCERTAIN,
            reason="Competition eligibility rules are marked uncertain.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    segments = [
        _normalize(segment)
        for item in competition.eligibility
        for segment in item.split(";")
        if segment.strip()
    ]
    minimum_ages: list[int] = []
    maximum_ages: list[tuple[int, bool]] = []
    country_terms = _country_terms(profile.country) if profile.country else set()

    for segment in segments:
        country_specific = "resident" in segment and "at least" in segment
        if country_specific and any(
            _contains_phrase(segment, term) for term in country_terms
        ):
            match = re.search(r"at\s+least\s+(\d{1,3})", segment)
            if match:
                minimum_ages.append(int(match.group(1)))
            continue
        if country_specific:
            continue
        for pattern in (_GENERAL_MIN_AGE, _GENERAL_OR_OLDER):
            minimum_ages.extend(int(value) for value in pattern.findall(segment))
        maximum_ages.extend(
            (int(value), False) for value in _GENERAL_UNDER_AGE.findall(segment)
        )
        maximum_ages.extend(
            (int(value), True) for value in _GENERAL_OR_YOUNGER.findall(segment)
        )

    if not minimum_ages and not maximum_ages:
        return EligibilityCheck(
            criterion="age",
            status=EligibilityStatus.UNCERTAIN,
            reason="No explicit numeric age rule can be evaluated deterministically.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    minimum = max(minimum_ages, default=None)
    if minimum is not None and profile.age < minimum:
        return EligibilityCheck(
            criterion="age",
            status=EligibilityStatus.INELIGIBLE,
            reason=f"User age {profile.age} is below the explicit minimum age {minimum}.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    for maximum, inclusive in maximum_ages:
        violates = profile.age > maximum if inclusive else profile.age >= maximum
        if violates:
            relation = "maximum" if inclusive else "exclusive upper limit"
            return EligibilityCheck(
                criterion="age",
                status=EligibilityStatus.INELIGIBLE,
                reason=f"User age {profile.age} exceeds the {relation} of {maximum}.",
                competition_fields=fields,
                profile_fields=profile_fields,
            )

    return EligibilityCheck(
        criterion="age",
        status=EligibilityStatus.ELIGIBLE,
        reason="User age satisfies every explicit numeric age limit found.",
        competition_fields=fields,
        profile_fields=profile_fields,
    )


def _entry_mode(profile: UserProfile) -> Literal["solo", "team", "either"] | None:
    if profile.solo_preference is True:
        if profile.team_preference == "team":
            return None
        return "solo"
    if profile.solo_preference is False:
        if profile.team_preference == "solo":
            return None
        return "team"
    if profile.team_preference in {"solo", "team", "either"}:
        return profile.team_preference
    return None


def _number_value(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token]


def _team_size_bounds(rule: str) -> tuple[int | None, int | None]:
    range_match = re.search(
        rf"({_NUMBER_PATTERN})\s+(?:to|through)\s+({_NUMBER_PATTERN})", rule
    )
    if range_match:
        return _number_value(range_match.group(1)), _number_value(range_match.group(2))

    minimum_match = re.search(rf"at\s+least\s+({_NUMBER_PATTERN})", rule)
    maximum_match = re.search(rf"up\s+to\s+({_NUMBER_PATTERN})", rule)
    minimum = _number_value(minimum_match.group(1)) if minimum_match else None
    maximum = _number_value(maximum_match.group(1)) if maximum_match else None
    return minimum, maximum


def _team_size_check(
    competition: CompetitionRecord, profile: UserProfile
) -> EligibilityCheck:
    fields = ["team_size"]
    profile_fields = ["team_preference", "solo_preference", "intended_team_size"]
    if _profile_field_uncertain(profile, set(profile_fields)):
        return EligibilityCheck(
            criterion="team_size",
            status=EligibilityStatus.UNCERTAIN,
            reason="User entry-mode preference is not confirmed.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    mode = _entry_mode(profile)
    if mode is None:
        return EligibilityCheck(
            criterion="team_size",
            status=EligibilityStatus.UNCERTAIN,
            reason="User solo and team preferences are missing or contradictory.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    if _competition_field_uncertain(competition, set(fields)):
        return EligibilityCheck(
            criterion="team_size",
            status=EligibilityStatus.UNCERTAIN,
            reason="Competition team-size rules are marked uncertain.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )
    if competition.team_size is None:
        return EligibilityCheck(
            criterion="team_size",
            status=EligibilityStatus.UNCERTAIN,
            reason="No explicit team-size rule is available.",
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    rule = _normalize(competition.team_size)
    team_forbidden = any(
        phrase in rule
        for phrase in ("solo only", "individual entries only", "no teams")
    )
    minimum, maximum = _team_size_bounds(rule)
    solo_allowed = (
        any(
            phrase in rule
            for phrase in (
                "alone",
                "solo",
                "individual or team",
                "individuals or teams",
            )
        )
        or minimum == 1
    )
    solo_forbidden = team_forbidden is False and minimum is not None and minimum >= 2
    team_allowed = "team" in rule and not team_forbidden
    has_numeric_team_constraint = bool(_TEAM_NUMBER_TOKEN.search(rule))

    intended_size = profile.intended_team_size
    if intended_size is None and mode == "solo":
        intended_size = 1
    if intended_size is not None:
        if (intended_size == 1 and mode == "team") or (
            intended_size >= 2 and mode == "solo"
        ):
            return EligibilityCheck(
                criterion="team_size",
                status=EligibilityStatus.UNCERTAIN,
                reason="User entry-mode preferences contradict the intended team size.",
                competition_fields=fields,
                profile_fields=profile_fields,
            )
        if intended_size > 1 and team_forbidden:
            status = EligibilityStatus.INELIGIBLE
        elif intended_size == 1 and solo_forbidden:
            status = EligibilityStatus.INELIGIBLE
        elif minimum is not None and intended_size < minimum:
            status = EligibilityStatus.INELIGIBLE
        elif maximum is not None and intended_size > maximum:
            status = EligibilityStatus.INELIGIBLE
        elif minimum is not None or maximum is not None:
            status = EligibilityStatus.ELIGIBLE
        elif intended_size == 1 and solo_allowed:
            status = EligibilityStatus.ELIGIBLE
        elif intended_size > 1 and team_allowed and not has_numeric_team_constraint:
            status = EligibilityStatus.ELIGIBLE
        else:
            status = EligibilityStatus.UNCERTAIN

        reasons = {
            EligibilityStatus.ELIGIBLE: (
                f"Intended team size {intended_size} satisfies the explicit rule."
            ),
            EligibilityStatus.INELIGIBLE: (
                f"Intended team size {intended_size} violates the explicit rule."
            ),
            EligibilityStatus.UNCERTAIN: (
                "The team-size wording is not sufficient to evaluate the intended "
                f"team size {intended_size}."
            ),
        }
        return EligibilityCheck(
            criterion="team_size",
            status=status,
            reason=reasons[status],
            competition_fields=fields,
            profile_fields=profile_fields,
        )

    if mode == "solo":
        status = (
            EligibilityStatus.ELIGIBLE
            if solo_allowed
            else EligibilityStatus.INELIGIBLE
            if solo_forbidden or team_allowed
            else EligibilityStatus.UNCERTAIN
        )
    elif mode == "team":
        status = (
            EligibilityStatus.INELIGIBLE
            if team_forbidden
            else EligibilityStatus.UNCERTAIN
            if team_allowed and has_numeric_team_constraint
            else EligibilityStatus.ELIGIBLE
            if team_allowed and not has_numeric_team_constraint
            else EligibilityStatus.UNCERTAIN
        )
    else:
        status = (
            EligibilityStatus.ELIGIBLE
            if solo_allowed or (team_allowed and not has_numeric_team_constraint)
            else EligibilityStatus.INELIGIBLE
            if team_forbidden
            else EligibilityStatus.UNCERTAIN
        )

    reasons = {
        EligibilityStatus.ELIGIBLE: f"The rules explicitly allow the {mode} entry mode.",
        EligibilityStatus.INELIGIBLE: f"The rules explicitly disallow the {mode} entry mode.",
        EligibilityStatus.UNCERTAIN: (
            "The team-size rule or intended team member count is not sufficient "
            "to establish the chosen mode."
        ),
    }
    return EligibilityCheck(
        criterion="team_size",
        status=status,
        reason=reasons[status],
        competition_fields=fields,
        profile_fields=profile_fields,
    )


def evaluate_hard_eligibility(
    competition: CompetitionRecord, profile: UserProfile
) -> HardEligibilityResult:
    """Evaluate only country, numeric age, and solo/team hard constraints."""
    checks = [
        _country_check(competition, profile),
        _age_check(competition, profile),
        _team_size_check(competition, profile),
    ]
    statuses = {check.status for check in checks}
    if EligibilityStatus.INELIGIBLE in statuses:
        status = EligibilityStatus.INELIGIBLE
    elif EligibilityStatus.UNCERTAIN in statuses:
        status = EligibilityStatus.UNCERTAIN
    else:
        status = EligibilityStatus.ELIGIBLE
    return HardEligibilityResult(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        competition_name=competition.competition_name,
        status=status,
        checks=checks,
    )
