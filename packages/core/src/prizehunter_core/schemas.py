"""Schemas that separate competition facts from future AI judgement."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SourceEvidence(BaseModel):
    """A short, verbatim excerpt that supports one extracted field."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="CompetitionRecord field supported by this excerpt.")
    excerpt: str = Field(description="Short verbatim excerpt from the supplied text.")


class Uncertainty(BaseModel):
    """An explicit unknown, ambiguity, or missing primary-source detail."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="CompetitionRecord field that needs verification.")
    reason: str = Field(
        description="Why the supplied text does not establish this fact."
    )


class CompetitionRecord(BaseModel):
    """Official competition facts only; no AI fit or recommendation judgement."""

    model_config = ConfigDict(extra="forbid")

    competition_name: str | None = None
    organizer: str | None = None
    source_url: str | None = None
    deadline: str | None = Field(
        default=None,
        description="Deadline wording from the source; preserve ambiguity and timezone.",
    )
    eligibility: list[str] = Field(default_factory=list)
    team_size: str | None = None
    geographic_restrictions: list[str] = Field(default_factory=list)
    tracks_or_categories: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    submission_requirements: list[str] = Field(default_factory=list)
    prize: str | None = None
    fees: str | None = None
    ip_terms: str | None = None
    existing_project_rules: str | None = None
    judging_criteria: list[str] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
