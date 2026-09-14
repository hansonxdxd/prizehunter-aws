"""Versioned, deterministic composition of core and deadline eligibility."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prizehunter_core.competition_intelligence import ClaimScope, CompetitionIntelligence
from prizehunter_core.deadlines import (
    DeadlineAdapterStatus,
    DeadlinePassResult,
    DeadlinePassStatus,
    DeadlineState,
    DeadlineType,
    adapt_deadline,
    assess_deadline_passed,
)
from prizehunter_core.eligibility import (
    EligibilityStatus,
    HardEligibilityResult,
    evaluate_hard_eligibility,
)
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile

_DEFAULT_DEADLINE_TYPE = DeadlineType("submission")


class AssessmentComponent(StrEnum):
    """Deterministic component that produced an aggregate finding."""

    HARD_ELIGIBILITY = "hard_eligibility"
    DEADLINE = "deadline"


class ProfileReference(BaseModel):
    """Stable reference to the user facts used for this assessment."""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)


class AssessmentFinding(BaseModel):
    """One UI-ready blocker or uncertainty, backed by a nested component."""

    model_config = ConfigDict(extra="forbid", strict=True)

    component: AssessmentComponent
    criterion: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    competition_fields: list[str] = Field(default_factory=list)
    profile_fields: list[str] = Field(default_factory=list)


def _aggregate_findings(
    core: HardEligibilityResult,
    deadline_state: DeadlineState,
    deadline_result: DeadlinePassResult,
) -> tuple[EligibilityStatus, list[AssessmentFinding], list[AssessmentFinding]]:
    blockers: list[AssessmentFinding] = []
    uncertainties: list[AssessmentFinding] = []

    for check in core.checks:
        finding = AssessmentFinding(
            component=AssessmentComponent.HARD_ELIGIBILITY,
            criterion=check.criterion,
            reason=check.reason,
            competition_fields=check.competition_fields,
            profile_fields=check.profile_fields,
        )
        if check.status is EligibilityStatus.INELIGIBLE:
            blockers.append(finding)
        elif check.status is EligibilityStatus.UNCERTAIN:
            uncertainties.append(finding)

    deadline_finding = AssessmentFinding(
        component=AssessmentComponent.DEADLINE,
        criterion="deadline",
        # Preserve an explicit source-conflict explanation. For other states,
        # the pass-result is more actionable (for example an invalid timezone)
        # than the adapter's provenance-oriented reason.
        reason=(
            deadline_state.reason
            if deadline_state.status is DeadlineAdapterStatus.UNRESOLVED_CONFLICT
            else deadline_result.reason
        ),
        competition_fields=[deadline_state.field_path],
    )
    if deadline_result.status is DeadlinePassStatus.PASSED:
        blockers.append(deadline_finding)
    elif deadline_result.status is DeadlinePassStatus.UNCERTAIN:
        uncertainties.append(deadline_finding)

    if blockers:
        overall_status = EligibilityStatus.INELIGIBLE
    elif uncertainties:
        overall_status = EligibilityStatus.UNCERTAIN
    else:
        overall_status = EligibilityStatus.ELIGIBLE
    return overall_status, blockers, uncertainties


class EligibilityAssessmentV2(BaseModel):
    """Opt-in aggregate; the legacy HardEligibilityResult remains unchanged."""

    model_config = ConfigDict(extra="forbid", strict=True)

    assessment_version: Literal["2.0"] = "2.0"
    competition_id: str = Field(min_length=1)
    profile_reference: ProfileReference
    core_eligibility: HardEligibilityResult
    deadline_state: DeadlineState
    deadline_result: DeadlinePassResult
    overall_status: EligibilityStatus
    confirmed_blockers: list[AssessmentFinding] = Field(default_factory=list)
    uncertainties: list[AssessmentFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_composition(self) -> Self:
        if (
            self.profile_reference.profile_id != self.core_eligibility.profile_id
            or self.profile_reference.profile_version
            != self.core_eligibility.profile_version
        ):
            raise ValueError(
                "profile_reference must match the nested HardEligibilityResult."
            )
        expected = _aggregate_findings(
            self.core_eligibility,
            self.deadline_state,
            self.deadline_result,
        )
        if (
            self.overall_status,
            self.confirmed_blockers,
            self.uncertainties,
        ) != expected:
            raise ValueError(
                "Aggregate status and findings must match the nested component results."
            )
        return self


def compose_eligibility_assessment_v2(
    *,
    competition_id: str,
    core_eligibility: HardEligibilityResult,
    deadline_state: DeadlineState,
    deadline_result: DeadlinePassResult,
) -> EligibilityAssessmentV2:
    """Pure composition boundary for callers that already evaluated components."""

    overall_status, blockers, uncertainties = _aggregate_findings(
        core_eligibility,
        deadline_state,
        deadline_result,
    )
    return EligibilityAssessmentV2(
        competition_id=competition_id,
        profile_reference=ProfileReference(
            profile_id=core_eligibility.profile_id,
            profile_version=core_eligibility.profile_version,
        ),
        core_eligibility=core_eligibility,
        deadline_state=deadline_state,
        deadline_result=deadline_result,
        overall_status=overall_status,
        confirmed_blockers=blockers,
        uncertainties=uncertainties,
    )


def evaluate_eligibility_v2(
    competition: CompetitionRecord,
    profile: UserProfile,
    *,
    competition_id: str,
    now: datetime,
    intelligence: CompetitionIntelligence | None = None,
    deadline_field_path: str = "/deadline",
    deadline_scope: ClaimScope | None = None,
    deadline_type: DeadlineType = _DEFAULT_DEADLINE_TYPE,
) -> EligibilityAssessmentV2:
    """Run existing deterministic components and return the opt-in V2 aggregate."""

    if intelligence is not None and intelligence.competition_id != competition_id:
        raise ValueError(
            "competition_id must match CompetitionIntelligence.competition_id."
        )
    core = evaluate_hard_eligibility(competition, profile)
    deadline_state = adapt_deadline(
        competition_record=competition,
        intelligence=intelligence,
        field_path=deadline_field_path,
        scope=deadline_scope,
        deadline_type=deadline_type,
    )
    deadline_result = assess_deadline_passed(deadline_state, now=now)
    return compose_eligibility_assessment_v2(
        competition_id=competition_id,
        core_eligibility=core,
        deadline_state=deadline_state,
        deadline_result=deadline_result,
    )
