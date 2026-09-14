"""Opt-in composition of legacy, expanded, and deadline eligibility results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prizehunter_core.competition_intelligence import ClaimScope, CompetitionIntelligence
from prizehunter_core.deadlines import DeadlineType
from prizehunter_core.eligibility import EligibilityStatus
from prizehunter_core.eligibility_assessment import (
    AssessmentComponent,
    EligibilityAssessmentV2,
    evaluate_eligibility_v2,
)
from prizehunter_core.expanded_eligibility import (
    ExpandedEligibilityFacts,
    ExpandedHardEligibilityResult,
    adapt_expanded_eligibility_facts,
    evaluate_expanded_hard_eligibility,
)
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile

_DEFAULT_DEADLINE_TYPE = DeadlineType("submission")


class AssessmentComponentV3(StrEnum):
    """Application components represented in the V3 consumer index."""

    LEGACY_HARD_ELIGIBILITY = "legacy_hard_eligibility"
    EXPANDED_HARD_ELIGIBILITY = "expanded_hard_eligibility"
    DEADLINE = "deadline"


class AssessmentFindingV3(BaseModel):
    """Small UI-ready index entry backed by nested deterministic results."""

    model_config = ConfigDict(extra="forbid", strict=True)

    component: AssessmentComponentV3
    criterion: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    competition_fields: list[str] = Field(default_factory=list)
    profile_fields: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


def _aggregate_v3(
    base: EligibilityAssessmentV2,
    expanded: ExpandedHardEligibilityResult,
) -> tuple[EligibilityStatus, list[AssessmentFindingV3], list[AssessmentFindingV3]]:
    typed_core_criteria = {
        {"residence": "country", "age": "age", "team_size": "team_size"}[
            check.criterion
        ]
        for check in expanded.checks
        if check.criterion in {"residence", "age", "team_size"}
        and check.status is not EligibilityStatus.UNCERTAIN
    }
    blockers = [
        AssessmentFindingV3(
            component=(
                AssessmentComponentV3.DEADLINE
                if item.component is AssessmentComponent.DEADLINE
                else AssessmentComponentV3.LEGACY_HARD_ELIGIBILITY
            ),
            criterion=item.criterion,
            reason=item.reason,
            competition_fields=item.competition_fields,
            profile_fields=item.profile_fields,
        )
        for item in base.confirmed_blockers
        if item.criterion not in typed_core_criteria
    ]
    uncertainties = [
        AssessmentFindingV3(
            component=(
                AssessmentComponentV3.DEADLINE
                if item.component is AssessmentComponent.DEADLINE
                else AssessmentComponentV3.LEGACY_HARD_ELIGIBILITY
            ),
            criterion=item.criterion,
            reason=item.reason,
            competition_fields=item.competition_fields,
            profile_fields=item.profile_fields,
        )
        for item in base.uncertainties
        if item.criterion not in typed_core_criteria
    ]
    for check in expanded.checks:
        finding = AssessmentFindingV3(
            component=AssessmentComponentV3.EXPANDED_HARD_ELIGIBILITY,
            criterion=check.criterion,
            reason=check.reason,
            competition_fields=check.competition_fields,
            profile_fields=check.profile_fields,
            claim_ids=check.claim_ids,
        )
        if check.status is EligibilityStatus.INELIGIBLE:
            blockers.append(finding)
        elif check.status is EligibilityStatus.UNCERTAIN:
            uncertainties.append(finding)

    if blockers:
        overall = EligibilityStatus.INELIGIBLE
    elif uncertainties:
        overall = EligibilityStatus.UNCERTAIN
    else:
        overall = EligibilityStatus.ELIGIBLE
    return overall, blockers, uncertainties


class EligibilityAssessmentV3(BaseModel):
    """Additive assessment version that keeps the complete V2 result nested."""

    model_config = ConfigDict(extra="forbid", strict=True)

    assessment_version: Literal["3.0"] = "3.0"
    base_assessment: EligibilityAssessmentV2
    expanded_hard_eligibility: ExpandedHardEligibilityResult
    overall_status: EligibilityStatus
    confirmed_blockers: list[AssessmentFindingV3] = Field(default_factory=list)
    uncertainties: list[AssessmentFindingV3] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_composition(self) -> Self:
        base = self.base_assessment
        expanded = self.expanded_hard_eligibility
        if base.competition_id != expanded.competition_id:
            raise ValueError("Nested competition references must match.")
        if (
            base.profile_reference.profile_id != expanded.profile_id
            or base.profile_reference.profile_version != expanded.profile_version
        ):
            raise ValueError("Nested profile references must match.")
        expected = _aggregate_v3(base, expanded)
        if (
            self.overall_status,
            self.confirmed_blockers,
            self.uncertainties,
        ) != expected:
            raise ValueError(
                "V3 status and findings must match the nested component results."
            )
        return self


def compose_eligibility_assessment_v3(
    *,
    base_assessment: EligibilityAssessmentV2,
    expanded_hard_eligibility: ExpandedHardEligibilityResult,
) -> EligibilityAssessmentV3:
    """Pure V3 composition with confirmed-blocker precedence."""

    overall, blockers, uncertainties = _aggregate_v3(
        base_assessment,
        expanded_hard_eligibility,
    )
    return EligibilityAssessmentV3(
        base_assessment=base_assessment,
        expanded_hard_eligibility=expanded_hard_eligibility,
        overall_status=overall,
        confirmed_blockers=blockers,
        uncertainties=uncertainties,
    )


def evaluate_eligibility_v3(
    competition: CompetitionRecord,
    profile: UserProfile,
    *,
    competition_id: str,
    now: datetime,
    intelligence: CompetitionIntelligence | None = None,
    deadline_field_path: str = "/deadline",
    deadline_scope: ClaimScope | None = None,
    deadline_type: DeadlineType = _DEFAULT_DEADLINE_TYPE,
) -> EligibilityAssessmentV3:
    """Run the unchanged V2 path plus opt-in typed expanded hard gates."""

    base = evaluate_eligibility_v2(
        competition,
        profile,
        competition_id=competition_id,
        now=now,
        intelligence=intelligence,
        deadline_field_path=deadline_field_path,
        deadline_scope=deadline_scope,
        deadline_type=deadline_type,
    )
    facts = (
        adapt_expanded_eligibility_facts(intelligence)
        if intelligence is not None
        else ExpandedEligibilityFacts(competition_id=competition_id)
    )
    expanded = evaluate_expanded_hard_eligibility(
        facts,
        profile,
        as_of=now.date(),
    )
    return compose_eligibility_assessment_v3(
        base_assessment=base,
        expanded_hard_eligibility=expanded,
    )
