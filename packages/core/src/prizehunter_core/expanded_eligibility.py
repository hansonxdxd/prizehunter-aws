"""Typed, provenance-aware facts for expanded deterministic eligibility gates."""

from __future__ import annotations

import json
import re
from datetime import date
from enum import StrEnum
from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from prizehunter_core.competition_intelligence import (
    ClaimScope,
    CompetitionIntelligence,
    ResolutionStatus,
    ScopeKind,
)
from prizehunter_core.eligibility import EligibilityStatus
from prizehunter_core.user_profile import (
    EducationStatus,
    EntityType,
    EntrantStatus,
    UserProfile,
)

_SIMPLE_PATHS = {
    "residence": "/eligibility/residence",
    "age": "/eligibility/age",
    "team_size": "/eligibility/team_size",
    "citizenship": "/eligibility/citizenship",
    "education": "/eligibility/education_status",
    "entrant_status": "/eligibility/entrant_status",
    "entity": "/eligibility/entity",
    "existing_work": "/eligibility/existing_work",
}
_DIVISION_PATH_PREFIX = "/eligibility/divisions/"


class ExistingWorkPolicy(StrEnum):
    """Controlled organizer-fact states from the Phase 2D-0B research."""

    ALLOWED = "allowed"
    ALLOWED_WITH_MODIFICATION = "allowed_with_modification"
    FRESH_WORK_REQUIRED = "fresh_work_required"
    MUST_START_AFTER_OPEN = "must_start_after_open"
    PRIOR_PUBLIC_RELEASE_PROHIBITED = "prior_public_release_prohibited"
    PREVIOUS_SUBMISSION_PROHIBITED = "previous_submission_prohibited"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class EntityRequirementMode(StrEnum):
    """Minimal legal-entry modes that can create a deterministic gate."""

    NO_REQUIREMENT = "no_requirement"
    INDIVIDUAL_ONLY = "individual_only"
    REGISTERED_ENTITY_REQUIRED = "registered_entity_required"
    STARTUP_REQUIRED = "startup_required"


class EligibilityFactStatus(StrEnum):
    """Compatibility state for one typed eligibility fact."""

    RESOLVED = "resolved"
    PROVISIONAL = "provisional"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    MISSING = "missing"
    UNPARSED = "unparsed"


class ResidenceRequirementMode(StrEnum):
    """Whether legal residence is worldwide or limited to an explicit list."""

    WORLDWIDE = "worldwide"
    ALLOWED_COUNTRIES = "allowed_countries"


class RegionExclusion(BaseModel):
    """One explicit sub-country exclusion, never inferred from a country name."""

    model_config = ConfigDict(extra="forbid", strict=True)

    country: str | None = Field(default=None, min_length=1)
    region: str = Field(min_length=1)


