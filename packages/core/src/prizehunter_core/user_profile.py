"""User-provided facts used by deterministic eligibility checks."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TeamPreference = Literal["solo", "team", "either", "unknown"]
WillingnessToLearn = Literal["low", "medium", "high", "unknown"]


class EducationStatus(StrEnum):
    """Small set of education states used only by explicit hard gates."""

    HIGH_SCHOOL_STUDENT = "high_school_student"
    UNIVERSITY_STUDENT = "university_student"
    RECENT_GRADUATE = "recent_graduate"
    NON_STUDENT = "non_student"


class EntrantStatus(StrEnum):
    """Non-exclusive roles a user can truthfully enter under."""

    GENERAL_PUBLIC = "general_public"
    STUDENT = "student"
    PROFESSIONAL = "professional"
    STARTUP = "startup"
    COMPANY = "company"
    RESEARCHER = "researcher"
    DEVELOPER = "developer"
    INDIVIDUAL = "individual"


class EntityType(StrEnum):
    """Minimal legal-entity categories needed by competition gates."""

    COMPANY = "company"
    STARTUP = "startup"
    NONPROFIT = "nonprofit"
    INSTITUTION = "institution"
    OTHER = "other"


class EntityProfile(BaseModel):
    """Candidate legal-entity facts, not a company CRM record."""

    model_config = ConfigDict(extra="forbid", strict=True)

    registered_legal_entity: bool
    entity_types: list[EntityType] = Field(default_factory=list)
    incorporation_country: str | None = Field(default=None, min_length=1)
    incorporated_on: date | None = None
    primary_business_country: str | None = Field(default=None, min_length=1)
    operating: bool | None = None
    qualifies_as_sme: bool | None = None

    @field_validator("entity_types")
    @classmethod
    def validate_unique_entity_types(cls, value: list[EntityType]) -> list[EntityType]:
        if len(value) != len(set(value)):
            raise ValueError("entity_types cannot contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_registration_details(self) -> EntityProfile:
        if not self.registered_legal_entity and (
            self.entity_types
            or self.incorporation_country is not None
            or self.incorporated_on is not None
            or self.primary_business_country is not None
            or self.operating is not None
            or self.qualifies_as_sme is not None
        ):
            raise ValueError(
                "An unregistered entity cannot carry incorporation details."
            )
        return self


class CandidateProjectProfile(BaseModel):
    """Facts about the specific project the user intends to submit."""

    model_config = ConfigDict(extra="forbid", strict=True)

    is_existing: bool
    started_on: date | None = None
    publicly_released: bool | None = None
    previously_submitted: bool | None = None
    will_be_materially_modified: bool | None = None


class AvailableTime(BaseModel):
    """Time the user explicitly says is available for a competition."""

    model_config = ConfigDict(extra="forbid", strict=True)

    hours_per_week: float | None = Field(default=None, ge=0)
    total_hours_before_deadline: float | None = Field(default=None, ge=0)


class ProfileUncertainty(BaseModel):
    """A user-profile field that is missing, provisional, or not confirmed."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class UserProfile(BaseModel):
    """Strict user-supplied facts; never competition rules or AI judgement."""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    country: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Legal country of residence used for competition eligibility; "
            "the field name remains country for backwards compatibility."
        ),
    )
    region: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "State, province, territory, or administrative region used when "
            "eligibility rules require it; not GPS or current location."
        ),
    )
    age: int | None = Field(default=None, ge=0, le=130)
    has_reached_age_of_majority: bool | None = Field(
        default=None,
        description=(
            "User-confirmed legal-majority status for the relevant residence; "
            "never inferred from age or country."
        ),
    )
    subject_to_us_sanctions_or_export_controls: bool | None = Field(
        default=None,
        description=(
            "User-confirmed status for an explicit U.S. sanctions/export-control "
            "entry gate; never inferred from country."
        ),
    )
    citizenships: list[str] | None = Field(
        default=None,
        description=(
            "Confirmed legal citizenships; never inferred from country of residence."
        ),
    )
    permanent_resident_countries: list[str] | None = Field(
        default=None,
        description=(
            "Confirmed permanent-resident statuses, separate from residence and "
            "citizenship."
        ),
    )
    education_statuses: list[EducationStatus] | None = None
    graduated_on: date | None = None
    entrant_statuses: list[EntrantStatus] | None = Field(
        default=None,
        description="Non-exclusive roles under which the user can enter.",
    )
    entity_profile: EntityProfile | None = None
    candidate_project: CandidateProjectProfile | None = None
    team_preference: TeamPreference = "unknown"
    solo_preference: bool | None = None
    intended_team_size: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Number of people the user intends to enter with, including the user."
        ),
    )
    skills: list[str] = Field(default_factory=list)
    technical_capability: list[str] = Field(default_factory=list)
    available_time: AvailableTime = Field(default_factory=AvailableTime)
    willingness_to_learn_new_tech: WillingnessToLearn = "unknown"
    profile_uncertainties: list[ProfileUncertainty] = Field(default_factory=list)

    @field_validator(
        "citizenships",
        "permanent_resident_countries",
        "education_statuses",
        "entrant_statuses",
    )
    @classmethod
    def validate_unique_optional_lists(cls, value: list | None) -> list | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Profile fact lists cannot contain duplicates.")
        return value