class ResidenceRequirement(BaseModel):
    """Typed legal-residence rule suitable for deterministic comparison."""

    model_config = ConfigDict(extra="forbid", strict=True)

    mode: ResidenceRequirementMode
    allowed_countries: list[str] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)
    excluded_residence_jurisdictions: list[str] = Field(default_factory=list)
    excluded_regions: list[RegionExclusion] = Field(default_factory=list)
    requires_not_subject_to_us_sanctions_or_export_controls: bool = False

    @field_validator("allowed_countries", "excluded_countries")
    @classmethod
    def validate_country_lists(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Country lists cannot contain blank values.")
        if len({item.casefold().strip() for item in value}) != len(value):
            raise ValueError("Country lists cannot contain duplicates.")
        return value

    @field_validator("excluded_residence_jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Jurisdiction lists cannot contain blank values.")
        if len({item.casefold().strip() for item in value}) != len(value):
            raise ValueError("Jurisdiction lists cannot contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if self.mode is ResidenceRequirementMode.ALLOWED_COUNTRIES:
            if not self.allowed_countries:
                raise ValueError(
                    "allowed_countries mode requires at least one country."
                )
        elif self.allowed_countries:
            raise ValueError("worldwide mode cannot carry an allowed-country list.")
        keys = {
            (
                _normalize(item.country) if item.country else None,
                _normalize(item.region),
            )
            for item in self.excluded_regions
        }
        if len(keys) != len(self.excluded_regions):
            raise ValueError("excluded_regions cannot contain duplicates.")
        return self


class AgeRequirement(BaseModel):
    """Explicit numeric and/or user-confirmable legal-majority age gate."""

    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_age: int | None = Field(default=None, ge=0, le=130)
    maximum_age: int | None = Field(default=None, ge=0, le=130)
    requires_age_of_majority: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if (
            self.minimum_age is None
            and self.maximum_age is None
            and not self.requires_age_of_majority
        ):
            raise ValueError("An age requirement needs a numeric or majority gate.")
        if (
            self.minimum_age is not None
            and self.maximum_age is not None
            and self.minimum_age > self.maximum_age
        ):
            raise ValueError("minimum_age cannot exceed maximum_age.")
        return self


class TeamSizeRequirement(BaseModel):
    """Explicit participant-count bounds; values include the user."""

    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_team_size: int | None = Field(default=None, ge=1)
    maximum_team_size: int | None = Field(default=None, ge=1)
    solo_allowed: bool
    teams_allowed: bool

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if not self.solo_allowed and not self.teams_allowed:
            raise ValueError("At least one entry mode must be allowed.")
        if (
            self.minimum_team_size is not None
            and self.maximum_team_size is not None
            and self.minimum_team_size > self.maximum_team_size
        ):
            raise ValueError("minimum_team_size cannot exceed maximum_team_size.")
        if self.minimum_team_size is not None and self.minimum_team_size >= 2:
            if self.solo_allowed:
                raise ValueError(
                    "A minimum team size of two or more forbids solo entry."
                )
        if self.maximum_team_size == 1 and self.teams_allowed:
            raise ValueError("A maximum team size of one forbids team entry.")
        return self


def _validate_unique_non_empty_strings(value: list[str]) -> list[str]:
    if any(not item.strip() for item in value):
        raise ValueError("String lists cannot contain blank values.")
    normalized = {item.casefold().strip() for item in value}
    if len(normalized) != len(value):
        raise ValueError("String lists cannot contain duplicates.")
    return value


class CitizenshipRequirement(BaseModel):
    """Citizenship gate, explicitly separate from legal residence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    allowed_citizenships: list[str] = Field(min_length=1)
    permanent_residence_accepted: bool = False

    _validate_citizenships = field_validator("allowed_citizenships")(
        _validate_unique_non_empty_strings
    )


class EducationRequirement(BaseModel):
    """Small education-status gate; not a full academic history."""

    model_config = ConfigDict(extra="forbid", strict=True)

    allowed_statuses: list[EducationStatus] = Field(min_length=1)
    max_years_since_graduation: int | None = Field(default=None, ge=0)

    @field_validator("allowed_statuses")
    @classmethod
    def validate_unique_statuses(
        cls, value: list[EducationStatus]
    ) -> list[EducationStatus]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_statuses cannot contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_graduate_window(self) -> Self:
        if (
            self.max_years_since_graduation is not None
            and EducationStatus.RECENT_GRADUATE not in self.allowed_statuses
        ):
            raise ValueError(
                "A graduation window requires recent_graduate in allowed_statuses."
            )
        return self


class EntrantStatusRequirement(BaseModel):
    """Allowed non-exclusive entrant roles."""

    model_config = ConfigDict(extra="forbid", strict=True)

    allowed_statuses: list[EntrantStatus] = Field(min_length=1)

    @field_validator("allowed_statuses")
    @classmethod
    def validate_unique_statuses(
        cls, value: list[EntrantStatus]
    ) -> list[EntrantStatus]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_statuses cannot contain duplicates.")
        return value


class EntityRequirement(BaseModel):
    """Minimum entity gate without turning UserProfile into a company CRM."""

    model_config = ConfigDict(extra="forbid", strict=True)

    mode: EntityRequirementMode
    registered_legal_entity_required: bool = False
    allowed_entity_types: list[EntityType] = Field(default_factory=list)
    incorporation_countries: list[str] = Field(default_factory=list)
    incorporated_on_or_after: date | None = None
    primary_business_countries: list[str] = Field(default_factory=list)
    operating_required: bool = False
    sme_status_required: bool = False

    _validate_countries = field_validator(
        "incorporation_countries", "primary_business_countries"
    )(_validate_unique_non_empty_strings)

    @field_validator("allowed_entity_types")
    @classmethod
    def validate_unique_entity_types(cls, value: list[EntityType]) -> list[EntityType]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_entity_types cannot contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_mode_constraints(self) -> Self:
        has_entity_constraints = bool(
            self.allowed_entity_types
            or self.incorporation_countries
            or self.incorporated_on_or_after is not None
            or self.primary_business_countries
            or self.operating_required
            or self.sme_status_required
        )
        if self.mode in {
            EntityRequirementMode.NO_REQUIREMENT,
            EntityRequirementMode.INDIVIDUAL_ONLY,
        } and (self.registered_legal_entity_required or has_entity_constraints):
            raise ValueError(
                "No-requirement and individual-only modes cannot carry entity constraints."
            )
        return self


class ExistingWorkRequirement(BaseModel):
    """Organizer policy for the specific project a user may submit."""

    model_config = ConfigDict(extra="forbid", strict=True)

    policy: ExistingWorkPolicy
    must_start_on_or_after: date | None = None

    @model_validator(mode="after")
    def validate_start_boundary(self) -> Self:
        if (self.policy is ExistingWorkPolicy.MUST_START_AFTER_OPEN) != (
            self.must_start_on_or_after is not None
        ):
            raise ValueError(
                "Only must_start_after_open requires a must_start_on_or_after date."
            )
        return self


class EligibilityDivision(BaseModel):
    """One eligibility-bearing division; theme-only tracks do not belong here."""

    model_config = ConfigDict(extra="forbid", strict=True)

    division_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1)
    citizenship: CitizenshipRequirement | None = None
    education: EducationRequirement | None = None
    entrant_status: EntrantStatusRequirement | None = None
    entity: EntityRequirement | None = None

    @model_validator(mode="after")
    def require_an_eligibility_gate(self) -> Self:
        if not any(
            (self.citizenship, self.education, self.entrant_status, self.entity)
        ):
            raise ValueError(
                "Eligibility divisions need at least one hard-gate requirement."
            )
        return self


FactValue = TypeVar("FactValue", bound=BaseModel)


class EligibilityFactState(BaseModel, Generic[FactValue]):
    """Typed adapter output backed by existing claims and a resolution state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: EligibilityFactStatus
    value: FactValue | None = None
    field_path: str = Field(pattern=r"^/.+")
    scope: ClaimScope = Field(default_factory=ClaimScope)
    claim_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        has_value = self.status in {
            EligibilityFactStatus.RESOLVED,
            EligibilityFactStatus.PROVISIONAL,
        }
        if has_value != (self.value is not None):
            raise ValueError(
                "Resolved/provisional facts require values; other states forbid them."
            )
        if len(self.claim_ids) != len(set(self.claim_ids)):
            raise ValueError("claim_ids cannot contain duplicates.")
        return self


class ExpandedEligibilityFacts(BaseModel):
    """Additive typed facts adapted from a CompetitionIntelligence sidecar."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"] = "1.0"
    competition_id: str = Field(min_length=1)
    residence: EligibilityFactState[ResidenceRequirement] | None = None
    age: EligibilityFactState[AgeRequirement] | None = None
    team_size: EligibilityFactState[TeamSizeRequirement] | None = None
    citizenship: EligibilityFactState[CitizenshipRequirement] | None = None
    education: EligibilityFactState[EducationRequirement] | None = None
    entrant_status: EligibilityFactState[EntrantStatusRequirement] | None = None
    entity: EligibilityFactState[EntityRequirement] | None = None
    divisions: list[EligibilityFactState[EligibilityDivision]] = Field(
        default_factory=list
    )
    existing_work: EligibilityFactState[ExistingWorkRequirement] | None = None

    @model_validator(mode="after")
    def validate_division_keys(self) -> Self:
        keys = [
            (item.field_path, item.scope.kind.value, item.scope.identifier)
            for item in self.divisions
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Division fact path/scope pairs must be unique.")
        return self


class ExpandedEligibilityCheck(BaseModel):
    """One consumer-readable deterministic expanded hard-gate result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    criterion: Literal[
        "residence",
        "age",
        "team_size",
        "citizenship",
        "education",
        "entrant_status",
        "entity",
        "divisions",
        "existing_work",
    ]
    status: EligibilityStatus
    reason: str = Field(min_length=1)
    competition_fields: list[str] = Field(default_factory=list)
    profile_fields: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class DivisionEligibilityResult(BaseModel):
    """Per-division result preserved even when another division is eligible."""

    model_config = ConfigDict(extra="forbid", strict=True)

    division_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: EligibilityStatus
    checks: list[ExpandedEligibilityCheck]


class ExpandedHardEligibilityResult(BaseModel):
    """Versioned expanded checks, separate from legacy HardEligibilityResult."""

    model_config = ConfigDict(extra="forbid", strict=True)

    result_version: Literal["1.0"] = "1.0"
    competition_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    status: EligibilityStatus
    checks: list[ExpandedEligibilityCheck]
    division_results: list[DivisionEligibilityResult] = Field(default_factory=list)


def _all_resolution_claim_ids(field) -> list[str]:
    return list(
        dict.fromkeys(
            field.supporting_claim_ids
            + field.conflicting_claim_ids
            + field.superseded_claim_ids
        )
    )


def _adapt_fact(
    intelligence: CompetitionIntelligence,
    *,
    field_path: str,
    scope: ClaimScope,
    value_model: type[FactValue],
) -> EligibilityFactState[FactValue] | None:
    resolution = next(
        (
            item
            for item in intelligence.resolved_fields
            if item.field_path == field_path and item.scope == scope
        ),
        None,
    )
    matching_claim_ids = [
        claim.claim_id
        for claim in intelligence.claims
        if claim.field_path == field_path and claim.scope == scope
    ]
    if resolution is None:
        if not matching_claim_ids:
            return None
        return EligibilityFactState[FactValue](
            status=EligibilityFactStatus.MISSING,
            field_path=field_path,
            scope=scope,
            claim_ids=matching_claim_ids,
            reason="Claims exist, but no resolution record is available.",
        )

    claim_ids = _all_resolution_claim_ids(resolution)
    if resolution.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT:
        return EligibilityFactState[FactValue](
            status=EligibilityFactStatus.UNRESOLVED_CONFLICT,
            field_path=field_path,
            scope=scope,
            claim_ids=claim_ids,
            reason=resolution.resolution_reason,
        )
    try:
        value = value_model.model_validate_json(json.dumps(resolution.effective_value))
    except (TypeError, ValueError):
        return EligibilityFactState[FactValue](
            status=EligibilityFactStatus.UNPARSED,
            field_path=field_path,
            scope=scope,
            claim_ids=claim_ids,
            reason="Resolved value does not match the typed eligibility contract.",
        )
    status = (
        EligibilityFactStatus.RESOLVED
        if resolution.resolution_status is ResolutionStatus.RESOLVED
        else EligibilityFactStatus.PROVISIONAL
    )
    return EligibilityFactState[FactValue](
        status=status,
        value=value,
        field_path=field_path,
        scope=scope,
        claim_ids=claim_ids,
        reason=resolution.resolution_reason,
    )


def adapt_expanded_eligibility_facts(
    intelligence: CompetitionIntelligence,
) -> ExpandedEligibilityFacts:
    """Adapt exact eligibility paths without inventing or ranking source claims."""

    whole_competition = ClaimScope()
    residence = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["residence"],
        scope=whole_competition,
        value_model=ResidenceRequirement,
    )
    age = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["age"],
        scope=whole_competition,
        value_model=AgeRequirement,
    )
    team_size = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["team_size"],
        scope=whole_competition,
        value_model=TeamSizeRequirement,
    )
    citizenship = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["citizenship"],
        scope=whole_competition,
        value_model=CitizenshipRequirement,
    )
    education = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["education"],
        scope=whole_competition,
        value_model=EducationRequirement,
    )
    entrant_status = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["entrant_status"],
        scope=whole_competition,
        value_model=EntrantStatusRequirement,
    )
    entity = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["entity"],
        scope=whole_competition,
        value_model=EntityRequirement,
    )
    existing_work = _adapt_fact(
        intelligence,
        field_path=_SIMPLE_PATHS["existing_work"],
        scope=whole_competition,
        value_model=ExistingWorkRequirement,
    )

    division_keys = {
        (item.field_path, item.scope.kind.value, item.scope.identifier)
        for item in [*intelligence.claims, *intelligence.resolved_fields]
        if item.field_path.startswith(_DIVISION_PATH_PREFIX)
        and item.scope.kind is ScopeKind.ENTRANT_CATEGORY
    }
    divisions: list[EligibilityFactState[EligibilityDivision]] = []
    for field_path, scope_kind, scope_identifier in sorted(division_keys):
        scope = ClaimScope(
            kind=ScopeKind(scope_kind),
            identifier=scope_identifier,
        )
        state = _adapt_fact(
            intelligence,
            field_path=field_path,
            scope=scope,
            value_model=EligibilityDivision,
        )
        if state is None:
            continue
        if state.value is not None and state.value.division_id != scope.identifier:
            state = EligibilityFactState[EligibilityDivision](
                status=EligibilityFactStatus.UNPARSED,
                field_path=field_path,
                scope=scope,
                claim_ids=state.claim_ids,
                reason="Division value ID does not match its entrant-category scope.",
            )
        divisions.append(state)

    return ExpandedEligibilityFacts(
        competition_id=intelligence.competition_id,
        residence=residence,
        age=age,
        team_size=team_size,
        citizenship=citizenship,
        education=education,
        entrant_status=entrant_status,
        entity=entity,
        divisions=divisions,
        existing_work=existing_work,
    )


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


_COUNTRY_EQUIVALENTS = {
    "united states": {"united states", "united states of america", "usa", "us"},
    "united states of america": {
        "united states",
        "united states of america",
        "usa",
        "us",
    },
    "usa": {"united states", "united states of america", "usa", "us"},
    "us": {"united states", "united states of america", "usa", "us"},
    "taiwan": {"taiwan", "republic of china", "roc"},
    "republic of china": {"taiwan", "republic of china", "roc"},
}


def _country_values(value: str) -> set[str]:
    normalized = _normalize(value)
    return _COUNTRY_EQUIVALENTS.get(normalized, {normalized})


def _country_lists_intersect(actual: list[str], allowed: list[str]) -> bool:
    actual_values = {item for value in actual for item in _country_values(value)}
    allowed_values = {item for value in allowed for item in _country_values(value)}
    return bool(actual_values & allowed_values)


def _profile_uncertain(profile: UserProfile, fields: set[str]) -> bool:
    return any(item.field in fields for item in profile.profile_uncertainties)


def _check(
    criterion: Literal[
        "residence",
        "age",
        "team_size",
        "citizenship",
        "education",
        "entrant_status",
        "entity",
        "divisions",
        "existing_work",
    ],
    status: EligibilityStatus,
    reason: str,
    *,
    field_path: str,
    profile_fields: list[str],
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    return ExpandedEligibilityCheck(
        criterion=criterion,
        status=status,
        reason=reason,
        competition_fields=[field_path],
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _state_uncertain_check(
    criterion: Literal[
        "residence",
        "age",
        "team_size",
        "citizenship",
        "education",
        "entrant_status",
        "entity",
        "divisions",
        "existing_work",
    ],
    state: EligibilityFactState,
    profile_fields: list[str],
) -> ExpandedEligibilityCheck:
    return _check(
        criterion,
        EligibilityStatus.UNCERTAIN,
        f"Eligibility fact is {state.status.value}: {state.reason}",
        field_path=state.field_path,
        profile_fields=profile_fields,
        claim_ids=state.claim_ids,
    )


def _country_matches(actual: str, expected: str) -> bool:
    return bool(_country_values(actual) & _country_values(expected))


def _residence_check(
    requirement: ResidenceRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = [
        "country",
        "region",
        "subject_to_us_sanctions_or_export_controls",
    ]
    if profile.country is None or _profile_uncertain(profile, {"country"}):
        return _check(
            "residence",
            EligibilityStatus.UNCERTAIN,
            "User legal country of residence is missing or not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if any(
        _country_matches(profile.country, country)
        for country in requirement.excluded_countries
    ):
        return _check(
            "residence",
            EligibilityStatus.INELIGIBLE,
            f"The typed residence rule explicitly excludes {profile.country}.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    user_jurisdictions = {_normalize(profile.country)}
    if profile.region is not None:
        user_jurisdictions.add(_normalize(profile.region))
    if user_jurisdictions & {
        _normalize(item) for item in requirement.excluded_residence_jurisdictions
    }:
        return _check(
            "residence",
            EligibilityStatus.INELIGIBLE,
            "The user's confirmed residence matches an explicitly excluded jurisdiction.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if requirement.mode is ResidenceRequirementMode.ALLOWED_COUNTRIES and not any(
        _country_matches(profile.country, country)
        for country in requirement.allowed_countries
    ):
        return _check(
            "residence",
            EligibilityStatus.INELIGIBLE,
            f"The typed allowed-country list does not include {profile.country}.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    applicable_exclusions = [
        item
        for item in requirement.excluded_regions
        if item.country is None or _country_matches(profile.country, item.country)
    ]
    if applicable_exclusions:
        if profile.region is None or _profile_uncertain(profile, {"region"}):
            return _check(
                "residence",
                EligibilityStatus.UNCERTAIN,
                "The residence rule has a regional exclusion, but the user region is not confirmed.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if any(
            _normalize(profile.region) == _normalize(item.region)
            for item in applicable_exclusions
        ):
            return _check(
                "residence",
                EligibilityStatus.INELIGIBLE,
                f"The typed residence rule explicitly excludes {profile.region}, {profile.country}.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.requires_not_subject_to_us_sanctions_or_export_controls:
        sanctions_status = profile.subject_to_us_sanctions_or_export_controls
        if sanctions_status is None or _profile_uncertain(
            profile, {"subject_to_us_sanctions_or_export_controls"}
        ):
            return _check(
                "residence",
                EligibilityStatus.UNCERTAIN,
                "The rules include a sanctions/export-control gate, but the user status is not confirmed.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if sanctions_status:
            return _check(
                "residence",
                EligibilityStatus.INELIGIBLE,
                "The user confirms the explicit sanctions/export-control exclusion applies.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    return _check(
        "residence",
        EligibilityStatus.ELIGIBLE,
        "Confirmed legal residence satisfies the complete typed residence rule.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _age_requirement_check(
    requirement: AgeRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["age", "has_reached_age_of_majority"]
    if requirement.minimum_age is not None or requirement.maximum_age is not None:
        if profile.age is None or _profile_uncertain(profile, {"age"}):
            return _check(
                "age",
                EligibilityStatus.UNCERTAIN,
                "A numeric age rule applies, but the user age is not confirmed.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if (
            requirement.minimum_age is not None
            and profile.age < requirement.minimum_age
        ):
            return _check(
                "age",
                EligibilityStatus.INELIGIBLE,
                f"User age {profile.age} is below the typed minimum age {requirement.minimum_age}.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if (
            requirement.maximum_age is not None
            and profile.age > requirement.maximum_age
        ):
            return _check(
                "age",
                EligibilityStatus.INELIGIBLE,
                f"User age {profile.age} exceeds the typed maximum age {requirement.maximum_age}.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.requires_age_of_majority:
        if profile.has_reached_age_of_majority is None or _profile_uncertain(
            profile, {"has_reached_age_of_majority"}
        ):
            return _check(
                "age",
                EligibilityStatus.UNCERTAIN,
                "The rules require legal majority, but the user has not confirmed that status.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not profile.has_reached_age_of_majority:
            return _check(
                "age",
                EligibilityStatus.INELIGIBLE,
                "The user confirms they have not reached the required age of majority.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    return _check(
        "age",
        EligibilityStatus.ELIGIBLE,
        "Confirmed user age facts satisfy the complete typed age rule.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _team_size_requirement_check(
    requirement: TeamSizeRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["intended_team_size"]
    intended = profile.intended_team_size
    if intended is None or _profile_uncertain(profile, {"intended_team_size"}):
        return _check(
            "team_size",
            EligibilityStatus.UNCERTAIN,
            "A typed team-size rule applies, but intended_team_size is not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    violates_mode = (intended == 1 and not requirement.solo_allowed) or (
        intended > 1 and not requirement.teams_allowed
    )
    violates_bounds = (
        requirement.minimum_team_size is not None
        and intended < requirement.minimum_team_size
    ) or (
        requirement.maximum_team_size is not None
        and intended > requirement.maximum_team_size
    )
    if violates_mode or violates_bounds:
        return _check(
            "team_size",
            EligibilityStatus.INELIGIBLE,
            f"Intended team size {intended} violates the complete typed team rule.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    return _check(
        "team_size",
        EligibilityStatus.ELIGIBLE,
        f"Intended team size {intended} satisfies the complete typed team rule.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _citizenship_check(
    requirement: CitizenshipRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["citizenships", "permanent_resident_countries"]
    if _profile_uncertain(profile, set(profile_fields)):
        return _check(
            "citizenship",
            EligibilityStatus.UNCERTAIN,
            "User citizenship or permanent-resident status is not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    citizenship_match = profile.citizenships is not None and _country_lists_intersect(
        profile.citizenships, requirement.allowed_citizenships
    )
    permanent_resident_match = (
        requirement.permanent_residence_accepted
        and profile.permanent_resident_countries is not None
        and _country_lists_intersect(
            profile.permanent_resident_countries,
            requirement.allowed_citizenships,
        )
    )
    if citizenship_match or permanent_resident_match:
        return _check(
            "citizenship",
            EligibilityStatus.ELIGIBLE,
            "User satisfies the explicit citizenship or permanent-resident rule.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    missing_avenue = profile.citizenships is None or (
        requirement.permanent_residence_accepted
        and profile.permanent_resident_countries is None
    )
    if missing_avenue:
        return _check(
            "citizenship",
            EligibilityStatus.UNCERTAIN,
            "A permitted citizenship or permanent-resident avenue is not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    return _check(
        "citizenship",
        EligibilityStatus.INELIGIBLE,
        "Confirmed citizenship and permanent-resident facts match no permitted country.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def _education_check(
    requirement: EducationRequirement,
    profile: UserProfile,
    *,
    as_of: date,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["education_statuses", "graduated_on"]
    if profile.education_statuses is None or _profile_uncertain(
        profile, set(profile_fields)
    ):
        return _check(
            "education",
            EligibilityStatus.UNCERTAIN,
            "User education status is missing or not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    profile_statuses = set(profile.education_statuses)
    allowed_statuses = set(requirement.allowed_statuses)
    direct_matches = (profile_statuses & allowed_statuses) - {
        EducationStatus.RECENT_GRADUATE
    }
    if direct_matches:
        return _check(
            "education",
            EligibilityStatus.ELIGIBLE,
            "User education status matches an explicitly allowed status.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    recent_graduate_matches = (
        EducationStatus.RECENT_GRADUATE in profile_statuses
        and EducationStatus.RECENT_GRADUATE in allowed_statuses
    )
    if recent_graduate_matches:
        if requirement.max_years_since_graduation is None:
            status = EligibilityStatus.ELIGIBLE
            reason = "User matches the explicitly allowed recent-graduate status."
        elif profile.graduated_on is None:
            status = EligibilityStatus.UNCERTAIN
            reason = (
                "Graduation date is required to evaluate the recent-graduate window."
            )
        elif profile.graduated_on >= _subtract_years(
            as_of, requirement.max_years_since_graduation
        ):
            status = EligibilityStatus.ELIGIBLE
            reason = "User graduation date is inside the explicit eligibility window."
        else:
            status = EligibilityStatus.INELIGIBLE
            reason = "User graduation date is outside the explicit eligibility window."
        return _check(
            "education",
            status,
            reason,
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    return _check(
        "education",
        EligibilityStatus.INELIGIBLE,
        "Confirmed user education statuses match no allowed status.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _entrant_status_check(
    requirement: EntrantStatusRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["entrant_statuses"]
    if profile.entrant_statuses is None or _profile_uncertain(
        profile, set(profile_fields)
    ):
        return _check(
            "entrant_status",
            EligibilityStatus.UNCERTAIN,
            "User entrant roles are missing or not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if set(profile.entrant_statuses) & set(requirement.allowed_statuses):
        status = EligibilityStatus.ELIGIBLE
        reason = "At least one confirmed user entrant role is explicitly allowed."
    else:
        status = EligibilityStatus.INELIGIBLE
        reason = "Confirmed user entrant roles match no allowed role."
    return _check(
        "entrant_status",
        status,
        reason,
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _entity_check(
    requirement: EntityRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["entrant_statuses", "entity_profile"]
    if _profile_uncertain(profile, set(profile_fields)):
        return _check(
            "entity",
            EligibilityStatus.UNCERTAIN,
            "User entrant or entity facts are not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if requirement.mode is EntityRequirementMode.NO_REQUIREMENT:
        return _check(
            "entity",
            EligibilityStatus.ELIGIBLE,
            "This entry path has no legal-entity requirement.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if requirement.mode is EntityRequirementMode.INDIVIDUAL_ONLY:
        if profile.entrant_statuses is None:
            status = EligibilityStatus.UNCERTAIN
            reason = "User individual-entry status is not confirmed."
        elif EntrantStatus.INDIVIDUAL in profile.entrant_statuses:
            status = EligibilityStatus.ELIGIBLE
            reason = "User can enter under the individual-only path."
        else:
            status = EligibilityStatus.INELIGIBLE
            reason = "User has no confirmed individual entrant role."
        return _check(
            "entity",
            status,
            reason,
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )

    if requirement.mode is EntityRequirementMode.STARTUP_REQUIRED:
        if profile.entrant_statuses is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "User startup status is not confirmed.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if EntrantStatus.STARTUP not in profile.entrant_statuses:
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entry path requires a startup and no startup role is confirmed.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not requirement.registered_legal_entity_required:
            return _check(
                "entity",
                EligibilityStatus.ELIGIBLE,
                "The confirmed startup role satisfies this entry path.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )

    entity = profile.entity_profile
    if entity is None:
        return _check(
            "entity",
            EligibilityStatus.UNCERTAIN,
            "The rules require entity facts that the user has not provided.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if not entity.registered_legal_entity:
        return _check(
            "entity",
            EligibilityStatus.INELIGIBLE,
            "The entry path requires a registered legal entity.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    if requirement.allowed_entity_types:
        if not entity.entity_types:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "Registered entity type is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not set(entity.entity_types) & set(requirement.allowed_entity_types):
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The registered entity type is not allowed for this entry path.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.incorporation_countries:
        if entity.incorporation_country is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "Entity incorporation country is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not _country_lists_intersect(
            [entity.incorporation_country], requirement.incorporation_countries
        ):
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entity is incorporated outside the explicitly allowed countries.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.incorporated_on_or_after is not None:
        if entity.incorporated_on is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "Entity incorporation date is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if entity.incorporated_on < requirement.incorporated_on_or_after:
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entity is older than the explicit incorporation-age boundary.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.primary_business_countries:
        if entity.primary_business_country is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "Entity primary business country is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not _country_lists_intersect(
            [entity.primary_business_country],
            requirement.primary_business_countries,
        ):
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entity is primarily based outside the explicitly allowed countries.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.operating_required:
        if entity.operating is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "Operating status is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not entity.operating:
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entry path requires an operating entity.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    if requirement.sme_status_required:
        if entity.qualifies_as_sme is None:
            return _check(
                "entity",
                EligibilityStatus.UNCERTAIN,
                "SME qualification is required but not provided.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
        if not entity.qualifies_as_sme:
            return _check(
                "entity",
                EligibilityStatus.INELIGIBLE,
                "The entity does not meet the required SME qualification.",
                field_path=field_path,
                profile_fields=profile_fields,
                claim_ids=claim_ids,
            )
    return _check(
        "entity",
        EligibilityStatus.ELIGIBLE,
        "Confirmed entity facts satisfy every explicit entity requirement.",
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _existing_work_check(
    requirement: ExistingWorkRequirement,
    profile: UserProfile,
    *,
    field_path: str,
    claim_ids: list[str],
) -> ExpandedEligibilityCheck:
    profile_fields = ["candidate_project"]
    if _profile_uncertain(profile, set(profile_fields)):
        return _check(
            "existing_work",
            EligibilityStatus.UNCERTAIN,
            "Candidate-project facts are not confirmed.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    policy = requirement.policy
    if policy in {ExistingWorkPolicy.UNKNOWN, ExistingWorkPolicy.CONFLICT}:
        return _check(
            "existing_work",
            EligibilityStatus.UNCERTAIN,
            "The organizer's existing-work policy is unknown or conflicting.",
            field_path=field_path,
            profile_fields=profile_fields,
            claim_ids=claim_ids,
        )
    project = profile.candidate_project
    if policy is ExistingWorkPolicy.ALLOWED:
        status = EligibilityStatus.ELIGIBLE
        reason = "The rules explicitly allow existing work."
    elif project is None:
        status = EligibilityStatus.ELIGIBLE
        reason = (
            "No candidate project is selected, so the work policy is not a current "
            "hard blocker."
        )
    elif policy is ExistingWorkPolicy.ALLOWED_WITH_MODIFICATION:
        if not project.is_existing:
            status = EligibilityStatus.ELIGIBLE
            reason = "The candidate is new, so no existing-work conflict is present."
        elif project.will_be_materially_modified is None:
            status = EligibilityStatus.UNCERTAIN
            reason = "Planned modification of the existing candidate is not confirmed."
        elif project.will_be_materially_modified:
            status = EligibilityStatus.ELIGIBLE
            reason = "The existing candidate will receive the required modification."
        else:
            status = EligibilityStatus.INELIGIBLE
            reason = (
                "The existing candidate will not receive the required modification."
            )
    elif policy is ExistingWorkPolicy.FRESH_WORK_REQUIRED:
        status = (
            EligibilityStatus.INELIGIBLE
            if project.is_existing
            else EligibilityStatus.ELIGIBLE
        )
        reason = (
            "The specified candidate is existing work, but fresh work is required."
            if project.is_existing
            else "The specified candidate is new work."
        )
    elif policy is ExistingWorkPolicy.MUST_START_AFTER_OPEN:
        start_boundary = requirement.must_start_on_or_after
        if not project.is_existing:
            status = EligibilityStatus.ELIGIBLE
            reason = "The specified candidate is not existing work."
        elif start_boundary is None:
            status = EligibilityStatus.UNCERTAIN
            reason = "The competition opening boundary is unavailable."
        elif project.started_on is None:
            status = EligibilityStatus.UNCERTAIN
            reason = (
                "Candidate start date is required to evaluate the opening boundary."
            )
        elif project.started_on >= start_boundary:
            status = EligibilityStatus.ELIGIBLE
            reason = "Candidate work started inside the permitted period."
        else:
            status = EligibilityStatus.INELIGIBLE
            reason = "Candidate work started before the permitted period."
    elif policy is ExistingWorkPolicy.PRIOR_PUBLIC_RELEASE_PROHIBITED:
        if project.publicly_released is None:
            status = EligibilityStatus.UNCERTAIN
            reason = "Candidate public-release status is not confirmed."
        elif project.publicly_released:
            status = EligibilityStatus.INELIGIBLE
            reason = "The candidate was publicly released before entry."
        else:
            status = EligibilityStatus.ELIGIBLE
            reason = "The candidate has no prohibited prior public release."
    else:
        if project.previously_submitted is None:
            status = EligibilityStatus.UNCERTAIN
            reason = "Candidate previous-submission status is not confirmed."
        elif project.previously_submitted:
            status = EligibilityStatus.INELIGIBLE
            reason = (
                "The candidate was previously submitted where the rules prohibit it."
            )
        else:
            status = EligibilityStatus.ELIGIBLE
            reason = "The candidate has no prohibited previous submission."
    return _check(
        "existing_work",
        status,
        reason,
        field_path=field_path,
        profile_fields=profile_fields,
        claim_ids=claim_ids,
    )


def _overall_status(checks: list[ExpandedEligibilityCheck]) -> EligibilityStatus:
    statuses = {check.status for check in checks}
    if EligibilityStatus.INELIGIBLE in statuses:
        return EligibilityStatus.INELIGIBLE
    if EligibilityStatus.UNCERTAIN in statuses:
        return EligibilityStatus.UNCERTAIN
    return EligibilityStatus.ELIGIBLE


def _division_result(
    state: EligibilityFactState[EligibilityDivision],
    profile: UserProfile,
    *,
    as_of: date,
) -> DivisionEligibilityResult:
    if state.status is not EligibilityFactStatus.RESOLVED or state.value is None:
        check = _state_uncertain_check("divisions", state, [])
        return DivisionEligibilityResult(
            division_id=state.scope.identifier or "unknown",
            name=state.scope.identifier or "Unknown division",
            status=EligibilityStatus.UNCERTAIN,
            checks=[check],
        )
    division = state.value
    checks: list[ExpandedEligibilityCheck] = []
    if division.citizenship is not None:
        checks.append(
            _citizenship_check(
                division.citizenship,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            )
        )
    if division.education is not None:
        checks.append(
            _education_check(
                division.education,
                profile,
                as_of=as_of,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            )
        )
    if division.entrant_status is not None:
        checks.append(
            _entrant_status_check(
                division.entrant_status,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            )
        )
    if division.entity is not None:
        checks.append(
            _entity_check(
                division.entity,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            )
        )
    return DivisionEligibilityResult(
        division_id=division.division_id,
        name=division.name,
        status=_overall_status(checks),
        checks=checks,
    )


def _division_reason_details(
    results: list[DivisionEligibilityResult],
    status: EligibilityStatus,
) -> str:
    details: list[str] = []
    for result in results:
        matching = [check.reason for check in result.checks if check.status is status]
        if matching:
            details.append(f"{result.name}: {' / '.join(matching)}")
    return "; ".join(details)


def evaluate_expanded_hard_eligibility(
    facts: ExpandedEligibilityFacts,
    profile: UserProfile,
    *,
    as_of: date,
) -> ExpandedHardEligibilityResult:
    """Evaluate only typed, resolved facts; never call a model or guess values."""

    checks: list[ExpandedEligibilityCheck] = []
    simple_specs = (
        (
            "residence",
            facts.residence,
            ["country", "region", "subject_to_us_sanctions_or_export_controls"],
            lambda state: _residence_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "age",
            facts.age,
            ["age", "has_reached_age_of_majority"],
            lambda state: _age_requirement_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "team_size",
            facts.team_size,
            ["intended_team_size"],
            lambda state: _team_size_requirement_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "citizenship",
            facts.citizenship,
            ["citizenships", "permanent_resident_countries"],
            lambda state: _citizenship_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "education",
            facts.education,
            ["education_statuses", "graduated_on"],
            lambda state: _education_check(
                state.value,
                profile,
                as_of=as_of,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "entrant_status",
            facts.entrant_status,
            ["entrant_statuses"],
            lambda state: _entrant_status_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "entity",
            facts.entity,
            ["entrant_statuses", "entity_profile"],
            lambda state: _entity_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
        (
            "existing_work",
            facts.existing_work,
            ["candidate_project"],
            lambda state: _existing_work_check(
                state.value,
                profile,
                field_path=state.field_path,
                claim_ids=state.claim_ids,
            ),
        ),
    )
    for criterion, state, profile_fields, evaluator in simple_specs:
        if state is None:
            continue
        if state.status is EligibilityFactStatus.RESOLVED and state.value is not None:
            checks.append(evaluator(state))
        else:
            checks.append(
                _state_uncertain_check(criterion, state, profile_fields)  # type: ignore[arg-type]
            )

    division_results = [
        _division_result(state, profile, as_of=as_of) for state in facts.divisions
    ]
    if division_results:
        eligible_names = [
            item.name
            for item in division_results
            if item.status is EligibilityStatus.ELIGIBLE
        ]
        if eligible_names:
            division_status = EligibilityStatus.ELIGIBLE
            division_reason = (
                "At least one eligibility division is available: "
                + ", ".join(eligible_names)
                + "."
            )
        elif any(
            item.status is EligibilityStatus.UNCERTAIN for item in division_results
        ):
            division_status = EligibilityStatus.UNCERTAIN
            division_reason = (
                "No division is confirmed eligible. Still needs confirmation: "
                + _division_reason_details(
                    division_results, EligibilityStatus.UNCERTAIN
                )
                + "."
            )
        else:
            division_status = EligibilityStatus.INELIGIBLE
            division_reason = (
                "User is confirmed ineligible for every available division: "
                + _division_reason_details(
                    division_results, EligibilityStatus.INELIGIBLE
                )
                + "."
            )
        division_checks = [
            check for result in division_results for check in result.checks
        ]
        checks.append(
            ExpandedEligibilityCheck(
                criterion="divisions",
                status=division_status,
                reason=division_reason,
                competition_fields=list(
                    dict.fromkeys(
                        field
                        for check in division_checks
                        for field in check.competition_fields
                    )
                ),
                profile_fields=list(
                    dict.fromkeys(
                        field
                        for check in division_checks
                        for field in check.profile_fields
                    )
                ),
                claim_ids=list(
                    dict.fromkeys(
                        claim_id
                        for check in division_checks
                        for claim_id in check.claim_ids
                    )
                ),
            )
        )

    return ExpandedHardEligibilityResult(
        competition_id=facts.competition_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        status=_overall_status(checks),
        checks=checks,
        division_results=division_results,
    )
